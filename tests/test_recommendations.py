import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app import db, recommendations, scenarios
from app.main import app

DOCTOR = {"X-Demo-Role": "doctor"}
PATIENT = {"X-Demo-Role": "patient"}


class RecommendationTests(unittest.TestCase):
    def setUp(self):
        self.original_path = db.DB_PATH
        self.temp_dir = tempfile.TemporaryDirectory()
        db.DB_PATH = Path(self.temp_dir.name) / "recommendations.db"
        db.init_db()
        scenarios.seed()
        scenarios.seed_clinical_profiles()

    def tearDown(self):
        db.DB_PATH = self.original_path
        self.temp_dir.cleanup()

    def test_critical_scenario_has_urgent_action_and_sources(self):
        result = recommendations.build(5)
        self.assertEqual(result["priority"], "critical")
        codes = {item["code"] for item in result["actions"]}
        self.assertIn("urgent-risk-assessment", codes)
        self.assertIn("mandatory-routing", codes)
        self.assertTrue(all(item["source"]["label"] for item in result["actions"]))
        self.assertIn("не изменяет лечение", result["disclaimer"])

    def test_pregnancy_blocks_therapy_suggestion(self):
        result = recommendations.build(3)
        action = next(item for item in result["actions"] if item["code"] == "aviandr-contraindication")
        self.assertEqual(action["priority"], "high")
        self.assertIn("беременность", action["rationale"].lower())
        self.assertEqual(action["source"]["kind"], "drug_instruction")

    def test_stable_scenario_has_evidence_and_plan_draft(self):
        result = recommendations.build(2)
        labels = {item["label"] for item in result["evidence"]}
        self.assertTrue({"GAD-7", "Приверженность"} <= labels)
        self.assertIn("phq9-missing", {item["code"] for item in result["actions"]})
        self.assertTrue(result["plan_draft"])
        self.assertTrue(all(item["status"] == "Требует решения врача" for item in result["actions"]))

    def test_only_doctor_receives_recommendations(self):
        with TestClient(app) as client:
            doctor = client.get("/api/patients/3", headers=DOCTOR)
            self.assertEqual(doctor.status_code, 200)
            self.assertEqual(doctor.json()["recommendations"]["priority"], "high")
            patient = client.get("/api/state", headers=PATIENT)
            self.assertEqual(patient.status_code, 200)
            self.assertIsNone(patient.json()["recommendations"])


if __name__ == "__main__":
    unittest.main()
