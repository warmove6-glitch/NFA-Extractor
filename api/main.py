from fastapi import FastAPI, APIRouter, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import logging
import time
from pydantic import BaseModel, Field
from typing import List, Optional

from api.routes import auditoria
from src.infrastructure.database_v2 import SessionLocal, Cliente, Laudo

# --- SCHEMAS PYDANTIC V2 ---
class ClientCreate(BaseModel):
    nome: str = Field(..., min_length=3)
    cpf_cnpj: str = Field(..., description="CPF ou CNPJ limpo")

class ChatRequest(BaseModel):
    pergunta: str
    contexto: Optional[str] = ""

app = FastAPI(title="ORGATEC Sovereign API", version="6.4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://localhost:5174", "http://localhost:5175",
        "http://127.0.0.1:5173", "http://127.0.0.1:5174", "http://127.0.0.1:5175"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Injeção de Dependência DB Otimizada
def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

# --- ROTAS DE CLIENTES ---
router_clientes = APIRouter(prefix="/clientes", tags=["Clientes"])

@router_clientes.get("/")
def listar_clientes(db: Session = Depends(get_db)):
    return db.query(Cliente).all()

@router_clientes.post("/")
def criar_cliente(client: ClientCreate, db: Session = Depends(get_db)):
    novo = Cliente(nome=client.nome, cpf_cnpj=client.cpf_cnpj)
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return novo

# --- ROTAS DO AGENTE ---
router_agente = APIRouter(prefix="/agente", tags=["Agente"])

@router_agente.post("/chat")
async def chat_agente(request: ChatRequest):
    from ai_client import perguntar
    try:
        res = perguntar(notas=[], context_ia=request.contexto, pergunta=request.pergunta)
        return {"response": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

app.include_router(auditoria.router)
app.include_router(router_clientes)
app.include_router(router_agente)

@app.get("/ping")
async def ping(): return {"message": "pong"}

@app.get("/")
def root(): return {"status": "Sovereign Shield Active"}
