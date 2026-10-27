"""Опросник скрытых побочных эффектов: 68 вопросов о самочувствии на фоне назначенного препарата.

Разделы А–И — шкала «Нет / Немного / Заметно / Сильно» (0–3) за последние 2 недели, в каждом разделе
«связано ли с лечением», «появилось ли после начала лечения» и свободный ответ. Раздел К — признаки,
о которых нужно срочно сообщить врачу, раздел Л — влияние на жизнь и лечение. Вопросы — в config/drug_survey.json.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

CONFIG_PATH = Path(__file__).resolve().parents[1] / 'config' / 'drug_survey.json'


@lru_cache(maxsize=1)
def config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding='utf-8'))


def _label(key: str, value: Any) -> str:
    return next((item['label'] for item in config()[key] if item['id'] == value), '')


def _scale_label(value: int) -> str:
    return next(item['label'] for item in config()['scale'] if item['value'] == value)


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    """Проверяет ответы по конфигурации и возвращает очищенную анкету."""
    settings = config()
    if payload['drug_id'] != settings['drug']['id']:
        raise ValueError('Анкета для этого препарата не найдена')
    given = {}
    for answer in payload['sections']:
        if answer['section'] in given:
            raise ValueError('Раздел анкеты указан дважды')
        given[answer['section']] = answer
    known = {section['id'] for section in settings['sections']}
    if set(given) - known:
        raise ValueError('Неизвестный раздел анкеты')

    sections = []
    for section in settings['sections']:
        title = f"{section['letter']}. {section['title']}"
        answer = given.get(section['id'])
        if not answer:
            raise ValueError(f'Ответьте на раздел «{title}»')
        if answer['skipped']:
            if not section.get('sensitive'):
                raise ValueError(f'Раздел «{title}» нельзя пропустить')
            sections.append({'section': section['id'], 'skipped': True, 'answers': {}, 'attribution': None, 'onset': None, 'note': ''})
            continue
        items = {item['id'] for item in section['items']}
        answers = answer['answers']
        if set(answers) != items:
            raise ValueError(f'Ответьте на все вопросы раздела «{title}»')
        if any(value not in (0, 1, 2, 3) for value in answers.values()):
            raise ValueError(f'Недопустимый ответ в разделе «{title}»')
        marked = any(answers.values())
        if marked and (answer['attribution'] not in {item['id'] for item in settings['attribution']}
                       or answer['onset'] not in {item['id'] for item in settings['onset']}):
            raise ValueError(f'В разделе «{title}» укажите, связано ли это с лечением и когда появилось')
        sections.append({
            'section': section['id'], 'skipped': False, 'answers': {key: int(answers[key]) for key in sorted(items, key=lambda x: int(x[1:]))},
            'attribution': answer['attribution'] if marked else None, 'onset': answer['onset'] if marked else None,
            'note': answer['note'].strip(),
        })

    flag_ids = {flag['id'] for flag in settings['red_flags']}
    if set(payload['red_flags']) != flag_ids:
        raise ValueError('Ответьте «Да» или «Нет» на все пункты раздела «Срочно сообщите врачу»')
    followup_ids = {item['id'] for item in settings['followups']}
    if set(payload['followups']) != followup_ids:
        raise ValueError('Ответьте на вопросы о влиянии на лечение')
    return {
        'drug_id': payload['drug_id'],
        'sections': sections,
        'red_flags': [flag['id'] for flag in settings['red_flags'] if payload['red_flags'][flag['id']]],
        'impact': payload['impact'],
        'followups': {key: bool(payload['followups'][key]) for key in sorted(followup_ids)},
        'note': payload['note'].strip(),
        'share_consent': bool(payload['share_consent']),
    }


def _items() -> dict[str, dict[str, Any]]:
    return {item['id']: {**item, 'section': section} for section in config()['sections'] for item in section['items']}


def signals(report: dict[str, Any]) -> list[dict[str, str]]:
    settings = config()
    drug = settings['drug']['name']
    flags = {flag['id']: flag['text'] for flag in settings['red_flags']}
    items = _items()
    result = []
    if report['red_flags']:
        result.append({
            'level': 'mandatory', 'reason_code': 'drug_red_flag',
            'reason_text': f"Опросник по {drug}: пациент отметил признаки для срочной связи — "
                           + '; '.join(flags[flag].lower() for flag in report['red_flags']) + '.',
        })
    severe = [items[key]['text'] for section in report.get('sections', []) for key, value in section['answers'].items() if value == 3]
    thinking_stop = report.get('followups', {}).get('q66')
    if severe or report.get('impact') == 'strong' or thinking_stop:
        reasons = []
        if severe:
            reasons.append('сильно выражено: ' + '; '.join(text.lower() for text in severe[:4]))
        if report.get('impact') == 'strong':
            reasons.append('очень сильно мешает жить')
        if thinking_stop:
            reasons.append('думал(а) прекратить лечение')
        result.append({
            'level': 'recommended', 'reason_code': 'drug_bothersome_effect',
            'reason_text': f"Опросник по {drug}: " + ', '.join(reasons) + '. Стоит обсудить переносимость.',
        })
    if report.get('followups', {}).get('q65'):
        result.append({
            'level': 'recommended', 'reason_code': 'drug_adherence',
            'reason_text': f"Из-за ощущений на фоне {drug} пациент пропускал приём или сам менял дозу; стоит уточнить.",
        })
    return result


def describe(report: dict[str, Any]) -> dict[str, Any]:
    """Подписи и итоги для интерфейса: отмеченные пункты по разделам, флаги, ответы раздела Л."""
    settings = config()
    by_id = {answer['section']: answer for answer in report.get('sections', [])}
    sections, skipped = [], []
    total = marked = strong = 0
    for section in settings['sections']:
        answer = by_id.get(section['id'])
        if not answer:
            continue
        title = f"{section['letter']}. {section['title']}"
        if answer['skipped']:
            skipped.append(title)
            continue
        items = [{'n': item['n'], 'text': item['text'], 'score': answer['answers'][item['id']], 'label': _scale_label(answer['answers'][item['id']])}
                 for item in section['items'] if answer['answers'].get(item['id'])]
        total += sum(answer['answers'].values())
        marked += len(items)
        strong += sum(1 for item in items if item['score'] >= 2)
        if items or answer['note']:
            sections.append({
                'id': section['id'], 'title': title, 'items': items, 'note': answer['note'],
                'attribution': answer['attribution'], 'attribution_label': _label('attribution', answer['attribution']),
                'onset': answer['onset'], 'onset_label': _label('onset', answer['onset']),
            })
    flags = {flag['id']: flag['text'] for flag in settings['red_flags']}
    followups = report.get('followups', {})
    return {
        **report,
        'sections_marked': sections,
        'skipped': skipped,
        'total_score': total,
        'marked_count': marked,
        'strong_count': strong,
        'red_flag_labels': [flags.get(flag, flag) for flag in report.get('red_flags', [])],
        'impact_label': _label('impact', report.get('impact')),
        'followup_labels': [item['text'] for item in settings['followups'] if followups.get(item['id'])],
    }


def insights(reports: list[dict[str, Any]]) -> dict[str, Any]:
    """Обезличенная сводка по всем анкетам препарата."""
    settings = config()
    reports = [report for report in reports if report.get('sections')]
    items = _items()
    counts = {key: [0, 0] for key in items}  # [отмечено ≥1, заметно или сильно ≥2]
    sections = []
    for section in settings['sections']:
        answers = [a for report in reports for a in report['sections'] if a['section'] == section['id'] and not a['skipped']]
        with_symptoms = [a for a in answers if any(a['answers'].values())]
        levels = [0, 0, 0]
        for answer in answers:
            for key, value in answer['answers'].items():
                if value:
                    counts[key][0] += 1
                    counts[key][1] += value >= 2
                    levels[value - 1] += 1
        sections.append({
            'id': section['id'], 'title': f"{section['letter']}. {section['title']}",
            'answered': len(answers), 'with_symptoms': len(with_symptoms),
            'attributed': sum(1 for a in with_symptoms if a['attribution'] == 'yes'),
            'new_onset': sum(1 for a in with_symptoms if a['onset'] == 'after_start'),
            'mild': levels[0], 'marked': levels[1], 'strong': levels[2],
        })
    top = sorted(((key, value) for key, value in counts.items() if value[0]), key=lambda pair: (-pair[1][0], -pair[1][1], items[pair[0]]['n']))
    notes = []
    for report in reports:
        for answer in report['sections']:
            if answer['note']:
                section = next(s for s in settings['sections'] if s['id'] == answer['section'])
                notes.append({'text': answer['note'], 'section': f"{section['letter']}. {section['title']}", 'created_at': report['created_at']})
        if report['note']:
            notes.append({'text': report['note'], 'section': 'Что-то ещё необычное', 'created_at': report['created_at']})
    notes.sort(key=lambda note: note['created_at'], reverse=True)
    return {
        'drug': settings['drug'],
        'reports': len(reports),
        'patients': len({report['patient_id'] for report in reports}),
        'consented': sum(1 for report in reports if report['share_consent']),
        'red_flags': sum(1 for report in reports if report['red_flags']),
        'thinking_stop': sum(1 for report in reports if report.get('followups', {}).get('q66')),
        'sections': sections,
        'top_items': [{'n': items[key]['n'], 'text': items[key]['text'], 'section': items[key]['section']['letter'],
                       'count': value[0], 'strong': value[1]} for key, value in top[:10]],
        'notes': notes[:20],
    }
