#!/usr/bin/env bash
# Установка и обновление демо-стенда на чистом Ubuntu-сервере (Timeweb Cloud и др.).
#
#   sudo GITHUB_TOKEN=github_pat_... bash setup.sh        # приватный репозиторий
#   sudo DOMAIN=compass.example.ru bash setup.sh           # свой домен (A-запись на IP сервера)
#
# Без DOMAIN стенд получает адрес вида https://<IP>.sslip.io. Повторный запуск забирает
# свежий код из GitHub и пересобирает приложение; база в томе cc-data сохраняется.
set -euo pipefail

REPO="github.com/nastyaleksa04/clinical-compass.git"
DIR="/opt/clinical-compass"

if [[ $EUID -ne 0 ]]; then
  echo "Запустите через sudo или под root"; exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Устанавливаю Docker..."
  curl -fsSL https://get.docker.com | sh
fi
if ! command -v git >/dev/null 2>&1; then
  apt-get update -y && apt-get install -y git
fi

URL="https://${REPO}"
if [[ -n "${GITHUB_TOKEN:-}" ]]; then
  URL="https://x-access-token:${GITHUB_TOKEN}@${REPO}"
fi
if [[ -d "$DIR/.git" ]]; then
  echo "Обновляю код..."
  git -C "$DIR" remote set-url origin "$URL"
  git -C "$DIR" pull --ff-only
else
  echo "Скачиваю код..."
  git clone "$URL" "$DIR"
fi

cd "$DIR/deploy"

if [[ ! -f .env ]]; then
  if [[ -z "${DOMAIN:-}" ]]; then
    IP="$(curl -fsSL https://api.ipify.org || hostname -I | awk '{print $1}')"
    DOMAIN="${IP}.sslip.io"
  fi
  echo "DOMAIN=${DOMAIN}" > .env
fi
if [[ ! -f app.env ]]; then
  printf 'OPENROUTER_API_KEY=\nOPENROUTER_SITE_URL=https://%s\n' "$(grep '^DOMAIN=' .env | cut -d= -f2)" > app.env
  chmod 600 app.env
fi

docker compose up -d --build

DOMAIN="$(grep '^DOMAIN=' .env | cut -d= -f2)"
echo
echo "Готово. Стенд: https://${DOMAIN}"
echo "Первый запуск: сертификат HTTPS выпускается за 1–2 минуты."
echo "Ключ OpenRouter: впишите в ${DIR}/deploy/app.env и выполните: cd ${DIR}/deploy && docker compose up -d"
echo "Логи: cd ${DIR}/deploy && docker compose logs -f app"
