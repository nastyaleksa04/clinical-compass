import os

os.environ.setdefault("CLINICAL_COMPASS_DEMO_HEADERS", "1")

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import db
from app import demo_life
from app import neuron
from app.main import app


class DemoLifeTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(db, "DB_PATH", Path(self.temp_dir.name) / "demo.db")
        self.db_patch.start()
        self.env_patch = patch.dict("os.environ", {"CLINICAL_COMPASS_DEMO_DATA": "1"})
        self.env_patch.start()
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        self.env_patch.stop()
        self.db_patch.stop()
        self.temp_dir.cleanup()

    def test_every_patient_has_at_least_five_days_of_history(self):
        for patient_id in range(1, 6):
            days = {item["created_at"][:10] for item in db.get_reports(patient_id, 200)}
            self.assertGreaterEqual(len(days), 5, patient_id)
            self.assertGreaterEqual(len(db.get_assessments(patient_id)), 2, patient_id)
            self.assertGreaterEqual(len(db.get_messages(patient_id)), 4, patient_id)

    def test_seed_is_idempotent(self):
        before = len(db.get_reports(1, 500))
        self.assertFalse(demo_life.seed())
        self.assertEqual(before, len(db.get_reports(1, 500)))

    def test_nothing_is_in_the_future(self):
        now = datetime.now(timezone.utc)
        for patient_id in range(1, 6):
            for item in db.get_timeline(patient_id, include_clinical=True, limit=500):
                self.assertLessEqual(datetime.fromisoformat(item["created_at"]), now, item["id"])

    def test_patients_show_different_neuron_moods(self):
        moods = {patient_id: neuron.state(patient_id)["mood"] for patient_id in range(1, 6)}
        self.assertEqual("blooming", moods[1])
        self.assertEqual(75, neuron.state(1)["score"])
        self.assertFalse(next(item for item in neuron.state(1)["today"] if item["id"] == "drug")["done"])
        self.assertEqual("sad", moods[5])
        self.assertGreaterEqual(len(set(moods.values())), 3)

    def test_each_patient_logs_into_own_cabinet(self):
        for login, patient_id in (("patient", 1), ("sokolova", 2), ("orlova", 5)):
            token = self.client.post("/api/auth/login", json={"login": login, "password": "patient2026"}).json()["token"]
            headers = {"Authorization": f"Bearer {token}"}
            state = self.client.get("/api/state", headers=headers).json()
            self.assertEqual(patient_id, state["patient"]["id"])
            other = 2 if patient_id != 2 else 1
            self.assertEqual(403, self.client.get(f"/api/patients/{other}/messages", headers=headers).status_code)

    def test_drug_survey_signal_created_for_bothersome_effect(self):
        signals = db.get_routing_signals(4, include_unconfirmed=True)
        self.assertIn("drug_bothersome_effect", {item["reason_code"] for item in signals})


if __name__ == "__main__":
    unittest.main()
