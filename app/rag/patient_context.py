"""Allow-listed patient-visible context for the patient assistant."""

from __future__ import annotations

import re
from typing import Any

from app import db


CONTEXT_FIELDS = (
    "latest_assessments",
    "recent_self_reports",
    "adherence_summary",
    "confirmed_plan",
    "care_tasks",
    "therapy_decisions",
    "confirmed_routing",
)
LONG_ID_RE = re.compile(r"(?<!\d)\d{7,}(?!\d)")


def _clean_text(value: str, patient_name: str) -> tuple[str, bool]:
    # Local import avoids a module cycle: patient_assistant imports this builder.
    from app.rag.patient_assistant import redact_personal_data

    result, changed = redact_personal_data(value.strip())
    for token in sorted(set(patient_name.split()), key=len, reverse=True):
        if len(token) >= 3:
            updated = re.sub(re.escape(token), "[ИМЯ]", result, flags=re.IGNORECASE)
            changed, result = changed or updated != result, updated
    updated = LONG_ID_RE.sub("[ИДЕНТИФИКАТОР]", result)
    return updated, changed or updated != result


def deidentify_text(patient_id: int, value: str) -> tuple[str, bool]:
    patient = db.get_patient(patient_id)
    if not patient:
        raise LookupError("Пациент не найден")
    return _clean_text(value, patient["name"])


def _clean_record(
    record: dict[str, Any], text_fields: tuple[str, ...], patient_name: str
) -> tuple[dict[str, Any], bool]:
    result = dict(record)
    redacted = False
    for field in text_fields:
        value = result.get(field)
        if isinstance(value, str) and value:
            result[field], changed = _clean_text(value, patient_name)
            redacted = redacted or changed
    return result, redacted


def build_patient_context(patient_id: int) -> dict[str, Any]:
    """Return only fields already visible to the patient in the application.

    Deliberately excluded: patient identity/profile, clinical profile, alerts,
    messages, internal recommendations, unconfirmed routing and AI summaries.
    """
    patient = db.get_patient(patient_id)
    if not patient:
        raise LookupError("Пациент не найден")
    patient_name = patient["name"]

    redacted = False

    latest_by_scale: dict[str, dict[str, Any]] = {}
    for item in db.get_assessments(patient_id, 20):
        scale_id = item["scale_id"]
        if scale_id not in latest_by_scale:
            latest_by_scale[scale_id] = {
                "scale": scale_id.upper(),
                "score": item["total"],
                "severity_label": item["severity"],
                "completed_at": item["created_at"],
                "interpretation_boundary": "screening_result_not_diagnosis",
            }

    reports = []
    for item in db.get_reports(patient_id, 3):
        report, changed = _clean_record(
            {
                "mood": item["mood"],
                "anxiety": item["anxiety"],
                "sleep": item["sleep"],
                "comment": item.get("comment", ""),
                "urgent_marked_by_patient": bool(item["urgent"]),
                "created_at": item["created_at"],
            },
            ("comment",),
            patient_name,
        )
        redacted = redacted or changed
        reports.append(report)

    plan = None
    stored_plan = db.get_plan(patient_id)
    if stored_plan:
        plan, changed = _clean_record(
            {"text": stored_plan["text"], "confirmed_at": stored_plan["created_at"]},
            ("text",),
            patient_name,
        )
        redacted = redacted or changed

    tasks = []
    for item in db.get_care_tasks(patient_id):
        if item["status"] not in {"pending", "completed"}:
            continue
        task, changed = _clean_record(
            {
                "title": item["title"],
                "description": item.get("description", ""),
                "category": item["category"],
                "status": item["status"],
                "due_date": item.get("due_date"),
            },
            ("title", "description"),
            patient_name,
        )
        redacted = redacted or changed
        tasks.append(task)

    decisions = []
    for item in db.get_therapy_decisions(patient_id, include_internal=False)[:10]:
        decision, changed = _clean_record(
            {
                "medication": item["medication_name"],
                "indication": item.get("indication", ""),
                "dosage": item.get("dosage", ""),
                "schedule": item.get("schedule", ""),
                "duration": item.get("duration", ""),
                "status": item["decision"],
                "confirmed_at": item["created_at"],
                "cancelled_at": item.get("cancelled_at"),
            },
            ("medication", "indication", "dosage", "schedule", "duration"),
            patient_name,
        )
        redacted = redacted or changed
        decisions.append(decision)

    routing = []
    for item in db.get_routing_signals(patient_id, include_unconfirmed=False)[:10]:
        signal, changed = _clean_record(
            {
                "level": item["level"],
                "reason": item["reason_text"],
                "doctor_comment": item.get("decision_comment", ""),
                "confirmed_at": item.get("decided_at") or item["created_at"],
            },
            ("reason", "doctor_comment"),
            patient_name,
        )
        redacted = redacted or changed
        routing.append(signal)

    adherence = db.adherence_summary(patient_id)
    context = {
        "latest_assessments": list(latest_by_scale.values()),
        "recent_self_reports": reports,
        "adherence_summary": adherence if adherence["total"] else None,
        "confirmed_plan": plan,
        "care_tasks": tasks[:10],
        "therapy_decisions": decisions,
        "confirmed_routing": routing,
    }
    return {
        "context": context,
        "context_fields": [field for field in CONTEXT_FIELDS if context[field]],
        "personal_data_redacted": redacted,
        "patient_visible_only": True,
    }
