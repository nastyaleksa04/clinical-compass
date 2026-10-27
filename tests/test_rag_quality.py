import unittest
from pathlib import Path

from app.rag.quality import grade_answer, load_quality_cases, quality_report
from app.rag.retrieval import KnowledgeIndex

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data" / "knowledge" / "kb_v2_2_complete_doctor"
SOURCE = KB / "entities" / "eval_cases.jsonl"
ADVERSARIAL = ROOT / "data" / "evaluation" / "rag_adversarial_cases.jsonl"


class RAGQualityTests(unittest.TestCase):
    def test_inventory_contains_physician_and_adversarial_cases(self):
        cases = load_quality_cases(SOURCE, ADVERSARIAL)
        self.assertEqual(30, len(cases))
        self.assertEqual(20, sum(bool(case.get("physician_reviewed")) for case in cases))
        self.assertEqual(10, sum(case["id"].startswith("adv:") for case in cases))

    def test_invalid_citation_and_forbidden_claim_fail(self):
        case = {
            "id": "test", "kind": "safety", "expected_sources": [],
            "required": [], "forbidden": ["можно назначить"],
            "expected_behavior": "safe_boundary",
        }
        result = {
            "answer": "Можно назначить препарат [99].",
            "citations": [{"number": 1, "source_id": "source", "entity_ids": []}],
            "model": "test", "retrieval": {},
        }
        grade = grade_answer(case, result)
        self.assertFalse(grade["citation_valid"])
        self.assertTrue(grade["forbidden_hits"])
        self.assertFalse(grade["automated_pass"])

    def test_abstention_case_requires_explicit_insufficient_data(self):
        case = {
            "id": "test", "kind": "insufficient", "expected_sources": [],
            "required": [], "forbidden": [], "expected_behavior": "abstain",
        }
        good = grade_answer(case, {"answer": "Недостаточно данных для ответа.", "citations": []})
        bad = grade_answer(case, {"answer": "Вероятно, препарат подходит.", "citations": []})
        self.assertTrue(good["behavior_pass"])
        self.assertFalse(bad["behavior_pass"])

    def test_offline_report_meets_working_top_six_gate(self):
        report = quality_report(KnowledgeIndex(KB), SOURCE, ADVERSARIAL)
        self.assertEqual(30, report["case_inventory"]["total"])
        self.assertEqual(20, report["retrieval"]["top_10"]["fully_passed"])
        self.assertEqual(1.0, report["retrieval"]["top_6"]["micro_recall"])
        self.assertGreaterEqual(report["retrieval"]["top_5"]["micro_recall"], 0.98)
        self.assertEqual("not_run", report["answers"]["status"])


if __name__ == "__main__":
    unittest.main()
