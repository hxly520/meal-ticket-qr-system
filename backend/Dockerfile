FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev curl fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

COPY app /app/app
COPY alembic.ini /app/alembic.ini
COPY alembic /app/alembic
COPY pyproject.toml /app/
RUN pip install .

CMD ["gunicorn", "app.main:app", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000", "--workers", "2"]
