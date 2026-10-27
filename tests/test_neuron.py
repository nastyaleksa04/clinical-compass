import os

os.environ.setdefault("CLINICAL_COMPASS_DEMO_HEADERS", "1")

import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import db
from app import neuron
from app.main import app

DOCTOR = {"X-Demo-Role": "doctor"}
PATIENT = {"X-Demo-Role": "patient"}
REPORT = {"mood": 3, "anxiety": 3, "sleep": 3, "comment": "", "urgent": False}
TODAY = date(2026, 10, 20)


def at(day: date) -> str:
    return datetime(day.year, day.month, day.day, 9, tzinfo=timezone.utc).isoformat()


class NeuronTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(db, "DB_PATH", Path(self.temp_dir.name) / "neuron.db")
        self.db_patch.start()
        self.today_patch = patch.object(neuron, "local_today", return_value=TODAY)
        self.today_patch.start()
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        self.today_patch.stop()
        self.db_patch.stop()
        self.temp_dir.cleanup()

    def report_on(self, day: date, **values):
        with patch.object(db, "now_iso", return_value=at(day)):
            db.create_report(1, {**REPORT, **values})

    def checkin_on(self, day: date, taken: bool):
        with patch.object(db, "now_iso", return_value=at(day)):
            db.create_checkin(1, {"taken": taken, "side_effect": "", "side_effect_severity": "none"})

    def state(self):
        return self.client.get("/api/neuron", headers=PATIENT).json()

    def test_new_patient_gets_calm_greeting(self):
        data = self.state()
        self.assertEqual("calm", data["mood"])
        self.assertEqual(0, data["score"])
        self.assertIn("Привет", data["message"])

    def test_regular_reports_cheer_neuron_up(self):
        for offset in range(7):
            self.report_on(TODAY - timedelta(days=offset))
        with patch.object(db, "now_iso", return_value=at(TODAY)):
            db.create_assessment(1, "phq9", [0] * 9, {"total": 0, "severity": "minimal", "alert": False, "alert_codes": []})
            db.create_drug_report(1, {"drug_id": "aviandr", "sections": [], "followups": {}, "red_flags": [],
                                      "impact": "none", "note": "", "share_consent": False})
        data = self.state()
        self.assertEqual("excited", data["mood"])
        self.assertEqual(100, data["score"])
        self.assertEqual(7, data["streak"])

    def test_mood_does_not_depend_on_answers(self):
        for offset in range(4):
            self.report_on(TODAY - timedelta(days=offset), mood=5, anxiety=1, sleep=5)
        good = self.state()
        self.tearDown(); self.setUp()
        for offset in range(4):
            self.report_on(TODAY - timedelta(days=offset), mood=1, anxiety=5, sleep=1)
        bad = self.state()
        self.assertEqual(good["mood"], bad["mood"])
        self.assertEqual(good["score"], bad["score"])

    def test_neuron_falls_asleep_then_gets_sad_without_marks(self):
        self.report_on(TODAY - timedelta(days=4))
        self.assertEqual("sleepy", self.state()["mood"])
        self.tearDown(); self.setUp()
        self.report_on(TODAY - timedelta(days=9))
        self.assertEqual("sad", self.state()["mood"])

    def test_missed_therapy_makes_neuron_sad(self):
        with patch.object(neuron, "_has_therapy", return_value=True):
            for offset in range(3):
                self.report_on(TODAY - timedelta(days=offset))
                self.checkin_on(TODAY - timedelta(days=offset), taken=False)
            data = self.state()
        self.assertEqual("sad", data["mood"])
        self.assertEqual(3, data["missed_recent"])

    def test_marked_miss_counts_more_than_silence(self):
        with patch.object(neuron, "_has_therapy", return_value=True):
            self.report_on(TODAY)
            silent = self.state()["score"]
            self.checkin_on(TODAY, taken=False)
            honest = self.state()["score"]
            self.checkin_on(TODAY - timedelta(days=1), taken=True)
            taken = self.state()["score"]
        self.assertLess(silent, honest)
        self.assertLess(honest, taken)

    def test_drug_survey_is_first_in_checklist(self):
        self.assertEqual("drug", self.state()["today"][0]["id"])

    def test_today_checklist_tracks_report(self):
        before = {item["id"]: item["done"] for item in self.state()["today"]}
        self.client.post("/api/patients/1/reports", headers=PATIENT, json=REPORT)
        with patch.object(neuron, "local_today", return_value=datetime.now(timezone.utc).date()):
            after = {item["id"]: item["done"] for item in self.state()["today"]}
        self.assertFalse(before["report"])
        self.assertTrue(after["report"])

    def test_doctor_sees_patient_neuron_and_patient_cannot(self):
        self.assertEqual(200, self.client.get("/api/patients/1/neuron", headers=DOCTOR).status_code)
        self.assertEqual(403, self.client.get("/api/patients/1/neuron", headers=PATIENT).status_code)
        self.assertEqual(404, self.client.get("/api/patients/999/neuron", headers=DOCTOR).status_code)


if __name__ == "__main__":
    unittest.main()
