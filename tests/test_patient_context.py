import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from app import db
from app.rag.patient_assistant import answer
from app.rag.patient_context import build_patient_context


class FakeClient:
    def __init__(self):
        self.messages = None

    def complete(self, messages):
        self.messages = messages
        return {
            "content": "Ваш последний GAD-7 — результат скрининга, а не диагноз [1].",
            "model": "test/qwen",
            "usage": {},
            "request_id": "patient-context-test",
        }


class PatientContextTests(unittest.TestCase):
    def setUp(self):
        self.original_path = db.DB_PATH
        self.temp_dir = tempfile.TemporaryDirectory()
        db.DB_PATH = Path(self.temp_dir.name) / "patient-context.db"
        db.init_db()

    def tearDown(self):
        db.DB_PATH = self.original_path
        self.temp_dir.cleanup()

    def _seed_visible_and_internal_data(self):
        patient_name = db.get_patient(1)["name"]
        db.create_assessment(1, "gad7", [1] * 7, {
            "total": 7,
            "severity": "Лёгкая выраженность",
            "alert": False,
            "alert_codes": [],
        })
        db.create_report(1, {
            "mood": 3,
            "anxiety": 4,
            "sleep": 2,
            "comment": "Перезвонить по +7 999 123-45-67",
            "urgent": False,
        })
        db.save_plan(
            1,
            f"{patient_name}, повторить GAD-7 через неделю, карта 18379499",
            "Секретное Имя Врача",
        )
        db.create_care_task(1, {
            "title": "Заполнить дневник",
            "description": "Вопросы: patient-private@example.com",
            "category": "monitoring",
            "due_date": date(2026, 11, 1),
        })
        safety = {"status": "ok", "findings": [], "source": "internal-source"}
        approved = {
            "medication_id": "demo-approved",
            "medication_name": "Подтверждённый препарат",
            "indication": "Подтверждённое показание",
            "dosage": "10 мг",
            "schedule": "1 раз в день",
            "duration": "7 дней",
            "decision": "approved",
            "rationale": "Скрытое обоснование",
        }
        db.create_therapy_decision(1, approved, safety, "Секретное Имя Врача")
        internal = {
            **approved,
            "medication_id": "demo-deferred",
            "medication_name": "Скрытый препарат",
            "decision": "deferred",
            "rationale": "Скрытая гипотеза",
        }
        db.create_therapy_decision(1, internal, safety, "Секретное Имя Врача")
        pending = db.create_routing_signal(
            1,
            {"level": "recommended", "reason_code": "private", "reason_text": "Скрытый маршрут"},
            "test",
            9001,
        )
        confirmed = db.create_routing_signal(
            1,
            {"level": "recommended", "reason_code": "visible", "reason_text": "Связаться с врачом"},
            "test",
            9002,
        )
        db.decide_routing_signal(confirmed["id"], "confirmed", "Подтверждено")
        self.assertEqual("pending", pending["status"])
        db.save_clinical_profile(1, {
            "visit_reason": "Скрытая причина",
            "complaints": "Скрытые жалобы",
            "symptom_duration": "Скрытая длительность",
            "history": "Скрытый анамнез",
            "comorbidities": "Скрытые заболевания",
            "current_medications": "Скрытые лекарства",
            "allergies": "Скрытые аллергии",
            "working_hypothesis": "СЕКРЕТНАЯ ГИПОТЕЗА",
            "psychosis_signs": False,
            "self_harm_concern": False,
            "pregnancy_status": "unknown",
        }, "Секретное Имя Врача")
        db.save_ai_summary(1, {
            "draft_text": "СЕКРЕТНЫЙ ЧЕРНОВИК",
            "content": "СЕКРЕТНАЯ AI-СВОДКА",
            "model": "test",
            "retrieval_release": "test",
            "citations": [],
        }, "Секретное Имя Врача")

    def test_allowlist_contains_visible_data_and_excludes_internal_data(self):
        self._seed_visible_and_internal_data()
        payload = build_patient_context(1)
        serialized = json.dumps(payload, ensure_ascii=False)

        self.assertTrue(payload["patient_visible_only"])
        self.assertIn("latest_assessments", payload["context_fields"])
        self.assertIn("confirmed_plan", payload["context_fields"])
        self.assertIn("Подтверждённый препарат", serialized)
        self.assertIn("Связаться с врачом", serialized)
        self.assertNotIn("Скрытый препарат", serialized)
        self.assertNotIn("Скрытый маршрут", serialized)
        self.assertNotIn("СЕКРЕТНАЯ ГИПОТЕЗА", serialized)
        self.assertNotIn("СЕКРЕТНАЯ AI-СВОДКА", serialized)
        self.assertNotIn("Секретное Имя Врача", serialized)
        self.assertNotIn("999 123", serialized)
        self.assertNotIn("patient-private@example.com", serialized)
        self.assertNotIn(db.get_patient(1)["name"], serialized)
        self.assertNotIn("18379499", serialized)
        self.assertTrue(payload["personal_data_redacted"])

    def test_answer_sends_only_allowlisted_context_to_fake_model(self):
        self._seed_visible_and_internal_data()
        client = FakeClient()
        result = answer("Что означает мой последний GAD-7?", client=client, patient_id=1)
        prompt = client.messages[1]["content"]

        self.assertTrue(result["context_used"])
        self.assertTrue(result["patient_visible_context_only"])
        self.assertIn("GAD7", prompt)
        self.assertIn("screening_result_not_diagnosis", prompt)
        self.assertNotIn("СЕКРЕТНАЯ ГИПОТЕЗА", prompt)
        self.assertNotIn("СЕКРЕТНАЯ AI-СВОДКА", prompt)
        self.assertNotIn("Скрытый препарат", prompt)

    def test_safety_routes_still_bypass_context_and_llm(self):
        client = FakeClient()
        result = answer("Я хочу увеличить дозу", client=client, patient_id=999)
        self.assertEqual("contact_doctor", result["route"])
        self.assertFalse(result["context_used"])
        self.assertIsNone(client.messages)


if __name__ == "__main__":
    unittest.main()
