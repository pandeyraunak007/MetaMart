"""Vercel serverless entrypoint.

Exposes a minimal FastAPI app with only the stateless quality endpoints. The
mart/* surface (libraries, folders, models, check-in/out, permissions) needs
Postgres and lives on a separate deployment when we want the full stack.
"""
import sys
from pathlib import Path

# Make `backend/src/metamart/...` importable from this serverless function.
_SRC = Path(__file__).resolve().parent.parent / "backend" / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from fastapi import FastAPI  # noqa: E402
from metamart.quality.router import router as quality_router  # noqa: E402

app = FastAPI(
    title="MetaMart Quality — Public Demo",
    description=(
        "Stateless quality scoring (POST /api/v1/quality/score-json). "
        "The full Mart Portal surface requires Postgres and is not deployed here."
    ),
    version="0.1.0",
)

app.include_router(quality_router, prefix="/api/v1")


@app.get("/api/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
