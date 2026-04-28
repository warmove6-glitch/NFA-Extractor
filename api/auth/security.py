"""
ORGATEC – Módulo de Segurança (JWT + Bcrypt)

Mudanças de segurança:
- CRASH se JWT_SECRET_KEY não estiver definida (nunca usar fallback inseguro)
- Algoritmo explícito (HS256)
- Token expiry configurável via env
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

# ── Configuração JWT ─────────────────────────────────────────────────────────

JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "")
JWT_ALGORITHM: str = "HS256"
JWT_EXPIRE_HOURS: int = int(os.getenv("JWT_EXPIRE_HOURS", "8"))

# SEGURANÇA CRÍTICA: Nunca rodar sem secret configurado
if not JWT_SECRET_KEY:
    print(
        "\n[ERRO FATAL] JWT_SECRET_KEY não está definida.\n"
        "Configure a variável de ambiente JWT_SECRET_KEY com pelo menos 32 caracteres.\n"
        "Exemplo: export JWT_SECRET_KEY=$(openssl rand -hex 32)\n",
        file=sys.stderr,
    )
    sys.exit(1)

if len(JWT_SECRET_KEY) < 32:
    print(
        f"\n[ERRO FATAL] JWT_SECRET_KEY tem apenas {len(JWT_SECRET_KEY)} caracteres.\n"
        "Use pelo menos 32 caracteres para segurança adequada.\n",
        file=sys.stderr,
    )
    sys.exit(1)

# ── Bcrypt ───────────────────────────────────────────────────────────────────

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ── Schemas ──────────────────────────────────────────────────────────────────

class TokenData(BaseModel):
    sub: str
    email: str = ""
    role: str = "user"


# ── Funções ──────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Gera hash bcrypt da senha."""
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Verifica senha contra hash bcrypt."""
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Cria JWT com expiração configurável."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(hours=JWT_EXPIRE_HOURS))
    to_encode["exp"] = expire
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    """Valida JWT e retorna dados do usuário autenticado."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido ou expirado.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        sub: str = payload.get("sub", "")
        if not sub:
            raise credentials_exception
        return TokenData(
            sub=sub,
            email=payload.get("email", ""),
            role=payload.get("role", "user"),
        )
    except JWTError:
        raise credentials_exception
