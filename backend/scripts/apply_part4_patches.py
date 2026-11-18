"""One-time setup after merging origin/main: wires Part 4 into Asad's files WITHOUT replacing them.

  1. backend/app/main.py        adds the Wazuh webhook router and the optional poller
  2. backend/requirements.txt   appends httpx, pytest and a bcrypt pin if missing
  3. backend/.env.example       appends the Wazuh ingestion settings if missing
  4. backend/.env               creates a local dev file if you do not have one

Safe to run twice. From the repo root:  python backend/scripts/apply_part4_patches.py
"""
from __future__ import annotations

import secrets
import sys
from pathlib import Path

BACKEND = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]


def fail(msg: str) -> None:
    print(f"ERROR: {msg}")
    sys.exit(1)


def find_line(lines: list[str], prefix: str) -> int:
    for i, line in enumerate(lines):
        if line.startswith(prefix):
            return i
    fail(f"could not find a line starting with {prefix!r} in main.py (has Asad changed it?)")
    return -1


# --------------------------------------------------------------------------- main.py
LIFESPAN = '''@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the Wazuh poller only when WAZUH_INGEST_MODE=poll (Part 4)."""
    w = get_wazuh_settings()
    poller = None
    if w.WAZUH_INGEST_MODE == "poll":
        poller = Poller(
            IndexerSource(w.WAZUH_INDEXER_URL, w.WAZUH_INDEXER_USER,
                          w.WAZUH_INDEXER_PASSWORD, w.WAZUH_VERIFY_TLS),
            get_session_factory(), w.WAZUH_POLL_INTERVAL_SECONDS, w.WAZUH_MIN_LEVEL,
        )
        poller.start()
    yield
    if poller:
        poller.stop()

'''.splitlines()

IMPORTS = [
    "from contextlib import asynccontextmanager",
    "",
    "from .ingestion.db_access import get_session_factory",
    "from .ingestion.poller import Poller",
    "from .ingestion.sources import IndexerSource",
    "from .ingestion.wazuh_settings import get_wazuh_settings",
    "from .ingestion.webhook import router as webhook_router",
]


def patch_main() -> None:
    path = BACKEND / "app" / "main.py"
    if not path.exists():
        fail(f"{path} not found (did you merge origin/main?)")
    text = path.read_text(encoding="utf-8")
    if "lifespan=lifespan" in text or "webhook_router" in text:
        print("main.py: already patched, skipped")
        return
    lines = text.splitlines()

    # work from the bottom up so earlier line numbers stay valid
    i = find_line(lines, "app.include_router(admin.router")
    lines.insert(i + 1, "app.include_router(webhook_router)  # Wazuh webhook (Part 4): POST /api/webhooks/wazuh")

    i = find_line(lines, "app = FastAPI(")
    lines.insert(i + 1, "    lifespan=lifespan,")
    lines[i:i] = LIFESPAN + [""]

    i = find_line(lines, "from .routers import")
    lines[i:i] = IMPORTS

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("main.py: patched")


# ------------------------------------------------------------------- requirements.txt
def patch_requirements() -> None:
    path = BACKEND / "requirements.txt"
    if not path.exists():
        fail(f"{path} not found")
    text = path.read_text(encoding="utf-8")
    names = {ln.split("[")[0].split(">")[0].split("=")[0].split("<")[0].strip().lower()
             for ln in text.splitlines() if ln.strip() and not ln.startswith("#")}
    wanted = [("httpx", "httpx>=0.27"), ("pytest", "pytest>=8.0"),
              # passlib 1.7.4 breaks with bcrypt 5.x, so keep bcrypt below 5
              ("bcrypt", "bcrypt>=4.0.1,<5")]
    added = [line for name, line in wanted if name not in names]
    if added:
        if not text.endswith("\n"):
            text += "\n"
        path.write_text(text + "\n".join(added) + "\n", encoding="utf-8")
    print("requirements.txt: added " + (", ".join(added) if added else "nothing (already present)"))


# ---------------------------------------------------------------------- .env.example
EXAMPLE_BLOCK = """
# Wazuh ingestion (Part 4)
# WAZUH_INGEST_MODE: replay | poll (indexer polling) | webhook
WAZUH_INGEST_MODE=replay
WAZUH_POLL_INTERVAL_SECONDS=30
WAZUH_MIN_LEVEL=4
WAZUH_VERIFY_TLS=false
WAZUH_WEBHOOK_SECRET=change-me-long-random-string
TRIAGE_WORKERS=32
"""


def patch_env_example() -> None:
    path = BACKEND / ".env.example"
    if not path.exists():
        print(".env.example: not found, skipped")
        return
    text = path.read_text(encoding="utf-8")
    if "WAZUH_INGEST_MODE" in text:
        print(".env.example: already has the Wazuh ingestion block, skipped")
        return
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text + EXAMPLE_BLOCK, encoding="utf-8")
    print(".env.example: appended the Wazuh ingestion block")


# ---------------------------------------------------------------------------- .env
def make_env() -> None:
    path = BACKEND / ".env"
    if path.exists():
        print(".env: already exists, left untouched. Check that DATABASE_URL points at "
              "postgresql+psycopg://sentrax:sentrax@localhost:5432/sentrax (the docker-compose database).")
        return
    path.write_text(
        "DATABASE_URL=postgresql+psycopg://sentrax:sentrax@localhost:5432/sentrax\n"
        "DATABASE_URL_ASYNC=postgresql+psycopg_async://sentrax:sentrax@localhost:5432/sentrax\n"
        f"SECRET_KEY={secrets.token_hex(24)}\n"
        "DEMO_MODE=true\n"
        "LLM_PROVIDER=mock\n"
        "WAZUH_INGEST_MODE=replay\n"
        f"WAZUH_WEBHOOK_SECRET={secrets.token_hex(24)}\n"
        "WAZUH_INDEXER_URL=https://localhost:9200\n"
        "WAZUH_INDEXER_USER=admin\n"
        "WAZUH_INDEXER_PASSWORD=\n",
        encoding="utf-8",
    )
    print(".env: created for local development (git ignores it)")


if __name__ == "__main__":
    patch_main()
    patch_requirements()
    patch_env_example()
    make_env()
