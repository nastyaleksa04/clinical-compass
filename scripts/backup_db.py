#!/usr/bin/env python3
"""Резервное копирование и восстановление базы SQLite без остановки сервера.

    python scripts/backup_db.py                 # снимок в data/backups/, хранит 14 последних
    python scripts/backup_db.py --keep 48       # хранить 48 снимков
    python scripts/backup_db.py --restore data/backups/clinical_compass-20261027-120000.db

Снимок делается через sqlite3 backup API: копия согласована даже при одновременной записи.
Каждый снимок и каждое восстановление проверяются PRAGMA integrity_check.
"""
import argparse
import os
import shutil
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = Path(os.environ.get("CLINICAL_COMPASS_DB", PROJECT_ROOT / "data" / "clinical_compass.db"))
DEFAULT_DIR = PROJECT_ROOT / "data" / "backups"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def integrity(path: Path) -> str:
    with sqlite3.connect(path) as database:
        return database.execute("PRAGMA integrity_check").fetchone()[0]


def backup(db_path: Path, target_dir: Path, keep: int) -> Path:
    if not db_path.exists():
        raise SystemExit(f"База не найдена: {db_path}")
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{db_path.stem}-{datetime.now():%Y%m%d-%H%M%S}.db"
    started = time.perf_counter()
    source = sqlite3.connect(db_path)
    destination = sqlite3.connect(target)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    status = integrity(target)
    if status != "ok":
        target.unlink(missing_ok=True)
        raise SystemExit(f"Снимок повреждён ({status}), удалён")
    snapshots = sorted(target_dir.glob(f"{db_path.stem}-*.db"))
    for old in snapshots[:-keep]:
        old.unlink()
    print(f"Снимок: {target} · {target.stat().st_size / 1024:.0f} КБ · {time.perf_counter() - started:.2f} с · проверка: ok")
    print(f"Хранится снимков: {min(len(snapshots), keep)}")
    return target


def restore(snapshot: Path, db_path: Path) -> None:
    if not snapshot.exists():
        raise SystemExit(f"Снимок не найден: {snapshot}")
    started = time.perf_counter()
    status = integrity(snapshot)
    if status != "ok":
        raise SystemExit(f"Снимок повреждён ({status}), восстановление отменено")
    if db_path.exists():
        safety_copy = db_path.with_name(f"{db_path.stem}.before-restore-{datetime.now():%Y%m%d-%H%M%S}.db")
        shutil.copy2(db_path, safety_copy)
        print(f"Текущая база сохранена: {safety_copy}")
    source = sqlite3.connect(snapshot)
    destination = sqlite3.connect(db_path)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    print(f"Восстановлено из {snapshot} за {time.perf_counter() - started:.2f} с · проверка: {integrity(db_path)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Резервное копирование базы Клинического компаса")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    parser.add_argument("--keep", type=int, default=14)
    parser.add_argument("--restore", type=Path, help="путь к снимку для восстановления")
    args = parser.parse_args()
    if args.restore:
        restore(args.restore, args.db)
    else:
        backup(args.db, args.dir, max(1, args.keep))


if __name__ == "__main__":
    main()
