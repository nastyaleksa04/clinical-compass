from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import alerting
from app import db
from app import knowledge
from app import recommendations
from app import safety
from app import scenarios
from app import therapy
from app import scales as scale_engine

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = PROJECT_ROOT / "dist"
Role = Literal["patient", "doctor"]


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    scenarios.seed()
    scenarios.seed_clinical_profiles()
    knowledge.seed_templates()
    scale_engine.catalogue()
    yield


app = FastAPI(
    title="Клинический компас",
    description="Локальный API прототипа цифрового ассистента врача",
    version="0.12.0",
    lifespan=lifespan,
)


class ReportCreate(BaseModel):
    mood: int = Field(ge=1, le=5)
    anxiety: int = Field(ge=1, le=5)
    sleep: int = Field(ge=1, le=5)
    comment: str = Field(default="", max_length=2000)
    urgent: bool = False


class AssessmentCreate(BaseModel):
    scale_id: str = Field(min_length=1, max_length=30)
    answers: list[int] = Field(min_length=1, max_length=30)


class PlanUpdate(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class MedicationCheckinCreate(BaseModel):
    taken: bool
    side_effect: str = Field(default="", max_length=2000)
    side_effect_severity: Literal["none", "mild", "moderate", "severe"] = "none"


class RoutingDecision(BaseModel):
    status: Literal["confirmed", "dismissed"]
    comment: str = Field(default="", max_length=2000)


class MessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class CareTaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    category: Literal["therapy", "assessment", "consultation", "monitoring"]
    due_date: date | None = None


class CareTaskUpdate(BaseModel):
    status: Literal["pending", "completed", "cancelled"]


class ProfileUpdate(BaseModel):
    phone: str = Field(default="", max_length=30, pattern=r"^[0-9+()\- ]*$")
    email: str = Field(default="", max_length=120, pattern=r"^$|^[^@\s]+@[^@\s]+\.[^@\s]+$")
    emergency_name: str = Field(default="", max_length=120)
    emergency_phone: str = Field(default="", max_length=30, pattern=r"^[0-9+()\- ]*$")
    reminder_enabled: bool = True
    reminder_time: str = Field(default="20:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    notify_messages: bool = True
    notify_plan: bool = True


class ClinicalProfileUpdate(BaseModel):
    visit_reason: str = Field(default="", max_length=500)
    complaints: str = Field(default="", max_length=4000)
    symptom_duration: str = Field(default="", max_length=300)
    history: str = Field(default="", max_length=6000)
    comorbidities: str = Field(default="", max_length=3000)
    current_medications: str = Field(default="", max_length=3000)
    allergies: str = Field(default="", max_length=2000)
    working_hypothesis: str = Field(default="", max_length=1000)
    psychosis_signs: bool = False
    self_harm_concern: bool = False
    pregnancy_status: Literal["unknown", "no", "yes", "not_applicable"] = "unknown"


class KnowledgeArticleWrite(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    category: Literal["scale", "therapy", "protocol", "note"] = "note"
    summary: str = Field(default="", max_length=500)
    body: str = Field(min_length=1, max_length=20000)
    tags: list[Annotated[str, Field(min_length=1, max_length=40)]] = Field(default_factory=list, max_length=10)
    source_url: str = Field(default="", max_length=500, pattern=r"^$|^https?://\S+$")


class TherapyDecisionCreate(BaseModel):
    medication_id: str = Field(min_length=1, max_length=100)
    indication: str = Field(default="", max_length=500)
    dosage: str = Field(default="", max_length=200)
    schedule: str = Field(default="", max_length=300)
    duration: str = Field(default="", max_length=200)
    decision: Literal["approved", "rejected", "deferred"]
    rationale: str = Field(default="", max_length=3000)
    factors: dict[str, bool] = Field(default_factory=dict)


class TherapyCheck(BaseModel):
    medication_id: str = Field(min_length=1, max_length=100)
    factors: dict[str, bool]


def demo_role(x_demo_role: Annotated[str, Header()] = "patient") -> Role:
    if x_demo_role not in {"patient", "doctor"}:
        raise HTTPException(status_code=401, detail="Неизвестная демонстрационная роль")
    return x_demo_role  # type: ignore[return-value]


def require_role(required: Role):
    def check(role: Role = Depends(demo_role)) -> Role:
        if role != required:
            raise HTTPException(status_code=403, detail="Недостаточно прав для этой роли")
        return role
    return check


def patient_bundle(patient_id: int, include_unconfirmed: bool = False) -> dict:
    patient = db.get_patient(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Пациент не найден")
    return {
        "patient": patient,
        "reports": db.get_reports(patient_id),
        "assessments": db.get_assessments(patient_id),
        "plan": db.get_plan(patient_id),
        "checkins": db.get_checkins(patient_id),
        "adherence": db.adherence_summary(patient_id),
        "routing_signals": db.get_routing_signals(patient_id, include_unconfirmed=include_unconfirmed),
        "unread_messages": db.unread_message_count(patient_id, "doctor" if include_unconfirmed else "patient"),
        "tasks": db.get_care_tasks(patient_id),
        "profile": db.get_profile(patient_id),
        "scenario": scenarios.public_scenario(patient_id),
        "clinical_profile": db.get_clinical_profile(patient_id) if include_unconfirmed else None,
        "timeline": db.get_timeline(patient_id, include_clinical=include_unconfirmed),
        "therapy_decisions": db.get_therapy_decisions(patient_id, include_internal=include_unconfirmed),
        "recommendations": recommendations.build(patient_id) if include_unconfirmed else None,
    }


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "clinical-compass", "storage": "sqlite", "version": "0.12.0"}


@app.get("/api/scales")
def available_scales(_: Role = Depends(demo_role)) -> dict:
    return {"version": scale_engine.catalogue()["version"], "scales": scale_engine.public_scales()}


@app.get("/api/state")
def application_state(role: Role = Depends(demo_role)) -> dict:
    if role == "patient":
        return {"role": role, **patient_bundle(1)}
    settings = alerting.config()
    return {
        "role": role,
        "patients": scenarios.attach_to_patients(db.get_patients(doctor_id=1)),
        "alerts": db.refresh_and_get_alerts(settings["escalation_seconds"]),
        "alerting": settings,
    }


@app.get("/api/patients/{patient_id}")
def patient_detail(patient_id: int, _: Role = Depends(require_role("doctor"))) -> dict:
    return patient_bundle(patient_id, include_unconfirmed=True)


@app.post("/api/patients/{patient_id}/reports", status_code=status.HTTP_201_CREATED)
def submit_report(patient_id: int, report: ReportCreate, _: Role = Depends(require_role("patient"))) -> dict:
    if patient_id != 1:
        raise HTTPException(status_code=403, detail="Пациент может изменять только свои данные")
    if not db.get_patient(patient_id):
        raise HTTPException(status_code=404, detail="Пациент не найден")
    saved = db.create_report(patient_id, report.model_dump())
    signal = safety.report_signal(saved)
    if signal:
        db.create_routing_signal(patient_id, signal, "report", saved["id"])
    return saved


@app.post("/api/patients/{patient_id}/assessments", status_code=status.HTTP_201_CREATED)
def submit_assessment(patient_id: int, assessment: AssessmentCreate, _: Role = Depends(require_role("patient"))) -> dict:
    if patient_id != 1:
        raise HTTPException(status_code=403, detail="Пациент может изменять только свои данные")
    if not db.get_patient(patient_id):
        raise HTTPException(status_code=404, detail="Пациент не найден")
    try:
        result = scale_engine.score(assessment.scale_id, assessment.answers)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    saved = db.create_assessment(patient_id, assessment.scale_id, assessment.answers, result)
    signal = safety.assessment_signal(assessment.scale_id, result)
    if signal:
        db.create_routing_signal(patient_id, signal, "assessment", saved["id"])
    return saved


@app.post("/api/patients/{patient_id}/medication-checkins", status_code=status.HTTP_201_CREATED)
def submit_medication_checkin(
    patient_id: int,
    checkin: MedicationCheckinCreate,
    _: Role = Depends(require_role("patient")),
) -> dict:
    if patient_id != 1:
        raise HTTPException(status_code=403, detail="Пациент может изменять только свои данные")
    if not db.get_patient(patient_id):
        raise HTTPException(status_code=404, detail="Пациент не найден")
    if checkin.side_effect_severity != "none" and not checkin.side_effect.strip():
        raise HTTPException(status_code=422, detail="Опишите нежелательную реакцию")
    saved = db.create_checkin(patient_id, checkin.model_dump())
    signal = safety.checkin_signal(saved)
    if signal:
        db.create_routing_signal(patient_id, signal, "medication_checkin", saved["id"])
    return saved


@app.post("/api/patients/{patient_id}/review")
def review_patient_updates(patient_id: int, _: Role = Depends(require_role("doctor"))) -> dict[str, bool]:
    if not db.get_patient(patient_id):
        raise HTTPException(status_code=404, detail="Пациент не найден")
    db.mark_items_reviewed(patient_id)
    return {"reviewed": True}


@app.put("/api/patients/{patient_id}/clinical-profile")
def update_clinical_profile(
    patient_id: int,
    update: ClinicalProfileUpdate,
    _: Role = Depends(require_role("doctor")),
) -> dict:
    if not db.get_patient(patient_id):
        raise HTTPException(status_code=404, detail="Пациент не найден")
    payload = {
        key: value.strip() if isinstance(value, str) else value
        for key, value in update.model_dump().items()
    }
    return db.save_clinical_profile(patient_id, payload, "Елена Крылова")


@app.put("/api/patients/{patient_id}/plan")
def update_plan(patient_id: int, plan: PlanUpdate, _: Role = Depends(require_role("doctor"))) -> dict:
    if not db.get_patient(patient_id):
        raise HTTPException(status_code=404, detail="Пациент не найден")
    return db.save_plan(patient_id, plan.text.strip(), "Елена Крылова")


@app.put("/api/routing-signals/{signal_id}")
def decide_routing(signal_id: int, decision: RoutingDecision, _: Role = Depends(require_role("doctor"))) -> dict:
    saved = db.decide_routing_signal(signal_id, decision.status, decision.comment.strip())
    if not saved:
        raise HTTPException(status_code=404, detail="Активный сигнал не найден")
    return saved


@app.get("/api/alerts")
def alerts(_: Role = Depends(require_role("doctor"))) -> dict:
    settings = alerting.config()
    return {
        "alerts": db.refresh_and_get_alerts(settings["escalation_seconds"]),
        "settings": settings,
    }


@app.post("/api/alerts/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: int, _: Role = Depends(require_role("doctor"))) -> dict:
    saved = db.acknowledge_alert(alert_id)
    if not saved:
        raise HTTPException(status_code=404, detail="Алерт не найден")
    return saved


@app.get("/api/therapy-reference")
def therapy_reference(_: Role = Depends(require_role("doctor"))) -> dict:
    return {"medications": therapy.public_catalogue()}


@app.post("/api/patients/{patient_id}/therapy-check")
def therapy_check(patient_id: int, request: TherapyCheck, _: Role = Depends(require_role("doctor"))) -> dict:
    if not db.get_patient(patient_id):
        raise HTTPException(status_code=404, detail="Пациент не найден")
    try:
        return therapy.evaluate(request.medication_id, request.factors)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post("/api/patients/{patient_id}/therapy-decisions", status_code=status.HTTP_201_CREATED)
def create_therapy_decision(
    patient_id: int,
    request: TherapyDecisionCreate,
    _: Role = Depends(require_role("doctor")),
) -> dict:
    if not db.get_patient(patient_id):
        raise HTTPException(status_code=404, detail="Пациент не найден")
    medication = therapy.get_medication(request.medication_id)
    if not medication:
        raise HTTPException(status_code=404, detail="Препарат не найден в справочнике")

    payload = {
        key: value.strip() if isinstance(value, str) else value
        for key, value in request.model_dump().items()
    }
    safety_result = therapy.evaluate(request.medication_id, request.factors)
    if request.decision == "approved":
        if payload["indication"] not in medication["indications"]:
            raise HTTPException(status_code=422, detail="Выберите зарегистрированное показание из справочника")
        if not payload["dosage"] or not payload["schedule"] or not payload["duration"]:
            raise HTTPException(status_code=422, detail="Для подтверждения заполните дозу, режим и длительность")
        if safety_result["status"] == "not_suitable":
            raise HTTPException(status_code=422, detail="Подтверждение невозможно: чек-лист содержит противопоказание")
        if safety_result["status"] == "review_required" and not payload["rationale"]:
            raise HTTPException(status_code=422, detail="Опишите решение врача с учётом предупреждений")
    elif not payload["rationale"]:
        raise HTTPException(status_code=422, detail="Укажите обоснование решения")

    payload["medication_name"] = medication["name"]
    return db.create_therapy_decision(patient_id, payload, safety_result, "Елена Крылова")


@app.put("/api/therapy-decisions/{decision_id}/cancel")
def cancel_therapy_decision(
    decision_id: int,
    _: Role = Depends(require_role("doctor")),
) -> dict:
    saved = db.cancel_therapy_decision(decision_id)
    if not saved:
        raise HTTPException(status_code=404, detail="Активное подтверждённое решение не найдено")
    return saved


@app.post("/api/patients/{patient_id}/tasks", status_code=status.HTTP_201_CREATED)
def add_care_task(
    patient_id: int,
    task: CareTaskCreate,
    _: Role = Depends(require_role("doctor")),
) -> dict:
    if not db.get_patient(patient_id):
        raise HTTPException(status_code=404, detail="Пациент не найден")
    payload = task.model_dump()
    payload["title"] = payload["title"].strip()
    payload["description"] = payload["description"].strip()
    return db.create_care_task(patient_id, payload)


@app.put("/api/tasks/{task_id}")
def change_care_task(task_id: int, update: CareTaskUpdate, role: Role = Depends(demo_role)) -> dict:
    task = db.get_care_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    if role == "patient":
        if task["patient_id"] != 1:
            raise HTTPException(status_code=403, detail="Пациент может изменять только свои задачи")
        if update.status not in {"pending", "completed"}:
            raise HTTPException(status_code=403, detail="Пациент не может отменять назначения врача")
    saved = db.update_care_task(task_id, update.status)
    if not saved:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return saved


def clean_article(article: KnowledgeArticleWrite) -> dict:
    payload = article.model_dump()
    for key in ("title", "summary", "body", "source_url"):
        payload[key] = payload[key].strip()
    if not payload["title"] or not payload["body"]:
        raise HTTPException(status_code=422, detail="Заполните название и текст статьи")
    payload["tags"] = list(dict.fromkeys(tag.strip() for tag in payload["tags"] if tag.strip()))
    return payload


def note_id(article_id: str) -> int:
    number = article_id.removeprefix("note-")
    if not article_id.startswith("note-") or not number.isdigit():
        raise HTTPException(status_code=403, detail="Системные статьи формируются из конфигурации и не редактируются")
    return int(number)


@app.get("/api/knowledge")
def knowledge_list(q: str = "", category: str = "", _: Role = Depends(require_role("doctor"))) -> dict:
    return {"categories": knowledge.CATEGORIES, "articles": knowledge.search(q.strip()[:200], category)}


@app.get("/api/knowledge/{article_id}")
def knowledge_article(article_id: str, _: Role = Depends(require_role("doctor"))) -> dict:
    article = knowledge.get(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Статья не найдена")
    return article


@app.post("/api/knowledge", status_code=status.HTTP_201_CREATED)
def knowledge_create(article: KnowledgeArticleWrite, _: Role = Depends(require_role("doctor"))) -> dict:
    return knowledge.doctor_article(db.create_kb_article(clean_article(article), "Елена Крылова"))


@app.put("/api/knowledge/{article_id}")
def knowledge_update(article_id: str, article: KnowledgeArticleWrite, _: Role = Depends(require_role("doctor"))) -> dict:
    saved = db.update_kb_article(note_id(article_id), clean_article(article))
    if not saved:
        raise HTTPException(status_code=404, detail="Статья не найдена")
    return knowledge.doctor_article(saved)


@app.delete("/api/knowledge/{article_id}", status_code=status.HTTP_204_NO_CONTENT)
def knowledge_delete(article_id: str, _: Role = Depends(require_role("doctor"))) -> None:
    if not db.delete_kb_article(note_id(article_id)):
        raise HTTPException(status_code=404, detail="Статья не найдена")


@app.get("/api/profile")
def profile(_: Role = Depends(require_role("patient"))) -> dict:
    return db.get_profile(1)


@app.put("/api/profile")
def update_profile(update: ProfileUpdate, _: Role = Depends(require_role("patient"))) -> dict:
    payload = {key: value.strip() if isinstance(value, str) else value for key, value in update.model_dump().items()}
    return db.save_profile(1, payload)


@app.get("/api/patients/{patient_id}/messages")
def messages(patient_id: int, role: Role = Depends(demo_role)) -> dict:
    if role == "patient" and patient_id != 1:
        raise HTTPException(status_code=403, detail="Пациент может просматривать только свой диалог")
    if not db.get_patient(patient_id):
        raise HTTPException(status_code=404, detail="Пациент не найден")
    db.mark_messages_read(patient_id, role)
    return {"messages": db.get_messages(patient_id), "unread": 0}


@app.post("/api/patients/{patient_id}/messages", status_code=status.HTTP_201_CREATED)
def send_message(patient_id: int, message: MessageCreate, role: Role = Depends(demo_role)) -> dict:
    if role == "patient" and patient_id != 1:
        raise HTTPException(status_code=403, detail="Пациент может писать только в свой диалог")
    if not db.get_patient(patient_id):
        raise HTTPException(status_code=404, detail="Пациент не найден")
    body = message.body.strip()
    if not body:
        raise HTTPException(status_code=422, detail="Сообщение не может быть пустым")
    return db.create_message(patient_id, role, body)


app.mount("/", StaticFiles(directory=DIST_DIR, html=True), name="frontend")
