import os

os.environ.setdefault("CLINICAL_COMPASS_DEMO_HEADERS", "1")

import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from pypdf import PdfReader

from app import db
from app.documents import generate_pdf, get_document, list_documents
from app.main import app


PATIENT = {"X-Demo-Role": "patient"}
DOCTOR = {"X-Demo-Role": "doctor"}


class PatientDocumentTests(unittest.TestCase):
    def setUp(self):
        self.original_path = db.DB_PATH
        self.temp_dir = tempfile.TemporaryDirectory()
        db.DB_PATH = Path(self.temp_dir.name) / "documents.db"
        db.init_db()
        db.save_clinical_profile(1, {
            "visit_reason": "Тревога и нарушения сна",
            "complaints": "Тревога усиливается вечером",
            "symptom_duration": "Три недели",
            "history": "Наблюдается амбулаторно",
            "comorbidities": "Не указаны",
            "current_medications": "По подтверждённому плану",
            "allergies": "Не указаны",
            "working_hypothesis": "Тревожное расстройство — рабочая гипотеза врача",
            "psychosis_signs": False,
            "self_harm_concern": False,
            "pregnancy_status": "unknown",
        }, "Тестовый врач")
        db.create_assessment(1, "gad7", [1] * 7, {
            "total": 7, "severity": "Лёгкая выраженность", "alert": False, "alert_codes": [],
        })
        db.create_report(1, {
            "mood": 3, "anxiety": 4, "sleep": 2,
            "comment": "Трудно заснуть", "urgent": False,
        })
        db.save_plan(1, "Продолжить наблюдение и повторить GAD-7 через неделю", "Тестовый врач")

    def tearDown(self):
        db.DB_PATH = self.original_path
        self.temp_dir.cleanup()

    @staticmethod
    def pdf_text(content: bytes) -> str:
        return "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(content)).pages)

    def test_catalogue_contains_generated_psychiatric_reports(self):
        items = list_documents(1)
        self.assertEqual(2, len(items))
        self.assertEqual({"visit_report", "monitoring_report"}, {item["category"] for item in items})
        self.assertTrue(all(item["available"] for item in items))
        self.assertTrue(all(item["generated"] for item in items))
        self.assertTrue(all(item["mime_type"] == "application/pdf" for item in items))

    def test_unknown_patient_or_document_is_not_resolved(self):
        self.assertEqual([], list_documents(999))
        self.assertIsNone(get_document(1, "../../secret"))

    def test_reports_are_generated_from_specific_patient_record(self):
        visit = self.pdf_text(generate_pdf(1, "psychiatric-visit-report"))
        monitoring = self.pdf_text(generate_pdf(1, "monitoring-results-report"))
        self.assertIn("Анастасия Александрова", visit)
        self.assertIn("Тревога и нарушения сна", visit)
        self.assertIn("рабочая гипотеза врача", visit)
        self.assertIn("GAD7", monitoring)
        self.assertIn("Трудно заснуть", monitoring)
        self.assertNotIn("Консультация терапевта", visit)
        self.assertNotIn("Клинический анализ крови", monitoring)

    def test_different_patient_gets_a_different_report(self):
        second = self.pdf_text(generate_pdf(2, "psychiatric-visit-report"))
        self.assertIn("Мария Соколова", second)
        self.assertNotIn("Анастасия Александрова", second)

    def test_patient_can_list_and_generate_own_pdf(self):
        with TestClient(app) as client:
            listing = client.get("/api/patients/1/documents", headers=PATIENT)
            self.assertEqual(200, listing.status_code)
            document_id = listing.json()["documents"][0]["id"]
            response = client.get(f"/api/patients/1/documents/{document_id}/file", headers=PATIENT)
        self.assertEqual(200, response.status_code)
        self.assertEqual("application/pdf", response.headers["content-type"])
        self.assertEqual("no-store", response.headers["cache-control"])
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_access_is_limited_to_own_patient_or_doctor(self):
        with TestClient(app) as client:
            self.assertEqual(401, client.get("/api/patients/1/documents").status_code)
            self.assertEqual(403, client.get("/api/patients/2/documents", headers=PATIENT).status_code)
            self.assertEqual(200, client.get("/api/patients/2/documents", headers=DOCTOR).status_code)

    def test_unknown_file_returns_404(self):
        with TestClient(app) as client:
            response = client.get("/api/patients/1/documents/not-found/file", headers=PATIENT)
        self.assertEqual(404, response.status_code)


if __name__ == "__main__":
    unittest.main()
