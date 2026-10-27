import json
import unittest
from pathlib import Path

from app.rag.evaluation import evaluate
from app.rag.retrieval import KnowledgeIndex


ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data" / "knowledge" / "kb_v2_2_complete_doctor"


def read_jsonl(relative: str) -> list[dict]:
    return [
        json.loads(line)
        for line in (KB / relative).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class CompleteKnowledgeBaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((KB / "manifest.json").read_text(encoding="utf-8"))
        cls.sources = read_jsonl("sources.jsonl")
        cls.chunks = read_jsonl("entities/chunks.jsonl")

    def test_manifest_counts_match_every_file_and_all_citations_resolve(self):
        for relative, expected in self.manifest["counts"].items():
            self.assertEqual(len(read_jsonl(relative)), expected, relative)
        source_ids = {row["source_id"] for row in self.sources}
        self.assertTrue(all(chunk["source_id"] in source_ids for chunk in self.chunks))
        self.assertTrue(all(chunk["audience"] == ["doctor"] for chunk in self.chunks))
        self.assertTrue(all(chunk["retrieval_eligible"] for chunk in self.chunks))

    def test_every_clinical_entity_has_a_retrieval_chunk(self):
        expected_ids = set()
        for relative in (
            "entities/conditions.jsonl",
            "entities/medications.jsonl",
            "entities/safety_rules.jsonl",
        ):
            expected_ids.update(row.get("id") or row.get("ID") for row in read_jsonl(relative))
        expected_ids.update(
            "card:" + (row.get("id") or row["Препарат (ID)"]).removeprefix("med:")
            for row in read_jsonl("entities/medication_cards.jsonl")
        )
        expected_ids.update(
            row["Шкала (ID)"] for row in read_jsonl("entities/scales.jsonl")
        )
        indexed_ids = {
            entity_id
            for chunk in self.chunks
            for entity_id in chunk.get("entity_ids", [])
        }
        self.assertEqual(set(), expected_ids - indexed_ids)

    def test_incomplete_records_remain_retrieval_only(self):
        exclusions = read_jsonl("quarantine/automation_exclusions.jsonl")
        self.assertEqual(self.manifest["automation_exclusion_count"], len(exclusions))
        self.assertEqual(
            {"missing_verified_label", "trigger_requires_manual_formalization"},
            {row["reason"] for row in exclusions},
        )
        excluded_ids = {row["entity_id"] for row in exclusions}
        excluded_chunks = [
            chunk
            for chunk in self.chunks
            if excluded_ids.intersection(chunk.get("entity_ids", []))
        ]
        self.assertTrue(excluded_chunks)
        self.assertTrue(all(not chunk["automation_eligible"] for chunk in excluded_chunks))

    def test_all_source_eval_cases_retrieve_every_expected_reference(self):
        report = evaluate(
            KnowledgeIndex(KB),
            KB / "entities/eval_cases.jsonl",
            limit=10,
        )
        self.assertEqual(20, report["fully_passed"])
        self.assertEqual(50, report["matched_items"])
        self.assertEqual(1.0, report["case_pass_rate"])
        self.assertEqual(1.0, report["micro_recall"])


if __name__ == "__main__":
    unittest.main()
