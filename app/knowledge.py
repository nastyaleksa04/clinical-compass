"""База знаний врача.

Системные статьи собираются из конфигурации и правил прототипа, поэтому всегда
совпадают с тем, как система считает баллы, формирует сигналы и алерты.
Статьи врача хранятся в SQLite и редактируются в интерфейсе.
"""
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app import alerting, db, safety, therapy
from app import scales as scale_engine

TEMPLATES_PATH = Path(__file__).resolve().parents[1] / "config" / "kb_templates.json"
TEMPLATES_META_KEY = "kb_templates_version"

CATEGORIES = {
    "scale": "Шкалы",
    "therapy": "Терапия",
    "protocol": "Протоколы",
    "note": "Заметки врача",
}


def _range(item: dict[str, Any]) -> str:
    return f"{item['min']}–{item['max']}"


def _scale_article(scale: dict[str, Any], version: str) -> dict[str, Any]:
    alert_items = scale.get("alert_items", [])
    sections = [
        {"title": "Назначение", "text": f"{scale['description']}. {scale['instruction']}"},
        {"title": "Интерпретация суммарного балла", "table": [[_range(item), item["label"]] for item in scale["thresholds"]]},
        {"title": "Подсчёт", "items": [
            f"{len(scale['questions'])} пунктов, каждый от 0 до 3 баллов; максимум — {scale['max_score']}.",
            "Балл считается на сервере, результат сохраняется в истории пациента.",
        ]},
        {"title": "Сигналы для врача", "items": [
            *[f"Пункт {rule['index'] + 1} («{scale['questions'][rule['index']]}») — ответ от {rule['min']} балла создаёт обязательный сигнал и критический алерт." for rule in alert_items],
            f"Суммарный балл от {safety.HIGH_SCORE_THRESHOLD} — желательный сигнал для клинической оценки.",
        ]},
        {"title": "Ограничения", "text": "Скрининговый инструмент: балл не устанавливает диагноз и не меняет терапию автоматически. Решение принимает врач."},
    ]
    links = [
        {"label": "Клинические рекомендации", "url": scale["source"]["clinical"]},
        {"label": "Валидация русскоязычной версии", "url": scale["source"]["validation"]},
    ]
    return {
        "id": scale["id"], "title": f"{scale['name']}: {scale['title'].lower()}", "category": "scale",
        "summary": f"Пороги выраженности, подсчёт и правила сигналов {scale['name']}.",
        "sections": sections, "links": links, "tags": [scale["name"], "скрининг", "опросник"],
        "system": True, "author": "Конфигурация шкал", "updated_at": version,
    }


def _medication_article(medication: dict[str, Any], version: str) -> dict[str, Any]:
    blocked = [rule["text"] for rule in medication["rules"] if rule["level"] == "blocked"]
    warnings = [rule["text"] for rule in medication["rules"] if rule["level"] == "warning"]
    return {
        "id": medication["id"], "title": medication["name"], "category": "therapy",
        "summary": "Показания, режим по инструкции, противопоказания и взаимодействия.",
        "sections": [
            {"title": "Регистрация", "text": f"{medication['registration']}." + (" Рецептурный препарат." if medication.get("prescription_only") else "")},
            {"title": "Показания", "items": medication["indications"]},
            {"title": "Режим по инструкции", "text": medication["reference_dose"]},
            {"title": "Противопоказания", "items": blocked, "tone": "danger"},
            {"title": "Взаимодействия и предупреждения", "items": warnings, "tone": "warning"},
            {"title": "Чек-лист", "text": "Индивидуальные факторы проверяются в карточке пациента, блок «Справочник терапии». Результат проверки не является назначением."},
        ],
        "links": [
            {"label": "Инструкция по применению", "url": medication["sources"]["instruction"]},
            {"label": "Клинические рекомендации", "url": medication["sources"]["clinical_guideline"]},
        ],
        "tags": [medication["name"], "противопоказания", "взаимодействия"],
        "system": True, "author": "Справочник терапии", "updated_at": version,
    }


def _routing_article() -> dict[str, Any]:
    return {
        "id": "routing", "title": "Сигналы и маршрутизация", "category": "protocol",
        "summary": "Какие события создают обязательные и желательные сигналы и что с ними делать.",
        "sections": [
            {"title": "Обязательно", "tone": "danger", "items": [
                "Пациент отметил в самоотчёте, что ему нужна срочная связь.",
                "Ненулевой ответ на пункт PHQ-9 о смерти или причинении себе вреда.",
                "Пациент сообщил о выраженной нежелательной реакции на терапию.",
            ]},
            {"title": "Желательно", "tone": "warning", "items": [
                f"Суммарный балл PHQ-9 или GAD-7 от {safety.HIGH_SCORE_THRESHOLD}.",
                "Пациент отметил пропуск назначенной терапии.",
            ]},
            {"title": "Порядок работы", "items": [
                "Сигнал появляется в карточке пациента со статусом «Ожидает решения».",
                "Врач подтверждает или отклоняет маршрутизацию; пациент видит только подтверждённое решение.",
                "Подтверждение обязательного сигнала закрывает связанный критический алерт и фиксирует время реакции.",
            ]},
            {"title": "Ограничения", "text": "Пороги желательных сигналов — прозрачное правило прототипа для последующей клинической оценки. Сигнал не является диагнозом или назначением."},
        ],
        "links": [], "tags": ["сигнал", "маршрутизация", "безопасность"],
        "system": True, "author": "Правила прототипа", "updated_at": None,
    }


def _alerting_article() -> dict[str, Any]:
    settings = alerting.config()
    minutes = round(settings["escalation_seconds"] / 60)
    return {
        "id": "alerting", "title": "Критический алертинг", "category": "protocol",
        "summary": f"Обязательные сигналы, реакция врача и эскалация через {minutes} мин.",
        "sections": [
            {"title": "Когда создаётся алерт", "text": "Каждый обязательный сигнал создаёт критический алерт с точным временем срабатывания."},
            {"title": "Что видит пациент", "items": settings["patient_actions"]},
            {"title": "Что делает система для врача", "items": settings["doctor_actions"]},
            {"title": "Реакция и эскалация", "tone": "danger", "items": [
                "Врач принимает алерт в работу — сохраняется время реакции в секундах.",
                f"Если реакции нет {minutes} мин, алерт получает статус эскалации: {settings['escalation_action'].lower()}.",
            ]},
            {"title": "Настройка", "text": "Порог и действия задаются в config/alerting.json."},
        ],
        "links": [], "tags": ["алерт", "эскалация", "дежурный врач"],
        "system": True, "author": "Конфигурация алертинга", "updated_at": settings.get("version"),
    }


def system_articles() -> list[dict[str, Any]]:
    scales = scale_engine.catalogue()
    medications = therapy.catalogue()
    return [
        *[_scale_article(scale, scales["version"]) for scale in scales["scales"]],
        *[_medication_article(item, medications["version"]) for item in medications["medications"]],
        _routing_article(),
        _alerting_article(),
    ]


@lru_cache(maxsize=1)
def templates_config() -> dict[str, Any]:
    return json.loads(TEMPLATES_PATH.read_text(encoding="utf-8"))


def seed_templates() -> int:
    """Один раз добавляет шаблоны протоколов как обычные статьи врача.

    Отметка хранится в базе, поэтому удалённый или изменённый врачом шаблон
    не восстанавливается при перезапуске.
    """
    if db.get_meta(TEMPLATES_META_KEY):
        return 0
    data = templates_config()
    values = {"escalation_minutes": round(alerting.config()["escalation_seconds"] / 60)}
    # Список статей сортируется от новых к старым, поэтому первый шаблон добавляется последним.
    for template in reversed(data["templates"]):
        db.create_kb_article({
            "title": template["title"], "category": template["category"],
            "summary": template["summary"].format(**values), "body": template["body"].format(**values),
            "tags": template["tags"], "source_url": "",
        }, data["author"])
    db.set_meta(TEMPLATES_META_KEY, data["version"])
    return len(data["templates"])


def doctor_article(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": f"note-{row['id']}", "title": row["title"], "category": row["category"],
        "summary": row["summary"], "body": row["body"], "sections": [{"title": "", "text": row["body"]}],
        "links": [{"label": row["source_url"], "url": row["source_url"]}] if row["source_url"] else [],
        "source_url": row["source_url"], "tags": row["tags"], "system": False,
        "template": row["author"] == templates_config()["author"],
        "author": row["author"], "updated_at": row["updated_at"],
    }


def _haystack(article: dict[str, Any]) -> str:
    parts = [article["title"], article["summary"], " ".join(article["tags"])]
    for section in article["sections"]:
        parts += [section.get("title", ""), section.get("text", ""), " ".join(section.get("items", []))]
        parts += [" ".join(row) for row in section.get("table", [])]
    return " ".join(parts).casefold()


def search(query: str = "", category: str = "") -> list[dict[str, Any]]:
    articles = system_articles() + [doctor_article(row) for row in db.get_kb_articles()]
    if category:
        articles = [item for item in articles if item["category"] == category]
    words = query.casefold().split()
    if words:
        articles = [item for item in articles if all(word in _haystack(item) for word in words)]
    return articles


def get(article_id: str) -> dict[str, Any] | None:
    if article_id.startswith("note-"):
        number = article_id.removeprefix("note-")
        row = db.get_kb_article(int(number)) if number.isdigit() else None
        return doctor_article(row) if row else None
    return next((item for item in system_articles() if item["id"] == article_id), None)
