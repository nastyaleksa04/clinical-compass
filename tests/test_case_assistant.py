import os

os.environ.setdefault("CLINICAL_COMPASS_DEMO_HEADERS", "1")

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.rag.case_assistant import _observation_scope, answer

DOCTOR = {"X-Demo-Role": "doctor"}
PATIENT = {"X-Demo-Role": "patient"}


class FakeClient:
    def __init__(self):
        self.messages = None

    def complete(self, messages):
        self.messages = messages
        return {
            "content": (
                "## Ответ по данным случая\nОтмечается динамика тревожных симптомов.\n\n"
                "## Что говорит база знаний\nРезультаты шкал требуют клинической интерпретации [1].\n\n"
                "## Что проверить врачу\n- Актуальную выраженность симптомов."
            ),
            "model": "test/qwen",
            "usage": {},
            "request_id": "case-test",
        }


class CaseAssistantTests(unittest.TestCase):
    def test_answer_combines_case_and_doctor_kb(self):
        client = FakeClient()
        result = answer(1, "Как изменилась тревога?", client=client)
        prompt = client.messages[1]["content"]
        self.assertIn("ВОПРОС ВРАЧА", prompt)
        self.assertIn("ДАННЫЕ СЛУЧАЯ", prompt)
        self.assertIn("ФРАГМЕНТЫ ВРАЧЕБНОЙ БАЗЫ", prompt)
        self.assertTrue(result["draft"])
        self.assertTrue(result["deidentified"])
        self.assertTrue(result["citations"])
        self.assertTrue(result["grounded"])
        self.assertEqual(["summary", "doctor_review"], result["sections"])
        self.assertIn("РАМКИ ИНТЕРПРЕТАЦИИ ПЕРИОДА", prompt)
        self.assertIn("observation_scope", result)

    def test_same_day_measurements_are_not_a_reliable_trend(self):
        case = {
            "assessments": [
                {"created_at": "2026-10-21T11:40:00+03:00"},
                {"created_at": "2026-10-21T14:03:00+03:00"},
            ],
            "reports": [{"created_at": "2026-10-21T13:00:00+03:00"}],
            "medication_checkins": [],
            "routing_signals": [],
        }
        scope = _observation_scope(case)
        self.assertEqual(1, scope["unique_dates"])
        self.assertLess(scope["span_hours"], 24)
        self.assertEqual("insufficient_for_reliable_trend", scope["longitudinal_conclusion"])

    def test_question_identifiers_are_redacted_before_model(self):
        client = FakeClient()
        result = answer(
            1,
            "Анастасия Александрова, почта patient@example.com, телефон +7 999 123-45-67: как изменилась тревога?",
            client=client,
        )
        prompt = client.messages[1]["content"]
        self.assertNotIn("Анастасия Александрова", prompt)
        self.assertNotIn("patient@example.com", prompt)
        self.assertNotIn("999 123", prompt)
        self.assertTrue(result["personal_data_redacted"])

    def test_endpoint_is_doctor_only(self):
        payload = {
            "answer": "Черновик ответа",
            "draft": True,
            "deidentified": True,
            "personal_data_redacted": False,
            "sections": ["case", "knowledge", "doctor_review"],
            "citations": [],
            "grounded": True,
            "citation_warnings": [],
            "model": "test/qwen",
            "usage": {},
            "request_id": "x",
            "retrieval": {"release": "test", "result_count": 0, "limit": 6},
        }
        with TestClient(app) as client:
            self.assertEqual(client.post(
                "/api/patients/1/case-assistant/answer",
                headers=PATIENT,
                json={"question": "Как изменилась тревога?"},
            ).status_code, 403)
            with patch("app.main.case_assistant.answer", return_value=payload) as mocked:
                response = client.post(
                    "/api/patients/1/case-assistant/answer",
                    headers=DOCTOR,
                    json={"question": "Как изменилась тревога?"},
                )
        self.assertEqual(response.status_code, 200)
        mocked.assert_called_once_with(1, "Как изменилась тревога?", 6)

    def test_unknown_patient_returns_404(self):
        with TestClient(app) as client, patch("app.main.case_assistant.answer") as mocked:
            response = client.post(
                "/api/patients/99999/case-assistant/answer",
                headers=DOCTOR,
                json={"question": "Какие данные требуют проверки?"},
            )
        self.assertEqual(response.status_code, 404)
        mocked.assert_not_called()


if __name__ == "__main__":
    unittest.main()
