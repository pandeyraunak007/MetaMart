from fastapi import FastAPI

from metamart.config import get_settings
from metamart.mart.router import router as mart_router

settings = get_settings()

app = FastAPI(
    title="MetaMart Quality",
    description="Mart-Portal-style data model quality scoring platform.",
    version="0.1.0",
)

app.include_router(mart_router, prefix=settings.api_v1_prefix)


@app.get("/healthz", tags=["meta"])
def healthz() -> dict[str, str]:
    return {"status": "ok"}
