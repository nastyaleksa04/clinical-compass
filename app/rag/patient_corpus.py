"""Build a small, isolated patient-facing corpus from product policies and scale config."""

from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "knowledge" / "kb_v2_3_patient"


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def build_patient_corpus(output: str | Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    output = Path(output)
    if output.exists():
        shutil.rmtree(output)
    (output / "entities").mkdir(parents=True)

    scale_config = json.loads((PROJECT_ROOT / "config/scales.json").read_text(encoding="utf-8"))
    scales = {row["id"]: row for row in scale_config["scales"]}
    built_at = date.today().isoformat()

    sources = [
        {
            "source_id": "patient_app_policy",
            "title": "Правила пациентского кабинета «Клинический компас»",
            "organization": "Clinical Compass",
            "version": "0.16",
            "url": "",
            "source_type": "internal_product_policy",
            "status": "prototype",
        },
        {
            "source_id": "patient_emergency_policy",
            "title": "Экстренная маршрутизация пациентского кабинета",
            "organization": "Clinical Compass",
            "version": "1.0",
            "url": "",
            "source_type": "internal_safety_policy",
            "status": "prototype",
        },
        {
            "source_id": "patient_phq9",
            "title": "PHQ-9: информация для пациента",
            "organization": "Clinical Compass",
            "version": scale_config["version"],
            "url": scales["phq9"]["source"]["validation"],
            "source_type": "validated_scale",
            "status": "active",
        },
        {
            "source_id": "patient_gad7",
            "title": "GAD-7: информация для пациента",
            "organization": "Clinical Compass",
            "version": scale_config["version"],
            "url": scales["gad7"]["source"]["validation"],
            "source_type": "validated_scale",
            "status": "active",
        },
    ]

    review = {
        "status": "prototype_patient_copy",
        "production_approved": False,
        "basis": "Derived from patient-facing product policies and configured validated scales.",
        "reviewed_at": built_at,
    }

    facts = [
        (
            "patient:assistant_scope",
            "patient_app_policy",
            "Возможности помощника",
            "Помощник объясняет разделы приложения, опросники и общие правила наблюдения простыми словами. "
            "Он не устанавливает диагноз, не подбирает препарат, не назначает дозу и не заменяет врача. "
            "Для решения о лечении нужно обратиться к лечащему врачу.",
        ),
        (
            "patient:phq9",
            "patient_phq9",
            "Опросник PHQ-9",
            "PHQ-9 — опросник из девяти пунктов для оценки частоты депрессивных симптомов за последние две недели. "
            "Результат помогает врачу оценивать выраженность симптомов и изменения во времени, но сам по себе не является диагнозом. "
            "Ответ о мыслях о смерти или причинении себе вреда требует отдельного внимания независимо от общего балла.",
        ),
        (
            "patient:gad7",
            "patient_gad7",
            "Опросник GAD-7",
            "GAD-7 — опросник из семи пунктов для оценки частоты тревожных симптомов за последние две недели. "
            "Баллы помогают обсуждать состояние с врачом и наблюдать динамику. Результат скрининга не устанавливает диагноз "
            "и не должен самостоятельно менять лечение.",
        ),
        (
            "patient:scale_dynamics",
            "patient_app_policy",
            "Динамика опросников",
            "Для наблюдения полезно проходить один и тот же опросник в согласованные с врачом сроки. "
            "Изменение балла следует обсуждать вместе с самочувствием, сном, нежелательными реакциями и другими обстоятельствами. "
            "Один результат не заменяет клиническую оценку.",
        ),
        (
            "patient:therapy_safety",
            "patient_app_policy",
            "Безопасность назначенной терапии",
            "Не начинайте, не отменяйте и не меняйте дозу назначенного препарата по ответу цифрового помощника. "
            "Если возник вопрос о пропущенном приёме, совместимости или изменении схемы, следуйте выданной врачом инструкции "
            "либо свяжитесь с врачом или фармацевтом. Не принимайте двойную дозу без прямого указания в инструкции или от врача.",
        ),
        (
            "patient:adverse_reaction",
            "patient_emergency_policy",
            "Нежелательная реакция",
            "Сообщите врачу о новой или усилившейся нежелательной реакции и отметьте её выраженность в приложении. "
            "При выраженной реакции, резком ухудшении, нарушении сознания, затруднении дыхания или непосредственной угрозе жизни "
            "нужна экстренная помощь: позвоните 112 или обратитесь в ближайшее отделение экстренной помощи.",
        ),
        (
            "patient:urgent_safety",
            "patient_emergency_policy",
            "Непосредственная угроза безопасности",
            "Если есть мысли о причинении себе вреда, намерение, план или непосредственная угроза жизни, не ждите ответа в приложении. "
            "Позвоните 112 или обратитесь в ближайшее отделение экстренной помощи. Сообщение в приложении является асинхронным "
            "и не заменяет экстренную помощь.",
        ),
        (
            "patient:doctor_contact",
            "patient_app_policy",
            "Связь с врачом",
            "Раздел «Связь» предназначен для неэкстренных сообщений лечащему врачу. Ответ может прийти не сразу. "
            "Через него можно уточнить план наблюдения, сообщить об изменении самочувствия или нежелательной реакции. "
            "При непосредственной угрозе жизни используйте экстренную помощь, а не чат.",
        ),
        (
            "patient:self_report",
            "patient_app_policy",
            "Самоотчёт",
            "В самоотчёте можно отметить настроение, тревогу, сон и добавить комментарий для врача. "
            "При резком ухудшении можно запросить срочную связь, но такой запрос не является каналом экстренной помощи. "
            "Если ждать небезопасно, позвоните 112 или обратитесь за экстренной помощью.",
        ),
    ]

    chunks = []
    for number, (entity_id, source_id, section, text) in enumerate(facts, 1):
        chunks.append({
            "chunk_id": f"patient_{number:03d}",
            "source_id": source_id,
            "entity_ids": [entity_id],
            "section_path": [section],
            "text": text,
            "char_len": len(text),
            "audience": ["patient"],
            "retrieval_eligible": True,
            "automation_eligible": False,
            "evidence": {"section": section},
            "review": review,
        })

    _write_jsonl(output / "sources.jsonl", sources)
    _write_jsonl(output / "entities/chunks.jsonl", chunks)
    manifest = {
        "release": "kb_v2.3-patient-prototype",
        "built_at": built_at,
        "policy": {
            "audience": ["patient"],
            "prototype_only": True,
            "production_approved": False,
            "automatic_diagnosis": False,
            "automatic_treatment_changes": False,
        },
        "counts": {"sources.jsonl": len(sources), "entities/chunks.jsonl": len(chunks)},
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest
