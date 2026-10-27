# Демо-стенд «Клинического компаса» (Amvera, Timeweb App Platform, любой сервер с Docker)
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Шрифты с кириллицей для PDF-документов медкарты
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .

# База — в постоянном хранилище /data (переживает перезапуск и пересборку).
# Демо-данные пересоздаются каждую ночь в 04:00 по Москве; отключить — пустое значение.
ENV CLINICAL_COMPASS_DB=/data/clinical_compass.db \
    CLINICAL_COMPASS_DEMO_RESET_AT=04:00

EXPOSE 8000
CMD ["python", "scripts/web_service.py", "--host", "0.0.0.0", "--port", "8000"]
