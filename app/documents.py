"""Generate patient-specific psychiatric PDF reports from the local record."""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from xml.sax.saxutils import escape

from app import db

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FONT_CANDIDATES = (
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("C:/Windows/Fonts/arial.ttf"),
)
BOLD_FONT_CANDIDATES = (
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("C:/Windows/Fonts/arialbd.ttf"),
)
REPORTS = (
    {
        "id": "psychiatric-visit-report",
        "category": "visit_report",
        "title": "Отчёт психиатрического приёма",
        "specialty": "Психиатрия",
        "description": "Актуальные сведения карты, результаты шкал, план и подтверждённые назначения",
    },
    {
        "id": "monitoring-results-report",
        "category": "monitoring_report",
        "title": "Результаты опросников и динамика",
        "specialty": "Наблюдение состояния",
        "description": "PHQ-9, GAD-7, самоотчёты, приверженность и задачи в динамике",
    },
)


def _register_fonts() -> tuple[str, str]:
    regular = next((path for path in FONT_CANDIDATES if path.is_file()), None)
    bold = next((path for path in BOLD_FONT_CANDIDATES if path.is_file()), None)
    if not regular or not bold:
        raise RuntimeError("Не найден локальный шрифт с поддержкой кириллицы")
    if "CompassSans" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("CompassSans", regular))
        pdfmetrics.registerFont(TTFont("CompassSans-Bold", bold))
    return "CompassSans", "CompassSans-Bold"


def _date(value: str | None) -> str:
    if not value:
        return "—"
    try:
        return datetime.fromisoformat(value).strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return value


def _text(value: Any) -> str:
    return escape(str(value or "—"))


def _styles() -> dict[str, ParagraphStyle]:
    regular, bold = _register_fonts()
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("CompassTitle", parent=base["Title"], fontName=bold, fontSize=18, leading=23, alignment=TA_CENTER, textColor=colors.HexColor("#171922"), spaceAfter=10),
        "subtitle": ParagraphStyle("CompassSubtitle", parent=base["Normal"], fontName=regular, fontSize=9, leading=13, alignment=TA_CENTER, textColor=colors.HexColor("#737781"), spaceAfter=16),
        "heading": ParagraphStyle("CompassHeading", parent=base["Heading2"], fontName=bold, fontSize=12, leading=16, textColor=colors.HexColor("#07958f"), spaceBefore=12, spaceAfter=7),
        "body": ParagraphStyle("CompassBody", parent=base["BodyText"], fontName=regular, fontSize=9.5, leading=14, textColor=colors.HexColor("#272a33"), spaceAfter=6),
        "small": ParagraphStyle("CompassSmall", parent=base["BodyText"], fontName=regular, fontSize=7.5, leading=11, textColor=colors.HexColor("#737781")),
        "table": ParagraphStyle("CompassTable", parent=base["BodyText"], fontName=regular, fontSize=8, leading=10),
        "table_bold": ParagraphStyle("CompassTableBold", parent=base["BodyText"], fontName=bold, fontSize=8, leading=10),
    }


def _table(rows: list[list[Any]], widths: list[float], styles: dict[str, ParagraphStyle]) -> Table:
    rendered = [[Paragraph(_text(cell), styles["table_bold"] if row_index == 0 else styles["table"]) for cell in row] for row_index, row in enumerate(rows)]
    table = Table(rendered, colWidths=widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6f8f7")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#075e5a")),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#dfe2e8")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def _header(story: list[Any], patient: dict[str, Any], title: str, styles: dict[str, ParagraphStyle]) -> None:
    story.extend([
        Paragraph(title, styles["title"]),
        Paragraph(f"Клинический компас · сформировано {_date(db.now_iso())}", styles["subtitle"]),
        _table([
            ["Пациент", "Возраст", "Документ"],
            [patient["name"], f"{patient['age']} лет", "Динамический PDF по данным локальной карты"],
        ], [63 * mm, 30 * mm, 77 * mm], styles),
        Spacer(1, 5 * mm),
    ])


def _visit_story(patient_id: int, styles: dict[str, ParagraphStyle]) -> list[Any]:
    patient = db.get_patient(patient_id)
    profile = db.get_clinical_profile(patient_id)
    assessments = db.get_assessments(patient_id, 8)
    plan = db.get_plan(patient_id)
    decisions = db.get_therapy_decisions(patient_id, include_internal=False)
    story: list[Any] = []
    _header(story, patient, "Отчёт психиатрического приёма", styles)
    sections = (
        ("Повод обращения", profile.get("visit_reason")),
        ("Жалобы", profile.get("complaints")),
        ("Длительность симптомов", profile.get("symptom_duration")),
        ("Анамнез", profile.get("history")),
        ("Сопутствующие состояния", profile.get("comorbidities")),
        ("Текущая терапия", profile.get("current_medications")),
        ("Аллергии", profile.get("allergies")),
        ("Рабочая гипотеза врача", profile.get("working_hypothesis")),
    )
    for heading, value in sections:
        story.extend([Paragraph(heading, styles["heading"]), Paragraph(_text(value), styles["body"])])
    story.extend([
        Paragraph("Клинически значимые признаки", styles["heading"]),
        Paragraph(
            f"Признаки психоза: {'отмечены' if profile.get('psychosis_signs') else 'не отмечены'}. "
            f"Опасения самоповреждения: {'отмечены' if profile.get('self_harm_concern') else 'не отмечены'}.",
            styles["body"],
        ),
        Paragraph("Последние результаты шкал", styles["heading"]),
    ])
    if assessments:
        story.append(_table([["Дата", "Шкала", "Баллы", "Интерпретация"]] + [[_date(x["created_at"]), x["scale_id"].upper(), x["total"], x["severity"]] for x in assessments], [35 * mm, 28 * mm, 22 * mm, 85 * mm], styles))
    else:
        story.append(Paragraph("Результаты шкал пока отсутствуют.", styles["body"]))
    story.extend([Paragraph("Подтверждённый план", styles["heading"]), Paragraph(_text(plan["text"] if plan else None), styles["body"]), Paragraph("Подтверждённые решения по терапии", styles["heading"])])
    if decisions:
        story.append(_table([["Препарат", "Схема", "Статус"]] + [[x["medication_name"], " · ".join(value for value in (x["dosage"], x["schedule"], x["duration"]) if value), x["decision"]] for x in decisions], [55 * mm, 78 * mm, 37 * mm], styles))
    else:
        story.append(Paragraph("Подтверждённые решения по терапии отсутствуют.", styles["body"]))
    return story


def _monitoring_story(patient_id: int, styles: dict[str, ParagraphStyle]) -> list[Any]:
    patient = db.get_patient(patient_id)
    assessments = db.get_assessments(patient_id, 30)
    reports = db.get_reports(patient_id, 14)
    adherence = db.adherence_summary(patient_id)
    tasks = db.get_care_tasks(patient_id)
    story: list[Any] = []
    _header(story, patient, "Результаты опросников и динамика", styles)
    story.append(Paragraph("Стандартизированные шкалы", styles["heading"]))
    if assessments:
        story.append(_table([["Дата", "Шкала", "Баллы", "Интерпретация"]] + [[_date(x["created_at"]), x["scale_id"].upper(), x["total"], x["severity"]] for x in assessments], [35 * mm, 28 * mm, 22 * mm, 85 * mm], styles))
    else:
        story.append(Paragraph("Результаты шкал пока отсутствуют.", styles["body"]))
    story.append(Paragraph("Самоотчёты пациента", styles["heading"]))
    if reports:
        story.append(_table([["Дата", "Настроение", "Тревога", "Сон", "Комментарий"]] + [[_date(x["created_at"]), f"{x['mood']}/5", f"{x['anxiety']}/5", f"{x['sleep']}/5", x.get("comment") or "—"] for x in reports], [31 * mm, 24 * mm, 22 * mm, 20 * mm, 73 * mm], styles))
    else:
        story.append(Paragraph("Самоотчёты пока отсутствуют.", styles["body"]))
    story.extend([
        Paragraph("Приверженность", styles["heading"]),
        Paragraph(f"Отметок: {adherence['total']}. Принято: {adherence['taken']}. Пропущено: {adherence['missed']}. Приверженность: {adherence['percent'] if adherence['percent'] is not None else '—'}%. Нежелательных явлений: {adherence['adverse_events']}.", styles["body"]),
        Paragraph("Задачи наблюдения", styles["heading"]),
    ])
    if tasks:
        story.append(_table([["Задача", "Категория", "Срок", "Статус"]] + [[x["title"], x["category"], x.get("due_date") or "—", x["status"]] for x in tasks], [72 * mm, 35 * mm, 28 * mm, 35 * mm], styles))
    else:
        story.append(Paragraph("Задачи пока отсутствуют.", styles["body"]))
    return story


def list_documents(patient_id: int) -> list[dict[str, Any]]:
    patient = db.get_patient(patient_id)
    if not patient:
        return []
    generated_at = db.now_iso()
    return [{**item, "patient_id": patient_id, "mime_type": "application/pdf", "generated": True, "generated_at": generated_at, "available": True} for item in REPORTS]


def get_document(patient_id: int, document_id: str) -> dict[str, Any] | None:
    if not db.get_patient(patient_id):
        return None
    return next((dict(item) for item in REPORTS if item["id"] == document_id), None)


def generate_pdf(patient_id: int, document_id: str) -> bytes:
    document = get_document(patient_id, document_id)
    if not document:
        raise LookupError("Документ не найден")
    styles = _styles()
    story = _visit_story(patient_id, styles) if document_id == "psychiatric-visit-report" else _monitoring_story(patient_id, styles)
    story.extend([
        Spacer(1, 8 * mm),
        Paragraph("Документ автоматически сформирован по данным прототипа «Клинический компас». Он не заменяет подписанное медицинское заключение и требует проверки врачом.", styles["small"]),
    ])
    output = BytesIO()
    pdf = SimpleDocTemplate(output, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm, title=document["title"], author="Клинический компас")
    pdf.build(story)
    return output.getvalue()
