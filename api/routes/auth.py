"""
ORGATEC – Rotas de Autenticação
POST /auth/login   → recebe email+senha, devolve JWT
GET  /auth/me      → devolve dados do usuário autenticado
POST /auth/seed    → cria usuário admin inicial (apenas se não existir)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from api.auth.security import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
    TokenData,
)
from src.infrastructure.database_v2 import SessionLocal, User

router = APIRouter(prefix="/auth", tags=["Auth"])


# ── Schemas de resposta ──────────────────────────────────────────────────────
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


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
    """
    Autentica via OAuth2PasswordRequestForm (campo 'username' = e-mail, 'password' = senha).
    Compatível com Swagger UI e também com fetch JSON do frontend.
    """
    user = db.query(User).filter(User.email == form.username).first()

    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha incorretos.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Conta desativada. Contate o administrador.")

    token = create_access_token(
        {"sub": str(user.id), "email": user.email, "role": user.role}
    )

    return {
        "access_token": token,
        "token_type": "bearer",
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
