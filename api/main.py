"""
ORGATEC Sovereign API – v7.0
Arquitetura: FastAPI + SQLAlchemy + JWT + Clean Architecture
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI, APIRouter, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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
    else [
        "http://localhost:5173", "http://localhost:5174", "http://localhost:5175",
        "http://localhost:3000", "http://localhost:8080",
        "http://127.0.0.1:5173", "http://127.0.0.1:5174", "http://127.0.0.1:5175",
        "http://127.0.0.1:3000",
    ]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Origin",
                   "X-Requested-With", "Access-Control-Request-Method",
                   "Access-Control-Request-Headers"],
    expose_headers=["Content-Disposition"],
    max_age=600,
)


# ── Exception handler global com CORS ─────────────────────────────────────────
@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception):
    """Garante que exceções não tratadas retornem JSON com headers CORS corretos."""
    origin = request.headers.get("origin", "")
    headers = {}
    if origin in ALLOWED_ORIGINS:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
    logger.error(f"Exceção não tratada em {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": f"Erro interno: {type(exc).__name__}: {exc}"},
        headers=headers,
    )


# ── Lifecycle ─────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    init_db()
    _seed_admin()
    logger.info("✅  ORGATEC API v7.0 iniciada")


def _seed_admin():
    """Cria ou reconstrói o hash do usuário admin padrão (usa bcrypt direto)."""
    from api.auth.security import hash_password
    from src.infrastructure.database_v2 import User
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == "admin@orgatec.com.br").first()
        new_hash = hash_password("Admin@2024!")
        if existing:
            # Sempre re-hasheia para garantir compatibilidade com bcrypt direto
            existing.hashed_password = new_hash
            db.commit()
            logger.info("✅  Hash admin atualizado (bcrypt direto)")
        else:
            db.add(User(
                nome="Administrador ORGATEC",
                email="admin@orgatec.com.br",
                hashed_password=new_hash,
                role="admin",
                is_active=True,
            ))
            db.commit()
            logger.info("✅  Admin padrão criado: admin@orgatec.com.br")
    except Exception as exc:
        logger.warning(f"Seed admin ignorado: {exc}")
    finally:
        db.close()


# ── DB Dependency ─────────────────────────────────────────────────────────────
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Schemas ───────────────────────────────────────────────────────────────────
class ClientCreate(BaseModel):
    nome: str = Field(..., min_length=3)
    cpf_cnpj: str = Field(..., description="CPF ou CNPJ (somente dígitos)")


# ── Rotas: Clientes (protegidas por JWT) ──────────────────────────────────────
router_clientes = APIRouter(prefix="/clientes", tags=["Clientes"])


@router_clientes.get("/")
def listar_clientes(
    db: Session = Depends(get_db),
    _: TokenData = Depends(get_current_user),
):
    return db.query(Cliente).all()


@router_clientes.post("/", status_code=201)
def criar_cliente(
    client: ClientCreate,
    db: Session = Depends(get_db),
    _: TokenData = Depends(get_current_user),
):
    if db.query(Cliente).filter_by(cpf_cnpj=client.cpf_cnpj).first():
        raise HTTPException(status_code=409, detail="CPF/CNPJ já cadastrado.")
    novo = Cliente(nome=client.nome, cpf_cnpj=client.cpf_cnpj)
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return novo


@router_clientes.delete("/{client_id}", status_code=204)
def remover_cliente(
    client_id: int,
    db: Session = Depends(get_db),
    _: TokenData = Depends(get_current_user),
):
    cliente = db.query(Cliente).filter_by(id=client_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")
    db.delete(cliente)
    db.commit()


# ── Registro de routers ───────────────────────────────────────────────────────
app.include_router(auth_router.router)
app.include_router(auditoria.router)
app.include_router(router_clientes)


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/ping", tags=["Health"])
def ping(db: Session = Depends(get_db)):
    try:
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
        db_status = "ok"
    except Exception as exc:
        db_status = f"error: {exc}"
    return {"status": "ok", "version": "7.0.0", "db": db_status}
