"""
ORGATEC Sovereign API – v7.0
Arquitetura: FastAPI + SQLAlchemy + JWT + Clean Architecture
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

# Carrega .env e config.env ANTES de importar quaisquer módulos que leiam
# variáveis de ambiente no top-level (database_v2, integrations, etc.).
# Estratégia:
#   1) config.env → defaults compartilhados (não sobrescreve ambient)
#   2) .env       → segredos do projeto (override de strings vazias do ambient)
from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / "config.env", override=False)

# .env tem prioridade — substitui valores vazios herdados do ambient
def _load_dotenv_substituindo_vazios(path: Path) -> None:
    if not path.exists():
        return
    for linha in path.read_text(encoding="utf-8").splitlines():
        s = linha.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        chave, valor = s.split("=", 1)
        chave = chave.strip()
        valor = valor.strip().strip('"').strip("'")
        # Sobrescreve apenas se ambient não tiver ou tiver vazio
        if not os.environ.get(chave):
            os.environ[chave] = valor


_load_dotenv_substituindo_vazios(_PROJECT_ROOT / ".env")


from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from api.auth.security import TokenData, get_current_user
from api.routes import auditoria
from api.routes import auth as auth_router
from api.routes import notas as notas_router
from api.schemas import ClienteCreate, ClienteResponse
from src.infrastructure.database_v2 import Cliente, SessionLocal, init_db

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
        new_hash = hash_password("Admin@2026!")
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


# ── Rotas: Clientes (protegidas por JWT) ──────────────────────────────────────
router_clientes = APIRouter(prefix="/clientes", tags=["Clientes"])


@router_clientes.get("/", response_model=list[ClienteResponse])
def listar_clientes(
    db: Session = Depends(get_db),
    _: TokenData = Depends(get_current_user),
):
    return db.query(Cliente).all()


@router_clientes.post("/", status_code=201, response_model=ClienteResponse)
def criar_cliente(
    client: ClienteCreate,
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
app.include_router(notas_router.router)


# ── Health ────────────────────────────────────────────────────────────────────
def _verificar_saude(db: Session) -> dict:
    try:
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
        db_status = "ok"
    except Exception as exc:
        db_status = f"error: {exc}"

    try:
        import fitz
        pdf_engine = f"pymupdf-{fitz.__version__}"
    except Exception:
        pdf_engine = "pdfplumber (slow fallback)"

    try:
        from src.nfa_repo_bridge import info_bridge
        bridge_info = info_bridge()
        bridge_status = {
            "disponivel": bridge_info.get("hardening_disponivel", False),
            "modulos_ok": sum(1 for v in bridge_info.get("modulos_carregados", {}).values() if v),
            "modulos_total": len(bridge_info.get("modulos_carregados", {})),
        }
    except Exception as exc:
        bridge_status = {"erro": str(exc)[:100]}

    # Status do squad Horizon-Blue (multiagente Claude)
    try:
        from src.integrations.horizon_squad import status_squad
        squad_status = status_squad()
    except Exception as exc:
        squad_status = {"erro": str(exc)[:100]}

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "version": "7.0.0",
        "db": db_status,
        "pdf_engine": pdf_engine,
        "nfa_repo_bridge": bridge_status,
        "horizon_squad": squad_status,
    }


@app.get("/ping", tags=["Health"])
def ping(db: Session = Depends(get_db)):
    return _verificar_saude(db)


@app.get("/health", tags=["Health"])
def health(db: Session = Depends(get_db)):
    return _verificar_saude(db)
