"""«Живые» демо-данные: 2–3 недели наблюдения у каждого синтетического пациента.

Самоотчёты, отметки терапии, PHQ-9/GAD-7, анкеты о препарате, план, задачи и переписка с врачом.
Все даты отсчитываются от момента заполнения, поэтому перед показом удобно пересоздать базу:
`python scripts/seed_demo.py --fresh`. Повторный запуск без --fresh данные не дублирует.
"""

import json
import random
from datetime import datetime, timedelta, timezone
from typing import Any

from app import db
from app import drug_survey
from app import scales as scale_engine

SEED_KEY = "demo_life_seed_v1"
LOCAL = timedelta(hours=3)
DOCTOR = "Елена Крылова"


def _at(days_ago: int, hour: int, minute: int = 0) -> str:
    """Момент в прошлом по местному времени (UTC+3); сегодняшние события не попадают в будущее."""
    now = datetime.now(timezone.utc)
    local_day = (now + LOCAL).date() - timedelta(days=days_ago)
    moment = datetime(local_day.year, local_day.month, local_day.day, hour, minute, tzinfo=timezone.utc) - LOCAL
    if moment > now - timedelta(minutes=5):
        # событие «позже, чем сейчас» сдвигаем в недавнее прошлое, сохраняя порядок внутри дня
        moment = now - timedelta(minutes=5 + (24 * 60 - hour * 60 - minute) / 6)
    return moment.isoformat()


def _answers(total: int, count: int, rng: random.Random, item9: int | None = None) -> list[int]:
    """Ответы шкалы с заданной суммой; для PHQ-9 последний пункт задаётся явно."""
    answers = [0] * count
    free = list(range(count - 1)) if item9 is not None else list(range(count))
    if item9 is not None:
        answers[-1] = item9
        total -= item9
    while total > 0:
        index = rng.choice([i for i in free if answers[i] < 3])
        answers[index] += 1
        total -= 1
    return answers


def _assessment(database, patient_id: int, scale_id: str, total: int, created_at: str, rng: random.Random,
                item9: int = 0, reviewed: bool = True) -> int:
    count = 9 if scale_id == "phq9" else 7
    answers = _answers(total, count, rng, item9 if scale_id == "phq9" else None)
    result = scale_engine.score(scale_id, answers)
    cursor = database.execute(
        """INSERT INTO assessments(patient_id, scale_id, answers_json, total, severity, alert, alert_codes_json, reviewed, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (patient_id, scale_id, json.dumps(answers), result["total"], result["severity"], int(result["alert"]),
         json.dumps(result["alert_codes"]), int(reviewed), created_at),
    )
    return int(cursor.lastrowid)


def _report(database, patient_id: int, mood: int, anxiety: int, sleep: int, comment: str, created_at: str, reviewed: bool = True) -> None:
    database.execute(
        "INSERT INTO reports(patient_id, mood, anxiety, sleep, comment, urgent, reviewed, created_at) VALUES (?, ?, ?, ?, ?, 0, ?, ?)",
        (patient_id, mood, anxiety, sleep, comment, int(reviewed), created_at),
    )


def _checkin(database, patient_id: int, taken: bool, created_at: str, side_effect: str = "", severity: str = "none") -> None:
    database.execute(
        "INSERT INTO medication_checkins(patient_id, taken, side_effect, side_effect_severity, created_at) VALUES (?, ?, ?, ?, ?)",
        (patient_id, int(taken), side_effect, severity, created_at),
    )


def _message(database, patient_id: int, sender: str, body: str, created_at: str, read: bool = True) -> None:
    database.execute(
        "INSERT INTO messages(patient_id, sender_role, body, read_by_patient, read_by_doctor, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (patient_id, sender, body, int(sender == "patient" or read), int(sender == "doctor" or read), created_at),
    )


def _slot(slots: dict[tuple[int, int], int], days_ago: int, hour: int) -> int:
    """Минуты для сообщений одного часа по порядку: ответ врача всегда после вопроса."""
    position = slots.get((days_ago, hour), 0)
    slots[(days_ago, hour)] = position + 1
    return min(58, 6 + 13 * position)


def _task(database, patient_id: int, title: str, category: str, created_at: str, description: str = "",
          due_in_days: int | None = None, completed_at: str | None = None) -> None:
    due = ((datetime.now(timezone.utc) + LOCAL).date() + timedelta(days=due_in_days)).isoformat() if due_in_days is not None else None
    database.execute(
        """INSERT INTO care_tasks(patient_id, title, description, category, due_date, status, completed_at, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (patient_id, title, description, category, due, "completed" if completed_at else "pending", completed_at, created_at),
    )


def _therapy(database, patient_id: int, decision: str, created_at: str, rationale: str, safety_status: str = "no_flags",
             findings: list[dict[str, str]] | None = None, duration: str = "8 недель с контролем через 2 недели") -> None:
    database.execute(
        """INSERT INTO therapy_decisions(patient_id, medication_id, medication_name, indication, dosage, schedule, duration,
               decision, rationale, safety_status, safety_findings_json, source_url, confirmed_by, created_at)
           VALUES (?, 'aviandr', 'АВИАНДР®', 'Генерализованное тревожное расстройство у взрослых', '20 мг',
                   '2 раза в сутки за 30 минут до еды', ?, ?, ?, ?, ?, ?, ?, ?)""",
        (patient_id, duration, decision, rationale, safety_status, json.dumps(findings or [], ensure_ascii=False),
         "https://grls.rosminzdrav.ru/GRLS.aspx", DOCTOR, created_at),
    )


def _drug_report(database, patient_id: int, created_at: str, scores: dict[str, int],
                 context: dict[str, tuple[str, str, str]] | None = None, skip: tuple[str, ...] = (), impact: str = "none",
                 followups: dict[str, bool] | None = None, note: str = "", consent: bool = False) -> dict[str, Any]:
    """Опросник скрытых побочных эффектов. scores — отмеченные пункты (q1…q56 → 0–3), остальные «Нет».
    context — по разделу: (связано ли с лечением, когда появилось, свободный ответ)."""
    context = context or {}
    sections = []
    for section in drug_survey.config()["sections"]:
        if section["id"] in skip:
            sections.append({"section": section["id"], "skipped": True, "answers": {}, "attribution": None, "onset": None, "note": ""})
            continue
        answers = {item["id"]: scores.get(item["id"], 0) for item in section["items"]}
        attribution, onset, section_note = context.get(section["id"], ("unknown", "after_start", ""))
        marked = any(answers.values())
        sections.append({"section": section["id"], "skipped": False, "answers": answers,
                         "attribution": attribution if marked else None, "onset": onset if marked else None, "note": section_note})
    followups = {"q65": False, "q66": False, "q67": False, **(followups or {})}
    cursor = database.execute(
        """INSERT INTO drug_reports(patient_id, drug_id, intake, duration, domains_json, red_flags_json, attribution, impact,
               note, share_consent, created_at) VALUES (?, 'aviandr', '', '', ?, '[]', NULL, ?, ?, ?, ?)""",
        (patient_id, json.dumps({"version": 2, "sections": sections, "followups": followups}, ensure_ascii=False),
         impact, note, int(consent), created_at),
    )
    return {"id": int(cursor.lastrowid), "drug_id": "aviandr", "sections": sections, "followups": followups,
            "red_flags": [], "impact": impact, "note": note, "share_consent": consent}


def _plan(database, patient_id: int, text: str, created_at: str) -> None:
    database.execute(
        """INSERT INTO plans(patient_id, text, confirmed_by, created_at) VALUES (?, ?, ?, ?)
           ON CONFLICT(patient_id) DO UPDATE SET text=excluded.text, confirmed_by=excluded.confirmed_by, created_at=excluded.created_at""",
        (patient_id, text, DOCTOR, created_at),
    )


def _series(start: float, end: float, days: int, rng: random.Random, low: int = 1, high: int = 5) -> list[int]:
    """Плавная траектория со случайными колебаниями ±1 — как в реальных самоотчётах."""
    values = []
    for step in range(days):
        base = start + (end - start) * step / max(1, days - 1)
        values.append(max(low, min(high, round(base + rng.choice((-0.6, 0, 0, 0.4))))))
    return values


ANASTASIA_PROFILE = {
    "visit_reason": "Постоянная тревога и беспокойство, мешающие работе и учёбе",
    "complaints": (
        "Постоянное трудноконтролируемое беспокойство по повседневным поводам (работа, учёба, здоровье близких); "
        "внутреннее напряжение и неспособность расслабиться; напряжение мышц шеи и плеч, головные боли напряжения; "
        "раздражительность; трудности концентрации; засыпание до 1–1,5 часа из-за тревожных мыслей; "
        "сердцебиение и потливость при волнении."
    ),
    "symptom_duration": "Около 8 месяцев, большую часть дней",
    "history": (
        "Тревога нарастала после поступления в магистратуру и начала работы. Панических атак, избегающего поведения, "
        "навязчивостей нет. Ранее не лечилась. Обследована терапевтом: ТТГ в норме, ЭКГ без патологии. "
        "Психоактивные вещества не употребляет, алкоголь эпизодически — рекомендовано исключить на время терапии. "
        "Автомобиль не водит. Наследственность не отягощена."
    ),
    "comorbidities": "Хронических соматических заболеваний нет. СКФ 98 мл/мин/1,73 м², печёночные пробы в норме.",
    "current_medications": "АВИАНДР® 20 мг 2 раза в сутки за 30 минут до еды (4-я неделя). Других препаратов не принимает.",
    "allergies": "Не отягощён",
    "working_hypothesis": "F41.1 Генерализованное тревожное расстройство",
    "psychosis_signs": False,
    "self_harm_concern": False,
    "pregnancy_status": "no",
}

# Ответы по пунктам шкал. GAD-7: 16 → 12 → 14 (неделя сдачи проекта на работе) → 9 → 6 — итоговое снижение
# более чем на 50%. PHQ-9: 7 → 6 → 8 (хуже сон и концентрация в ту же неделю) → 5 → 4. Пункт 9 PHQ-9 всегда 0.
ANASTASIA_SCALES = (
    (28, [3, 3, 3, 2, 1, 2, 2], [1, 1, 2, 1, 0, 0, 2, 0, 0]),
    (21, [2, 2, 2, 2, 1, 2, 1], [1, 1, 2, 1, 0, 0, 1, 0, 0]),
    (14, [2, 3, 2, 2, 1, 2, 2], [1, 1, 3, 1, 0, 0, 2, 0, 0]),
    (7, [1, 2, 2, 1, 0, 2, 1], [0, 1, 2, 1, 0, 0, 1, 0, 0]),
    (1, [1, 1, 1, 1, 0, 1, 1], [0, 0, 2, 1, 0, 0, 1, 0, 0]),
)

# Ежедневные самоотчёты с 28 дней назад до сегодня (настроение и сон: 5 — отлично; тревога: 5 — очень сильная).
# Улучшение не прямое: в неделю сдачи проекта (16–14 дней назад) тревога и сон временно ухудшаются.
ANASTASIA_DAILY = {
    "mood":    [2, 2, 2, 2, 2, 3, 2, 3, 3, 3, 4, 3, 3, 2, 2, 3, 3, 3, 4, 3, 4, 3, 4, 4, 3, 4, 4, 4, 5],
    "anxiety": [5, 5, 5, 5, 4, 4, 4, 4, 3, 3, 3, 3, 4, 5, 4, 4, 3, 3, 3, 3, 2, 3, 2, 2, 3, 2, 2, 2, 1],
    "sleep":   [2, 2, 1, 2, 2, 2, 3, 3, 3, 4, 3, 3, 2, 2, 2, 3, 3, 4, 3, 4, 4, 4, 4, 4, 3, 4, 4, 4, 4],
}


def _scale(database, patient_id: int, scale_id: str, answers: list[int], created_at: str, reviewed: bool = True) -> None:
    result = scale_engine.score(scale_id, answers)
    database.execute(
        """INSERT INTO assessments(patient_id, scale_id, answers_json, total, severity, alert, alert_codes_json, reviewed, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (patient_id, scale_id, json.dumps(answers), result["total"], result["severity"], int(result["alert"]),
         json.dumps(result["alert_codes"]), int(reviewed), created_at),
    )


def _anastasia(database, rng: random.Random) -> None:
    """Генерализованное тревожное расстройство (F41.1) — зарегистрированное показание АВИАНДР® у взрослых. 4 недели терапии."""
    pid = 1
    database.execute("UPDATE patients SET age = 22, note = ? WHERE id = ?", ("ГТР · АВИАНДР® 4 недели · улучшение", pid))

    # День 28: первичный приём — шкалы, чек-лист противопоказаний, решение врача и план.
    gad, phq = ANASTASIA_SCALES[0][1:]
    _scale(database, pid, "phq9", phq, _at(28, 11))
    _scale(database, pid, "gad7", gad, _at(28, 11, 10))
    _therapy(
        database, pid, "approved", _at(28, 12),
        "F41.1 Генерализованное тревожное расстройство, GAD-7 16 (выраженная тревога), PHQ-9 7, пункт 9 — 0. "
        "Показание по инструкции: ГТР у взрослых. Чек-лист: беременность исключена (тест отрицательный), грудное вскармливание, "
        "эпилепсия и органические заболевания мозга, СКФ < 60, печёночная недостаточность, ИМАО, нарушения усвоения лактозы — нет. "
        "Серотонинергические препараты, ингибиторы CYP2D6 и седативные не принимает. Автомобиль не водит, алкоголь обещала исключить.",
        duration="Оценка эффекта через 4 недели; длительность курса определяет врач",
    )
    _plan(database, pid, (
        "Диагноз: F41.1 Генерализованное тревожное расстройство.\n"
        "1. АВИАНДР® (маритупирдин) 20 мг 2 раза в сутки за 30 минут до еды — по инструкции. Оценка эффекта через 4 недели, длительность курса определяет врач.\n"
        "2. На время терапии не употреблять алкоголь и не управлять транспортом.\n"
        "3. Ежедневно: отметка приёма и самоотчёт о самочувствии.\n"
        "4. GAD-7 и PHQ-9 раз в неделю, опросник побочных эффектов раз в 2 недели.\n"
        "5. Вечерняя дыхательная практика 10 минут.\n"
        "6. Консультация через 4 недели или раньше при ухудшении."
    ), _at(28, 12, 15))

    # Еженедельные шкалы.
    for days_ago, gad, phq in ANASTASIA_SCALES[1:]:
        # GAD-7 — основная шкала при ГТР, поэтому заполняется последней и показывается врачу первой
        _scale(database, pid, "phq9", phq, _at(days_ago, 20))
        _scale(database, pid, "gad7", gad, _at(days_ago, 20, 10))

    # Ежедневные самоотчёты; три дня без отметки.
    days = list(range(28, -1, -1))
    moods, anxieties, sleeps = ANASTASIA_DAILY["mood"], ANASTASIA_DAILY["anxiety"], ANASTASIA_DAILY["sleep"]
    comments = {
        28: "Весь день прокручивала тревожные мысли о работе и здоровье мамы. Шея как каменная.",
        27: "Первый день приёма. Засыпала больше часа.",
        25: "Перед совещанием колотилось сердце, вспотели ладони.",
        22: "Голова болит к вечеру, трудно сосредоточиться на учёбе.",
        19: "Заснула минут за 20 — давно такого не было.",
        18: "Тревога всё ещё есть, но вечером получилось отвлечься.",
        16: "Дедлайн по проекту, снова тревожно. Утром проспала приём.",
        15: "Тяжёлая неделя: плохо сплю, напряжение в плечах вернулось.",
        13: "Сдали проект — стало заметно легче.",
        12: "Спокойнее реагирую на задачи на работе.",
        8: "Снились очень яркие цветные сны.",
        6: "Выходные прошли спокойно, гуляла с подругой.",
        2: "Почти не прокручиваю мысли перед сном.",
        0: "Проснулась спокойной, напряжения в плечах нет.",
    }
    for index, days_ago in enumerate(days):
        if days_ago in (24, 17, 10):
            continue
        _report(database, pid, moods[index], anxieties[index], sleeps[index], comments.get(days_ago, ""),
                _at(days_ago, 21, rng.randint(5, 50)), reviewed=days_ago > 0)

    # Отметки приёма с первого дня терапии; один пропуск отмечен честно. Нежелательных реакций не отмечено.
    for days_ago in range(27, -1, -1):
        _checkin(database, pid, days_ago != 16, _at(days_ago, 8, rng.randint(15, 45)))

    # Опросник скрытых побочных эффектов раз в 2 недели. Исходный — на приёме до начала терапии: симптомы ГТР
    # отмечены как «было и раньше», чтобы потом отличать их от новых ощущений. Второй — через 2 недели терапии.
    # Третий ждёт заполнения сегодня: бодрость Нейрона 75% («расцветает»), после опросника Нейрон начинает сиять.
    _drug_report(database, pid, _at(28, 11, 30), {"q5": 3, "q4": 1, "q13": 2, "q24": 2, "q28": 1, "q30": 1},
                 context={"A": ("no", "before", "Засыпаю больше часа из-за мыслей — так уже несколько месяцев."),
                          "B": ("no", "before", ""), "D": ("no", "before", ""),
                          "E": ("no", "before", "Сердце колотится и болит голова, когда волнуюсь.")},
                 impact="marked", note="Заполняю до начала лечения, всё отмеченное было и раньше.", consent=True)
    _drug_report(database, pid, _at(14, 21, 40), {"q1": 2, "q2": 1, "q5": 1, "q24": 1},
                 context={"A": ("unknown", "after_start", "Сны стали цветными и очень яркими, раньше почти не запоминала. "
                                "Засыпать труднее только на неделе дедлайна."),
                          "D": ("no", "before", "Сосредоточиться трудно, когда много работы.")},
                 impact="none", note="Иногда хочется лечь пораньше, чтобы снова увидеть цветной сон.", consent=True)

    # Задачи плана.
    _task(database, pid, "Начать приём АВИАНДР® 20 мг 2 раза в сутки", "therapy", _at(28, 12, 20), "За 30 минут до еды, по инструкции", completed_at=_at(27, 8, 30))
    for days_ago, week in ((21, 1), (14, 2), (7, 3), (1, 4)):
        _task(database, pid, f"GAD-7 и PHQ-9 · {week}-я неделя терапии", "assessment", _at(28, 12, 25), "Еженедельный контроль динамики",
              completed_at=_at(days_ago, 20, 15))
    _task(database, pid, "Вечерняя дыхательная практика 10 минут", "monitoring", _at(28, 12, 30), "Медленный выдох длиннее вдоха")
    _task(database, pid, "Онлайн-консультация: оценка ответа на терапию", "consultation", _at(1, 22), "Через 4 недели терапии", due_in_days=2)

    slots: dict[tuple[int, int], int] = {}
    for days_ago, hour, sender, body in (
        (28, 14, "doctor", "Анастасия, добрый день! По итогам приёма: генерализованное тревожное расстройство. Назначила АВИАНДР® 20 мг 2 раза в сутки за 30 минут до еды — подробности в разделе «Мой план». Отмечайте приём и самочувствие каждый день, через неделю — GAD-7 и PHQ-9."),
        (28, 18, "patient", "Спасибо! Купила по рецепту. Начинать завтра утром?"),
        (28, 18, "doctor", "Да, завтра утром. Если заметите что-то необычное в самочувствии — отметьте в опроснике побочных эффектов или напишите мне."),
        (26, 21, "patient", "Пока изменений не чувствую, по вечерам тревога всё ещё сильная."),
        (26, 21, "doctor", "Это ожидаемо: действие оцениваем постепенно, первый контроль по шкалам через неделю. Продолжайте приём по схеме и вечернюю дыхательную практику."),
        (16, 13, "patient", "Проспала и не выпила утреннюю таблетку. Выпить сейчас две?"),
        (16, 13, "doctor", "Нет, двойную дозу не принимайте. Вечерний приём — как обычно, по схеме. Хорошо, что отметили пропуск."),
        (14, 20, "patient", "Прошла шкалы — GAD-7 14, на прошлой неделе было 12. На работе сдаём проект, снова тревожно и плохо сплю. Лечение перестало помогать?"),
        (14, 21, "doctor", "Анастасия, временное усиление тревоги на фоне сильного стресса — частая ситуация, и по сравнению с исходными 16 баллами улучшение сохраняется. Продолжайте приём по схеме и вечернюю дыхательную практику, дозу не меняйте. Если через неделю не станет легче или появится что-то новое — напишите, обсудим раньше."),
        (13, 19, "patient", "Проект сдали, сегодня уже спокойнее."),
        (7, 20, "patient", "GAD-7 — 9 баллов! Такого не было с весны."),
        (7, 21, "doctor", "Отличная динамика: после напряжённой недели тревога снова снижается. Продолжаем по плану."),
        (8, 21, "patient", "Мне стали сниться очень яркие цветные сны, раньше почти не запоминала. Это нормально?"),
        (8, 22, "doctor", "Спасибо, что рассказали — я видела это и в вашем опроснике. Для нового препарата такие наблюдения особенно ценны. Если сны не тревожат и вы высыпаетесь, менять ничего не нужно. Продолжайте отмечать."),
        (1, 21, "patient", "Иногда даже ложусь пораньше, чтобы снова их увидеть 🙂 А тревоги почти нет."),
        (1, 21, "doctor", "GAD-7 сейчас 6 — лёгкий уровень, снижение больше чем вдвое от исходных 16, несмотря на трудную неделю. Послезавтра на консультации обсудим дальнейший план."),
        (0, 9, "patient", "Доброе утро! Сегодня впервые за долгое время проснулась спокойной."),
    ):
        _message(database, pid, sender, body, _at(days_ago, hour, _slot(slots, days_ago, hour)), read=not (days_ago == 0 and sender == "patient"))


def _maria(database, rng: random.Random) -> None:
    pid = 2
    _therapy(database, pid, "approved", _at(22, 10), "ГТР, GAD-7 13. Противопоказаний нет. Контроль через 2 недели.")
    existing = {6, 3, 0}
    moods, anxieties, sleeps = _series(3, 4, 14, rng), _series(3, 2, 14, rng), _series(3, 4, 14, rng)
    for index, days_ago in enumerate(range(13, -1, -1)):
        if days_ago in existing or days_ago == 10:
            continue
        _report(database, pid, moods[index], anxieties[index], sleeps[index], "", _at(days_ago, 20, rng.randint(0, 50)))
    for days_ago in range(20, 7, -1):
        _checkin(database, pid, True, _at(days_ago, 8, rng.randint(0, 40)))
    for days_ago, phq in ((14, 7), (1, 4)):
        _assessment(database, pid, "phq9", phq, _at(days_ago, 19), rng)
    _drug_report(database, pid, _at(10, 20), {"q36": 1, "q26": 1},
                 context={"F": ("unknown", "after_start", "По вечерам тянет на сладкое."), "E": ("unknown", "after_start", "")},
                 impact="some", note="Сон стал лучше, сил больше.", consent=True)
    _task(database, pid, "Пройти PHQ-9", "assessment", _at(15, 11), completed_at=_at(14, 19, 5))
    _task(database, pid, "Повторить GAD-7", "assessment", _at(1, 11), "Через 2 недели", due_in_days=13)
    slots: dict[tuple[int, int], int] = {}
    for days_ago, hour, sender, body in (
        (12, 18, "patient", "Добрый вечер! Можно ли на фоне Авиандра пить кофе по утрам?"),
        (12, 19, "doctor", "Мария, добрый вечер. Одна-две чашки в первой половине дня допустимы, но кофеин может усиливать тревогу — понаблюдайте за собой."),
        (5, 13, "patient", "Через две недели уезжаю в отпуск. Взять таблетки с запасом?"),
        (5, 15, "doctor", "Да, возьмите на весь отпуск и ещё на 3–4 дня. Приём не прерывайте. Алкоголь во время терапии лучше исключить."),
        (2, 20, "patient", "Сон стал гораздо лучше, сил больше. Спасибо!"),
        (2, 21, "doctor", "Отличная динамика, GAD-7 тоже снизился. Продолжаем по плану."),
    ):
        _message(database, pid, sender, body, _at(days_ago, hour, _slot(slots, days_ago, hour)))


def _olga(database, rng: random.Random) -> None:
    pid = 3
    _therapy(database, pid, "rejected", _at(1, 15),
             "Беременность 10 недель — противопоказание по инструкции. Рекомендованы КПТ и консультация акушера-гинеколога.",
             "not_suitable", [{"field": "pregnancy", "level": "blocked", "text": "Противопоказан при беременности."}])
    _plan(database, pid, "1. Лекарственная терапия тревоги не назначается (беременность).\n2. Курс когнитивно-поведенческой терапии, 8 встреч.\n3. Дыхательные упражнения 2 раза в день.\n4. Ежедневный самоотчёт, GAD-7 раз в неделю.\n5. Совместное наблюдение с акушером-гинекологом.", _at(1, 15, 30))
    moods, anxieties, sleeps = _series(3, 3, 8, rng), _series(4, 4.3, 8, rng), _series(2.4, 2, 8, rng)
    comments = {7: "Тревога за малыша, постоянно прокручиваю мысли.", 4: "Ночью просыпалась три раза.", 2: "Помогли дыхательные упражнения."}
    for index, days_ago in enumerate(range(8, 0, -1)):
        _report(database, pid, moods[index], anxieties[index], sleeps[index], comments.get(days_ago, ""), _at(days_ago, 21, rng.randint(0, 40)))
    _assessment(database, pid, "gad7", 13, _at(8, 20), rng)
    _assessment(database, pid, "phq9", 7, _at(5, 20), rng)
    _task(database, pid, "Записаться на КПТ", "consultation", _at(1, 16), "Психотерапевт клиники, 8 встреч", due_in_days=3)
    _task(database, pid, "Дыхательные упражнения 2 раза в день", "monitoring", _at(1, 16), "Техника 4–7–8, по 5 минут")
    _task(database, pid, "Пройти GAD-7", "assessment", _at(1, 16), due_in_days=6)
    slots: dict[tuple[int, int], int] = {}
    for days_ago, hour, sender, body in (
        (2, 19, "patient", "Здравствуйте. Я беременна, 10 недель. Можно ли мне что-нибудь от тревоги? Совсем не сплю."),
        (2, 20, "doctor", "Ольга, здравствуйте. Спасибо, что сообщили о беременности. Авиандр при беременности противопоказан, поэтому начнём с немедикаментозных методов: КПТ и дыхательные упражнения. Я подготовлю план."),
        (1, 16, "doctor", "План в разделе «Мой план». Пожалуйста, обсудите его и с вашим акушером-гинекологом."),
        (0, 10, "patient", "Спасибо! Записалась к психотерапевту на пятницу."),
    ):
        _message(database, pid, sender, body, _at(days_ago, hour, _slot(slots, days_ago, hour)), read=not (days_ago == 0 and sender == "patient"))


def _ilya(database, rng: random.Random) -> list[dict[str, Any]]:
    pid = 4
    _therapy(database, pid, "approved", _at(11, 12), "Тревога с депрессивными симптомами, GAD-7 13. Противопоказаний нет. Седативные не принимает.")
    moods, anxieties, sleeps = _series(3, 2, 10, rng), _series(3, 5, 10, rng), _series(3, 2, 10, rng)
    comments = {9: "", 6: "Плохо сплю, днём клюю носом.", 3: "На работе всё валится из рук.", 1: "Жена говорит, что я отдалился."}
    for index, days_ago in enumerate(range(10, 0, -1)):
        _report(database, pid, moods[index], anxieties[index], sleeps[index], comments.get(days_ago, ""), _at(days_ago, 22, rng.randint(0, 40)))
    for days_ago in range(10, 0, -1):
        if days_ago in (5, 2):
            _checkin(database, pid, False, _at(days_ago, 11))
        elif days_ago == 7:
            _checkin(database, pid, True, _at(days_ago, 9), "Сонливость днём", "mild")
        else:
            _checkin(database, pid, True, _at(days_ago, 9, rng.randint(0, 40)))
    _assessment(database, pid, "phq9", 11, _at(10, 21), rng)
    _assessment(database, pid, "gad7", 13, _at(10, 21, 10), rng)
    _assessment(database, pid, "phq9", 14, _at(4, 21), rng)
    report = _drug_report(database, pid, _at(3, 22), {"q6": 2, "q4": 1, "q9": 2, "q10": 1, "q41": 3, "q47": 2},
                          context={"A": ("unknown", "after_start", "Днём клюю носом на работе."),
                                   "B": ("unknown", "after_start", ""),
                                   "G": ("yes", "after_start", "Стал меньше интересоваться женой, это сильно беспокоит.")},
                          impact="marked", followups={"q67": True})
    _task(database, pid, "Очная консультация: пересмотр терапии", "consultation", _at(1, 12), "Обсудить влечение, сон и маршрутизацию", due_in_days=1)
    slots: dict[tuple[int, int], int] = {}
    for days_ago, hour, sender, body in (
        (6, 23, "patient", "Доктор, не могу уснуть до двух ночи, а днём хочется спать. Можно пить две таблетки вечером, чтобы спать лучше?"),
        (6, 23, "doctor", "Илья, нет — дозу не меняйте самостоятельно. Двойная доза не улучшит сон и может усилить сонливость. Запишите, пожалуйста, режим сна за неделю."),
        (3, 22, "patient", "Заполнил опросник. Есть деликатный момент — снизилось влечение. Это пройдёт?"),
        (2, 9, "doctor", "Спасибо, что написали, — это важно и не редкость. Обсудим очно, возможно, скорректируем лечение. Записала вас на завтра."),
        (1, 22, "patient", "Хорошо. Но настроение совсем плохое, всё раздражает."),
    ):
        _message(database, pid, sender, body, _at(days_ago, hour, _slot(slots, days_ago, hour)), read=not (days_ago == 1 and sender == "patient"))
    return [{"patient_id": pid, "report": report}]


def _elena(database, rng: random.Random) -> list[dict[str, Any]]:
    pid = 5
    _therapy(database, pid, "approved", _at(19, 12), "ГТР с депрессивными симптомами, GAD-7 14, PHQ-9 13, пункт 9 — 0. Контроль через неделю.")
    moods, anxieties, sleeps = _series(3, 1, 9, rng), _series(3.5, 5, 9, rng), _series(3, 1, 9, rng)
    comments = {8: "Тяжело просыпаться.", 5: "Ничего не хочется.", 3: "Плачу без причины.", 1: "Совсем нет сил."}
    for index, days_ago in enumerate(range(9, 0, -1)):
        if days_ago == 6:
            continue
        _report(database, pid, moods[index], anxieties[index], sleeps[index], comments.get(days_ago, ""), _at(days_ago, 23, rng.randint(0, 40)), reviewed=days_ago > 2)
    for days_ago in range(14, 0, -1):
        _checkin(database, pid, days_ago not in (5, 3, 2, 1), _at(days_ago, 10, rng.randint(0, 40)))
    _assessment(database, pid, "phq9", 13, _at(14, 20), rng)
    _assessment(database, pid, "gad7", 14, _at(14, 20, 10), rng)
    _assessment(database, pid, "phq9", 18, _at(7, 20), rng)
    _assessment(database, pid, "gad7", 17, _at(7, 20, 10), rng)
    report = _drug_report(database, pid, _at(9, 22), {"q3": 2, "q4": 2, "q9": 2, "q10": 3, "q13": 2},
                          context={"A": ("unknown", "after_start", "Снятся тревожные сны."),
                                   "B": ("unknown", "before", "Часто плачу, ничего не радует.")},
                          impact="strong", followups={"q65": True, "q66": True}, note="Не уверена, что лечение помогает.")
    slots: dict[tuple[int, int], int] = {}
    for days_ago, hour, sender, body in (
        (8, 21, "patient", "Здравствуйте. Последнюю неделю стало хуже, плачу по вечерам."),
        (8, 22, "doctor", "Елена, спасибо, что написали. Давайте созвонимся завтра в 12:00. Если станет совсем тяжело — сразу звоните 112."),
        (4, 23, "patient", "Пропускаю таблетки, не вижу смысла их пить."),
        (3, 10, "doctor", "Понимаю, что сейчас тяжело. Пожалуйста, не прекращайте приём самостоятельно — обсудим, что можно изменить. Я позвоню вам сегодня."),
        (1, 23, "patient", "Мне очень плохо. Не знаю, сколько ещё выдержу."),
    ):
        _message(database, pid, sender, body, _at(days_ago, hour, _slot(slots, days_ago, hour)), read=not (days_ago == 1 and sender == "patient"))
    return [{"patient_id": pid, "report": report}]


def seed() -> bool:
    """Заполняет историю наблюдения один раз; возвращает True, если данные добавлены."""
    rng = random.Random(2026)
    with db.connection() as database:
        if database.execute("SELECT 1 FROM app_meta WHERE key = ?", (SEED_KEY,)).fetchone():
            return False
        if database.execute("SELECT COUNT(*) FROM patients").fetchone()[0] < 5:
            return False
        _anastasia(database, rng)
        _maria(database, rng)
        _olga(database, rng)
        reports = _ilya(database, rng) + _elena(database, rng)
        database.execute("INSERT INTO app_meta(key, value) VALUES (?, ?)", (SEED_KEY, datetime.now(timezone.utc).isoformat()))
    db.save_clinical_profile(1, ANASTASIA_PROFILE, DOCTOR)
    # сигналы по анкетам о препарате — через обычные правила, как при отправке пациентом
    for item in reports:
        for signal in drug_survey.signals(item["report"]):
            db.create_routing_signal(item["patient_id"], signal, "drug_report", item["report"]["id"])
    return True


def reset_database() -> None:
    """Очищает все таблицы и заново заполняет демо-стенд: пользователи, сценарии, живые данные «на сегодня»."""
    from app import auth, knowledge, scenarios

    with db.connection() as database:
        database.execute("PRAGMA foreign_keys = OFF")
        tables = [row[0] for row in database.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")]
        for table in tables:
            database.execute(f'DELETE FROM "{table}"')
        if database.execute("SELECT 1 FROM sqlite_master WHERE name = 'sqlite_sequence'").fetchone():
            database.execute("DELETE FROM sqlite_sequence")
    db.init_db()
    scenarios.seed()
    auth.seed_demo_users()
    scenarios.seed_clinical_profiles()
    knowledge.seed_templates()
    seed()


def seconds_until(clock: str, now: datetime | None = None) -> float:
    """Секунды до ближайшего наступления времени «ЧЧ:ММ» по Москве."""
    hour, minute = (int(part) for part in clock.split(":"))
    local = (now or datetime.now(timezone.utc)) + LOCAL
    target = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= local:
        target += timedelta(days=1)
    return (target - local).total_seconds()


async def reset_daily(clock: str) -> None:
    """Фоновая задача демо-стенда: каждый день в заданное время база возвращается к исходному состоянию."""
    import asyncio

    while True:
        await asyncio.sleep(seconds_until(clock))
        await asyncio.to_thread(reset_database)
