import os

os.environ.setdefault("CLINICAL_COMPASS_DEMO_HEADERS", "1")

import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import db
from app import history_import
from app.main import app
from scripts.evaluate_history_import import evaluate

DOCTOR = {"X-Demo-Role": "doctor"}
PATIENT = {"X-Demo-Role": "patient"}
DATASETS = Path(__file__).resolve().parents[1] / "data" / "evaluation"


class HistoryParserTests(unittest.TestCase):
    def test_sections_found_in_any_order_and_style(self):
        result = history_import.parse("ДИАГНОЗ\nF41.1\n\nЖАЛОБЫ\nтревога, бессонница\n\nAn. morbi: в течение 3 месяцев")
        self.assertIn("тревога", result["fields"]["complaints"])
        self.assertEqual("в течение 3 месяцев", result["fields"]["symptom_duration"])
        self.assertEqual(["F41.1"], result["icd_codes"])

    def test_negation_is_respected(self):
        denied = history_import.parse("Суицидальные мысли отрицает. Галлюцинаций не выявлено, бреда нет.")
        self.assertFalse(denied["fields"]["self_harm_concern"])
        self.assertFalse(denied["fields"]["psychosis_signs"])
        present = history_import.parse("Говорит, что не хочет жить.")
        self.assertTrue(present["fields"]["self_harm_concern"])
        self.assertTrue(any("суицид" in warning for warning in present["warnings"]))

    def test_drugs_map_to_aviandr_checklist_factors(self):
        result = history_import.parse("Принимаемые препараты: пароксетин 20 мг утром. Моклобемид отменён 5 дней назад.")
        factors = result["therapy_factors"]
        self.assertTrue(factors["serotonergic_drugs"])
        self.assertTrue(factors["cyp2d6_inhibitors"])
        self.assertTrue(factors["maoi_recent"])
        self.assertEqual("20 мг", next(item for item in result["medications"] if item["name"] == "пароксетин")["dose"])

    def test_out_of_range_scale_is_skipped_with_warning(self):
        result = history_import.parse("PHQ-9: 45 баллов")
        self.assertNotIn("phq9", result["scales"])
        self.assertTrue(result["warnings"])

    def test_empty_and_scanned_inputs_rejected(self):
        with self.assertRaises(ValueError):
            history_import.parse("   ")
        with self.assertRaises(ValueError):
            history_import.extract_text(b"%PDF-1.4 broken", "scan.pdf")

    def test_cp1251_text_is_decoded(self):
        text = history_import.extract_text("Жалобы: тревога".encode("cp1251"), "old.txt")
        self.assertEqual("Жалобы: тревога", text)

    def test_evaluation_sets_quality(self):
        for name in ("histories", "histories_holdout"):
            report = evaluate(DATASETS / name)
            self.assertGreaterEqual(report["scalar_accuracy"], 0.9, name)
            self.assertGreaterEqual(report["set_f1"], 0.9, name)
            self.assertGreaterEqual(report["text_accuracy"], 0.85, name)


class HistoryImportApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(db, "DB_PATH", Path(self.temp_dir.name) / "history.db")
        self.db_patch.start()
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        self.db_patch.stop()
        self.temp_dir.cleanup()

    def test_pdf_upload_is_parsed_without_saving(self):
        pdf = (DATASETS / "histories" / "08_pdf.pdf").read_bytes()
        before = self.client.get("/api/patients/1", headers=DOCTOR).json()["clinical_profile"]
        response = self.client.post("/api/patients/1/history-import", headers=DOCTOR,
                                    json={"filename": "08_pdf.pdf", "content_base64": base64.b64encode(pdf).decode()})
        self.assertEqual(200, response.status_code)
        self.assertEqual({"gad7": 18, "phq9": 12}, response.json()["scales"])
        after = self.client.get("/api/patients/1", headers=DOCTOR).json()["clinical_profile"]
        self.assertEqual(before, after)

    def test_only_doctor_can_import(self):
        response = self.client.post("/api/patients/1/history-import", headers=PATIENT, json={"text": "Жалобы: тревога"})
        self.assertEqual(403, response.status_code)

    def test_bad_base64_returns_422(self):
        response = self.client.post("/api/patients/1/history-import", headers=DOCTOR, json={"content_base64": "%%%"})
        self.assertEqual(422, response.status_code)


if __name__ == "__main__":
    unittest.main()
