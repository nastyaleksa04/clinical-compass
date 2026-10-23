from typing import Any, Literal

RoutingLevel = Literal['mandatory', 'recommended']
HIGH_SCORE_THRESHOLD = 15


def report_signal(report: dict[str, Any]) -> dict[str, str] | None:
    if report.get('urgent'):
        return {
            'level': 'mandatory',
            'reason_code': 'urgent_patient_request',
            'reason_text': 'Пациент сообщил о резком ухудшении и запросил срочную связь.',
        }
    return None


def assessment_signal(scale_id: str, result: dict[str, Any]) -> dict[str, str] | None:
    if 'self_harm_response' in result.get('alert_codes', []):
        return {
            'level': 'mandatory',
            'reason_code': 'self_harm_response',
            'reason_text': 'Ненулевой ответ на вопрос PHQ-9 о смерти или причинении себе вреда.',
        }
    if result.get('total', 0) >= HIGH_SCORE_THRESHOLD:
        return {
            'level': 'recommended',
            'reason_code': 'high_screening_score',
            'reason_text': f'Высокая выраженность симптомов по {scale_id.upper()}; требуется клиническая оценка.',
        }
    return None


def checkin_signal(checkin: dict[str, Any]) -> dict[str, str] | None:
    if checkin.get('side_effect_severity') == 'severe':
        return {
            'level': 'mandatory',
            'reason_code': 'severe_adverse_event',
            'reason_text': 'Пациент сообщил о выраженной нежелательной реакции на фоне терапии.',
        }
    if not checkin.get('taken'):
        return {
            'level': 'recommended',
            'reason_code': 'missed_therapy',
            'reason_text': 'Пациент отметил пропуск назначенной терапии; стоит уточнить причину.',
        }
    return None
