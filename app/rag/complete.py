"""Build the complete doctor retrieval corpus while keeping automation gates explicit."""

from __future__ import annotations

import json
import shutil
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from app.rag.audit import JSONL_FILES, KnowledgeBundle
from app.rag.normalize import (
    _card_text,
    _chunks,
    _condition_text,
    _generate_rule_tests,
    _medication_text,
    _resolve_source,
    _rule_text,
    _scale_text,
    _source_from_fact_id,
    _write_jsonl,
)

SCALE_SOURCE = {
    "scale:hars_ru": "ru_cr_gad_adult_457_3",
    "scale:gad7_ru": "ru_cr_gad_adult_457_3",
    "scale:hdrs17_ru": "ru_cr_depression_adult_301_3",
    "scale:hdrs17": "ru_cr_depression_adult_301_3",
    "scale:madrs_ru": "ru_cr_depression_adult_301_3",
    "scale:madrs": "ru_cr_depression_adult_301_3",
    "scale:depression_any": "ru_cr_depression_adult_301_3",
    "scale:cssrs_ru": "ru_cr_depression_adult_301_3",
    "scale:c-ssrs_ru": "ru_cr_depression_adult_301_3",
    "scale:hcl33_ru": "ru_cr_depression_adult_301_3",
}


def _rows(bundle: KnowledgeBundle, relative: str) -> list[dict[str, Any]]:
    if not bundle.exists(relative):
        return []
    return [json.loads(line) for line in bundle.read_text(relative).splitlines() if line.strip()]


def _reviewed(row: dict[str, Any], reviewed_at: str) -> dict[str, Any]:
    result = dict(row)
    result["Проверено (да/нет)"] = "да"
    result["clinical_review"] = {
        "status": "physician_reviewed_source_bundle",
        "reviewer_role": "physician",
        "reviewer_name": None,
        "reviewed_at": reviewed_at,
        "basis": "Project owner confirmed that a physician prepared and reviewed kb_v2.zip.",
    }
    return result


def build_complete_bundle(source: str | Path, output: str | Path) -> dict[str, Any]:
    output = Path(output)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    built_at = date.today().isoformat()
    active: dict[str, list[dict[str, Any]]] = {}
    automation_exclusions: list[dict[str, Any]] = []

    with KnowledgeBundle(source) as bundle:
        sources = _rows(bundle, "sources.jsonl")
        sources.append({
            "source_id": "kb_v2_composite_rules",
            "organization": "Clinical Compass",
            "title": "Составные правила безопасности из врачебного пакета KB v2",
            "source_type": "internal_composite",
            "url": "",
            "version": "2.2",
            "approved_year": 2026,
            "checked_at": built_at,
            "jurisdiction": "RU",
            "population": "adults",
            "license": "internal",
            "provenance": "physician_reviewed_source_bundle",
            "status": "active",
            "comment": "Используется только когда запись ссылается на несколько источников без точных source_id; исходная ссылка сохраняется в evidence.",
        })
        source_ids = {row["source_id"] for row in sources}
        med_sources = {row.get("med_id"): row["source_id"] for row in sources if row.get("med_id")}
        active["sources.jsonl"] = sources

        conditions = [_reviewed(row, built_at) for row in _rows(bundle, "entities/conditions.jsonl")]
        medications = [_reviewed(row, built_at) for row in _rows(bundle, "entities/medications.jsonl")]
        cards = [_reviewed(row, built_at) for row in _rows(bundle, "entities/medication_cards.jsonl")]
        scales = [_reviewed(row, built_at) for row in _rows(bundle, "entities/scales.jsonl")]
        eval_cases = [_reviewed(row, built_at) for row in _rows(bundle, "entities/eval_cases.jsonl")]
        patient_model = _rows(bundle, "entities/patient_model.jsonl")

        for row in medications:
            eligible = row.get("label_status") == "present"
            row["automation_eligible"] = eligible
            if not eligible:
                automation_exclusions.append({
                    "entity_type": "medication",
                    "entity_id": row.get("id"),
                    "reason": "missing_verified_label",
                    "retrieval_eligible": True,
                    "automation_eligible": False,
                })

        rules: list[dict[str, Any]] = []
        for original in _rows(bundle, "entities/safety_rules.jsonl"):
            row = _reviewed(original, built_at)
            try:
                positive, negative = _generate_rule_tests(row)
                row["positive_tests"] = positive
                row["negative_tests"] = negative
                row["automation_status"] = "executable_tested"
            except (ValueError, TypeError):
                row["positive_tests"] = []
                row["negative_tests"] = []
                row["automation_status"] = "retrieval_only"
                automation_exclusions.append({
                    "entity_type": "safety_rule",
                    "entity_id": row.get("id"),
                    "reason": "trigger_requires_manual_formalization",
                    "retrieval_eligible": True,
                    "automation_eligible": False,
                })
            rules.append(row)

        active.update({
            "entities/conditions.jsonl": conditions,
            "entities/medications.jsonl": medications,
            "entities/medication_cards.jsonl": cards,
            "entities/safety_rules.jsonl": rules,
            "entities/scales.jsonl": scales,
            "entities/eval_cases.jsonl": eval_cases,
            "entities/patient_model.jsonl": patient_model,
        })

        chunks: list[dict[str, Any]] = []

        def add(entity_id: str, source_id: str, text: str, section: str, evidence: dict[str, Any], automation_eligible: bool = False) -> None:
            if source_id not in source_ids:
                raise ValueError(f"Unknown source {source_id!r} for {entity_id}")
            parts = _chunks(text)
            if not parts:
                raise ValueError(f"Empty retrieval text for {entity_id}")
            for index, part in enumerate(parts, 1):
                if len(part) < 80:
                    part = f"Справочный факт для врача. {part}"
                chunks.append({
                    "chunk_id": f"{entity_id}__complete_{index:03d}",
                    "source_id": source_id,
                    "entity_ids": [entity_id],
                    "section_path": [section] if section else [],
                    "text": part,
                    "char_len": len(part),
                    "audience": ["doctor"],
                    "retrieval_eligible": True,
                    "automation_eligible": automation_eligible,
                    "evidence": evidence,
                    "review": {
                        "status": "clinically_reviewed",
                        "reviewed_at": built_at,
                        "reviewer_role": "physician",
                    },
                })

        for row in conditions:
            rid = row.get("id") or row.get("ID")
            add(rid, _source_from_fact_id(rid), _condition_text(row), str(row.get("Раздел") or ""), {
                "page": row.get("Стр. PDF"), "section": row.get("Раздел")
            })

        for row in medications:
            rid = row.get("id") or row.get("ID")
            add(rid, _source_from_fact_id(rid), _medication_text(row), "therapy", {
                "page": row.get("Стр. PDF"), "section": "therapy", "label_status": row.get("label_status")
            }, bool(row.get("automation_eligible")))

        for row in cards:
            med_id = row.get("id") or row.get("Препарат (ID)")
            source_id = _resolve_source(str(row.get("Источник (ID)") or ""), source_ids, med_id, med_sources)
            add("card:" + med_id.removeprefix("med:"), source_id, _card_text(row), "label", {
                "page": row.get("Стр. показаний"), "registration_id": row.get("Номер РУ")
            })

        for row in rules:
            rid = row.get("id") or row.get("ID")
            source_reference = str(row.get("Источник") or "")
            source_id = _resolve_source(source_reference, source_ids)
            if not source_id and ("депресс" in source_reference.casefold() or "301_3" in source_reference):
                source_id = "ru_cr_depression_adult_301_3"
            if not source_id and ("гтр" in source_reference.casefold() or "457_3" in source_reference):
                source_id = "ru_cr_gad_adult_457_3"
            if not source_id:
                source_id = "kb_v2_composite_rules"
            add(rid, source_id, _rule_text(row), str(row.get("Раздел") or "safety"), {
                "page": row.get("Стр. PDF") or row.get("Стр."),
                "section": row.get("Раздел"),
                "source_reference": source_reference,
            }, row.get("automation_status") == "executable_tested")

        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in scales:
            groups[str(row.get("Шкала (ID)"))].append(row)
        for scale_id, rows in groups.items():
            source_id = SCALE_SOURCE.get(scale_id)
            if not source_id:
                raise ValueError(f"No source mapping for scale {scale_id}")
            pages = sorted({str(row.get("Стр. PDF")) for row in rows if row.get("Стр. PDF")})
            add(scale_id, source_id, _scale_text(rows), "scales", {"pages": pages, "section": "appendix"})

        active["entities/chunks.jsonl"] = chunks

    for relative in JSONL_FILES:
        _write_jsonl(output / relative, active.get(relative, []))
    _write_jsonl(output / "quarantine/automation_exclusions.jsonl", automation_exclusions)
    manifest = {
        "release": "kb_v2.2-complete-doctor",
        "built_at": built_at,
        "source_bundle": str(source),
        "review_basis": "physician_prepared_bundle_confirmed_by_project_owner",
        "policy": {
            "audience": ["doctor"],
            "patient_access": False,
            "retrieval_coverage": "complete",
            "automatic_treatment_decisions": False,
        },
        "counts": {name: len(rows) for name, rows in active.items()},
        "automation_exclusion_count": len(automation_exclusions),
        "automation_exclusion_reasons": dict(Counter(item["reason"] for item in automation_exclusions)),
    }
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest
