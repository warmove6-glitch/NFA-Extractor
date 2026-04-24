"""
ORGATEC Sovereign API – v7.0
Arquitetura: FastAPI + SQLAlchemy + JWT + Clean Architecture
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI, APIRouter, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Optional

from api.routes import auditoria
from api.routes import auth as auth_router
from api.auth.security import get_current_user, TokenData
from src.infrastructure.database_v2 import SessionLocal, Cliente, init_db

logger = logging.getLogger("uvicorn")

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="ORGATEC Sovereign API",
    version="7.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
_raw = os.getenv("ALLOWED_ORIGINS", "")
ALLOWED_ORIGINS: list[str] = (
    [o.strip() for o in _raw.split(",") if o.strip()]
    if _raw
    else ["http://localhost:5173", "http://localhost:5174", "http://localhost:3000",
           "http://127.0.0.1:5173", "http://127.0.0.1:5174"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)


# ── Lifecycle ─────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    init_db()
    logger.info("✅  ORGATEC API v7.0 iniciada")


# ── DB Dependency ─────────────────────────────────────────────────────────────
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Schemas ────────────────────────────────