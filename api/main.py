"""
ORGATEC Sovereign API – v7.2
Bootstrap limpo: apenas configuração, middleware e registro de routers.
Toda lógica de negócio em api/routes/*.
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.middleware.rate_limit import RateLimitMiddleware
from api.routes import auditoria
from api.routes import auth as auth_router
from api.routes import clientes, agente, metrics, finance
from src.infrastructure.database_v2 import init_db
from src.infrastructure.laudos_cleanup import cleanup_laudos_antigos
from src.infrastructure.logging_config import setup_logging, get_logger

logger = get_logger("orgatec.api")


async def _cleanup_loop() -> None:
    """Tarefa periódica: cleanup de laudos antigos a cada 24h."""
    intervalo = int(os.getenv("LAUDOS_CLEANUP_INTERVAL_SECONDS", "86400"))
    while True:
        try:
            cleanup_laudos_antigos()
        except Exception:
            logger.exception("cleanup laudos falhou")
        await asyncio.sleep(intervalo)


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    init_db()
    cleanup_task = asyncio.create_task(_cleanup_loop())
    logger.info("ORGATEC API v7.2 iniciada")
    try:
        yield
    finally:
        cleanup_task.cancel()
        logger.info("ORGATEC API v7.2 encerrada")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="ORGATEC Sovereign API",
    version="7.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── Rate Limiting ─────────────────────────────────────────────────────────────
app.add_middleware(RateLimitMiddleware, rate=60, window=60.0)


# ── CORS ──────────────────────────────────────────────────────────────────────
_raw = os.getenv("ALLOWED_ORIGINS", "")
ALLOWED_ORIGINS: list[str] = (
    [o.strip() for o in _raw.split(",") if o.strip()]
    if _raw
    else ["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth_router.router)
app.include_router(auditoria.router)
app.include_router(clientes.router)
app.include_router(agente.router)
app.include_router(metrics.router)
app.include_router(finance.router)


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/ping", tags=["Health"])
async def ping():
    return {"status": "ok", "version": "7.2.0"}
