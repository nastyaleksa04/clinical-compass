#!/usr/bin/env python3
"""Evaluate doctor RAG retrieval and optionally live OpenRouter answers."""

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.rag.assistant import OpenRouterClient, answer
from app.rag.quality import (
    grade_answer,
    load_quality_cases,
    markdown_report,
    quality_gate,
    quality_report,
    refresh_text_grade,
    summarize_answer_rows,
)
from app.rag.retrieval import KnowledgeIndex

KB = ROOT / "data" / "knowledge" / "kb_v2_2_complete_doctor"
SOURCE_CASES = KB / "entities" / "eval_cases.jsonl"
ADVERSARIAL_CASES = ROOT / "data" / "evaluation" / "rag_adversarial_cases.jsonl"

class EvaluationClient:
    def __init__(self):
        self.client = OpenRouterClient()

    def complete(self, messages):
        return self.client.complete(messages, max_tokens=700)

def read_cache(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {row["case_id"]: row for row in rows}

def append_cache(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, ensure_ascii=False) + "\n")

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Call OpenRouter for synthetic cases.")
    parser.add_argument("--limit", type=int, default=6, choices=range(1, 11))
    parser.add_argument("--workers", type=int, default=3, choices=range(1, 5))
    parser.add_argument("--cache", type=Path, default=ROOT / "docs" / "rag_quality_live_cache.jsonl")
    parser.add_argument("--json-output", type=Path, default=ROOT / "docs" / "rag_quality_report.json")
    parser.add_argument("--markdown-output", type=Path, default=ROOT / "docs" / "RAG_QUALITY_REPORT.md")
    args = parser.parse_args()

    index = KnowledgeIndex(KB)
    report = quality_report(index, SOURCE_CASES, ADVERSARIAL_CASES)
    if args.live:
        cases = load_quality_cases(SOURCE_CASES, ADVERSARIAL_CASES)
        cached = read_cache(args.cache)
        by_id = {case["id"]: case for case in cases}
        cached = {
            case_id: refresh_text_grade(by_id[case_id], row)
            for case_id, row in cached.items()
            if case_id in by_id
        }
        if cached:
            args.cache.write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in cached.values()),
                encoding="utf-8",
            )
        pending = [case for case in cases if case["id"] not in cached]
        for number, case in enumerate(cases, 1):
            if case["id"] in cached:
                print(f"[{number}/{len(cases)}] {case['id']} — cached", flush=True)

        def evaluate_case(case):
            try:
                result = answer(case["question"], args.limit, client=EvaluationClient(), index=index)
                return grade_answer(case, result)
            except Exception as error:
                return {
                    "case_id": case["id"], "kind": case.get("kind"),
                    "error": str(error), "automated_pass": False,
                    "requires_physician_review": True,
                }

        if pending:
            print(f"Running {len(pending)} remaining cases with {args.workers} workers", flush=True)
            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                futures = {pool.submit(evaluate_case, case): case for case in pending}
                completed_count = len(cached)
                for future in as_completed(futures):
                    case = futures[future]
                    row = future.result()
                    append_cache(args.cache, row)
                    cached[case["id"]] = row
                    completed_count += 1
                    status = "error" if "error" in row else "saved"
                    print(f"[{completed_count}/{len(cases)}] {case['id']} — {status}", flush=True)

        ordered = [cached[case["id"]] for case in cases if case["id"] in cached]
        report["answers"] = summarize_answer_rows(ordered, len(cases))

    report["quality_gate"] = quality_gate(report)

    args.json_output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    text = markdown_report(report)
    args.markdown_output.write_text(text, encoding="utf-8")
    print(text)
    answers = report["answers"]
    return 0 if answers.get("status") == "not_run" or report["quality_gate"]["passed"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
