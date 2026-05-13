"""Vercel `backend` service entrypoint.

Exposes a minimal FastAPI app with the stateless quality endpoints.
Vercel auto-detects `app` and serves it as an ASGI function. The
`mart/*` surface (libraries, check-in/out, etc.) is intentionally not
wired here because it needs Postgres — it lives in `metamart.main` for
local dev only.
"""
import sys
from pathlib import Path

# Make `src/metamart/...` importable inside the Vercel function bundle.
_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from fastapi import FastAPI  # noqa: E402
from metamart.quality.router import router as quality_router  # noqa: E402

app = FastAPI(
    title="MetaMart Quality — Public Demo",
    description=(
        "Stateless quality-scoring endpoint. The full Mart Portal "
        "surface (libraries, folders, models, check-in/out, "
        "permissions) requires Postgres and is not deployed here."
    ),
    version="0.1.0",
)

# The Vercel routePrefix `/api` is stripped before reaching this service,
# so we register routes at `/v1/...` (not `/api/v1/...`).
app.include_router(quality_router, prefix="/v1")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
