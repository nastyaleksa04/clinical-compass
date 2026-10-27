"""Deterministic, patient-facing clarification questions before LLM use."""

from __future__ import annotations

import re
from typing import Any


INFORMATIONAL_PHRASES = (
    "что такое", "что означает", "что показывает", "зачем", "как сообщить",
    "как работает", "какие задачи", "что указано",
)
FIRST_PERSON_MARKERS = (
    "у меня", "мне ", "я ", "стало ", "чувствую", "заметил",
    "заметила", "усилил", "ухудш",
)
DURATION_RE = re.compile(r"\b\d+\s*(?:час|дн|день|дня|дней|недел|месяц)", re.IGNORECASE)
INTENSITY_RE = re.compile(r"\b[1-5]\s*(?:из|/)\s*5\b", re.IGNORECASE)
IMPACT_MARKERS = ("мешает", "не могу", "трудно работать", "трудно учиться", "обычные дела")
ADVERSE_DETAILS = (
    "тошнот", "головокруж", "сып", "устал", "сонлив", "тремор",
    "сердцеби", "слабост",
)


def _question(
    question_id: str,
    label: str,
    *,
    kind: str = "text",
    options: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    return {"id": question_id, "label": label, "type": kind, "options": options or []}


def _topic(query: str) -> str | None:
    normalized = query.casefold().replace("ё", "е")
    if any(phrase in normalized for phrase in INFORMATIONAL_PHRASES):
        return None
    if not any(marker in normalized for marker in FIRST_PERSON_MARKERS):
        return None
    if any(value in normalized for value in ("побоч", "нежелательн", "после лекарства", "после препарата")):
        return "adverse_effect"
    if any(value in normalized for value in ("не сплю", "плохо сплю", "бессон", "сон ухудш", "проблемы со сном")):
        return "sleep"
    if any(value in normalized for value in ("тревож", "паник", "беспокойств")):
        return "anxiety"
    if any(value in normalized for value in ("плохое настроение", "груст", "подавлен", "ничего не хочется")):
        return "mood"
    if any(value in normalized for value in ("стало хуже", "самочувствие ухудш", "состояние ухудш")):
        return "worsening"
    return None


def _questions(topic: str, query: str, context: dict[str, Any]) -> list[dict[str, Any]]:
    normalized = query.casefold().replace("ё", "е")
    has_duration = bool(DURATION_RE.search(normalized))
    has_impact = any(marker in normalized for marker in IMPACT_MARKERS)
    latest_report = next(iter(context.get("recent_self_reports") or []), None)
    questions: list[dict[str, Any]] = []

    if topic == "adverse_effect":
        if not any(detail in normalized for detail in ADVERSE_DETAILS):
            questions.append(_question("symptom", "Что именно вы почувствовали или заметили?"))
        questions.append(_question(
            "severity",
            "Насколько это выражено?",
            kind="select",
            options=[
                {"value": "mild", "label": "Слабо, обычные дела возможны"},
                {"value": "moderate", "label": "Умеренно, мешает обычным делам"},
                {"value": "severe", "label": "Сильно, обычные дела невозможны"},
            ],
        ))
        if not has_duration:
            questions.append(_question("onset", "Когда это началось и как связано по времени с приёмом?"))
    elif topic == "sleep":
        questions.append(_question("sleep_change", "Что изменилось: засыпание, пробуждения или ранний подъём?"))
        if not has_duration:
            questions.append(_question("duration", "Как долго это продолжается?"))
        if not has_impact:
            questions.append(_question("impact", "Как это влияет на ваше состояние и обычные дела днём?"))
    elif topic in {"anxiety", "mood"}:
        if not has_duration:
            questions.append(_question("duration", "Как долго это продолжается или когда усилилось?"))
        if not latest_report and not INTENSITY_RE.search(normalized):
            questions.append(_question(
                "intensity",
                "Оцените выраженность сейчас от 1 до 5.",
                kind="select",
                options=[{"value": str(value), "label": str(value)} for value in range(1, 6)],
            ))
        if not has_impact:
            questions.append(_question("impact", "Насколько это мешает сну, работе, учёбе или обычным делам?"))
    elif topic == "worsening":
        questions.append(_question("what_changed", "Что именно изменилось или стало хуже?"))
        if not has_duration:
            questions.append(_question("duration", "Когда вы впервые это заметили?"))
        if not has_impact:
            questions.append(_question("impact", "Как изменение влияет на обычные дела?"))

    return questions[:3]


def analyze(
    query: str,
    context: dict[str, Any],
    supplied_answers: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    topic = _topic(query)
    if not topic:
        return None
    questions = _questions(topic, query, context)
    if not questions:
        return None
    allowed = {item["id"] for item in questions}
    answers = {
        key: str(value).strip()[:500]
        for key, value in (supplied_answers or {}).items()
        if key in allowed and str(value).strip()
    }
    missing = [item for item in questions if item["id"] not in answers]
    return {
        "topic": topic,
        "questions": questions,
        "missing_questions": missing,
        "answers": answers,
        "complete": not missing,
        "summary": [
            {"id": item["id"], "label": item["label"], "answer": answers[item["id"]]}
            for item in questions
            if item["id"] in answers
        ],
    }
