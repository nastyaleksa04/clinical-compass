import os

os.environ.setdefault("CLINICAL_COMPASS_DEMO_HEADERS", "1")

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.rag.patient_assistant import answer, redact_personal_data
from app.rag.retrieval import patient_index

DOCTOR = {"X-Demo-Role": "doctor"}
PATIENT = {"X-Demo-Role": "patient"}


class FakeClient:
    def __init__(self):
        self.messages = None

    def complete(self, messages):
        self.messages = messages
        return {
            "content": "GAD-7 помогает наблюдать тревожные симптомы, но не устанавливает диагноз [1].",
            "model": "test/qwen",
            "usage": {},
            "request_id": "patient-test",
        }


class PatientAssistantTests(unittest.TestCase):
    def test_patient_corpus_is_physically_separate_and_patient_only(self):
        index = patient_index()
        self.assertEqual("kb_v2.3-patient-prototype", index.manifest["release"])
        self.assertTrue(index.chunks)
        self.assertTrue(all(chunk["audience"] == ["patient"] for chunk in index.chunks))
        self.assertTrue(all(not chunk["automation_eligible"] for chunk in index.chunks))

    def test_crisis_message_bypasses_llm_and_routes_to_emergency(self):
        client = FakeClient()
        result = answer("Я не хочу жить и думаю причинить себе вред", client=client)
        self.assertEqual("emergency", result["route"])
        self.assertFalse(result["generated_by_llm"])
        self.assertIn("112", result["answer"])
        self.assertIsNone(client.messages)

    def test_therapy_change_bypasses_llm_and_routes_to_doctor(self):
        client = FakeClient()
        result = answer("Можно мне увеличить дозу лекарства?", client=client)
        self.assertEqual("contact_doctor", result["route"])
        self.assertFalse(result["generated_by_llm"])
        self.assertIn("Не меняйте", result["answer"])
        self.assertIsNone(client.messages)

    def test_general_question_uses_only_patient_corpus(self):
        client = FakeClient()
        result = answer("Что показывает GAD-7?", client=client)
        self.assertEqual("self_service", result["route"])
        self.assertTrue(result["generated_by_llm"])
        self.assertTrue(result["grounded"])
        self.assertIn("Фрагменты пациентской базы", client.messages[1]["content"])
        self.assertNotIn("врачебному корпусу", client.messages[1]["content"])

    def test_email_and_phone_are_redacted_before_llm(self):
        text, changed = redact_personal_data("Почта test@example.com, телефон +7 999 123-45-67")
        self.assertTrue(changed)
        self.assertNotIn("test@example.com", text)
        self.assertNotIn("999 123", text)

    def test_endpoints_are_patient_only(self):
        with TestClient(app) as client:
            self.assertEqual(client.get("/api/patient-assistant/status", headers=DOCTOR).status_code, 403)
            response = client.post(
                "/api/patient-assistant/answer",
                headers=PATIENT,
                json={"query": "Я хочу увеличить дозу"},
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["route"], "contact_doctor")
            self.assertEqual(client.post(
                "/api/patient-assistant/answer",
                headers=DOCTOR,
                json={"query": "Что такое GAD-7?"},
            ).status_code, 403)


if __name__ == "__main__":
    unittest.main()
