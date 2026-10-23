import tempfile
import unittest
from pathlib import Path

from app import db, scenarios


class TimelineTests(unittest.TestCase):
    def setUp(self):
        self.original_path = db.DB_PATH
        self.temp_dir = tempfile.TemporaryDirectory()
        db.DB_PATH = Path(self.temp_dir.name) / "timeline.db"
        db.init_db()
        scenarios.seed()
        scenarios.seed_clinical_profiles()

    def tearDown(self):
        db.DB_PATH = self.original_path
        self.temp_dir.cleanup()

    def test_doctor_timeline_combines_and_sorts_events(self):
        events = db.get_timeline(5, include_clinical=True)
        types = {item["type"] for item in events}
        self.assertTrue({"report", "assessment", "routing", "alert", "clinical"}.issubset(types))
        timestamps = [item["created_at"] for item in events]
        self.assertEqual(timestamps, sorted(timestamps, reverse=True))
        self.assertTrue(all({"id", "category", "title", "status", "created_at"} <= item.keys() for item in events))

    def test_patient_timeline_hides_internal_events_and_pending_route(self):
        events = db.get_timeline(5, include_clinical=False)
        types = {item["type"] for item in events}
        self.assertNotIn("clinical", types)
        self.assertNotIn("alert", types)
        self.assertNotIn("routing", types)
        self.assertIn("assessment", types)
        self.assertIn("report", types)

    def test_confirmed_route_is_visible_to_patient(self):
        signal = db.get_routing_signals(4, include_unconfirmed=True)[0]
        db.decide_routing_signal(signal["id"], "confirmed", "Рекомендована очная консультация")
        events = db.get_timeline(4, include_clinical=False)
        route = next(item for item in events if item["type"] == "routing")
        self.assertEqual(route["status"], "Подтверждено")
        self.assertIn("очная консультация", route["details"])


if __name__ == "__main__":
    unittest.main()
