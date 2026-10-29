from fastapi import FastAPI
from sqlalchemy import create_engine, text

from app.settings import get_settings

app = FastAPI(title="Sentra-X")


@app.get("/api/health")
def health():
    db = "down"
    try:
        engine = create_engine(get_settings().db_url, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db = "up"
    except Exception:
        pass
    return {"status": "ok", "db": db}