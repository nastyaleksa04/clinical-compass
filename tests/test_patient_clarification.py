import os

os.environ.setdefault("CLINICAL_COMPASS_DEMO_HEADERS", "1")

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app import db
from app.main import app
from app.rag.clarification import analyze
from app.rag.patient_assistant import answer


class FakeClient:
    def __init__(self):
        self.calls = []

    def complete(self, messages):
        self.calls.append(messages)
        return {
            "content": "Вы описали изменение, которое стоит обсудить с врачом [1].",
            "model": "test/qwen",
            "usage": {},
            "request_id": "clarification-test",
        }


class PatientClarificationTests(unittest.TestCase):
    def setUp(self):
        self.original_path = db.DB_PATH
        self.temp_dir = tempfile.TemporaryDirectory()
        db.DB_PATH = Path(self.temp_dir.name) / "clarification.db"
        db.init_db()
        self.client = FakeClient()

    def tearDown(self):
        db.DB_PATH = self.original_path
        self.temp_dir.cleanup()

    def test_incomplete_complaint_asks_questions_without_llm_or_storage(self):
        result = answer("У меня появился побочный эффект", client=self.client)

        self.assertEqual("clarification", result["route"])
        self.assertEqual(3, len(result["clarification"]["missing_questions"]))
        self.assertFalse(result["clarification_saved"])
        self.assertEqual([], self.client.calls)
        self.assertEqual([], db.get_assistant_intakes(1))

    def test_complete_answers_require_confirmation_before_storage_and_llm(self):
        answers = {"symptom": "Тошнота", "severity": "moderate", "onset": "Вчера вечером"}
        result = answer(
            "У меня появился побочный эффект",
            clarification_answers=answers,
            client=self.client,
        )

        self.assertEqual("clarification_confirmation", result["route"])
        self.assertIn("Умеренно", result["clarification"]["summary"][1]["answer"])
        self.assertEqual([], self.client.calls)
        self.assertEqual([], db.get_assistant_intakes(1))

    def test_confirmation_saves_once_and_sends_deidentified_answers(self):
        patient_name = db.get_patient(1)["name"]
        answers = {
            "symptom": "Тошнота",
            "severity": "moderate",
            "onset": f"{patient_name}, вчера; телефон +7 999 123-45-67",
        }
        first = answer(
            "У меня появился побочный эффект",
            clarification_answers=answers,
            confirm_clarification=True,
            client=self.client,
        )
        second = answer(
            "У меня появился побочный эффект",
            clarification_answers=answers,
            confirm_clarification=True,
            client=self.client,
        )

        self.assertEqual("self_service", first["route"])
        self.assertTrue(first["clarification_saved"])
        self.assertEqual(first["intake_id"], second["intake_id"])
        self.assertEqual(1, len(db.get_assistant_intakes(1)))
        prompt = self.client.calls[0][1]["content"]
        stored = str(db.get_assistant_intakes(1)[0])
        for private_value in (patient_name, "999 123"):
            self.assertNotIn(private_value, prompt)
            self.assertNotIn(private_value, stored)
        event = next(item for item in db.get_timeline(1) if item["type"] == "assistant_intake")
        self.assertEqual("Подтверждено пациентом", event["status"])

    def test_risk_in_clarification_answer_bypasses_llm_and_storage(self):
        result = answer(
            "Мне тревожно",
            clarification_answers={
                "duration": "Два дня",
                "intensity": "5",
                "impact": "Я не хочу жить",
            },
            confirm_clarification=True,
            client=self.client,
        )
        self.assertEqual("emergency", result["route"])
        self.assertEqual([], self.client.calls)
        self.assertEqual([], db.get_assistant_intakes(1))

    def test_severe_adverse_effect_routes_to_doctor_without_llm(self):
        result = answer(
            "У меня побочный эффект",
            clarification_answers={"severity": "severe"},
            client=self.client,
        )
        self.assertEqual("contact_doctor", result["route"])
        self.assertEqual([], self.client.calls)

    def test_existing_self_report_prevents_repeated_intensity_question(self):
        context = {"recent_self_reports": [{"anxiety": 4}]}
        result = analyze("Мне тревожно", context)
        question_ids = {item["id"] for item in result["questions"]}
        self.assertNotIn("intensity", question_ids)
        self.assertIn("duration", question_ids)

    def test_informational_question_does_not_trigger_clarification(self):
        self.assertIsNone(analyze("Как сообщить врачу о нежелательной реакции?", {}))

    def test_api_returns_questions_without_openrouter_configuration(self):
        with TestClient(app) as client:
            response = client.post(
                "/api/patient-assistant/answer",
                headers={"X-Demo-Role": "patient"},
                json={"query": "У меня появился побочный эффект"},
            )
        self.assertEqual(200, response.status_code)
        self.assertEqual("clarification", response.json()["route"])
        self.assertFalse(response.json()["generated_by_llm"])


if __name__ == "__main__":
    unittest.main()
