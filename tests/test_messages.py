import tempfile
import unittest
from pathlib import Path

from app import db


class MessageStorageTests(unittest.TestCase):
    def setUp(self):
        self.original_path = db.DB_PATH
        self.temp_dir = tempfile.TemporaryDirectory()
        db.DB_PATH = Path(self.temp_dir.name) / 'messages.db'
        db.init_db()

    def tearDown(self):
        db.DB_PATH = self.original_path
        self.temp_dir.cleanup()

    def test_unread_state_is_separate_for_patient_and_doctor(self):
        patient_message = db.create_message(1, 'patient', 'Здравствуйте')
        self.assertTrue(patient_message['read_by_patient'])
        self.assertFalse(patient_message['read_by_doctor'])
        self.assertEqual(db.unread_message_count(1, 'doctor'), 1)
        self.assertEqual(db.unread_message_count(1, 'patient'), 0)

        db.mark_messages_read(1, 'doctor')
        self.assertEqual(db.unread_message_count(1, 'doctor'), 0)

        doctor_message = db.create_message(1, 'doctor', 'Добрый день')
        self.assertTrue(doctor_message['read_by_doctor'])
        self.assertFalse(doctor_message['read_by_patient'])
        self.assertEqual(db.unread_message_count(1, 'patient'), 1)

    def test_messages_keep_chronological_order(self):
        db.create_message(1, 'patient', 'Первое')
        db.create_message(1, 'doctor', 'Второе')
        messages = db.get_messages(1)
        self.assertEqual([item['body'] for item in messages], ['Первое', 'Второе'])


if __name__ == '__main__':
    unittest.main()
