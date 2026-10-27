#!/usr/bin/env python3
"""Подготовка базы к демонстрации.

    python scripts/seed_demo.py           # добавить живые демо-данные в текущую базу (если их ещё нет)
    python scripts/seed_demo.py --fresh   # снимок текущей базы в data/backups/ и новая база с данными «на сегодня»

Даты демо-данных отсчитываются от момента заполнения, поэтому --fresh удобно запускать в день показа
(при остановленном сервере).
"""
import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app import auth, db, demo_life, knowledge, scenarios  # noqa: E402
from scripts.backup_db import DEFAULT_DIR, backup  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Живые демо-данные Клинического компаса")
    parser.add_argument("--fresh", action="store_true", help="пересоздать базу (текущая сохраняется в data/backups/)")
    prepare(parser.parse_args().fresh)


def prepare(fresh: bool) -> None:
    if fresh and db.DB_PATH.exists():
        backup(db.DB_PATH, DEFAULT_DIR, keep=14)
        for suffix in ("", "-wal", "-shm"):
            Path(f"{db.DB_PATH}{suffix}").unlink(missing_ok=True)
        print(f"Старая база удалена: {db.DB_PATH}")
    db.init_db()
    scenarios.seed()
    auth.seed_demo_users()
    scenarios.seed_clinical_profiles()
    knowledge.seed_templates()
    added = demo_life.seed()
    print("Живые демо-данные добавлены." if added else "Живые демо-данные уже есть — используйте --fresh, чтобы обновить даты.")
    print("Входы: врач doctor / doctor2026; пациенты patient, sokolova, lebedeva, morozov, orlova — пароль patient2026.")


if __name__ == "__main__":
    os.environ.setdefault("CLINICAL_COMPASS_DEMO_DATA", "1")
    main()
