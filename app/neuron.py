"""Нейрон: настроение AI-помощника отражает регулярность наблюдения, а не клинический результат."""

import json
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from app import db

CONFIG_PATH = Path(__file__).resolve().parents[1] / 'config' / 'neuron.json'


@lru_cache(maxsize=1)
def config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding='utf-8'))


def _offset() -> timedelta:
    return timedelta(hours=config().get('utc_offset_hours', 0))


def local_today() -> date:
    return (datetime.now(timezone.utc) + _offset()).date()


def _local_date(value: str | None) -> date | None:
    if not value:
        return None
    moment = datetime.fromisoformat(value)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return (moment.astimezone(timezone.utc) + _offset()).date()


def _has_therapy(patient_id: int) -> bool:
    return any(item['decision'] == 'approved' for item in db.get_therapy_decisions(patient_id))


def _streak(active: set[date], today: date) -> int:
    day = today if today in active else today - timedelta(days=1)
    count = 0
    while day in active:
        count += 1
        day -= timedelta(days=1)
    return count


def _mood(mood_id: str) -> dict[str, Any]:
    return next(item for item in config()['moods'] if item['id'] == mood_id)


def state(patient_id: int) -> dict[str, Any]:
    settings = config()
    today = local_today()
    window = settings['window_days']
    days = [today - timedelta(days=offset) for offset in range(window - 1, -1, -1)]
    first = days[0]

    reports = {_local_date(item['created_at']) for item in db.get_reports(patient_id, 200)}
    taken, missed = set(), set()
    for item in db.get_checkins(patient_id, 200):
        (taken if item['taken'] else missed).add(_local_date(item['created_at']))
    missed -= taken
    assessments = db.get_assessments(patient_id, 200)
    assessed = {_local_date(item['created_at']) for item in assessments}
    tasks = db.get_care_tasks(patient_id)
    completed = {_local_date(item['completed_at']) for item in tasks if item['status'] == 'completed'}

    drug_days = {_local_date(item['created_at']) for item in db.get_drug_reports(patient_id, limit=200)}
    last_drug = max(drug_days - {None}, default=None)
    drug_fresh = bool(last_drug and (today - last_drug).days < settings['drug_survey_interval_days'])

    active = reports | taken | missed | assessed | completed | drug_days
    active.discard(None)
    has_therapy = _has_therapy(patient_id)
    weights = settings['weights']['with_therapy' if has_therapy else 'without_therapy']
    interval = settings['assessment_interval_days']
    last_assessment = max(assessed - {None}, default=None)
    assessment_fresh = bool(last_assessment and (today - last_assessment).days < interval)

    in_window = lambda values: sum(1 for day in values if day and first <= day <= today)
    dose_credit = in_window(taken) + settings['missed_dose_credit'] * in_window(missed)
    score = round(100 * (
        weights['drug'] * drug_fresh
        + weights['report'] * in_window(reports) / window
        + weights['medication'] * dose_credit / window
        + weights['assessment'] * assessment_fresh
    ))

    last_active = max(active, default=None)
    idle_days = (today - last_active).days if last_active else None
    missed_recent = in_window(missed)
    if last_active is None:
        mood_id = 'calm'
    elif idle_days >= settings['idle']['sad_days'] or (has_therapy and missed_recent >= settings['missed_doses_sad']):
        mood_id = 'sad'
    elif idle_days >= settings['idle']['sleepy_days']:
        mood_id = 'sleepy'
    else:
        scored = [item for item in settings['moods'] if item['min_score'] is not None and score >= item['min_score']]
        mood_id = scored[-1]['id']

    pending = [item for item in tasks if item['status'] == 'pending']
    next_assessment = last_assessment + timedelta(days=interval) if last_assessment else today
    next_drug = last_drug + timedelta(days=settings['drug_survey_interval_days']) if last_drug else today
    today_items = [
        {'id': 'drug', 'title': 'Анкета о назначенном препарате', 'done': drug_fresh, 'view': 'drug-survey',
         'hint': f'Следующая — с {next_drug.strftime("%d.%m")}' if drug_fresh else 'Сон, эмоции, тело — раз в 2 недели, ~10 минут'},
        {'id': 'report', 'title': 'Отметить самочувствие', 'done': today in reports, 'view': 'report',
         'hint': 'Готово на сегодня' if today in reports else 'Минута на три шкалы'},
    ]
    if has_therapy:
        dose_done = today in taken or today in missed
        today_items.append({'id': 'medication', 'title': 'Отметить приём терапии', 'done': dose_done, 'view': 'plan',
                            'hint': 'Готово на сегодня' if dose_done else 'Даже пропуск лучше отметить'})
    today_items.append({'id': 'assessment', 'title': 'Пройти опросник', 'done': assessment_fresh, 'view': 'assessments',
                        'hint': f'Следующий — с {next_assessment.strftime("%d.%m")}' if assessment_fresh else 'PHQ-9 или GAD-7, раз в две недели'})
    if pending:
        today_items.append({'id': 'tasks', 'title': 'Выполнить задачи врача', 'done': False, 'view': 'plan',
                            'hint': f'Ожидают выполнения: {len(pending)}'})

    mood = _mood(mood_id)
    order = [item['id'] for item in settings['moods']]
    return {
        'name': settings['name'],
        'mood': mood_id,
        'rank': order.index(mood_id),
        'title': mood['title'],
        'message': mood['message'] if last_active else 'Привет! Я Нейрон. Отмечайте самочувствие и терапию — и я буду расцветать вместе с вашим наблюдением.',
        'score': score,
        'streak': _streak(active, today),
        'idle_days': idle_days,
        'has_therapy': has_therapy,
        'missed_recent': missed_recent,
        'week': [{
            'date': day.isoformat(),
            'report': day in reports,
            'medication': 'taken' if day in taken else 'missed' if day in missed else None,
            'assessment': day in assessed,
            'drug': day in drug_days,
            'active': day in active,
        } for day in days],
        'today': today_items,
        'moods': [{'id': item['id'], 'title': item['title']} for item in settings['moods']],
        'principles': settings['principles'],
    }
