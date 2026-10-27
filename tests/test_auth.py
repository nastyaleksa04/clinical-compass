import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import db
from app.main import app


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(db, "DB_PATH", Path(self.temp_dir.name) / "auth.db")
        self.db_patch.start()
        self.env_patch = patch.dict("os.environ", {"CLINICAL_COMPASS_DEMO_HEADERS": "0"})
        self.env_patch.start()
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        self.env_patch.stop()
        self.db_patch.stop()
        self.temp_dir.cleanup()

    def login(self, login, password):
        return self.client.post("/api/auth/login", json={"login": login, "password": password})

    def bearer(self, login, password):
        return {"Authorization": f"Bearer {self.login(login, password).json()['token']}"}

    def test_requests_without_login_are_rejected(self):
        self.assertEqual(401, self.client.get("/api/state").status_code)

    def test_demo_role_header_is_ignored_in_production_mode(self):
        self.assertEqual(401, self.client.get("/api/state", headers={"X-Demo-Role": "doctor"}).status_code)

    def test_wrong_password_rejected(self):
        self.assertEqual(401, self.login("doctor", "wrong").status_code)

    def test_role_comes_from_session(self):
        doctor = self.bearer("doctor", "doctor2026")
        patient = self.bearer("patient", "patient2026")
        self.assertEqual("doctor", self.client.get("/api/auth/me", headers=doctor).json()["role"])
        self.assertEqual(200, self.client.get("/api/alerts", headers=doctor).status_code)
        self.assertEqual(403, self.client.get("/api/alerts", headers=patient).status_code)
        forged = {**patient, "X-Demo-Role": "doctor"}
        self.assertEqual(403, self.client.get("/api/alerts", headers=forged).status_code)

    def test_logout_invalidates_token(self):
        headers = self.bearer("patient", "patient2026")
        self.assertEqual(204, self.client.post("/api/auth/logout", headers=headers).status_code)
        self.assertEqual(401, self.client.get("/api/state", headers=headers).status_code)

    def test_passwords_are_hashed(self):
        stored = db.get_user_by_login("doctor")["password_hash"]
        self.assertTrue(stored.startswith("pbkdf2_sha256$"))
        self.assertNotIn("doctor2026", stored)

    def test_alert_delivery_time_recorded_once(self):
        patient = self.bearer("patient", "patient2026")
        doctor = self.bearer("doctor", "doctor2026")
        self.client.post("/api/patients/1/reports", headers=patient,
                         json={"mood": 1, "anxiety": 5, "sleep": 1, "comment": "", "urgent": True})
        feed = self.client.get("/api/alerts", headers=doctor).json()
        alert = next(item for item in feed["alerts"] if item["status"] == "new")
        first = self.client.post(f"/api/alerts/{alert['id']}/delivered", headers=doctor).json()
        second = self.client.post(f"/api/alerts/{alert['id']}/delivered", headers=doctor).json()
        self.assertIsNotNone(first["delivery_seconds"])
        self.assertEqual(first["delivered_at"], second["delivered_at"])
        self.assertEqual(1, self.client.get("/api/alerts", headers=doctor).json()["delivery"]["count"])


if __name__ == "__main__":
    unittest.main()
