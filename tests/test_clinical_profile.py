import os

os.environ.setdefault("CLINICAL_COMPASS_DEMO_HEADERS", "1")

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app import db
from app.main import app

DOCTOR = {"X-Demo-Role": "doctor"}
PATIENT = {"X-Demo-Role": "patient"}


class ClinicalProfileTests(unittest.TestCase):
    def setUp(self):
        self.original_path = db.DB_PATH
        self.temp_dir = tempfile.TemporaryDirectory()
        db.DB_PATH = Path(self.temp_dir.name) / "clinical-profile.db"
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        db.DB_PATH = self.original_path
        self.temp_dir.cleanup()

    def payload(self):
        return {
            "visit_reason": "Тревога и нарушение сна",
            "complaints": "Постоянное беспокойство",
            "symptom_duration": "3 месяца",
            "history": "Постепенное начало",
            "comorbidities": "Не указаны",
            "current_medications": "Не принимает",
            "allergies": "Не отмечает",
            "working_hypothesis": "Требуется уточнение тревожного расстройства",
            "psychosis_signs": False,
            "self_harm_concern": False,
            "pregnancy_status": "not_applicable",
        }

    def test_doctor_can_save_and_read_summary(self):
        response = self.client.put("/api/patients/2/clinical-profile", headers=DOCTOR, json=self.payload())
        self.assertEqual(response.status_code, 200)
        saved = response.json()
        self.assertEqual(saved["visit_reason"], "Тревога и нарушение сна")
        self.assertEqual(saved["updated_by"], "Елена Крылова")

        detail = self.client.get("/api/patients/2", headers=DOCTOR).json()
        self.assertEqual(detail["clinical_profile"]["working_hypothesis"], self.payload()["working_hypothesis"])

    def test_patient_cannot_edit_or_receive_doctor_summary(self):
        self.assertEqual(
            self.client.put("/api/patients/1/clinical-profile", headers=PATIENT, json=self.payload()).status_code,
            403,
        )
        state = self.client.get("/api/state", headers=PATIENT).json()
        self.assertIsNone(state["clinical_profile"])

    def test_unknown_patient_is_rejected(self):
        self.assertEqual(
            self.client.put("/api/patients/999/clinical-profile", headers=DOCTOR, json=self.payload()).status_code,
            404,
        )


if __name__ == "__main__":
    unittest.main()
