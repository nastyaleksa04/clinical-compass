"""Build a safe doctor-only retrieval bundle from the KB v2 pilot."""

from __future__ import annotations

import json
import shutil
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from app.rag.audit import JSONL_FILES, KnowledgeBundle

CHECKED_VALUES = {"да", "yes", "true"}
MAX_CHUNK_LENGTH = 1500


def _checked(row: dict[str, Any]) -> bool:
    return str(row.get("Проверено (да/нет)", "")).strip().casefold() in CHECKED_VALUES


def _rows(bundle: KnowledgeBundle, relative: str) -> list[dict[str, Any]]:
    if not bundle.exists(relative):
        return []
    return [json.loads(line) for line in bundle.read_text(relative).splitlines() if line.strip()]


def _source_from_fact_id(record_id: str) -> str:
    for marker in ("__A", "__D", "__M"):
        if marker in record_id:
            return record_id.split(marker, 1)[0]
    return ""


def _resolve_source(reference: str, source_ids: set[str], med_id: str = "", med_sources: dict[str, str] | None = None) -> str:
    if reference in source_ids:
        return reference
    candidates = [source_id for source_id in source_ids if reference.startswith(source_id)]
    if candidates:
        return max(candidates, key=len)
    return (med_sources or {}).get(med_id, "")


def _clean(parts: list[Any]) -> str:
    return " ".join(str(part).strip() for part in parts if part is not None and str(part).strip() not in {"", "—", "PDF"})


def _condition_text(row: dict[str, Any]) -> str:
    return _clean([
        row.get("Тип факта"),
        row.get("Дословный фрагмент КР") or row.get("Текст"),
        f"Риск: {row.get('Риск')}." if row.get("Риск") else None,
        f"УУР: {row.get('УУР')}; УДД: {row.get('УДД')}." if row.get("УУР") or row.get("УДД") else None,
    ])


def _medication_text(row: dict[str, Any]) -> str:
    dose_min = row.get("Доза принятая мин")
    dose_max = row.get("Доза принятая макс")
    dose = None
    if dose_min is not None or dose_max is not None:
        dose = f"Доза по клиническим рекомендациям: {dose_min}–{dose_max} {row.get('Ед.', '')}."
    return _clean([
        f"{row.get('МНН', '')}.",
        f"Группа: {row.get('Группа по КР')}." if row.get("Группа по КР") else None,
        f"Линия терапии: {row.get('Линия')}." if row.get("Линия") else None,
        f"Применение: {row.get('Условие назначения')}." if row.get("Условие назначения") else None,
        dose,
        f"Режим: {row.get('Режим')}." if row.get("Режим") else None,
        f"Титрация или кратность: {row.get('Титрация / кратность')}." if row.get("Титрация / кратность") else None,
        f"Фрагмент источника: {row.get('Дословный фрагмент КР')}." if row.get("Дословный фрагмент КР") else None,
        f"УУР: {row.get('УУР')}; УДД: {row.get('УДД')}." if row.get("УУР") or row.get("УДД") else None,
    ])


def _card_text(row: dict[str, Any]) -> str:
    return _clean([
        f"{row.get('МНН', '')}",
        f"({row.get('Торговое название')})." if row.get("Торговое название") else None,
        f"Регистрационный номер: {row.get('Номер РУ')}." if row.get("Номер РУ") else None,
        f"ГТР в показаниях: {row.get('ГТР в показаниях')}." if row.get("ГТР в показаниях") else None,
        f"Депрессия в показаниях: {row.get('Депрессия в показаниях')}." if row.get("Депрессия в показаниях") else None,
        f"Возраст: с {row.get('Возраст от, лет')} лет." if row.get("Возраст от, лет") is not None else None,
        f"Беременность: {row.get('Беременность')}." if row.get("Беременность") else None,
        f"Грудное вскармливание: {row.get('Грудное вскармливание')}." if row.get("Грудное вскармливание") else None,
        f"Пожилые: {row.get('Пожилые')}." if row.get("Пожилые") else None,
        f"Ключевые сведения: {row.get('Ключевые находки')}." if row.get("Ключевые находки") else None,
        f"Максимальная доза по инструкции: {row.get('Макс. доза по инструкции, мг/сут')} мг/сут." if row.get("Макс. доза по инструкции, мг/сут") is not None else None,
    ])


