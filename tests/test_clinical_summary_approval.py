import os

os.environ.setdefault("CLINICAL_COMPASS_DEMO_HEADERS", "1")

import unittest

from fastapi.testclient import TestClient

from app import db
from app.main import app

DOCTOR = {"X-Demo-Role": "doctor"}
PATIENT = {"X-Demo-Role": "patient"}


class ClinicalSummaryApprovalTests(unittest.TestCase):
    def setUp(self):
        db.init_db()
        self.created_ids = []

    def tearDown(self):
        if not self.created_ids:
            return
        with db.connection() as database:
            for summary_id in self.created_ids:
                database.execute("DELETE FROM ai_clinical_summaries WHERE id = ?", (summary_id,))

    def payload(self):
        return {
            "content": "## Клинический обзор\nПроверенный врачом текст клинической сводки.",
            "draft_text": "## Клинический обзор\nИсходный текст, сформированный моделью для проверки.",
            "model": "qwen/test",
            "retrieval_release": "kb-test",
            "citations": [{"number": 1, "source_id": "test-source"}],
        }

    def test_storage_keeps_draft_final_text_and_provenance(self):
        saved = db.save_ai_summary(4, self.payload(), "Тестовый врач")
        self.created_ids.append(saved["id"])
        self.assertEqual(self.payload()["content"], saved["final_text"])
        self.assertEqual(self.payload()["draft_text"], saved["draft_text"])
        self.assertEqual("Тестовый врач", saved["confirmed_by"])
        self.assertEqual("test-source", saved["citations"][0]["source_id"])
        event = next(item for item in db.get_timeline(4, include_clinical=True) if item["id"] == f"ai-summary-{saved['id']}")
        self.assertEqual("ai_summary", event["type"])
        self.assertEqual("Подтверждено врачом", event["status"])

    def test_confirmation_endpoint_is_doctor_only(self):
        with TestClient(app) as client:
            self.assertEqual(client.post(
                "/api/patients/4/ai-summaries/confirm", headers=PATIENT, json=self.payload()
            ).status_code, 403)
            response = client.post(
                "/api/patients/4/ai-summaries/confirm", headers=DOCTOR, json=self.payload()
            )
        self.assertEqual(response.status_code, 201)
        self.created_ids.append(response.json()["id"])
        self.assertEqual("Елена Крылова", response.json()["confirmed_by"])

    def test_short_or_unknown_patient_is_rejected(self):
        with TestClient(app) as client:
            short = self.payload()
            short["content"] = "коротко"
            self.assertEqual(client.post(
                "/api/patients/4/ai-summaries/confirm", headers=DOCTOR, json=short
            ).status_code, 422)
            self.assertEqual(client.post(
                "/api/patients/99999/ai-summaries/confirm", headers=DOCTOR, json=self.payload()
            ).status_code, 404)


if __name__ == "__main__":
    unittest.main()
