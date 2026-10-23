import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app import db
from app.main import app

DOCTOR = {"X-Demo-Role": "doctor"}
PATIENT = {"X-Demo-Role": "patient"}
INDICATION = "Генерализованное тревожное расстройство у взрослых"


class TherapyDecisionTests(unittest.TestCase):
    def setUp(self):
        self.original_path = db.DB_PATH
        self.temp_dir = tempfile.TemporaryDirectory()
        db.DB_PATH = Path(self.temp_dir.name) / "therapy-decisions.db"
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        db.DB_PATH = self.original_path
        self.temp_dir.cleanup()

    def payload(self, **updates):
        data = {
            "medication_id": "aviandr",
            "indication": INDICATION,
            "dosage": "20 мг",
            "schedule": "2 раза в сутки",
            "duration": "4 недели",
            "decision": "approved",
            "rationale": "",
            "factors": {},
        }
        data.update(updates)
        return data

    def test_approved_decision_is_visible_to_patient_and_timeline(self):
        response = self.client.post("/api/patients/1/therapy-decisions", headers=DOCTOR, json=self.payload())
        self.assertEqual(response.status_code, 201)
        state = self.client.get("/api/state", headers=PATIENT).json()
        self.assertEqual(state["therapy_decisions"][0]["decision"], "approved")
        self.assertEqual(state["therapy_decisions"][0]["dosage"], "20 мг")
        self.assertTrue(any(event["type"] == "therapy_decision" for event in state["timeline"]))

    def test_contraindication_blocks_approval(self):
        response = self.client.post(
            "/api/patients/1/therapy-decisions",
            headers=DOCTOR,
            json=self.payload(factors={"pregnancy": True}, rationale="Оценено врачом"),
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn("противопоказание", response.json()["detail"])

    def test_unregistered_indication_and_incomplete_regimen_are_rejected(self):
        bad_indication = self.client.post(
            "/api/patients/1/therapy-decisions",
            headers=DOCTOR,
            json=self.payload(indication="Бессонница"),
        )
        self.assertEqual(bad_indication.status_code, 422)
        incomplete = self.client.post(
            "/api/patients/1/therapy-decisions",
            headers=DOCTOR,
            json=self.payload(duration=""),
        )
        self.assertEqual(incomplete.status_code, 422)

    def test_warning_requires_rationale(self):
        without = self.client.post(
            "/api/patients/1/therapy-decisions",
            headers=DOCTOR,
            json=self.payload(factors={"serotonergic_drugs": True}),
        )
        self.assertEqual(without.status_code, 422)
        with_rationale = self.client.post(
            "/api/patients/1/therapy-decisions",
            headers=DOCTOR,
            json=self.payload(factors={"serotonergic_drugs": True}, rationale="Проверены взаимодействия"),
        )
        self.assertEqual(with_rationale.status_code, 201)

    def test_internal_decision_is_hidden_from_patient(self):
        response = self.client.post(
            "/api/patients/1/therapy-decisions",
            headers=DOCTOR,
            json=self.payload(decision="deferred", rationale="Нужно уточнить анамнез"),
        )
        self.assertEqual(response.status_code, 201)
        doctor = self.client.get("/api/patients/1", headers=DOCTOR).json()
        patient = self.client.get("/api/state", headers=PATIENT).json()
        self.assertEqual(doctor["therapy_decisions"][0]["decision"], "deferred")
        self.assertEqual(patient["therapy_decisions"], [])

    def test_cancelled_decision_remains_visible_and_patient_cannot_change_it(self):
        created = self.client.post("/api/patients/1/therapy-decisions", headers=DOCTOR, json=self.payload()).json()
        forbidden = self.client.put("/api/therapy-decisions/%s/cancel" % created["id"], headers=PATIENT)
        self.assertEqual(forbidden.status_code, 403)
        cancelled = self.client.put("/api/therapy-decisions/%s/cancel" % created["id"], headers=DOCTOR)
        self.assertEqual(cancelled.status_code, 200)
        self.assertEqual(cancelled.json()["decision"], "cancelled")
        patient = self.client.get("/api/state", headers=PATIENT).json()
        self.assertEqual(patient["therapy_decisions"][0]["decision"], "cancelled")

    def test_patient_cannot_create_decision(self):
        response = self.client.post("/api/patients/1/therapy-decisions", headers=PATIENT, json=self.payload())
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
