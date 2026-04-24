"""
ORGATEC – Módulo de Segurança JWT
Responsabilidades:
  - Hashing de senhas (bcrypt direto — sem passlib para evitar bug truncate)
  - Criação e verificação de tokens JWT (python-jose)
  - Dependência FastAPI para extrair o usuário autenticado
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt as _bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel

# ── Configurações ────────────────────────────────────────────────────────────
SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "TROQUE_EM_PRODUCAO_32_CHARS_MINIMO!")
ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))  # 8h

# ── Crypto ───────────────────────────────────────────────────────────────────
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


class TokenData(BaseModel):
    sub: str          # user id como string
    email: str
    role: str = "user"


# ── Funções de senha (bcrypt direto, sem passlib) ────────────────────────────
def hash_password(plain: str) -> str:
    """Gera hash bcrypt sem passar por passlib (evita bug truncate em bcrypt≥4.1)."""
    return _bcrypt.hashpw(plain.encode("utf-8"), _bcrypt.gensalt(12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verifica senha com bcrypt direto. Compatível com hashes gerados por passlib ($2b$)."""
    try:
        return _bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ── Funções de token ─────────────────────────────────────────────────────────
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> TokenData:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return TokenData(
            sub=payload["sub"],
            email=payload["email"],
            role=payload.get("role", "user"),
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── Dependência FastAPI ──────────────────────────────────────────────────────
def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    """Injete em qualquer rota protegida: current_user: TokenData = Depends(get_current_user)"""
    return decode_token(token)


def require_admin(current_user: TokenData = Depends(get_current_user)) -> TokenData:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores.")
    return current_user
