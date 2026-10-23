import tempfile
import unittest
from datetime import date
from pathlib import Path

from app import db


class CareTaskStorageTests(unittest.TestCase):
    def setUp(self):
        self.original_path = db.DB_PATH
        self.temp_dir = tempfile.TemporaryDirectory()
        db.DB_PATH = Path(self.temp_dir.name) / 'tasks.db'
        db.init_db()

    def tearDown(self):
        db.DB_PATH = self.original_path
        self.temp_dir.cleanup()

    def test_task_lifecycle(self):
        task = db.create_care_task(1, {
            'title': 'Пройти PHQ-9',
            'description': 'До следующего контакта',
            'category': 'assessment',
            'due_date': date(2026, 10, 30),
        })
        self.assertEqual(task['status'], 'pending')
        self.assertEqual(task['due_date'], '2026-10-30')

        completed = db.update_care_task(task['id'], 'completed')
        self.assertEqual(completed['status'], 'completed')
        self.assertIsNotNone(completed['completed_at'])

        reopened = db.update_care_task(task['id'], 'pending')
        self.assertEqual(reopened['status'], 'pending')
        self.assertIsNone(reopened['completed_at'])

    def test_pending_tasks_are_listed_first(self):
        first = db.create_care_task(1, {
            'title': 'Выполнено', 'description': '', 'category': 'monitoring', 'due_date': None,
        })
        db.update_care_task(first['id'], 'completed')
        db.create_care_task(1, {
            'title': 'Активно', 'description': '', 'category': 'therapy', 'due_date': None,
        })
        self.assertEqual(db.get_care_tasks(1)[0]['title'], 'Активно')


if __name__ == '__main__':
    unittest.main()
