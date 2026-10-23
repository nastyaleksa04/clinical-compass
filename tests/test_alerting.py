import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from app import db

class AlertingTests(unittest.TestCase):
    def setUp(self):
        self.old=db.DB_PATH
        self.tmp=tempfile.TemporaryDirectory()
        db.DB_PATH=Path(self.tmp.name)/'alerts.db'
        db.init_db()
    def tearDown(self):
        db.DB_PATH=self.old
        self.tmp.cleanup()
    def test_mandatory_signal_creates_and_acknowledges_alert(self):
        signal=db.create_routing_signal(1, {'level':'mandatory','reason_code':'test','reason_text':'Тест'}, 'test', 1)
        alerts=db.refresh_and_get_alerts(900)
        self.assertEqual(len(alerts),1)
        self.assertEqual(alerts[0]['signal_id'],signal['id'])
        saved=db.acknowledge_alert(alerts[0]['id'])
        self.assertEqual(saved['status'],'acknowledged')
        self.assertIsNotNone(saved['response_seconds'])
    def test_recommended_signal_does_not_create_alert(self):
        db.create_routing_signal(1, {'level':'recommended','reason_code':'test','reason_text':'Тест'}, 'test', 2)
        self.assertEqual(db.refresh_and_get_alerts(900),[])
    def test_expired_alert_escalates(self):
        db.create_routing_signal(1, {'level':'mandatory','reason_code':'old','reason_text':'Старый'}, 'test', 3)
        old=(datetime.now(timezone.utc)-timedelta(minutes=20)).isoformat()
        with db.connection() as database:
            database.execute('UPDATE alerts SET triggered_at=?',(old,))
        self.assertEqual(db.refresh_and_get_alerts(900)[0]['status'],'escalated')

if __name__=='__main__':
    unittest.main()
