import os

os.environ.setdefault("CLINICAL_COMPASS_DEMO_HEADERS", "1")

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app import alerting, db, knowledge, safety, therapy
from app import scales as scale_engine
from app.main import app

DOCTOR = {'X-Demo-Role': 'doctor'}
PATIENT = {'X-Demo-Role': 'patient'}


class KnowledgeBaseTests(unittest.TestCase):
    def setUp(self):
        self.original_path = db.DB_PATH
        self.temp_dir = tempfile.TemporaryDirectory()
        db.DB_PATH = Path(self.temp_dir.name) / 'knowledge.db'
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        db.DB_PATH = self.original_path
        self.temp_dir.cleanup()

    def test_system_articles_follow_configuration(self):
        articles = {item['id']: item for item in knowledge.system_articles()}
        phq9 = scale_engine.get_scale('phq9')
        table = next(section['table'] for section in articles['phq9']['sections'] if 'table' in section)
        self.assertEqual(len(table), len(phq9['thresholds']))
        self.assertEqual(table[-1][1], phq9['thresholds'][-1]['label'])
        medication = therapy.catalogue()['medications'][0]
        contraindications = next(s for s in articles['aviandr']['sections'] if s['title'] == 'Противопоказания')
        self.assertEqual(len(contraindications['items']), sum(rule['level'] == 'blocked' for rule in medication['rules']))
        self.assertIn(str(safety.HIGH_SCORE_THRESHOLD), ' '.join(articles['routing']['sections'][1]['items']))

    def test_search_is_case_insensitive_for_cyrillic(self):
        found = [item['id'] for item in knowledge.search('ЭСКАЛАЦИЯ')]
        self.assertIn('alerting', found)
        self.assertEqual([item['id'] for item in knowledge.search('беременности', 'therapy')], ['aviandr'])
        self.assertEqual(knowledge.search('несуществующееслово'), [])

    def test_doctor_article_lifecycle(self):
        created = self.client.post('/api/knowledge', headers=DOCTOR, json={
            'title': '  Протокол первичного приёма ', 'category': 'protocol', 'summary': 'Шаги',
            'body': 'Уточнить хронотип.\n- Проверить PHQ-9', 'tags': ['приём', 'приём', ' ']
        })
        self.assertEqual(created.status_code, 201)
        article = created.json()
        self.assertEqual(article['title'], 'Протокол первичного приёма')
        self.assertEqual(article['tags'], ['приём'])
        self.assertFalse(article['system'])

        found = self.client.get('/api/knowledge', headers=DOCTOR, params={'q': 'хронотип'}).json()['articles']
        self.assertEqual([item['id'] for item in found], [article['id']])

        updated = self.client.put(f"/api/knowledge/{article['id']}", headers=DOCTOR, json={
            'title': 'Протокол', 'category': 'note', 'body': 'Новый текст', 'source_url': 'https://example.com/doc'
        })
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()['category'], 'note')

        self.assertEqual(self.client.delete(f"/api/knowledge/{article['id']}", headers=DOCTOR).status_code, 204)
        self.assertEqual(self.client.get(f"/api/knowledge/{article['id']}", headers=DOCTOR).status_code, 404)

    def test_system_articles_are_read_only(self):
        self.assertEqual(self.client.get('/api/knowledge/phq9', headers=DOCTOR).status_code, 200)
        response = self.client.put('/api/knowledge/phq9', headers=DOCTOR, json={'title': 'X', 'body': 'Y'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.delete('/api/knowledge/aviandr', headers=DOCTOR).status_code, 403)

    def test_protocol_templates_are_seeded_once(self):
        titles = [item['title'] for item in db.get_kb_articles()]
        self.assertEqual(titles, ['Первичный приём', 'Повторный контроль', 'Действия при критическом алерте'])
        self.assertTrue(all(item['template'] for item in knowledge.search('шаблон') if not item['system']))
        alert = next(item for item in db.get_kb_articles() if item['title'] == 'Действия при критическом алерте')
        minutes = str(round(alerting.config()['escalation_seconds'] / 60))
        self.assertIn(f'{minutes} мин', alert['body'])
        self.assertNotIn('{', alert['body'] + alert['summary'])
        self.assertEqual(knowledge.seed_templates(), 0)

        db.delete_kb_article(alert['id'])
        self.assertEqual(knowledge.seed_templates(), 0)
        self.assertEqual(len(db.get_kb_articles()), 2)

    def test_templates_are_editable_doctor_articles(self):
        article = next(item for item in knowledge.search('повторный контроль') if not item['system'])
        response = self.client.put(f"/api/knowledge/{article['id']}", headers=DOCTOR, json={
            'title': 'Повторный контроль (клиника №1)', 'category': 'protocol', 'body': article['body'],
        })
        self.assertEqual(response.status_code, 200)

    def test_patient_has_no_access(self):
        self.assertEqual(self.client.get('/api/knowledge', headers=PATIENT).status_code, 403)
        self.assertEqual(self.client.post('/api/knowledge', headers=PATIENT, json={'title': 'X', 'body': 'Y'}).status_code, 403)

    def test_invalid_article_is_rejected(self):
        self.assertEqual(self.client.post('/api/knowledge', headers=DOCTOR, json={'title': '   ', 'body': 'Y'}).status_code, 422)
        self.assertEqual(self.client.post('/api/knowledge', headers=DOCTOR, json={'title': 'X', 'body': 'Y', 'source_url': 'javascript:alert(1)'}).status_code, 422)


if __name__ == '__main__':
    unittest.main()
