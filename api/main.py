"""
ORGATEC Sovereign API – v7.1
Arquitetura: FastAPI + SQLAlchemy + JWT + Clean Architecture

Mudanças v7.1:
- Lifespan context manager (substitui on_event depreciado)
- Endpoint /metrics para observabilidade do circuit breaker
- get_db centralizado
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

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


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicialização e shutdown da aplicação."""
    init_db()
    logger.info("ORGATEC API v7.1 iniciada")
    yield
    logger.info("ORGATEC API v7.1 encerrada")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="ORGATEC Sovereign API",
    version="7.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

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


class ChatRequest(BaseModel):
    pergunta: str
    contexto: Optional[str] = ""


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


# ── Rotas: Agente IA (protegidas por JWT) ─────────────────────────────────────
router_agente = APIRouter(prefix="/agente", tags=["Agente"])


@router_agente.post("/chat")
async def chat_agente(
    request: ChatRequest,
    _: TokenData = Depends(get_current_user),
):
    from src.infrastructure.ai_client import perguntar
    try:
        res = perguntar(notas=[], context_ia=request.contexto, pergunta=request.pergunta)
        return {"response": res}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Rotas: Métricas IA (protegidas por JWT admin) ────────────────────────────
router_metrics = APIRouter(prefix="/metrics", tags=["Observabilidade"])


@router_metrics.get("/ai")
def ai_metrics(current_user: TokenData = Depends(get_current_user)):
    """Retorna métricas do circuit breaker dos provedores de IA."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores.")
    from src.infrastructure.ai_client import get_ai_metrics
    return get_ai_metrics()


# ── Registro de routers ───────────────────────────────────────────────────────
app.include_router(auth_router.router)
app.include_router(auditoria.router)
app.include_router(router_clientes)
app.include_router(router_agente)
app.include_router(router_metrics)


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/ping", tags=["Health"])
async def ping():
    return {"status": "ok", "version": "7.1.0"}
