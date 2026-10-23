from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app import db
from app import scales as scale_engine
from app import therapy

PRIORITY_ORDER = {"critical": 0, "high": 1, "attention": 2, "routine": 3}


def _scale_config(scale_id: str) -> dict[str, Any] | None:
    return next((item for item in scale_engine.catalogue()["scales"] if item["id"] == scale_id), None)


def _source(label: str, url: str, kind: str) -> dict[str, str]:
    return {"label": label, "url": url, "kind": kind}


def _action(
    code: str,
    priority: str,
    title: str,
    rationale: str,
    plan_text: str,
    source: dict[str, str],
) -> dict[str, Any]:
    return {
        "code": code,
        "priority": priority,
        "title": title,
        "rationale": rationale,
        "plan_text": plan_text,
        "source": source,
        "status": "Требует решения врача",
    }


def build(patient_id: int) -> dict[str, Any]:
    assessments = db.get_assessments(patient_id)
    checkins = db.get_checkins(patient_id)
    routes = db.get_routing_signals(patient_id, include_unconfirmed=True)
    adherence = db.adherence_summary(patient_id)
    clinical = db.get_clinical_profile(patient_id)
    decisions = db.get_therapy_decisions(patient_id, include_internal=True)

    latest_by_scale: dict[str, dict[str, Any]] = {}
    for result in assessments:
        latest_by_scale.setdefault(result["scale_id"], result)

    evidence: list[dict[str, str]] = []
    actions: list[dict[str, Any]] = []

    for scale_id in ("phq9", "gad7"):
        result = latest_by_scale.get(scale_id)
        config = _scale_config(scale_id)
        if result and config:
            tone = "danger" if result["alert"] or result["total"] >= 15 else ("warning" if result["total"] >= 10 else "neutral")
            evidence.append({
                "label": config["name"],
                "value": f'{result["total"]}/{config["max_score"]} · {result["severity"]}',
                "tone": tone,
            })
            if result["alert"]:
                actions.append(_action(
                    "urgent-risk-assessment",
                    "critical",
                    "Незамедлительно оценить безопасность пациента",
                    "В PHQ-9 отмечен ненулевой ответ на пункт о смерти или самоповреждении.",
                    "Связаться с пациентом и провести клиническую оценку риска. При непосредственной угрозе рекомендовать экстренную помощь.",
                    _source("Клинические рекомендации и правила PHQ-9", config["source"]["clinical"], "clinical_guideline"),
                ))
            elif result["total"] >= 15:
                actions.append(_action(
                    f"{scale_id}-high-score",
                    "high",
                    f'Оценить выраженные симптомы по {config["name"]}',
                    f'Последний результат: {result["total"]} баллов — {result["severity"].lower()}.',
                    f'Обсудить результат {config["name"]} на консультации и определить дальнейшую тактику.',
                    _source(f'{config["name"]}: клинический источник', config["source"]["clinical"], "clinical_guideline"),
                ))
        elif config:
            actions.append(_action(
                f"{scale_id}-missing",
                "routine",
                f'Получить исходную оценку {config["name"]}',
                "В карточке нет результата этой стандартизированной шкалы.",
                f'Пройти {config["name"]} до следующего контакта.',
                _source(f'{config["name"]}: русскоязычная валидация', config["source"]["validation"], "validation"),
            ))

    mandatory = [item for item in routes if item["level"] == "mandatory" and item["status"] == "pending"]
    recommended = [item for item in routes if item["level"] == "recommended" and item["status"] == "pending"]
    if mandatory:
        actions.append(_action(
            "mandatory-routing",
            "critical",
            "Рассмотреть обязательную маршрутизацию",
            mandatory[0]["reason_text"],
            "Оценить состояние и подтвердить либо отклонить обязательную маршрутизацию с комментарием.",
            _source("Правило маршрутизации прототипа", _scale_config("phq9")["source"]["clinical"], "clinical_guideline"),
        ))
    elif recommended:
        actions.append(_action(
            "recommended-routing",
            "attention",
            "Рассмотреть желательную консультацию психиатра",
            recommended[0]["reason_text"],
            "Обсудить показания к консультации психиатра и зафиксировать решение по маршрутизации.",
            _source("Клинические рекомендации по тревожным расстройствам", _scale_config("gad7")["source"]["clinical"], "clinical_guideline"),
        ))

    if clinical["psychosis_signs"] or clinical["self_harm_concern"]:
        actions.append(_action(
            "clinical-risk-flags",
            "critical",
            "Проверить признаки высокого клинического риска",
            "Врачом отмечены признаки психоза или опасения самоповреждения.",
            "Провести очную оценку риска и определить срочность специализированной помощи.",
            _source("Клиническая запись врача", "", "clinical_record"),
        ))

    medication = therapy.get_medication("aviandr")
    if clinical["pregnancy_status"] == "yes":
        actions.append(_action(
            "aviandr-contraindication",
            "high",
            "Не подтверждать АВИАНДР® по текущим данным",
            "В клинической сводке указана беременность; в справочнике это противопоказание.",
            "Уточнить данные и выбрать дальнейшую тактику без автоматического назначения препарата.",
            _source("Инструкция АВИАНДР®", medication["sources"]["instruction"], "drug_instruction"),
        ))
    elif not any(item["decision"] == "approved" for item in decisions):
        actions.append(_action(
            "therapy-review",
            "routine",
            "Завершить врачебное рассмотрение терапии",
            "Активного подтверждённого решения по терапии нет.",
            "Проверить зарегистрированное показание, противопоказания, взаимодействия и зафиксировать решение врача.",
            _source("Инструкция АВИАНДР®", medication["sources"]["instruction"], "drug_instruction"),
        ))

    significant_reactions = [item for item in checkins if item["side_effect_severity"] in {"moderate", "severe"}]
    if significant_reactions:
        actions.append(_action(
            "adverse-event-review",
            "high" if significant_reactions[0]["side_effect_severity"] == "severe" else "attention",
            "Оценить зарегистрированное нежелательное явление",
            significant_reactions[0]["side_effect"] or "Пациент отметил нежелательную реакцию.",
            "Связаться с пациентом, оценить тяжесть реакции и зафиксировать врачебное решение.",
            _source("Инструкция применяемого препарата", medication["sources"]["instruction"], "drug_instruction"),
        ))

    if adherence["total"] >= 3 and adherence["percent"] is not None and adherence["percent"] < 80:
        actions.append(_action(
            "low-adherence",
            "attention",
            "Обсудить причины снижения приверженности",
            f'По отметкам пациента принято {adherence["percent"]}% запланированных приёмов.',
            "Обсудить пропуски и согласовать выполнимый план наблюдения.",
            _source("Данные дневника пациента", "", "patient_report"),
        ))
    evidence.append({
        "label": "Приверженность",
        "value": "Нет данных" if adherence["percent"] is None else f'{adherence["percent"]}% по {adherence["total"]} отметкам',
        "tone": "warning" if adherence["percent"] is not None and adherence["percent"] < 80 else "neutral",
    })

    actions.append(_action(
        "monitoring",
        "routine",
        "Продолжить измеримый мониторинг динамики",
        "Повторные шкалы и самоотчёты позволяют оценивать изменение состояния во времени.",
        "Продолжить самоотчёты и повторить релевантные шкалы в согласованный врачом срок.",
        _source("Методики PHQ-9 и GAD-7", _scale_config("gad7")["source"]["validation"], "validation"),
    ))

    unique: dict[str, dict[str, Any]] = {}
    for item in actions:
        unique.setdefault(item["code"], item)
    actions = sorted(unique.values(), key=lambda item: PRIORITY_ORDER[item["priority"]])

    plan_lines = [item["plan_text"] for item in actions if item["priority"] != "critical"][:4]
    highest = actions[0]["priority"] if actions else "routine"
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "priority": highest,
        "summary": {
            "critical": "Нужна срочная оценка врача",
            "high": "Есть клинически значимые вопросы",
            "attention": "Есть вопросы для ближайшего контакта",
            "routine": "Плановый контроль",
        }[highest],
        "evidence": evidence,
        "actions": actions,
        "plan_draft": "\n".join(f"• {line}" for line in plan_lines),
        "disclaimer": "Сводка формируется прозрачными правилами, не устанавливает диагноз и не изменяет лечение. Итоговое решение принимает врач.",
    }
