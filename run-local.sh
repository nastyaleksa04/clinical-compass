#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "Ошибка: нужен Python 3. Установите: sudo apt update && sudo apt install python3 python3-venv"
  exit 1
fi

if [[ ! -x .venv/bin/python ]]; then
  echo "Создаю локальное окружение .venv..."
  python3 -m venv .venv
fi

if [[ ! -f .venv/.requirements-installed || requirements.txt -nt .venv/.requirements-installed ]]; then
  echo "Устанавливаю зависимости..."
  .venv/bin/python -m pip install -r requirements.txt
  touch .venv/.requirements-installed
fi

PORT="${PORT:-8000}"
exec .venv/bin/python scripts/web_service.py --host 127.0.0.1 --port "$PORT" "$@"