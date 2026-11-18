FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv/backend

COPY requirements.txt .
RUN pip install --default-timeout=180 --retries 10 -r requirements.txt

COPY . .

# non-root user
RUN useradd --create-home --uid 10001 sentrax && chown -R sentrax:sentrax /srv/backend
USER sentrax

EXPOSE 8000
# docker_start.py: wait for Postgres, run the Alembic migrations, seed demo data into an empty database, start uvicorn
CMD ["python", "scripts/docker_start.py"]
