#!/usr/bin/env python3
import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)
# живые демо-данные (2–3 недели наблюдения) добавляются в базу один раз; отключить: CLINICAL_COMPASS_DEMO_DATA=0
os.environ.setdefault("CLINICAL_COMPASS_DEMO_DATA", "1")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import uvicorn


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Локальный сервер Clinical Compass")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true", help="Перезапускать сервер при изменениях")
    parser.add_argument("--fresh-demo", action="store_true",
                        help="перед запуском пересоздать базу с демо-данными «на сегодня» (текущая сохраняется в data/backups/)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.fresh_demo:
        from scripts.seed_demo import prepare
        prepare(fresh=True)
    print(f"Клинический компас: http://{args.host}:{args.port}")
    print("Проверка API:       http://localhost:%d/api/health" % args.port)
    uvicorn.run("app.main:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()