def _scale_text(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""
    parts = [f"Шкала: {rows[0].get('Шкала')}."]
    for row in rows:
        bounds = ""
        if row.get("Мин") is not None or row.get("Макс") is not None:
            bounds = f" Диапазон: {row.get('Мин')}–{row.get('Макс')}."
        rule = f" Правило: {row.get('Правило')}." if row.get("Правило") else ""
        quote = f" Источник: {row.get('Дословный фрагмент КР')}." if row.get("Дословный фрагмент КР") else ""
        parts.append(f"{row.get('Параметр')}.{bounds}{rule}{quote}")
    return _clean(parts)


def _rule_text(row: dict[str, Any]) -> str:
    return _clean([
        f"Правило: {row.get('Правило')}.",
        f"Применяется к: {row.get('Применяется к')}." if row.get("Применяется к") else None,
        f"Формальное условие: {row.get('trigger_raw') or row.get('Условие (формально)')}.",
        f"Тяжесть: {row.get('Тяжесть')}." if row.get("Тяжесть") else None,
        f"Действие системы: {row.get('Действие системы')}." if row.get("Действие системы") else None,
        f"Текст для врача: {row.get('Текст для врача')}." if row.get("Текст для врача") else None,
        f"Фрагмент источника: {row.get('Дословный фрагмент')}." if row.get("Дословный фрагмент") else None,
    ])


def _chunks(text: str) -> list[str]:
    text = " ".join(text.split())
    if len(text) <= MAX_CHUNK_LENGTH:
        return [text] if text else []
    result: list[str] = []
    while text:
        cut = min(MAX_CHUNK_LENGTH, len(text))
        if cut < len(text):
            boundary = text.rfind(" ", 0, cut)
            cut = boundary if boundary >= 900 else cut
        result.append(text[:cut].strip())
        text = text[cut:].strip()
    return result


def _flip(value: Any) -> Any:
    if isinstance(value, bool):
        return not value
    if isinstance(value, (int, float)):
        return value + 1
    return "__other__"


def _positive_value(condition: dict[str, Any]) -> Any:
    op, value = condition["op"], condition.get("value")
    if op in {"eq", "gte"}:
        return value
    if op == "neq":
        return _flip(value)
    if op == "gt":
        return value + 1
    if op == "lt":
        return value - 1
    if op == "in":
        return value[0]
    raise ValueError(f"Unsupported operator: {op}")


def _negative_value(condition: dict[str, Any]) -> Any:
    op, value = condition["op"], condition.get("value")
    if op in {"eq", "neq", "in"}:
        return value if op == "neq" else _flip(value)
    if op in {"gt", "gte", "lt"}:
        return value
    raise ValueError(f"Unsupported operator: {op}")


def _generate_rule_tests(rule: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    trigger = rule.get("trigger") or {}
    groups = trigger.get("groups") or []
    conditions = [condition for group in groups for condition in group]
    if not conditions or any(condition.get("op") == "raw" or not condition.get("field") for condition in conditions):
        raise ValueError("rule is not fully formalized")
    positive = {condition["field"]: _positive_value(condition) for condition in conditions}
    negative = dict(positive)
    first = conditions[0]
    negative[first["field"]] = _negative_value(first)
    return (
        [{"name": "generated_positive", "input": positive, "expected": True}],
        [{"name": "generated_negative", "input": negative, "expected": False}],
    )


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)
    path.write_text(body, encoding="utf-8")


def normalize_bundle(source: str | Path, output: str | Path) -> dict[str, Any]:
    output = Path(output)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    quarantine: list[dict[str, Any]] = []
    active: dict[str, list[dict[str, Any]]] = {}
    release_date = date.today().isoformat()

    with KnowledgeBundle(source) as bundle:
        sources = _rows(bundle, "sources.jsonl")
        source_ids = {row.get("source_id") for row in sources}
        med_sources = {row.get("med_id"): row.get("source_id") for row in sources if row.get("med_id")}
        active["sources.jsonl"] = sources

        conditions = _rows(bundle, "entities/conditions.jsonl")
        active_conditions = [row for row in conditions if _checked(row)]
        for row in conditions:
            if not _checked(row):
                quarantine.append({"entity_type": "condition", "entity_id": row.get("id"), "reason": "not_clinically_checked"})
        active["entities/conditions.jsonl"] = active_conditions

        medications = _rows(bundle, "entities/medications.jsonl")
        active_meds = [row for row in medications if _checked(row) and row.get("label_status") == "present"]
        for row in medications:
            reasons = []
            if not _checked(row):
                reasons.append("not_clinically_checked")
            if row.get("label_status") != "present":
                reasons.append("missing_verified_label")
            if reasons:
                quarantine.append({"entity_type": "medication", "entity_id": row.get("id"), "reason": ",".join(reasons)})
        active["entities/medications.jsonl"] = active_meds

        cards = _rows(bundle, "entities/medication_cards.jsonl")
        active_cards = [row for row in cards if _checked(row)]
        for row in cards:
            if not _checked(row):
                quarantine.append({"entity_type": "medication_card", "entity_id": row.get("id"), "reason": "not_clinically_checked"})
        active["entities/medication_cards.jsonl"] = active_cards

        rules = _rows(bundle, "entities/safety_rules.jsonl")
        active_rules: list[dict[str, Any]] = []
        for row in rules:
            if not _checked(row):
                quarantine.append({"entity_type": "safety_rule", "entity_id": row.get("id"), "reason": "not_clinically_checked"})
                continue
            try:
                positive, negative = _generate_rule_tests(row)
            except ValueError:
                quarantine.append({"entity_type": "safety_rule", "entity_id": row.get("id"), "reason": "trigger_requires_manual_formalization"})
                continue
            normalized = dict(row)
            normalized["positive_tests"] = positive
            normalized["negative_tests"] = negative
            normalized["automation_status"] = "executable_tested"
            active_rules.append(normalized)
        active["entities/safety_rules.jsonl"] = active_rules

        scales = _rows(bundle, "entities/scales.jsonl")
        active_scales = [row for row in scales if _checked(row)]
        for row in scales:
            if not _checked(row):
                quarantine.append({"entity_type": "scale", "entity_id": row.get("id"), "reason": "not_clinically_checked"})
        active["entities/scales.jsonl"] = active_scales

        active["entities/patient_model.jsonl"] = _rows(bundle, "entities/patient_model.jsonl")
        active["entities/eval_cases.jsonl"] = _rows(bundle, "entities/eval_cases.jsonl")

        chunks: list[dict[str, Any]] = []
        def add(entity_id: str, source_id: str, text: str, section: str, evidence: dict[str, Any]) -> None:
            if source_id not in source_ids:
                quarantine.append({"entity_type": "chunk", "entity_id": entity_id, "reason": "unknown_source"})
                return
            for index, part in enumerate(_chunks(text), 1):
                if len(part) < 80:
                    quarantine.append({"entity_type": "chunk", "entity_id": entity_id, "reason": "content_too_short"})
                    continue
                chunks.append({
                    "chunk_id": f"{entity_id}__safe_{index:03d}",
                    "source_id": source_id,
                    "entity_ids": [entity_id],
                    "section_path": [section] if section else [],
                    "text": part,
                    "char_len": len(part),
                    "audience": ["doctor"],
                    "retrieval_eligible": True,
                    "evidence": evidence,
                    "review": {"status": "source_checked", "reviewed_at": release_date},
                })

        for row in active_conditions:
            rid = row.get("id") or row.get("ID")
            add(rid, _source_from_fact_id(rid), _condition_text(row), str(row.get("Раздел") or ""), {"page": row.get("Стр. PDF"), "section": row.get("Раздел")})

        for row in active_meds:
            rid = row.get("id") or row.get("ID")
            add(rid, _source_from_fact_id(rid), _medication_text(row), "therapy", {"page": row.get("Стр. PDF"), "section": "therapy"})

        for row in active_cards:
            rid = row.get("id") or row.get("Препарат (ID)")
            source_id = _resolve_source(str(row.get("Источник (ID)") or ""), source_ids, rid, med_sources)
            add("card:" + rid.removeprefix("med:"), source_id, _card_text(row), "label", {"page": row.get("Стр. показаний"), "registration_id": row.get("Номер РУ")})

        for row in active_rules:
            rid = row.get("id") or row.get("ID")
            source_id = _resolve_source(str(row.get("Источник") or ""), source_ids)
            add(rid, source_id, _rule_text(row), str(row.get("Раздел") or "safety"), {"page": row.get("Стр. PDF") or row.get("Стр."), "section": row.get("Раздел")})

        scale_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in active_scales:
            scale_groups[str(row.get("Шкала (ID)"))].append(row)
        for scale_id, rows in scale_groups.items():
            pages = sorted({str(row.get("Стр. PDF")) for row in rows if row.get("Стр. PDF")})
            add(scale_id, "ru_cr_gad_adult_457_3", _scale_text(rows), "scales", {"pages": pages, "section": "appendix"})

        active["entities/chunks.jsonl"] = chunks

    for relative in JSONL_FILES:
        _write_jsonl(output / relative, active.get(relative, []))
    _write_jsonl(output / "quarantine/exclusions.jsonl", quarantine)

    manifest = {
        "release": "kb_v2.1-doctor-safe",
        "built_at": release_date,
        "source_bundle": str(source),
        "policy": {
            "audience": ["doctor"],
            "review_status": "source_checked",
            "patient_access": False,
            "automatic_treatment_decisions": False,
        },
        "counts": {name: len(rows) for name, rows in active.items()},
        "quarantine_count": len(quarantine),
        "quarantine_reasons": dict(sorted(__import__("collections").Counter(item["reason"] for item in quarantine).items())),
    }
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest
