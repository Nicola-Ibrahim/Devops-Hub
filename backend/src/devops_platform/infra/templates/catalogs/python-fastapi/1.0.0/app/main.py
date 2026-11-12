"""FastAPI starter with readiness endpoint and redacted structured logs."""

import logging
import os

import psycopg
from fastapi import FastAPI, HTTPException

from app.database import check_database
from app.logging_config import configure_logging

configure_logging()
logger = logging.getLogger("application")
app = FastAPI(title="__APPLICATION_NAME__")


@app.get("/healthz", include_in_schema=False)
def healthz() -> dict[str, str]:
    try:
        check_database()
    except (OSError, ValueError, psycopg.Error):
        logger.warning("database readiness unavailable")
        raise HTTPException(status_code=503, detail="Database unavailable") from None
    return {"status": "ok"}


@app.get("/")
async def root() -> dict[str, str]:
    logger.info("application request")
    return {
        "service": "__APPLICATION_NAME__",
        "environment": os.getenv("APP_ENV", "local"),
    }
