import os

os.environ.setdefault("CLINICAL_COMPASS_DEMO_HEADERS", "1")

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import db
from app.main import app

DOCTOR = {"X-Demo-Role": "doctor"}
PATIENT = {"X-Demo-Role": "patient"}

AI_DRAFT = {
    "summary": "## Клинический обзор\nСостояние требует планового наблюдения.\n\n## Динамика состояния\nПолучены новые данные пациента [1].\n\n## Риски и клиническое внимание\nНужна врачебная оценка.\n\n## Что уточнить на следующем контакте\n- Изменилась ли тревога?\n\n## Недостающие данные\nНужна повторная оценка.",
    "draft": True,
    "deidentified": True,
    "personal_data_redacted": False,
    "context_fields": ["patient", "assessments", "reports"],
    "citations": [{"number": 1, "source_id": "demo-source", "title": "Демонстрационный источник"}],
    "grounded": True,
    "citation_warnings": [],
    "model": "demo/qwen",
    "usage": {},
    "request_id": "demo-flow",
    "retrieval": {"release": "kb-demo", "result_count": 1, "limit": 6},
}


class MVPFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(db, "DB_PATH", Path(self.temp_dir.name) / "mvp-flow.db")
        self.db_patch.start()
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        self.db_patch.stop()
        self.temp_dir.cleanup()

    def test_complete_patient_doctor_flow_without_restart_or_manual_db_changes(self):
        initial = self.client.get("/api/state", headers=PATIENT)
        self.assertEqual(initial.status_code, 200)
        self.assertEqual(1, initial.json()["patient"]["id"])

        report = self.client.post(
            "/api/patients/1/reports",
            headers=PATIENT,
            json={"mood": 3, "anxiety": 4, "sleep": 2, "comment": "Тревога усилилась к вечеру", "urgent": False},
        )
        self.assertEqual(report.status_code, 201)

        assessment = self.client.post(
            "/api/patients/1/assessments",
            headers=PATIENT,
            json={"scale_id": "phq9", "answers": [1, 1, 1, 1, 1, 1, 1, 1, 0]},
        )
        self.assertEqual(assessment.status_code, 201)
        self.assertEqual(8, assessment.json()["total"])

        patient_question = self.client.post(
            "/api/patient-assistant/answer",
            headers=PATIENT,
            json={"query": "Можно увеличить дозу лекарства?"},
        )
        self.assertEqual(patient_question.status_code, 200)
        self.assertEqual("contact_doctor", patient_question.json()["route"])
        self.assertFalse(patient_question.json()["generated_by_llm"])

        doctor_card = self.client.get("/api/patients/1", headers=DOCTOR)
        self.assertEqual(doctor_card.status_code, 200)
        card = doctor_card.json()
        self.assertTrue(any(item["comment"] == "Тревога усилилась к вечеру" for item in card["reports"]))
        self.assertTrue(any(item["scale_id"] == "phq9" and item["total"] == 8 for item in card["assessments"]))

        rag = self.client.post(
            "/api/rag/search",
            headers=DOCTOR,
            json={"query": "GAD-7 тревога интерпретация", "limit": 5},
        )
        self.assertEqual(rag.status_code, 200)
        self.assertTrue(rag.json()["results"])

        with patch("app.main.clinical_summary.generate", return_value=AI_DRAFT):
            generated = self.client.post(
                "/api/patients/1/ai-summary", headers=DOCTOR, json={"limit": 6}
            )
        self.assertEqual(generated.status_code, 200)
        self.assertTrue(generated.json()["draft"])

        final_text = generated.json()["summary"].replace(
            "Состояние требует планового наблюдения.",
            "Врач проверил динамику; состояние требует планового наблюдения.",
        )
        confirmed = self.client.post(
            "/api/patients/1/ai-summaries/confirm",
            headers=DOCTOR,
            json={
                "content": final_text,
                "draft_text": generated.json()["summary"],
                "model": generated.json()["model"],
                "retrieval_release": generated.json()["retrieval"]["release"],
                "citations": generated.json()["citations"],
            },
        )
        self.assertEqual(confirmed.status_code, 201)
        self.assertIn("Врач проверил динамику", confirmed.json()["final_text"])

        plan = self.client.put(
            "/api/patients/1/plan",
            headers=DOCTOR,
            json={"text": "Продолжить наблюдение. Повторный контакт через 7 дней."},
        )
        self.assertEqual(plan.status_code, 200)

        refreshed_doctor = self.client.get("/api/patients/1", headers=DOCTOR).json()
        self.assertEqual(1, len(refreshed_doctor["ai_summaries"]))
        self.assertTrue(any(item["type"] == "ai_summary" for item in refreshed_doctor["timeline"]))

        refreshed_patient = self.client.get("/api/state", headers=PATIENT).json()
        self.assertEqual("Продолжить наблюдение. Повторный контакт через 7 дней.", refreshed_patient["plan"]["text"])
        self.assertEqual([], refreshed_patient["ai_summaries"])
        self.assertFalse(any(item["type"] == "ai_summary" for item in refreshed_patient["timeline"]))


if __name__ == "__main__":
    unittest.main()
