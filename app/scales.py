import json
from functools import lru_cache
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCALES_PATH = PROJECT_ROOT / "config" / "scales.json"


@lru_cache(maxsize=1)
def catalogue() -> dict[str, Any]:
    with SCALES_PATH.open(encoding="utf-8") as source:
        return json.load(source)


def public_scales() -> list[dict[str, Any]]:
    options = catalogue()["response_options"]
    return [{**scale, "response_options": options} for scale in catalogue()["scales"]]


def get_scale(scale_id: str) -> dict[str, Any] | None:
    return next((scale for scale in public_scales() if scale["id"] == scale_id), None)


def score(scale_id: str, answers: list[int]) -> dict[str, Any]:
    scale = get_scale(scale_id)
    if not scale:
        raise ValueError("Неизвестная шкала")
    if len(answers) != len(scale["questions"]):
        raise ValueError("Нужно ответить на все вопросы")
    if any(not isinstance(answer, int) or answer < 0 or answer > 3 for answer in answers):
        raise ValueError("Недопустимый вариант ответа")

    total = sum(answers)
    threshold = next(item for item in scale["thresholds"] if item["min"] <= total <= item["max"])
    alerts = [
        rule["code"]
        for rule in scale.get("alert_items", [])
        if answers[rule["index"]] >= rule["min"]
    ]
    return {
        "total": total,
        "severity": threshold["label"],
        "alert": bool(alerts),
        "alert_codes": alerts,
    }