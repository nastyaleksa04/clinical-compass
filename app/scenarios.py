import json
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from app import db
from app import scales as scale_engine

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "config" / "demo_scenarios.json"
SEED_KEY = "demo_scenarios_seed_v1"
CLINICAL_SEED_KEY = "demo_clinical_profiles_seed_v1"


@lru_cache(maxsize=1)
def catalogue() -> dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def public_scenario(patient_id: int) -> dict[str, Any] | None:
    item = next((x for x in catalogue()["scenarios"] if x["patient_id"] == patient_id), None)
    return dict(item) if item else None


def attach_to_patients(patients: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for patient in patients:
        patient["scenario"] = public_scenario(patient["id"])
    return patients


def _at(days_ago: int, hour_offset: int = 0) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago, hours=hour_offset)).isoformat()


def _assessment(database, patient_id: int, scale_id: str, answers: list[int], days_ago: int, reviewed: bool = True) -> int:
    result = scale_engine.score(scale_id, answers)
    cursor = database.execute(
        """INSERT INTO assessments(
               patient_id, scale_id, answers_json, total, severity, alert,
               alert_codes_json, reviewed, created_at
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            patient_id, scale_id, json.dumps(answers), result["total"], result["severity"],
            int(result["alert"]), json.dumps(result["alert_codes"]), int(reviewed), _at(days_ago),
        ),
    )
    return int(cursor.lastrowid)


def _route(database, patient_id: int, level: str, code: str, text: str, source_id: int, alert: bool = False) -> None:
    created_at = _at(0, 1)
    cursor = database.execute(
        """INSERT INTO routing_signals(
               patient_id, level, reason_code, reason_text, source_type, source_id, created_at
           ) VALUES (?, ?, ?, ?, 'demo_scenario', ?, ?)""",
        (patient_id, level, code, text, source_id, created_at),
    )
    if alert:
        database.execute(
            """INSERT INTO alerts(signal_id, patient_id, actions_json, triggered_at)
               VALUES (?, ?, ?, ?)""",
            (cursor.lastrowid, patient_id, json.dumps(["patient_emergency_guidance", "doctor_notification"]), created_at),
        )


def seed() -> int:
    with db.connection() as database:
        if database.execute("SELECT 1 FROM app_meta WHERE key = ?", (SEED_KEY,)).fetchone():
            return 0

        database.executemany(
            """INSERT INTO patients(id, doctor_id, name, initials, age, note)
               VALUES (?, 1, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET name=excluded.name, initials=excluded.initials,
                   age=excluded.age, note=excluded.note""",
            [
                (2, "Мария Соколова", "МС", 34, "Стабильная динамика · 3 недели"),
                (3, "Ольга Лебедева", "ОЛ", 29, "Проверка противопоказаний"),
                (4, "Илья Морозов", "ИМ", 41, "Требуется решение о маршрутизации"),
                (5, "Елена Орлова", "ЕО", 30, "Критический алерт"),
            ],
        )
        for patient_id, name in [(2, "Алексей Соколов"), (3, "Игорь Лебедев"), (4, "Анна Морозова"), (5, "Светлана Орлова")]:
            database.execute(
                """INSERT OR IGNORE INTO patient_profiles(
                       patient_id, phone, email, emergency_name, emergency_phone,
                       consent_accepted_at, updated_at
                   ) VALUES (?, '+7 900 000-00-00', 'demo@example.com', ?, '+7 900 000-00-09', ?, ?)""",
                (patient_id, name, _at(30), _at(1)),
            )

        # Сценарий 2: устойчивая положительная динамика.
        for days, gad in [(21, [2, 2, 2, 2, 1, 1, 1]), (7, [1, 1, 1, 1, 1, 0, 0]), (0, [1, 1, 1, 0, 0, 0, 0])]:
            _assessment(database, 2, "gad7", gad, days)
        for days, mood, anxiety, sleep in [(6, 3, 3, 3), (3, 4, 2, 4), (0, 4, 2, 4)]:
            database.execute(
                "INSERT INTO reports(patient_id,mood,anxiety,sleep,comment,urgent,reviewed,created_at) VALUES (2,?,?,?,?,0,1,?)",
                (mood, anxiety, sleep, "Состояние постепенно улучшается.", _at(days)),
            )
        for index in range(7):
            database.execute(
                "INSERT INTO medication_checkins(patient_id,taken,side_effect,side_effect_severity,created_at) VALUES (2,1,'','none',?)",
                (_at(index),),
            )
        database.execute(
            "INSERT INTO plans(patient_id,text,confirmed_by,created_at) VALUES (2,?,?,?)",
            ("Продолжить наблюдение. Повторить GAD-7 через 14 дней. Не менять терапию самостоятельно.", "Елена Крылова", _at(2)),
        )

        # Сценарий 3: противопоказание — беременность.
        _assessment(database, 3, "gad7", [2, 2, 2, 2, 2, 1, 1], 0)
        database.execute(
            "INSERT INTO reports(patient_id,mood,anxiety,sleep,comment,urgent,reviewed,created_at) VALUES (3,3,4,2,'Беременность 10 недель, усилилась тревога.',0,1,?)",
            (_at(0),),
        )

        # Сценарий 4: выраженная тревожно-депрессивная симптоматика.
        phq4 = _assessment(database, 4, "phq9", [2, 2, 2, 2, 2, 2, 2, 2, 0], 0, False)
        _assessment(database, 4, "gad7", [3, 3, 2, 2, 2, 2, 2], 0, False)
        database.execute(
            "INSERT INTO reports(patient_id,mood,anxiety,sleep,comment,urgent,reviewed,created_at) VALUES (4,2,5,2,'Трудно работать и общаться с близкими.',0,0,?)",
            (_at(0),),
        )
        _route(database, 4, "recommended", "mixed_high_scores", "Высокая выраженность тревожных и депрессивных симптомов: рекомендуется консультация психиатра.", phq4)

        # Сценарий 5: ненулевой ответ на пункт 9 PHQ-9 и срочный запрос.
        phq5 = _assessment(database, 5, "phq9", [3, 3, 3, 3, 2, 2, 2, 2, 1], 0, False)
        _assessment(database, 5, "gad7", [3, 3, 3, 2, 2, 2, 2], 0, False)
        database.execute(
            "INSERT INTO reports(patient_id,mood,anxiety,sleep,comment,urgent,reviewed,created_at) VALUES (5,1,5,1,'Мне резко стало хуже, нужна срочная связь.',1,0,?)",
            (_at(0),),
        )
        _route(database, 5, "mandatory", "self_harm_response", "Ненулевой ответ на пункт 9 PHQ-9: требуется немедленная клиническая оценка.", phq5, True)

        database.execute("INSERT INTO app_meta(key, value) VALUES (?, ?)", (SEED_KEY, catalogue()["version"]))
        return 4


def seed_clinical_profiles() -> int:
    with db.connection() as database:
        if database.execute("SELECT 1 FROM app_meta WHERE key = ?", (CLINICAL_SEED_KEY,)).fetchone():
            return 0

    profiles = {
        2: {
            "visit_reason": "Повторный контроль тревожных симптомов",
            "complaints": "Остаточная тревога и эпизодические трудности засыпания",
            "symptom_duration": "Около 3 месяцев",
            "history": "На фоне наблюдения отмечает постепенное улучшение; баллы GAD-7 снижаются.",
            "comorbidities": "Клинически значимые сопутствующие состояния не указаны",
            "current_medications": "Синтетический сценарий: терапия по подтверждённому плану",
            "allergies": "Не отмечает",
            "working_hypothesis": "Тревожная симптоматика с положительной динамикой",
            "psychosis_signs": False,
            "self_harm_concern": False,
            "pregnancy_status": "not_applicable",
        },
        3: {
            "visit_reason": "Усиление тревоги во время беременности",
            "complaints": "Постоянное беспокойство, мышечное напряжение, нарушения сна",
            "symptom_duration": "Около 6 недель",
            "history": "Беременность 10 недель. Сценарий предназначен для проверки противопоказаний.",
            "comorbidities": "Беременность",
            "current_medications": "Не указаны",
            "allergies": "Не отмечает",
            "working_hypothesis": "Тревожная симптоматика; требуется очная клиническая оценка",
            "psychosis_signs": False,
            "self_harm_concern": False,
            "pregnancy_status": "yes",
        },
        4: {
            "visit_reason": "Сочетание тревоги и сниженного настроения",
            "complaints": "Утрата интереса, снижение настроения, выраженная тревога, нарушение сна",
            "symptom_duration": "Более 2 месяцев",
            "history": "PHQ-9 и GAD-7 показывают высокую выраженность симптомов. Пункт 9 PHQ-9 отрицательный.",
            "comorbidities": "Требуют уточнения",
            "current_medications": "Не указаны",
            "allergies": "Не отмечает",
            "working_hypothesis": "Тревожно-депрессивная симптоматика; требуется уточнение диагноза",
            "psychosis_signs": False,
            "self_harm_concern": False,
            "pregnancy_status": "not_applicable",
        },
        5: {
            "visit_reason": "Резкое ухудшение состояния",
            "complaints": "Безнадёжность, выраженная тревога, мысли о причинении себе вреда",
            "symptom_duration": "Ухудшение в последние дни",
            "history": "Ненулевой ответ на пункт 9 PHQ-9 и срочный запрос пациента.",
            "comorbidities": "Не оценены",
            "current_medications": "Требуют срочной сверки при контакте",
            "allergies": "Не оценены",
            "working_hypothesis": "Кризисное состояние; необходима немедленная оценка риска",
            "psychosis_signs": False,
            "self_harm_concern": True,
            "pregnancy_status": "unknown",
        },
    }
    for patient_id, payload in profiles.items():
        db.save_clinical_profile(patient_id, payload, "Елена Крылова")

    with db.connection() as database:
        database.execute(
            "INSERT INTO app_meta(key, value) VALUES (?, ?)",
            (CLINICAL_SEED_KEY, catalogue()["version"]),
        )
    return len(profiles)
