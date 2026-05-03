"""
ORGATEC – Rotas de Autenticação
POST /auth/login    → recebe email+senha, devolve access + refresh token
POST /auth/refresh  → recebe refresh token, devolve novo par de tokens
GET  /auth/me       → devolve dados do usuário autenticado
POST /auth/seed     → cria usuário admin inicial (apenas se não existir)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.auth.security import (
    TokenData,
    create_token_pair,
    get_current_user,
    hash_password,
    verify_password,
    verify_refresh_token,
)
from src.infrastructure.database_v2 import SessionLocal, User

router = APIRouter(prefix="/auth", tags=["Auth"])


# ── Schemas ──────────────────────────────────────────────────────────────────

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


# ── DB Dependency ────────────────────────────────────────────────────────────
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Autentica e retorna par access + refresh token."""
    user = db.query(User).filter(User.email == form.username).first()

    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha incorretos.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Conta desativada. Contate o administrador.")

    token_data = {"sub": str(user.id), "email": user.email, "role": user.role}
    pair = create_token_pair(token_data)

    return {
        "access_token": pair.access_token,
        "refresh_token": pair.refresh_token,
        "token_type": pair.token_type,
        "expires_in": pair.expires_in,
        "user": {"id": user.id, "email": user.email, "nome": user.nome, "role": user.role},
    }


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    """Renova tokens usando refresh token válido."""
    token_data = verify_refresh_token(body.refresh_token)

    # Verificar se o usuário ainda existe e está ativo
    user = db.query(User).filter(User.id == int(token_data.sub)).first()
    if not user:
        raise HTTPException(status_code=401, detail="Usuário não encontrado.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Conta desativada.")

    new_pair = create_token_pair(
        {"sub": str(user.id), "email": user.email, "role": user.role}
    )

    return {
        "access_token": new_pair.access_token,
        "refresh_token": new_pair.refresh_token,
        "token_type": new_pair.token_type,
        "expires_in": new_pair.expires_in,
        "user": {"id": user.id, "email": user.email, "nome": user.nome, "role": user.role},
    }


@router.get("/me", response_model=MeResponse)
def me(current_user: TokenData = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == int(current_user.sub)).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    return {"id": user.id, "email": user.email, "nome": user.nome, "role": user.role}


@router.post("/seed", status_code=201)
def seed_admin(db: Session = Depends(get_db)):
    """Cria o usuário admin padrão se ainda não existir. Remover em produção."""
    existing = db.query(User).filter(User.email == "admin@orgatec.com.br").first()
    if existing:
        return {"detail": "Usuário admin já existe."}

    admin = User(
        nome="Administrador ORGATEC",
        email="admin@orgatec.com.br",
        hashed_password=hash_password("Admin@2024!"),
        role="admin",
        is_active=True,
    )
    db.add(admin)
    db.commit()
    return {"detail": "Usuário admin criado.", "email": "admin@orgatec.com.br", "senha": "Admin@2024!"}
