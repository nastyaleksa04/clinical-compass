import json
import tempfile
import unittest
from pathlib import Path

from app.rag.audit import audit_bundle
from app.rag.normalize import normalize_bundle
from app.rag.rules import evaluate_trigger, validate_rule_tests


class KnowledgeNormalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path(__file__).resolve().parents[1] / "data" / "knowledge" / "kb_v2.zip"

    def test_normalized_bundle_contains_only_meaningful_doctor_chunks(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "kb"
            manifest = normalize_bundle(self.source, output)
            chunks = [
                json.loads(line)
                for line in (output / "entities/chunks.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(manifest["release"], "kb_v2.1-doctor-safe")
            self.assertTrue(chunks)
            self.assertTrue(all(chunk["audience"] == ["doctor"] for chunk in chunks))
            self.assertTrue(all(chunk["review"]["status"] == "source_checked" for chunk in chunks))
            self.assertTrue(all(chunk["text"] != "PDF" and len(chunk["text"]) >= 80 for chunk in chunks))

    def test_unchecked_and_unsupported_records_are_quarantined(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "kb"
            manifest = normalize_bundle(self.source, output)
            exclusions = [
                json.loads(line)
                for line in (output / "quarantine/exclusions.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            reasons = {item["reason"] for item in exclusions}
            self.assertGreater(manifest["quarantine_count"], 0)
            self.assertIn("not_clinically_checked", reasons)
            self.assertIn("missing_verified_label", reasons)
            self.assertIn("trigger_requires_manual_formalization", reasons)

    def test_generated_safety_tests_execute_successfully(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "kb"
            normalize_bundle(self.source, output)
            rules = [
                json.loads(line)
                for line in (output / "entities/safety_rules.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertTrue(rules)
            self.assertEqual([], [failure for rule in rules for failure in validate_rule_tests(rule)])
            self.assertTrue(all(rule["positive_tests"] and rule["negative_tests"] for rule in rules))

    def test_normalized_bundle_passes_doctor_search_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "kb"
            normalize_bundle(self.source, output)
            report = audit_bundle(output)
            self.assertTrue(report["readiness"]["doctor_search_experimental"])
            self.assertFalse(report["readiness"]["patient_rag"])
            self.assertEqual(report["summary"]["errors"], 0)
            codes = {issue["code"] for issue in report["issues"]}
            self.assertNotIn("tiny_chunk", codes)
            self.assertNotIn("missing_audience", codes)
            self.assertNotIn("untested_safety_rules", codes)
            self.assertNotIn("missing_medication_label", codes)

    def test_trigger_evaluator_supports_or_groups(self):
        trigger = {
            "logic": "or",
            "groups": [
                [{"field": "age", "op": "gte", "value": 65}],
                [{"field": "risk", "op": "eq", "value": "high"}],
            ],
        }
        self.assertTrue(evaluate_trigger(trigger, {"age": 20, "risk": "high"}))
        self.assertFalse(evaluate_trigger(trigger, {"age": 20, "risk": "low"}))


if __name__ == "__main__":
    unittest.main()
