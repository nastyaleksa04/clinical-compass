#!/usr/bin/env python3
"""Оценка извлечения сведений из историй болезни разных шаблонов (метрика 2).

    python scripts/evaluate_history_import.py            # таблица в консоль
    python scripts/evaluate_history_import.py --json     # подробный отчёт

Набор: data/evaluation/histories/*.txt|*.pdf + эталон *.json с тем же именем.
Скалярные поля сравниваются точно, множества (МКБ, препараты, факторы риска) — по precision/recall,
текстовые поля — по наличию всех ключевых фраз эталона.
"""
import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app import history_import  # noqa: E402

DATASET = PROJECT_ROOT / "data" / "evaluation" / "histories"
SCALARS = ("age", "sex", "pregnancy_status", "self_harm_concern", "psychosis_signs")
SETS = ("icd_codes", "medications", "therapy_factors")


def age_from(birth: str) -> int:
    born, today = date.fromisoformat(birth), date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def actual_values(result: dict) -> dict:
    return {
        "age": result["age"], "sex": result["sex"],
        "pregnancy_status": result["fields"]["pregnancy_status"],
        "self_harm_concern": result["fields"]["self_harm_concern"],
        "psychosis_signs": result["fields"]["psychosis_signs"],
        "icd_codes": set(code for code in result["icd_codes"] if code.startswith("F")),
        "medications": {item["name"] for item in result["medications"]},
        "therapy_factors": {key for key, value in result["therapy_factors"].items() if value},
        "scales": result["scales"],
    }


def evaluate(directory: Path) -> dict:
    cases, totals = [], {"scalar": [0, 0], "scales": [0, 0], "text": [0, 0], "tp": 0, "fp": 0, "fn": 0}
    per_field: dict[str, list[int]] = {}
    for expected_path in sorted(directory.glob("*.json")):
        source = next((p for p in (expected_path.with_suffix(".txt"), expected_path.with_suffix(".pdf")) if p.exists()), None)
        if not source:
            continue
        expected = json.loads(expected_path.read_text(encoding="utf-8"))
        if "birth_date" in expected:
            expected["age"] = age_from(expected["birth_date"])
        started = time.perf_counter()
        result = history_import.parse(history_import.extract_text(source.read_bytes(), source.name))
        elapsed = (time.perf_counter() - started) * 1000
        actual = actual_values(result)
        errors = []
        for field in SCALARS:
            ok = actual[field] == expected[field]
            per_field.setdefault(field, [0, 0])
            per_field[field][0] += ok
            per_field[field][1] += 1
            totals["scalar"][0] += ok
            totals["scalar"][1] += 1
            if not ok:
                errors.append(f"{field}: {actual[field]!r} ≠ {expected[field]!r}")
        for scale, value in expected["scales"].items():
            ok = actual["scales"].get(scale) == value
            totals["scales"][0] += ok
            totals["scales"][1] += 1
            if not ok:
                errors.append(f"{scale}: {actual['scales'].get(scale)!r} ≠ {value}")
        extra_scales = set(actual["scales"]) - set(expected["scales"])
        totals["scales"][1] += len(extra_scales)
        errors += [f"лишняя шкала {scale}" for scale in extra_scales]
        for field in SETS:
            want, got = set(expected[field]), actual[field]
            totals["tp"] += len(want & got)
            totals["fp"] += len(got - want)
            totals["fn"] += len(want - got)
            if want != got:
                errors.append(f"{field}: лишнее {sorted(got - want)}, пропущено {sorted(want - got)}")
        for field, phrases in expected.get("text", {}).items():
            value = result["fields"].get(field, "").lower()
            ok = all(phrase.lower() in value for phrase in phrases)
            per_field.setdefault(f"text:{field}", [0, 0])
            per_field[f"text:{field}"][0] += ok
            per_field[f"text:{field}"][1] += 1
            totals["text"][0] += ok
            totals["text"][1] += 1
            if not ok:
                errors.append(f"{field}: «{result['fields'].get(field, '')[:80]}» без {phrases}")
        cases.append({"case": source.name, "ms": round(elapsed, 1), "errors": errors, "sections": result["sections_found"]})
    precision = totals["tp"] / max(1, totals["tp"] + totals["fp"])
    recall = totals["tp"] / max(1, totals["tp"] + totals["fn"])
    return {
        "cases": cases,
        "scalar_accuracy": totals["scalar"][0] / max(1, totals["scalar"][1]),
        "scale_accuracy": totals["scales"][0] / max(1, totals["scales"][1]),
        "text_accuracy": totals["text"][0] / max(1, totals["text"][1]),
        "set_precision": precision, "set_recall": recall,
        "set_f1": 2 * precision * recall / max(1e-9, precision + recall),
        "per_field": {key: value[0] / value[1] for key, value in per_field.items()},
        "median_ms": sorted(case["ms"] for case in cases)[len(cases) // 2] if cases else 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dir", type=Path, default=DATASET)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.dir)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    print(f"Историй: {len(report['cases'])} · медианное время разбора: {report['median_ms']} мс\n")
    print("| Показатель | Значение |\n|---|---|")
    print(f"| Точность скалярных полей (возраст, пол, беременность, суицидальный риск, психоз) | {report['scalar_accuracy']:.0%} |")
    print(f"| Точность баллов шкал | {report['scale_accuracy']:.0%} |")
    print(f"| МКБ-10, препараты, факторы риска: precision / recall / F1 | {report['set_precision']:.0%} / {report['set_recall']:.0%} / {report['set_f1']:.0%} |")
    print(f"| Текстовые поля (ключевые фразы на месте) | {report['text_accuracy']:.0%} |")
    for case in report["cases"]:
        status = "ok" if not case["errors"] else "; ".join(case["errors"])
        print(f"\n- {case['case']} ({case['ms']} мс): {status}")


if __name__ == "__main__":
    main()
