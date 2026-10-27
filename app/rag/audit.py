"""Validation and readiness audit for Clinical Compass knowledge bundles."""

from __future__ import annotations

import json
import zipfile
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

JSONL_FILES = (
    "sources.jsonl",
    "entities/chunks.jsonl",
    "entities/conditions.jsonl",
    "entities/eval_cases.jsonl",
    "entities/medication_cards.jsonl",
    "entities/medications.jsonl",
    "entities/patient_model.jsonl",
    "entities/safety_rules.jsonl",
    "entities/scales.jsonl",
)
MIN_CHUNK_LENGTH = 80
DOCTOR_REVIEW_STATUSES = {"source_checked", "clinically_reviewed", "approved", "patient_approved", "verified", "published"}
PATIENT_REVIEW_STATUSES = {"patient_approved", "published"}


@dataclass(frozen=True)
class AuditIssue:
    severity: str
    code: str
    message: str
    count: int = 1
    samples: tuple[str, ...] = ()


class KnowledgeBundle:
    def __init__(self, source: str | Path):
        self.source = Path(source)
        self._zip: zipfile.ZipFile | None = None
        self.prefix = ""

    def __enter__(self) -> "KnowledgeBundle":
        if self.source.is_file():
            self._zip = zipfile.ZipFile(self.source)
            self.prefix = "kb_v2/" if any(n.startswith("kb_v2/") for n in self._zip.namelist()) else ""
        elif not self.source.is_dir():
            raise FileNotFoundError(f"Knowledge bundle not found: {self.source}")
        return self

    def __exit__(self, *_: object) -> None:
        if self._zip:
            self._zip.close()

    def exists(self, relative: str) -> bool:
        if self._zip:
            return self.prefix + relative in self._zip.namelist()
        return (self.source / relative).is_file()

    def read_text(self, relative: str) -> str:
        if self._zip:
            return self._zip.read(self.prefix + relative).decode("utf-8-sig")
        return (self.source / relative).read_text(encoding="utf-8-sig")

    def raw_exists(self, relative: str) -> bool:
        normalized = relative.replace("\\", "/").lstrip("/")
        if self._zip:
            return self.prefix + normalized in self._zip.namelist()
        return (self.source / normalized).is_file()


def _record_id(relative: str, record: dict[str, Any]) -> str | None:
    if relative == "sources.jsonl":
        return record.get("source_id")
    if relative == "entities/chunks.jsonl":
        return record.get("chunk_id")
    return record.get("id") or record.get("ID")


def _is_checked(record: dict[str, Any]) -> bool:
    return str(record.get("Проверено (да/нет)", "")).strip().casefold() in {"да", "yes", "true"}


def _sample(values: Iterable[Any], limit: int = 5) -> tuple[str, ...]:
    return tuple(str(value) for value in list(values)[:limit])


def audit_bundle(source: str | Path) -> dict[str, Any]:
    issues: list[AuditIssue] = []
    records: dict[str, list[dict[str, Any]]] = {}
    invalid_json = 0

    with KnowledgeBundle(source) as bundle:
        for relative in JSONL_FILES:
            if not bundle.exists(relative):
                issues.append(AuditIssue("error", "missing_file", f"Required file is missing: {relative}"))
                records[relative] = []
                continue
            rows: list[dict[str, Any]] = []
            for line_number, line in enumerate(bundle.read_text(relative).splitlines(), 1):
                if not line.strip():
                    continue
                try:
                    value = json.loads(line)
                    if not isinstance(value, dict):
                        raise ValueError("record is not a JSON object")
                    rows.append(value)
                except (json.JSONDecodeError, ValueError) as exc:
                    invalid_json += 1
                    issues.append(AuditIssue("error", "invalid_json", f"{relative}:{line_number}: {exc}"))
            records[relative] = rows
            ids = [_record_id(relative, row) for row in rows]
            missing_ids = sum(value is None or str(value).strip() == "" for value in ids)
            if missing_ids:
                issues.append(AuditIssue("error", "missing_id", f"Records without an ID in {relative}", missing_ids))
            duplicates = sorted(value for value, count in Counter(ids).items() if value and count > 1)
            if duplicates:
                issues.append(AuditIssue("error", "duplicate_id", f"Duplicate IDs in {relative}", len(duplicates), _sample(duplicates)))

        sources = records["sources.jsonl"]
        chunks = records["entities/chunks.jsonl"]
        source_ids = {row.get("source_id") for row in sources if row.get("source_id")}
        unknown_sources = sorted({
            row.get("source_id") for row in chunks
            if row.get("source_id") and row.get("source_id") not in source_ids
        })
        if unknown_sources:
            issues.append(AuditIssue("error", "unknown_chunk_source", "Chunks reference source IDs absent from sources.jsonl", len(unknown_sources), _sample(unknown_sources)))

        empty_chunks = [row.get("chunk_id") for row in chunks if not str(row.get("text", "")).strip()]
        if empty_chunks:
            issues.append(AuditIssue("error", "empty_chunk", "Chunks contain no text", len(empty_chunks), _sample(empty_chunks)))

        length_mismatch = [
            row.get("chunk_id") for row in chunks
            if isinstance(row.get("char_len"), int) and row["char_len"] != len(row.get("text", ""))
        ]
        if length_mismatch:
            issues.append(AuditIssue("warning", "chunk_length_mismatch", "Stored char_len differs from actual text length", len(length_mismatch), _sample(length_mismatch)))

        tiny_chunks = [
            row.get("chunk_id") for row in chunks
            if 0 < len(str(row.get("text", "")).strip()) < MIN_CHUNK_LENGTH
        ]
        if tiny_chunks:
            issues.append(AuditIssue("warning", "tiny_chunk", f"Chunks shorter than {MIN_CHUNK_LENGTH} characters need merging or exclusion", len(tiny_chunks), _sample(tiny_chunks)))

        draft_chunks = [
            row.get("chunk_id") for row in chunks
            if str((row.get("review") or {}).get("status", "")).casefold() not in DOCTOR_REVIEW_STATUSES
        ]
        if draft_chunks:
            issues.append(AuditIssue("blocker", "unapproved_chunks", "Chunks are not approved for clinical RAG output", len(draft_chunks), _sample(draft_chunks)))

        missing_audience = [row.get("chunk_id") for row in chunks if not row.get("audience")]
        if missing_audience:
            issues.append(AuditIssue("blocker", "missing_audience", "Chunks have no doctor/patient access scope", len(missing_audience), _sample(missing_audience)))

        patient_chunks = [row for row in chunks if "patient" in (row.get("audience") or [])]
        if not patient_chunks:
            issues.append(AuditIssue("blocker", "missing_patient_corpus", "No chunks are approved and scoped for patient retrieval"))
        else:
            unapproved_patient = [
                row.get("chunk_id") for row in patient_chunks
                if str((row.get("review") or {}).get("status", "")).casefold() not in PATIENT_REVIEW_STATUSES
            ]
            if unapproved_patient:
                issues.append(AuditIssue("blocker", "unapproved_patient_chunks", "Patient-scoped chunks lack patient approval", len(unapproved_patient), _sample(unapproved_patient)))

        missing_raw = [
            row.get("source_id") for row in sources
            if row.get("raw_file") and not bundle.raw_exists(str(row["raw_file"]))
        ]
        if missing_raw:
            issues.append(AuditIssue("warning", "missing_raw_source", "Source registry points to raw files absent from the bundle", len(missing_raw), _sample(missing_raw)))

        unknown_license = [
            row.get("source_id") for row in sources
            if not row.get("license") or str(row.get("license")).casefold() == "unknown"
        ]
        if unknown_license:
            issues.append(AuditIssue("warning", "unknown_license", "Source reuse license is missing or unknown", len(unknown_license), _sample(unknown_license)))

        unchecked_groups = {
            "condition facts": records["entities/conditions.jsonl"],
            "medication rows": records["entities/medications.jsonl"],
            "medication cards": records["entities/medication_cards.jsonl"],
            "safety rules": records["entities/safety_rules.jsonl"],
            "scale rows": records["entities/scales.jsonl"],
            "evaluation cases": records["entities/eval_cases.jsonl"],
        }
        for label, rows in unchecked_groups.items():
            unchecked = [(_record_id("", row) or "?") for row in rows if not _is_checked(row)]
            if unchecked:
                severity = "blocker" if label in {"safety rules", "evaluation cases"} else "warning"
                issues.append(AuditIssue(severity, "unchecked_records", f"Unchecked {label}", len(unchecked), _sample(unchecked)))

        rules = records["entities/safety_rules.jsonl"]
        rules_without_tests = [
            _record_id("", row) for row in rules
            if row.get("automation_status") != "retrieval_only" and not row.get("positive_tests") and not row.get("negative_tests")
        ]
        if rules_without_tests:
            issues.append(AuditIssue("blocker", "untested_safety_rules", "Safety rules have neither positive nor negative tests", len(rules_without_tests), _sample(rules_without_tests)))

        meds = records["entities/medications.jsonl"]
        missing_labels = sorted({
            row.get("med_id") for row in meds
            if row.get("label_status") == "missing" and row.get("automation_eligible") is not False and row.get("med_id")
        })
        if missing_labels:
            issues.append(AuditIssue("blocker", "missing_medication_label", "Medication rows have no verified label card", len(missing_labels), _sample(missing_labels)))

    errors = sum(issue.count for issue in issues if issue.severity == "error")
    blockers = sum(issue.count for issue in issues if issue.severity == "blocker")
    warnings = sum(issue.count for issue in issues if issue.severity == "warning")
    doctor_search_ready = invalid_json == 0 and bool(records.get("entities/chunks.jsonl")) and not any(issue.severity == "error" for issue in issues)
    patient_rag_ready = doctor_search_ready and bool(patient_chunks) and not any(issue.severity in {"error", "blocker"} for issue in issues)
    clinical_automation_ready = patient_rag_ready and not any(issue.code == "untested_safety_rules" for issue in issues)
    return {
        "bundle": str(Path(source)),
        "counts": {relative: len(rows) for relative, rows in records.items()},
        "summary": {"issues": len(issues), "errors": errors, "blockers": blockers, "warnings": warnings},
        "readiness": {
            "doctor_search_experimental": doctor_search_ready,
            "patient_rag": patient_rag_ready,
            "clinical_automation": clinical_automation_ready,
        },
        "issues": [asdict(issue) for issue in issues],
    }


def markdown_report(report: dict[str, Any]) -> str:
    readiness = report["readiness"]
    summary = report["summary"]
    lines = [
        "# KB v2 audit", "", f"Bundle: {report['bundle']}", "", "## Decision", "",
        f"- Experimental doctor search: **{'YES' if readiness['doctor_search_experimental'] else 'NO'}**",
        f"- Patient RAG: **{'YES' if readiness['patient_rag'] else 'NO'}**",
        f"- Clinical automation: **{'YES' if readiness['clinical_automation'] else 'NO'}**",
        "",
        "The bundle may be used to develop and evaluate retrieval for doctors. Draft or unchecked knowledge must not be shown to patients or used for automatic treatment decisions.",
        "", "## Summary", "",
        f"- Issue groups: {summary['issues']}",
        f"- Errors: {summary['errors']}",
        f"- Blocking records: {summary['blockers']}",
        f"- Warnings: {summary['warnings']}",
        "", "## Record counts", "",
    ]
    lines.extend(f"- {name}: {count}" for name, count in report["counts"].items())
    lines += ["", "## Findings", ""]
    for issue in report["issues"]:
        samples = ", ".join(issue["samples"])
        suffix = f" Samples: {samples}." if samples else ""
        lines.append(f"- **{issue['severity'].upper()} / {issue['code']}** — {issue['message']} ({issue['count']}).{suffix}")
    lines += [
        "", "## Gate for the next stage", "",
        "The next implementation step may build a doctor-only retrieval endpoint with citations. Patient access remains disabled until chunks receive an explicit audience, clinical approval, and the evaluation and safety-rule gates pass.", "",
    ]
    return "\n".join(lines)
