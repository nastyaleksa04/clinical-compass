import json
import tempfile
import unittest
from pathlib import Path

from app.rag.audit import JSONL_FILES, audit_bundle


class KnowledgeBundleAuditTests(unittest.TestCase):
    def make_bundle(self, *, audience=True, approved=True, bad_source=False):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        for relative in JSONL_FILES:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("", encoding="utf-8")

        source = {
            "source_id": "source:1",
            "title": "Test source",
            "url": "https://example.test/source",
            "status": "active",
            "license": "test",
        }
        (root / "sources.jsonl").write_text(json.dumps(source) + "\n", encoding="utf-8")
        chunk = {
            "chunk_id": "chunk:1",
            "source_id": "source:missing" if bad_source else "source:1",
            "entity_ids": [],
            "text": "A sufficiently long verified test fragment used only by automated tests. " * 2,
            "char_len": 140,
            "review": {"status": "patient_approved" if approved and audience else ("approved" if approved else "draft")},
        }
        chunk["char_len"] = len(chunk["text"])
        if audience:
            chunk["audience"] = ["doctor", "patient"]
        (root / "entities/chunks.jsonl").write_text(
            json.dumps(chunk, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        return temp, root

    def test_approved_scoped_bundle_passes_readiness_gate(self):
        temp, root = self.make_bundle()
        try:
            report = audit_bundle(root)
            self.assertTrue(report["readiness"]["doctor_search_experimental"])
            self.assertTrue(report["readiness"]["patient_rag"])
            self.assertEqual(report["summary"]["errors"], 0)
            self.assertEqual(report["summary"]["blockers"], 0)
        finally:
            temp.cleanup()

    def test_draft_and_unscoped_chunk_is_doctor_only_experimental(self):
        temp, root = self.make_bundle(audience=False, approved=False)
        try:
            report = audit_bundle(root)
            codes = {issue["code"] for issue in report["issues"]}
            self.assertTrue(report["readiness"]["doctor_search_experimental"])
            self.assertFalse(report["readiness"]["patient_rag"])
            self.assertIn("unapproved_chunks", codes)
            self.assertIn("missing_audience", codes)
        finally:
            temp.cleanup()

    def test_unknown_source_blocks_even_experimental_search(self):
        temp, root = self.make_bundle(bad_source=True)
        try:
            report = audit_bundle(root)
            self.assertFalse(report["readiness"]["doctor_search_experimental"])
            self.assertIn("unknown_chunk_source", {issue["code"] for issue in report["issues"]})
        finally:
            temp.cleanup()

    def test_committed_pilot_bundle_is_recognized_as_draft(self):
        bundle = Path(__file__).resolve().parents[1] / "data" / "knowledge" / "kb_v2.zip"
        report = audit_bundle(bundle)
        self.assertEqual(report["counts"]["entities/chunks.jsonl"], 320)
        self.assertTrue(report["readiness"]["doctor_search_experimental"])
        self.assertFalse(report["readiness"]["patient_rag"])
        self.assertFalse(report["readiness"]["clinical_automation"])


if __name__ == "__main__":
    unittest.main()
