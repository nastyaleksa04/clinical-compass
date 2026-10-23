import json
from functools import lru_cache
from pathlib import Path
from typing import Any

CONFIG_PATH = Path(__file__).resolve().parents[1] / 'config' / 'medications.json'

@lru_cache(maxsize=1)
def catalogue() -> dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding='utf-8'))

def public_catalogue() -> list[dict[str, Any]]:
    return catalogue()['medications']

def get_medication(medication_id: str) -> dict[str, Any] | None:
    return next((item for item in catalogue()['medications'] if item['id'] == medication_id), None)

def evaluate(medication_id: str, factors: dict[str, bool]) -> dict[str, Any]:
    medication = get_medication(medication_id)
    if not medication:
        raise ValueError('Препарат не найден в справочнике')
    findings = [{'level': rule['level'], 'text': rule['text'], 'field': rule['field']} for rule in medication['rules'] if factors.get(rule['field'], False)]
    blocked = any(item['level'] == 'blocked' for item in findings)
    return {'medication_id': medication_id, 'status': 'not_suitable' if blocked else ('review_required' if findings else 'no_flags'), 'title': 'Не подходит по инструкции' if blocked else ('Нужна дополнительная проверка' if findings else 'Противопоказания по чек-листу не выявлены'), 'findings': findings, 'source': medication['sources']['instruction'], 'disclaimer': 'Результат не является назначением. Окончательное решение принимает врач.'}
