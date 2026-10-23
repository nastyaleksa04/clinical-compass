import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from app import db
from app.main import ProfileUpdate


class ProfileStorageTests(unittest.TestCase):
    def setUp(self):
        self.original_path = db.DB_PATH
        self.temp_dir = tempfile.TemporaryDirectory()
        db.DB_PATH = Path(self.temp_dir.name) / 'profile.db'
        db.init_db()

    def tearDown(self):
        db.DB_PATH = self.original_path
        self.temp_dir.cleanup()

    def test_demo_patient_has_seeded_profile(self):
        profile = db.get_profile(1)
        self.assertTrue(profile['phone'])
        self.assertIsNotNone(profile['consent_accepted_at'])
        self.assertIs(profile['reminder_enabled'], True)

    def test_profile_update_persists_and_keeps_consent(self):
        consent = db.get_profile(1)['consent_accepted_at']
        payload = ProfileUpdate(
            phone='+7 900 111-22-33', email='new@example.com', emergency_name='Контакт',
            emergency_phone='+7 900 444-55-66', reminder_enabled=False, reminder_time='09:30',
            notify_messages=False, notify_plan=True,
        ).model_dump()
        saved = db.save_profile(1, payload)
        self.assertEqual(saved['reminder_time'], '09:30')
        self.assertIs(saved['reminder_enabled'], False)
        self.assertIs(saved['notify_messages'], False)
        self.assertEqual(saved['consent_accepted_at'], consent)
        self.assertEqual(db.get_profile(1)['email'], 'new@example.com')

    def test_patient_without_profile_gets_defaults(self):
        profile = db.get_profile(2)
        self.assertEqual(profile['reminder_time'], '20:00')
        self.assertIsNone(profile['consent_accepted_at'])

    def test_invalid_values_are_rejected(self):
        with self.assertRaises(ValidationError):
            ProfileUpdate(reminder_time='25:00')
        with self.assertRaises(ValidationError):
            ProfileUpdate(email='not-an-email')
        with self.assertRaises(ValidationError):
            ProfileUpdate(phone='abc')


if __name__ == '__main__':
    unittest.main()
