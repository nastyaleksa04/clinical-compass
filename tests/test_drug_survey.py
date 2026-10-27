import os

os.environ.setdefault("CLINICAL_COMPASS_DEMO_HEADERS", "1")

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import db
from app import drug_survey
from app.main import app

DOCTOR = {"X-Demo-Role": "doctor"}
PATIENT = {"X-Demo-Role": "patient"}


def survey(scores=None, context=None, skip=(), red=(), impact="none", followups=None, note="", consent=False):
    """Полностью заполненный опросник: всё «Нет», кроме scores; context — (связь, начало, комментарий) по разделам."""
    scores, context = scores or {}, context or {}
    config = drug_survey.config()
    sections = []
    for section in config["sections"]:
        if section["id"] in skip:
            sections.append({"section": section["id"], "skipped": True})
            continue
        answers = {item["id"]: scores.get(item["id"], 0) for item in section["items"]}
        attribution, onset, text = context.get(section["id"], ("unknown", "after_start", "") if any(answers.values()) else (None, None, ""))
        sections.append({"section": section["id"], "answers": answers, "attribution": attribution, "onset": onset, "note": text})
    return {
        "sections": sections,
        "red_flags": {flag["id"]: flag["id"] in red for flag in config["red_flags"]},
        "impact": impact,
        "followups": {"q65": False, "q66": False, "q67": False, **(followups or {})},
        "note": note,
        "share_consent": consent,
    }


class DrugSurveyConfigTests(unittest.TestCase):
    def test_questionnaire_matches_paper_version(self):
        config = drug_survey.config()
        numbers = [item["n"] for section in config["sections"] for item in section["items"]]
        numbers += [flag["n"] for flag in config["red_flags"]] + [item["n"] for item in config["followups"]]
        self.assertEqual(list(range(1, 57)), numbers[:56])
        self.assertEqual(list(range(57, 64)), numbers[56:63])
        self.assertEqual([65, 66, 67], numbers[63:])
        self.assertEqual(["А", "Б", "В", "Г", "Д", "Е", "Ж", "З", "И"], [section["letter"] for section in config["sections"]])
        self.assertEqual(["G"], [section["id"] for section in config["sections"] if section.get("sensitive")])


class DrugSurveyApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(db, "DB_PATH", Path(self.temp_dir.name) / "drug.db")
        self.db_patch.start()
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        self.db_patch.stop()
        self.temp_dir.cleanup()

    def submit(self, payload, headers=PATIENT):
        return self.client.post("/api/patients/1/drug-reports", headers=headers, json=payload)

    def test_colored_dreams_with_section_comment(self):
        payload = survey({"q1": 2, "q2": 1}, {"A": ("unknown", "after_start", "Сны стали цветными")},
                         note="Хочется лечь пораньше, чтобы увидеть сон")
        response = self.submit(payload)
        self.assertEqual(201, response.status_code)
        data = response.json()
        section = data["sections_marked"][0]
        self.assertEqual("А. Сон и сновидения", section["title"])
        self.assertEqual([(1, "Заметно"), (2, "Немного")], [(item["n"], item["label"]) for item in section["items"]])
        self.assertEqual("Сны стали цветными", section["note"])
        self.assertEqual(2, data["marked_count"])
        self.assertEqual([], data["signals"])

    def test_free_text_allowed_without_marked_items(self):
        payload = survey(context={"E": (None, None, "Иногда покалывает в пальцах")})
        data = self.submit(payload).json()
        self.assertEqual("Иногда покалывает в пальцах", data["sections_marked"][0]["note"])

    def test_intimate_section_can_be_skipped_others_cannot(self):
        self.assertEqual(201, self.submit(survey(skip=("G",))).status_code)
        self.assertEqual(422, self.submit(survey(skip=("A",))).status_code)

    def test_every_item_must_be_answered(self):
        payload = survey()
        del payload["sections"][0]["answers"]["q8"]
        self.assertEqual(422, self.submit(payload).status_code)
        payload = survey()
        payload["sections"][0]["answers"]["q1"] = 4
        self.assertEqual(422, self.submit(payload).status_code)

    def test_marked_section_needs_attribution_and_onset(self):
        payload = survey({"q27": 1}, {"E": (None, None, "")})
        response = self.submit(payload)
        self.assertEqual(422, response.status_code)
        self.assertIn("связано ли это с лечением", response.json()["detail"])

    def test_all_red_flags_must_be_answered(self):
        payload = survey()
        del payload["red_flags"]["q60"]
        self.assertEqual(422, self.submit(payload).status_code)

    def test_red_flag_raises_mandatory_signal(self):
        data = self.submit(survey(red=("q57",))).json()
        self.assertIn("mandatory", data["signals"])
        signal = next(item for item in db.get_routing_signals(1, include_unconfirmed=True) if item["reason_code"] == "drug_red_flag")
        self.assertIn("мысли о смерти", signal["reason_text"])

    def test_strong_item_or_thinking_to_stop_raise_recommended_signal(self):
        self.assertEqual(["recommended"], self.submit(survey({"q41": 3}, skip=())).json()["signals"])
        self.assertEqual(["recommended"], self.submit(survey(followups={"q66": True})).json()["signals"])
        self.assertEqual(["recommended", "recommended"], self.submit(survey(impact="strong", followups={"q65": True})).json()["signals"])

    def test_doctor_only_insights_and_patient_cannot_submit_for_others(self):
        self.submit(survey({"q1": 2}, consent=True))
        self.submit(survey({"q1": 1, "q41": 3}, {"A": ("yes", "after_start", ""), "G": ("yes", "after_start", "")}))
        insights = self.client.get("/api/drug-insights", headers=DOCTOR).json()
        self.assertEqual(2, insights["reports"])
        self.assertEqual(1, insights["consented"])
        self.assertEqual({"n": 1, "text": "Сны стали ярче, красочнее, «цветными»", "section": "А", "count": 2, "strong": 1}, insights["top_items"][0])
        sleep = next(section for section in insights["sections"] if section["id"] == "A")
        self.assertEqual((2, 2, 1), (sleep["answered"], sleep["with_symptoms"], sleep["attributed"]))
        self.assertEqual(403, self.client.get("/api/drug-insights", headers=PATIENT).status_code)
        self.assertEqual(403, self.client.post("/api/patients/2/drug-reports", headers=PATIENT, json=survey()).status_code)
        self.assertEqual(403, self.submit(survey(), headers=DOCTOR).status_code)

    def test_report_appears_in_doctor_list_and_timeline(self):
        self.submit(survey({"q5": 1}))
        reports = self.client.get("/api/patients/1/drug-reports", headers=DOCTOR).json()
        self.assertEqual(1, reports[0]["marked_count"])
        event = next(item for item in db.get_timeline(1, include_clinical=True) if item["type"] == "drug_report")
        self.assertEqual("Отмечено пунктов: 1 в 1 разделах", event["summary"])


if __name__ == "__main__":
    unittest.main()
