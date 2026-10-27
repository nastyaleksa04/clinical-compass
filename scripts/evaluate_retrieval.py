#!/usr/bin/env python3
"""Run the local doctor retrieval evaluation suite."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.rag.evaluation import evaluate, markdown_report
from app.rag.retrieval import KnowledgeIndex

DEFAULT_KB = ROOT / "data" / "knowledge" / "kb_v2_2_complete_doctor"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kb", type=Path, default=DEFAULT_KB)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--json-output", type=Path, default=ROOT / "docs" / "retrieval_eval_v2_2.json")
    parser.add_argument("--markdown-output", type=Path, default=ROOT / "docs" / "RETRIEVAL_EVAL_V2_2.md")
    args = parser.parse_args()
    report = evaluate(KnowledgeIndex(args.kb), args.kb / "entities/eval_cases.jsonl", args.limit)
    args.json_output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.markdown_output.write_text(markdown_report(report), encoding="utf-8")
    print(markdown_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
