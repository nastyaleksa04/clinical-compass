import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = Path(os.environ.get("CLINICAL_COMPASS_DB", DATA_DIR / "clinical_compass.db"))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    database = sqlite3.connect(DB_PATH)
    database.row_factory = sqlite3.Row
    database.execute("PRAGMA foreign_keys = ON")
    try:
        yield database
        database.commit()
    finally:
        database.close()


def init_db() -> None:
    with connection() as database:
        database.executescript(
            """
            CREATE TABLE IF NOT EXISTS patients (
                id INTEGER PRIMARY KEY,
                doctor_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                initials TEXT NOT NULL,
                age INTEGER NOT NULL,
                note TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
                mood INTEGER NOT NULL CHECK(mood BETWEEN 1 AND 5),
                anxiety INTEGER NOT NULL CHECK(anxiety BETWEEN 1 AND 5),
                sleep INTEGER NOT NULL CHECK(sleep BETWEEN 1 AND 5),
                comment TEXT NOT NULL DEFAULT '',
                urgent INTEGER NOT NULL DEFAULT 0,
                reviewed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS plans (
                patient_id INTEGER PRIMARY KEY REFERENCES patients(id) ON DELETE CASCADE,
                text TEXT NOT NULL,
                confirmed_by TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS therapy_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
                medication_id TEXT NOT NULL,
                medication_name TEXT NOT NULL,
                indication TEXT NOT NULL DEFAULT '',
                dosage TEXT NOT NULL DEFAULT '',
                schedule TEXT NOT NULL DEFAULT '',
                duration TEXT NOT NULL DEFAULT '',
                decision TEXT NOT NULL CHECK(decision IN ('approved', 'rejected', 'deferred', 'cancelled')),
                rationale TEXT NOT NULL DEFAULT '',
                safety_status TEXT NOT NULL,
                safety_findings_json TEXT NOT NULL DEFAULT '[]',
                source_url TEXT NOT NULL DEFAULT '',
                confirmed_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                cancelled_at TEXT
            );
            CREATE TABLE IF NOT EXISTS assessments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
                scale_id TEXT NOT NULL,
                answers_json TEXT NOT NULL,
                total INTEGER NOT NULL,
                severity TEXT NOT NULL,
                alert INTEGER NOT NULL DEFAULT 0,
                alert_codes_json TEXT NOT NULL DEFAULT '[]',
                reviewed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS medication_checkins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
                taken INTEGER NOT NULL DEFAULT 0,
                side_effect TEXT NOT NULL DEFAULT '',
                side_effect_severity TEXT NOT NULL DEFAULT 'none'
                    CHECK(side_effect_severity IN ('none', 'mild', 'moderate', 'severe')),
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS care_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL CHECK(category IN ('therapy', 'assessment', 'consultation', 'monitoring')),
                due_date TEXT,
                status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'completed', 'cancelled')),
                completed_at TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
                sender_role TEXT NOT NULL CHECK(sender_role IN ('patient', 'doctor')),
                body TEXT NOT NULL,
                read_by_patient INTEGER NOT NULL DEFAULT 0,
                read_by_doctor INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS routing_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
                level TEXT NOT NULL CHECK(level IN ('mandatory', 'recommended')),
                reason_code TEXT NOT NULL,
                reason_text TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK(status IN ('pending', 'confirmed', 'dismissed')),
                decision_comment TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                decided_at TEXT,
                UNIQUE(source_type, source_id, reason_code)
            );
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id INTEGER NOT NULL UNIQUE REFERENCES routing_signals(id) ON DELETE CASCADE,
                patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
                status TEXT NOT NULL DEFAULT 'new' CHECK(status IN ('new', 'acknowledged', 'escalated')),
                actions_json TEXT NOT NULL DEFAULT '[]',
                triggered_at TEXT NOT NULL,
                acknowledged_at TEXT,
                response_seconds REAL
            );
            CREATE TABLE IF NOT EXISTS patient_profiles (
                patient_id INTEGER PRIMARY KEY REFERENCES patients(id) ON DELETE CASCADE,
                phone TEXT NOT NULL DEFAULT '',
                email TEXT NOT NULL DEFAULT '',
                emergency_name TEXT NOT NULL DEFAULT '',
                emergency_phone TEXT NOT NULL DEFAULT '',
                reminder_enabled INTEGER NOT NULL DEFAULT 1,
                reminder_time TEXT NOT NULL DEFAULT '20:00',
                notify_messages INTEGER NOT NULL DEFAULT 1,
                notify_plan INTEGER NOT NULL DEFAULT 1,
                consent_accepted_at TEXT,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS clinical_profiles (
                patient_id INTEGER PRIMARY KEY REFERENCES patients(id) ON DELETE CASCADE,
                visit_reason TEXT NOT NULL DEFAULT '',
                complaints TEXT NOT NULL DEFAULT '',
                symptom_duration TEXT NOT NULL DEFAULT '',
                history TEXT NOT NULL DEFAULT '',
                comorbidities TEXT NOT NULL DEFAULT '',
                current_medications TEXT NOT NULL DEFAULT '',
                allergies TEXT NOT NULL DEFAULT '',
                working_hypothesis TEXT NOT NULL DEFAULT '',
                psychosis_signs INTEGER NOT NULL DEFAULT 0,
                self_harm_concern INTEGER NOT NULL DEFAULT 0,
                pregnancy_status TEXT NOT NULL DEFAULT 'unknown'
                    CHECK(pregnancy_status IN ('unknown', 'no', 'yes', 'not_applicable')),
                updated_by TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS app_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS kb_articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                category TEXT NOT NULL CHECK(category IN ('scale', 'therapy', 'protocol', 'note')),
                summary TEXT NOT NULL DEFAULT '',
                body TEXT NOT NULL,
                tags_json TEXT NOT NULL DEFAULT '[]',
                source_url TEXT NOT NULL DEFAULT '',
                author TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_therapy_decisions_patient_created
            ON therapy_decisions(patient_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_reports_patient_created
            ON reports(patient_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_assessments_patient_created
            ON assessments(patient_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_checkins_patient_created
            ON medication_checkins(patient_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_signals_patient_status
            ON routing_signals(patient_id, status, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_messages_patient_created
            ON messages(patient_id, created_at ASC);
            CREATE INDEX IF NOT EXISTS idx_tasks_patient_status_due
            ON care_tasks(patient_id, status, due_date);
            CREATE INDEX IF NOT EXISTS idx_alerts_status_triggered
            ON alerts(status, triggered_at DESC);
            """
        )
        if database.execute("SELECT COUNT(*) FROM patients").fetchone()[0] == 0:
            database.executemany(
                "INSERT INTO patients(id, doctor_id, name, initials, age, note) VALUES (?, 1, ?, ?, ?, ?)",
                [
                    (1, "Анастасия Александрова", "АА", 22, "Наблюдение · 3 недели"),
                    (2, "Мария Соколова", "МС", 34, "Следующий контроль 24 октября"),
                    (3, "Илья Морозов", "ИМ", 41, "План подтверждён"),
                    (4, "Елена Орлова", "ЕО", 30, "Ожидается самоотчёт"),
                ],
            )
        created_at = now_iso()
        database.execute(
            """INSERT OR IGNORE INTO patient_profiles(
                   patient_id, phone, email, emergency_name, emergency_phone, consent_accepted_at, updated_at
               ) VALUES (1, '+7 900 000-00-01', 'patient@example.com', 'Ирина Александрова', '+7 900 000-00-02', ?, ?)""",
            (created_at, created_at),
        )


def row_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row else None


def get_patient(patient_id: int) -> dict[str, Any] | None:
    with connection() as database:
        return row_dict(database.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone())


def get_patients(doctor_id: int = 1) -> list[dict[str, Any]]:
    with connection() as database:
        rows = database.execute(
            """
            SELECT p.*,
                   r.id AS latest_report_id,
                   r.mood AS latest_mood,
                   r.anxiety AS latest_anxiety,
                   r.sleep AS latest_sleep,
                   r.urgent AS latest_urgent,
                   r.reviewed AS latest_report_reviewed,
                   r.created_at AS latest_report_at,
                   a.id AS latest_assessment_id,
                   a.scale_id AS latest_scale_id,
                   a.total AS latest_scale_total,
                   a.severity AS latest_scale_severity,
                   a.alert AS latest_scale_alert,
                   a.reviewed AS latest_scale_reviewed,
                   a.created_at AS latest_scale_at,
                   (SELECT COUNT(*) FROM routing_signals s WHERE s.patient_id=p.id AND s.status='pending') AS pending_signals,
                   (SELECT COUNT(*) FROM routing_signals s WHERE s.patient_id=p.id AND s.status='pending' AND s.level='mandatory') AS mandatory_signals,
                   (SELECT COUNT(*) FROM messages m WHERE m.patient_id=p.id AND m.sender_role='patient' AND m.read_by_doctor=0) AS unread_messages,
                   (SELECT body FROM messages m WHERE m.patient_id=p.id ORDER BY m.created_at DESC, m.id DESC LIMIT 1) AS latest_message
            FROM patients p
            LEFT JOIN reports r ON r.id = (
                SELECT id FROM reports WHERE patient_id = p.id
                ORDER BY created_at DESC, id DESC LIMIT 1
            )
            LEFT JOIN assessments a ON a.id = (
                SELECT id FROM assessments WHERE patient_id = p.id
                ORDER BY created_at DESC, id DESC LIMIT 1
            )
            WHERE p.doctor_id = ?
            ORDER BY mandatory_signals DESC, pending_signals DESC, CASE
                WHEN a.alert = 1 AND a.reviewed = 0 THEN 0
                WHEN r.reviewed = 0 AND r.id IS NOT NULL THEN 1
                ELSE 2 END,
                COALESCE(a.created_at, r.created_at) DESC, p.name
            """,
            (doctor_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def get_reports(patient_id: int, limit: int = 30) -> list[dict[str, Any]]:
    with connection() as database:
        rows = database.execute(
            "SELECT * FROM reports WHERE patient_id = ? ORDER BY created_at DESC, id DESC LIMIT ?",
            (patient_id, limit),
        ).fetchall()
        return [{**dict(row), "urgent": bool(row["urgent"]), "reviewed": bool(row["reviewed"])} for row in rows]


def create_report(patient_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    created_at = now_iso()
    with connection() as database:
        cursor = database.execute(
            """INSERT INTO reports(patient_id, mood, anxiety, sleep, comment, urgent, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (patient_id, payload["mood"], payload["anxiety"], payload["sleep"], payload["comment"], int(payload["urgent"]), created_at),
        )
        row = database.execute("SELECT * FROM reports WHERE id = ?", (cursor.lastrowid,)).fetchone()
        result = dict(row)
        result["urgent"] = bool(result["urgent"])
        result["reviewed"] = bool(result["reviewed"])
        return result


def get_assessments(patient_id: int, limit: int = 50) -> list[dict[str, Any]]:
    with connection() as database:
        rows = database.execute(
            "SELECT * FROM assessments WHERE patient_id = ? ORDER BY created_at DESC, id DESC LIMIT ?",
            (patient_id, limit),
        ).fetchall()
        results = []
        for row in rows:
            item = dict(row)
            item["answers"] = json.loads(item.pop("answers_json"))
            item["alert_codes"] = json.loads(item.pop("alert_codes_json"))
            item["alert"] = bool(item["alert"])
            item["reviewed"] = bool(item["reviewed"])
            results.append(item)
        return results


def create_assessment(patient_id: int, scale_id: str, answers: list[int], result: dict[str, Any]) -> dict[str, Any]:
    created_at = now_iso()
    with connection() as database:
        cursor = database.execute(
            """INSERT INTO assessments(
                   patient_id, scale_id, answers_json, total, severity,
                   alert, alert_codes_json, created_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                patient_id, scale_id, json.dumps(answers), result["total"], result["severity"],
                int(result["alert"]), json.dumps(result["alert_codes"]), created_at,
            ),
        )
        assessment_id = cursor.lastrowid
    return next(item for item in get_assessments(patient_id) if item["id"] == assessment_id)


def create_routing_signal(patient_id: int, signal: dict[str, str], source_type: str, source_id: int) -> dict[str, Any]:
    created_at = now_iso()
    with connection() as database:
        database.execute(
            "INSERT OR IGNORE INTO routing_signals(patient_id, level, reason_code, reason_text, source_type, source_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (patient_id, signal['level'], signal['reason_code'], signal['reason_text'], source_type, source_id, created_at),
        )
        row = database.execute(
            'SELECT * FROM routing_signals WHERE source_type = ? AND source_id = ? AND reason_code = ?',
            (source_type, source_id, signal['reason_code']),
        ).fetchone()
        result = dict(row)
        if signal['level'] == 'mandatory':
            actions = json.dumps(['patient_emergency_guidance', 'doctor_notification'])
            database.execute(
                'INSERT OR IGNORE INTO alerts(signal_id, patient_id, actions_json, triggered_at) VALUES (?, ?, ?, ?)',
                (result['id'], patient_id, actions, created_at),
            )
        return result


def refresh_and_get_alerts(escalation_seconds: int) -> list[dict[str, Any]]:
    current = datetime.now(timezone.utc)
    with connection() as database:
        rows = database.execute(
            "SELECT a.*, p.name AS patient_name, p.initials, s.reason_code, s.reason_text FROM alerts a JOIN patients p ON p.id=a.patient_id JOIN routing_signals s ON s.id=a.signal_id ORDER BY CASE a.status WHEN 'new' THEN 0 WHEN 'escalated' THEN 1 ELSE 2 END, a.triggered_at DESC"
        ).fetchall()
        results = []
        for row in rows:
            item = dict(row)
            if item['status'] == 'new':
                elapsed = (current - datetime.fromisoformat(item['triggered_at'])).total_seconds()
                if elapsed >= escalation_seconds:
                    item['status'] = 'escalated'
                    database.execute("UPDATE alerts SET status='escalated' WHERE id=?", (item['id'],))
            item['actions'] = json.loads(item.pop('actions_json'))
            results.append(item)
        return results


def acknowledge_alert(alert_id: int) -> dict[str, Any] | None:
    acknowledged_at = now_iso()
    with connection() as database:
        row = database.execute('SELECT * FROM alerts WHERE id = ?', (alert_id,)).fetchone()
        if not row:
            return None
        if row['status'] != 'acknowledged':
            response = (datetime.fromisoformat(acknowledged_at) - datetime.fromisoformat(row['triggered_at'])).total_seconds()
            database.execute(
                "UPDATE alerts SET status='acknowledged', acknowledged_at=?, response_seconds=? WHERE id=?",
                (acknowledged_at, response, alert_id),
            )
        return row_dict(database.execute('SELECT * FROM alerts WHERE id = ?', (alert_id,)).fetchone())


def get_checkins(patient_id: int, limit: int = 30) -> list[dict[str, Any]]:
    with connection() as database:
        rows = database.execute(
            'SELECT * FROM medication_checkins WHERE patient_id = ? ORDER BY created_at DESC, id DESC LIMIT ?',
            (patient_id, limit),
        ).fetchall()
        return [{**dict(row), 'taken': bool(row['taken'])} for row in rows]


def create_checkin(patient_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    created_at = now_iso()
    with connection() as database:
        cursor = database.execute(
            'INSERT INTO medication_checkins(patient_id, taken, side_effect, side_effect_severity, created_at) VALUES (?, ?, ?, ?, ?)',
            (patient_id, int(payload['taken']), payload['side_effect'], payload['side_effect_severity'], created_at),
        )
        checkin_id = cursor.lastrowid
    return next(item for item in get_checkins(patient_id) if item['id'] == checkin_id)


def adherence_summary(patient_id: int) -> dict[str, Any]:
    checkins = get_checkins(patient_id, 30)
    total = len(checkins)
    taken = sum(1 for item in checkins if item['taken'])
    return {
        'total': total, 'taken': taken, 'missed': total - taken,
        'percent': round(taken / total * 100) if total else None,
        'adverse_events': sum(1 for item in checkins if item['side_effect_severity'] != 'none'),
        'severe_events': sum(1 for item in checkins if item['side_effect_severity'] == 'severe'),
    }


def get_routing_signals(patient_id: int, include_unconfirmed: bool = False) -> list[dict[str, Any]]:
    query = 'SELECT * FROM routing_signals WHERE patient_id = ?'
    params: list[Any] = [patient_id]
    if not include_unconfirmed:
        query += " AND status = 'confirmed'"
    query += " ORDER BY CASE level WHEN 'mandatory' THEN 0 ELSE 1 END, created_at DESC, id DESC"
    with connection() as database:
        return [dict(row) for row in database.execute(query, params).fetchall()]


def decide_routing_signal(signal_id: int, status_value: str, comment: str) -> dict[str, Any] | None:
    with connection() as database:
        cursor = database.execute(
            "UPDATE routing_signals SET status = ?, decision_comment = ?, decided_at = ? WHERE id = ? AND status = 'pending'",
            (status_value, comment, now_iso(), signal_id),
        )
        if cursor.rowcount == 0:
            return None
        alert = database.execute('SELECT id FROM alerts WHERE signal_id = ?', (signal_id,)).fetchone()
        if alert:
            acknowledged_at = now_iso()
            source = database.execute('SELECT triggered_at FROM alerts WHERE id = ?', (alert['id'],)).fetchone()
            response = (datetime.fromisoformat(acknowledged_at) - datetime.fromisoformat(source['triggered_at'])).total_seconds()
            database.execute("UPDATE alerts SET status='acknowledged', acknowledged_at=?, response_seconds=? WHERE id=?", (acknowledged_at, response, alert['id']))
        return row_dict(database.execute('SELECT * FROM routing_signals WHERE id = ?', (signal_id,)).fetchone())



def get_clinical_profile(patient_id: int) -> dict[str, Any]:
    with connection() as database:
        row = database.execute(
            "SELECT * FROM clinical_profiles WHERE patient_id = ?", (patient_id,)
        ).fetchone()
    if not row:
        return {
            "patient_id": patient_id,
            "visit_reason": "",
            "complaints": "",
            "symptom_duration": "",
            "history": "",
            "comorbidities": "",
            "current_medications": "",
            "allergies": "",
            "working_hypothesis": "",
            "psychosis_signs": False,
            "self_harm_concern": False,
            "pregnancy_status": "unknown",
            "updated_by": "",
            "updated_at": None,
        }
    result = dict(row)
    result["psychosis_signs"] = bool(result["psychosis_signs"])
    result["self_harm_concern"] = bool(result["self_harm_concern"])
    return result


def save_clinical_profile(patient_id: int, payload: dict[str, Any], updated_by: str) -> dict[str, Any]:
    updated_at = now_iso()
    with connection() as database:
        database.execute(
            """INSERT INTO clinical_profiles(
                   patient_id, visit_reason, complaints, symptom_duration, history,
                   comorbidities, current_medications, allergies, working_hypothesis,
                   psychosis_signs, self_harm_concern, pregnancy_status, updated_by, updated_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(patient_id) DO UPDATE SET
                   visit_reason=excluded.visit_reason,
                   complaints=excluded.complaints,
                   symptom_duration=excluded.symptom_duration,
                   history=excluded.history,
                   comorbidities=excluded.comorbidities,
                   current_medications=excluded.current_medications,
                   allergies=excluded.allergies,
                   working_hypothesis=excluded.working_hypothesis,
                   psychosis_signs=excluded.psychosis_signs,
                   self_harm_concern=excluded.self_harm_concern,
                   pregnancy_status=excluded.pregnancy_status,
                   updated_by=excluded.updated_by,
                   updated_at=excluded.updated_at""",
            (
                patient_id, payload["visit_reason"], payload["complaints"],
                payload["symptom_duration"], payload["history"], payload["comorbidities"],
                payload["current_medications"], payload["allergies"],
                payload["working_hypothesis"], int(payload["psychosis_signs"]),
                int(payload["self_harm_concern"]), payload["pregnancy_status"],
                updated_by, updated_at,
            ),
        )
    return get_clinical_profile(patient_id)




def get_therapy_decisions(patient_id: int, include_internal: bool = False) -> list[dict[str, Any]]:
    query = "SELECT * FROM therapy_decisions WHERE patient_id = ?"
    params: list[Any] = [patient_id]
    if not include_internal:
        query += " AND decision IN ('approved', 'cancelled')"
    query += " ORDER BY created_at DESC, id DESC"
    with connection() as database:
        rows = database.execute(query, params).fetchall()
    results = []
    for row in rows:
        item = dict(row)
        item["safety_findings"] = json.loads(item.pop("safety_findings_json"))
        results.append(item)
    return results


def create_therapy_decision(patient_id: int, payload: dict[str, Any], safety: dict[str, Any], confirmed_by: str) -> dict[str, Any]:
    created_at = now_iso()
    with connection() as database:
        if payload["decision"] == "approved":
            database.execute(
                """UPDATE therapy_decisions SET decision='cancelled', cancelled_at=?
                   WHERE patient_id=? AND medication_id=? AND decision='approved'""",
                (created_at, patient_id, payload["medication_id"]),
            )
        cursor = database.execute(
            """INSERT INTO therapy_decisions(
                   patient_id, medication_id, medication_name, indication, dosage,
                   schedule, duration, decision, rationale, safety_status,
                   safety_findings_json, source_url, confirmed_by, created_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                patient_id, payload["medication_id"], payload["medication_name"],
                payload["indication"], payload["dosage"], payload["schedule"],
                payload["duration"], payload["decision"], payload["rationale"],
                safety["status"], json.dumps(safety["findings"], ensure_ascii=False),
                safety["source"], confirmed_by, created_at,
            ),
        )
        decision_id = int(cursor.lastrowid)
    return next(item for item in get_therapy_decisions(patient_id, include_internal=True) if item["id"] == decision_id)


def cancel_therapy_decision(decision_id: int) -> dict[str, Any] | None:
    cancelled_at = now_iso()
    with connection() as database:
        cursor = database.execute(
            """UPDATE therapy_decisions SET decision='cancelled', cancelled_at=?
               WHERE id=? AND decision='approved'""",
            (cancelled_at, decision_id),
        )
        if cursor.rowcount == 0:
            return None
        patient_id = database.execute(
            "SELECT patient_id FROM therapy_decisions WHERE id=?", (decision_id,)
        ).fetchone()["patient_id"]
    return next(item for item in get_therapy_decisions(patient_id, include_internal=True) if item["id"] == decision_id)


def get_timeline(patient_id: int, include_clinical: bool = False, limit: int = 100) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []

    for item in get_reports(patient_id, limit):
        values = f"Настроение {item['mood']}/5 · тревога {item['anxiety']}/5 · сон {item['sleep']}/5"
        events.append({
            "id": f"report-{item['id']}",
            "type": "report",
            "category": "monitoring",
            "title": "Самоотчёт пациента",
            "summary": item["comment"] or values,
            "details": values,
            "tone": "danger" if item["urgent"] else "neutral",
            "status": "Срочная связь" if item["urgent"] else "Получен",
            "created_at": item["created_at"],
        })

    for item in get_assessments(patient_id, limit):
        events.append({
            "id": f"assessment-{item['id']}",
            "type": "assessment",
            "category": "assessment",
            "title": item["scale_id"].upper(),
            "summary": f"{item['total']} баллов · {item['severity']}",
            "details": "Есть критический ответ" if item["alert"] else "Стандартизированная оценка",
            "tone": "danger" if item["alert"] else "info",
            "status": "Требует оценки" if item["alert"] else "Результат",
            "created_at": item["created_at"],
        })

    for item in get_checkins(patient_id, limit):
        severity = {
            "none": "без нежелательной реакции",
            "mild": "лёгкая реакция",
            "moderate": "умеренная реакция",
            "severe": "выраженная реакция",
        }[item["side_effect_severity"]]
        events.append({
            "id": f"checkin-{item['id']}",
            "type": "checkin",
            "category": "therapy",
            "title": "Отметка терапии",
            "summary": "Принято" if item["taken"] else "Приём пропущен",
            "details": item["side_effect"] or severity,
            "tone": "danger" if item["side_effect_severity"] == "severe" else ("warning" if not item["taken"] else "success"),
            "status": severity,
            "created_at": item["created_at"],
        })

    for item in get_therapy_decisions(patient_id, include_internal=include_clinical):
        decision_label = {
            "approved": "Подтверждено врачом",
            "rejected": "Не применять",
            "deferred": "Решение отложено",
            "cancelled": "Отменено врачом",
        }[item["decision"]]
        regimen = " · ".join(x for x in [item["dosage"], item["schedule"], item["duration"]] if x)
        events.append({
            "id": f"therapy-decision-{item['id']}",
            "type": "therapy_decision",
            "category": "therapy",
            "title": f"{item['medication_name']}: {decision_label}",
            "summary": item["indication"] or item["rationale"] or decision_label,
            "details": regimen or item["rationale"],
            "tone": "success" if item["decision"] == "approved" else ("danger" if item["decision"] == "rejected" else "muted"),
            "status": decision_label,
            "created_at": item["cancelled_at"] or item["created_at"],
        })

    plan = get_plan(patient_id)
    if plan:
        events.append({
            "id": f"plan-{patient_id}",
            "type": "plan",
            "category": "plan",
            "title": "План наблюдения подтверждён",
            "summary": plan["text"],
            "details": f"Подтвердил: {plan['confirmed_by']}",
            "tone": "success",
            "status": "Подтверждено врачом",
            "created_at": plan["created_at"],
        })

    for item in get_care_tasks(patient_id):
        status_label = {"pending": "Ожидает выполнения", "completed": "Выполнено", "cancelled": "Отменено"}[item["status"]]
        events.append({
            "id": f"task-{item['id']}",
            "type": "task",
            "category": "plan",
            "title": item["title"],
            "summary": item["description"] or status_label,
            "details": f"Срок: {item['due_date']}" if item["due_date"] else "Без срока",
            "tone": "success" if item["status"] == "completed" else ("neutral" if item["status"] == "pending" else "muted"),
            "status": status_label,
            "created_at": item["completed_at"] or item["created_at"],
        })

    for item in get_routing_signals(patient_id, include_unconfirmed=include_clinical):
        status_label = {"pending": "Ожидает решения", "confirmed": "Подтверждено", "dismissed": "Отклонено"}[item["status"]]
        events.append({
            "id": f"route-{item['id']}",
            "type": "routing",
            "category": "safety",
            "title": "Маршрутизация: " + ("обязательно" if item["level"] == "mandatory" else "желательно"),
            "summary": item["reason_text"],
            "details": item["decision_comment"] or status_label,
            "tone": "danger" if item["level"] == "mandatory" else "warning",
            "status": status_label,
            "created_at": item["decided_at"] or item["created_at"],
        })

    if include_clinical:
        profile = get_clinical_profile(patient_id)
        if profile["updated_at"]:
            events.append({
                "id": f"clinical-{patient_id}",
                "type": "clinical",
                "category": "clinical",
                "title": "Клиническая сводка обновлена",
                "summary": profile["working_hypothesis"] or profile["visit_reason"] or "Сведения врача сохранены",
                "details": f"Обновил: {profile['updated_by']}",
                "tone": "danger" if profile["self_harm_concern"] or profile["psychosis_signs"] else "info",
                "status": "Врачебная запись",
                "created_at": profile["updated_at"],
            })
        with connection() as database:
            rows = database.execute(
                "SELECT * FROM alerts WHERE patient_id = ? ORDER BY triggered_at DESC", (patient_id,)
            ).fetchall()
        for row in rows:
            item = dict(row)
            status_label = {"new": "Новый", "escalated": "Эскалирован", "acknowledged": "Принят в работу"}[item["status"]]
            events.append({
                "id": f"alert-{item['id']}",
                "type": "alert",
                "category": "safety",
                "title": "Критический алерт",
                "summary": "Система уведомила врача и показала пациенту экстренную инструкцию.",
                "details": status_label,
                "tone": "danger",
                "status": status_label,
                "created_at": item["acknowledged_at"] or item["triggered_at"],
            })

    events.sort(key=lambda item: item["created_at"], reverse=True)
    return events[:limit]


def get_care_tasks(patient_id: int) -> list[dict[str, Any]]:
    with connection() as database:
        rows = database.execute(
            "SELECT * FROM care_tasks WHERE patient_id = ? ORDER BY CASE status WHEN 'pending' THEN 0 WHEN 'completed' THEN 1 ELSE 2 END, due_date IS NULL, due_date, created_at DESC",
            (patient_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def get_care_task(task_id: int) -> dict[str, Any] | None:
    with connection() as database:
        return row_dict(database.execute('SELECT * FROM care_tasks WHERE id = ?', (task_id,)).fetchone())


def create_care_task(patient_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    created_at = now_iso()
    due_date = payload['due_date'].isoformat() if payload.get('due_date') else None
    with connection() as database:
        cursor = database.execute(
            'INSERT INTO care_tasks(patient_id, title, description, category, due_date, created_at) VALUES (?, ?, ?, ?, ?, ?)',
            (patient_id, payload['title'], payload['description'], payload['category'], due_date, created_at),
        )
        return dict(database.execute('SELECT * FROM care_tasks WHERE id = ?', (cursor.lastrowid,)).fetchone())


def update_care_task(task_id: int, status_value: str) -> dict[str, Any] | None:
    completed_at = now_iso() if status_value == 'completed' else None
    with connection() as database:
        cursor = database.execute(
            'UPDATE care_tasks SET status = ?, completed_at = ? WHERE id = ?',
            (status_value, completed_at, task_id),
        )
        if cursor.rowcount == 0:
            return None
        return row_dict(database.execute('SELECT * FROM care_tasks WHERE id = ?', (task_id,)).fetchone())


def get_messages(patient_id: int, limit: int = 100) -> list[dict[str, Any]]:
    with connection() as database:
        rows = database.execute(
            'SELECT * FROM messages WHERE patient_id = ? ORDER BY created_at ASC, id ASC LIMIT ?',
            (patient_id, limit),
        ).fetchall()
        return [
            {**dict(row), 'read_by_patient': bool(row['read_by_patient']), 'read_by_doctor': bool(row['read_by_doctor'])}
            for row in rows
        ]


def create_message(patient_id: int, sender_role: str, body: str) -> dict[str, Any]:
    created_at = now_iso()
    with connection() as database:
        cursor = database.execute(
            'INSERT INTO messages(patient_id, sender_role, body, read_by_patient, read_by_doctor, created_at) VALUES (?, ?, ?, ?, ?, ?)',
            (patient_id, sender_role, body, int(sender_role == 'patient'), int(sender_role == 'doctor'), created_at),
        )
        row = database.execute('SELECT * FROM messages WHERE id = ?', (cursor.lastrowid,)).fetchone()
        result = dict(row)
        result['read_by_patient'] = bool(result['read_by_patient'])
        result['read_by_doctor'] = bool(result['read_by_doctor'])
        return result


def mark_messages_read(patient_id: int, reader_role: str) -> None:
    column = 'read_by_patient' if reader_role == 'patient' else 'read_by_doctor'
    sender = 'doctor' if reader_role == 'patient' else 'patient'
    with connection() as database:
        database.execute(
            f'UPDATE messages SET {column} = 1 WHERE patient_id = ? AND sender_role = ?',
            (patient_id, sender),
        )


def unread_message_count(patient_id: int, reader_role: str) -> int:
    column = 'read_by_patient' if reader_role == 'patient' else 'read_by_doctor'
    sender = 'doctor' if reader_role == 'patient' else 'patient'
    with connection() as database:
        return database.execute(
            f'SELECT COUNT(*) FROM messages WHERE patient_id = ? AND sender_role = ? AND {column} = 0',
            (patient_id, sender),
        ).fetchone()[0]


def mark_items_reviewed(patient_id: int) -> None:
    with connection() as database:
        database.execute("UPDATE reports SET reviewed = 1 WHERE patient_id = ?", (patient_id,))
        database.execute("UPDATE assessments SET reviewed = 1 WHERE patient_id = ?", (patient_id,))


def get_meta(key: str) -> str | None:
    with connection() as database:
        row = database.execute("SELECT value FROM app_meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None


def set_meta(key: str, value: str) -> None:
    with connection() as database:
        database.execute(
            "INSERT INTO app_meta(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def _kb_row(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["tags"] = json.loads(item.pop("tags_json"))
    return item


def get_kb_articles() -> list[dict[str, Any]]:
    with connection() as database:
        rows = database.execute("SELECT * FROM kb_articles ORDER BY updated_at DESC, id DESC").fetchall()
        return [_kb_row(row) for row in rows]


def get_kb_article(article_id: int) -> dict[str, Any] | None:
    with connection() as database:
        row = database.execute("SELECT * FROM kb_articles WHERE id = ?", (article_id,)).fetchone()
        return _kb_row(row) if row else None


def create_kb_article(payload: dict[str, Any], author: str) -> dict[str, Any]:
    created_at = now_iso()
    with connection() as database:
        cursor = database.execute(
            """INSERT INTO kb_articles(title, category, summary, body, tags_json, source_url, author, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (payload["title"], payload["category"], payload["summary"], payload["body"],
             json.dumps(payload["tags"], ensure_ascii=False), payload["source_url"], author, created_at, created_at),
        )
        article_id = cursor.lastrowid
    return get_kb_article(article_id)


def update_kb_article(article_id: int, payload: dict[str, Any]) -> dict[str, Any] | None:
    with connection() as database:
        cursor = database.execute(
            """UPDATE kb_articles SET title = ?, category = ?, summary = ?, body = ?, tags_json = ?, source_url = ?, updated_at = ?
               WHERE id = ?""",
            (payload["title"], payload["category"], payload["summary"], payload["body"],
             json.dumps(payload["tags"], ensure_ascii=False), payload["source_url"], now_iso(), article_id),
        )
        if cursor.rowcount == 0:
            return None
    return get_kb_article(article_id)


def delete_kb_article(article_id: int) -> bool:
    with connection() as database:
        return database.execute("DELETE FROM kb_articles WHERE id = ?", (article_id,)).rowcount > 0


PROFILE_FLAGS = ("reminder_enabled", "notify_messages", "notify_plan")


def get_profile(patient_id: int) -> dict[str, Any]:
    with connection() as database:
        row = database.execute("SELECT * FROM patient_profiles WHERE patient_id = ?", (patient_id,)).fetchone()
    if not row:
        return {
            "patient_id": patient_id, "phone": "", "email": "", "emergency_name": "", "emergency_phone": "",
            "reminder_enabled": True, "reminder_time": "20:00", "notify_messages": True, "notify_plan": True,
            "consent_accepted_at": None, "updated_at": None,
        }
    result = dict(row)
    for flag in PROFILE_FLAGS:
        result[flag] = bool(result[flag])
    return result


def save_profile(patient_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    values = {**payload, **{flag: int(payload[flag]) for flag in PROFILE_FLAGS}}
    with connection() as database:
        database.execute(
            """INSERT INTO patient_profiles(
                   patient_id, phone, email, emergency_name, emergency_phone,
                   reminder_enabled, reminder_time, notify_messages, notify_plan, updated_at
               ) VALUES (:patient_id, :phone, :email, :emergency_name, :emergency_phone,
                   :reminder_enabled, :reminder_time, :notify_messages, :notify_plan, :updated_at)
               ON CONFLICT(patient_id) DO UPDATE SET phone=excluded.phone, email=excluded.email,
                   emergency_name=excluded.emergency_name, emergency_phone=excluded.emergency_phone,
                   reminder_enabled=excluded.reminder_enabled, reminder_time=excluded.reminder_time,
                   notify_messages=excluded.notify_messages, notify_plan=excluded.notify_plan,
                   updated_at=excluded.updated_at""",
            {**values, "patient_id": patient_id, "updated_at": now_iso()},
        )
    return get_profile(patient_id)


def get_plan(patient_id: int) -> dict[str, Any] | None:
    with connection() as database:
        return row_dict(database.execute("SELECT * FROM plans WHERE patient_id = ?", (patient_id,)).fetchone())


def save_plan(patient_id: int, text: str, confirmed_by: str) -> dict[str, Any]:
    created_at = now_iso()
    with connection() as database:
        database.execute(
            """INSERT INTO plans(patient_id, text, confirmed_by, created_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(patient_id) DO UPDATE SET text=excluded.text,
               confirmed_by=excluded.confirmed_by, created_at=excluded.created_at""",
            (patient_id, text, confirmed_by, created_at),
        )
        return dict(database.execute("SELECT * FROM plans WHERE patient_id = ?", (patient_id,)).fetchone())