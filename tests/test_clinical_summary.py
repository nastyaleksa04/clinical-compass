import os

os.environ.setdefault("CLINICAL_COMPASS_DEMO_HEADERS", "1")

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.rag.clinical_summary import build_case_context, generate

DOCTOR = {"X-Demo-Role": "doctor"}
PATIENT = {"X-Demo-Role": "patient"}


class FakeClient:
    def __init__(self):
        self.messages = None

    def complete(self, messages):
        self.messages = messages
        return {
            "content": "Наблюдаемые данные\nЕсть симптомы тревоги.\n\nРиски\nТребуется клиническая проверка [1].",
            "model": "test/qwen",
            "usage": {"total_tokens": 42},
            "request_id": "summary-test",
        }


class ClinicalSummaryTests(unittest.TestCase):
    def test_context_is_allow_listed_and_redacts_identifiers(self):
        profile = {
            "visit_reason": "Анастасия Александрова, patient@example.com, +7 999 123-45-67",
            "complaints": "тревога", "symptom_duration": "месяц", "history": "",
            "comorbidities": "", "current_medications": "", "allergies": "",
            "working_hypothesis": "ГТР", "psychosis_signs": False,
            "self_harm_concern": False, "pregnancy_status": "unknown", "updated_at": None,
        }
        with patch("app.rag.clinical_summary.db.get_clinical_profile", return_value=profile):
            context = build_case_context(1)
        encoded = str(context)
        self.assertTrue(context["deidentified"])
        self.assertNotIn("Анастасия", encoded)
        self.assertNotIn("patient@example.com", encoded)
        self.assertNotIn("999 123", encoded)
        self.assertNotIn("name", context["patient"])
        self.assertNotIn("phone", context["patient"])
        self.assertIn("adherence", context)
        self.assertIn("assessments", context)

    def test_generate_uses_doctor_kb_and_marks_draft(self):
        client = FakeClient()
        result = generate(1, client=client)
        prompt = client.messages[1]["content"]
        self.assertTrue(result["draft"])
        self.assertTrue(result["deidentified"])
        self.assertTrue(result["citations"])
        self.assertTrue(result["grounded"])
        self.assertIn("ДАННЫЕ СЛУЧАЯ", prompt)
        self.assertIn("ФРАГМЕНТЫ БАЗЫ ЗНАНИЙ", prompt)
        self.assertNotIn("Анастасия Александрова", prompt)
        self.assertNotIn("patient@example.com", prompt)

    def test_endpoint_is_doctor_only_and_does_not_persist_result(self):
        payload = {
            "summary": "Черновик", "draft": True, "deidentified": True,
            "personal_data_redacted": False, "context_fields": ["patient"],
            "citations": [], "grounded": True, "citation_warnings": [],
            "model": "test/qwen", "usage": {}, "request_id": "x",
            "retrieval": {"release": "test", "result_count": 0, "limit": 6},
        }
        with TestClient(app) as client:
            self.assertEqual(client.post("/api/patients/1/ai-summary", headers=PATIENT, json={}).status_code, 403)
            with patch("app.main.clinical_summary.generate", return_value=payload) as mocked:
                response = client.post("/api/patients/1/ai-summary", headers=DOCTOR, json={})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()["draft"])
            mocked.assert_called_once_with(1, 6)

    def test_unknown_patient_returns_404_without_calling_model(self):
        with TestClient(app) as client, patch("app.main.clinical_summary.generate") as mocked:
            response = client.post("/api/patients/99999/ai-summary", headers=DOCTOR, json={})
        self.assertEqual(response.status_code, 404)
        mocked.assert_not_called()


if __name__ == "__main__":
    unittest.main()
