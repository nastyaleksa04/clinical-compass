"""Evaluation helpers for citation retrieval against KB eval cases."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.rag.retrieval import KnowledgeIndex


def _expected_items(case: dict[str, Any]) -> list[str]:
    raw = case.get("Ожидаемые источники и записи") or ""
    return [line.strip() for line in raw.splitlines() if line.strip()]


def _matches(expected: str, result: dict[str, Any]) -> bool:
    expected_folded = expected.casefold()
    source_id = result["source"]["source_id"].casefold()
    entity_ids = [value.casefold() for value in result.get("entity_ids", [])]
    if expected_folded == source_id or expected_folded.startswith(source_id + "_") or expected_folded.startswith(source_id + " "):
        return True
    if expected_folded in entity_ids:
        return True
    # Scale IDs in the source eval set omit the locale suffix used by records.
    if expected_folded.startswith("scale:") and any(
        value == expected_folded + "_ru" for value in entity_ids
    ):
        return True
    if "safety rule" in expected_folded and any(
        value.startswith(("safety:", "alert:", "route:")) for value in entity_ids
    ):
        return True
    return False


def evaluate(index: KnowledgeIndex, cases_path: str | Path, limit: int = 10) -> dict[str, Any]:
    cases = [
        json.loads(line)
        for line in Path(cases_path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    results = []
    total_expected = 0
    total_matched = 0
    for case in cases:
        query = case.get("Входные данные (вымышленный случай)") or ""
        retrieved = index.search(query, limit)["results"]
        expected = _expected_items(case)
        matches = {
            item: next((result["rank"] for result in retrieved if _matches(item, result)), None)
            for item in expected
        }
        matched = sum(rank is not None for rank in matches.values())
        total_expected += len(expected)
        total_matched += matched
        results.append({
            "case_id": case.get("id") or case.get("ID"),
            "task_type": case.get("Тип задачи"),
            "query": query,
            "expected": expected,
            "matches": matches,
            "matched": matched,
            "expected_count": len(expected),
            "recall": round(matched / len(expected), 4) if expected else 1.0,
            "top_results": [
                {
                    "rank": result["rank"],
                    "chunk_id": result["chunk_id"],
                    "source_id": result["source"]["source_id"],
                    "entity_ids": result["entity_ids"],
                }
                for result in retrieved
            ],
        })
    fully_passed = sum(item["matched"] == item["expected_count"] for item in results)
    return {
        "limit": limit,
        "cases": len(results),
        "fully_passed": fully_passed,
        "case_pass_rate": round(fully_passed / len(results), 4) if results else 0.0,
        "expected_items": total_expected,
        "matched_items": total_matched,
        "micro_recall": round(total_matched / total_expected, 4) if total_expected else 0.0,
        "results": results,
    }


def markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Retrieval evaluation: KB v2.2 complete doctor corpus",
        "",
        f"- Top K: {report['limit']}",
        f"- Cases: {report['cases']}",
        f"- Fully passed: {report['fully_passed']}",
        f"- Case pass rate: {report['case_pass_rate']:.1%}",
        f"- Expected references found: {report['matched_items']} / {report['expected_items']}",
        f"- Micro recall: {report['micro_recall']:.1%}",
        "",
        "## Cases",
        "",
    ]
    for case in report["results"]:
        missing = [item for item, rank in case["matches"].items() if rank is None]
        lines.append(
            f"- **{case['case_id']}** — recall {case['recall']:.1%}; "
            f"missing: {', '.join(missing) if missing else 'none'}"
        )
    lines += [
        "",
        "This report measures retrieval only. It does not validate clinical correctness or LLM answer quality.",
        "",
    ]
    return "\n".join(lines)
