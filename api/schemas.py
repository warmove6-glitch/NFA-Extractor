"""
ORGATEC – Schemas Pydantic (API layer).

Separados dos models SQLAlchemy para manutenibilidade.
Cada schema tem responsabilidade única: input, output ou internal.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional


# ── Auth ─────────────────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict


class RefreshRequest(BaseModel):
    refresh_token: str


class MeResponse(BaseModel):
    id: int
    email: str
    nome: str
    role: str


# ── Clientes ─────────────────────────────────────────────────────────────────

class ClienteCreate(BaseModel):
    nome: str = Field(..., min_length=3)
    cpf_cnpj: str = Field(..., description="CPF ou CNPJ (somente dígitos)")


class ClienteResponse(BaseModel):
    id: int
    nome: str
    cpf_cnpj: str

    model_config = {"from_attributes": True}


# ── Agente IA ────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    pergunta: str
    contexto: Optional[str] = ""


class ChatResponse(BaseModel):
    response: str


# ── Health ───────────────────────────────────────────────────────────────────

class PingResponse(BaseModel):
    status: str
    version: str
