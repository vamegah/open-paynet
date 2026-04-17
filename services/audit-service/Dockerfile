FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*

COPY services/audit-service/requirements.txt ./requirements.txt
RUN python -m pip install --upgrade --no-cache-dir pip setuptools wheel \
    && python -m pip install --no-cache-dir -r requirements.txt
COPY services/audit-service/app /app/app
COPY shared /app/shared

RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app

ENV PYTHONPATH=/app
USER appuser
CMD ["python", "-m", "app.elastic_logger"]
