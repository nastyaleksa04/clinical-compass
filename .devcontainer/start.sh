#!/usr/bin/env bash
# Запуск демо-стенда в GitHub Codespaces: при каждом старте — свежие демо-данные «на сегодня».
# Лог сервера: /tmp/clinical-compass.log
cd "$(dirname "$0")/.."
pkill -f "scripts/web_service.py" 2>/dev/null || true
setsid nohup python scripts/web_service.py --host 0.0.0.0 --port 8000 --fresh-demo > /tmp/clinical-compass.log 2>&1 < /dev/null &
echo "Клинический компас запускается на порту 8000 (лог: /tmp/clinical-compass.log)"
