"""
ORGATEC – Módulo de Segurança (JWT + Bcrypt + Refresh Token)

Segurança:
- CRASH se JWT_SECRET_KEY não estiver definida (nunca usar fallback inseguro)
- Access token curto (30min) + Refresh token longo (7 dias)
- Refresh tokens com claim "type" para impedir uso cruzado
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
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

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


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # segundos até expiração do access token


# ── Política de Senha ────────────────────────────────────────────────────────

MIN_PASSWORD_LENGTH = 12


class PasswordPolicyError(ValueError):
    """Senha não atende à política mínima."""


def validate_password(password: str, *, email: str = "", nome: str = "") -> None:
    """Valida senha contra política mínima.

    Regras:
    - Pelo menos 12 caracteres
    - Não pode conter o local-part do email
    - Não pode conter palavras de >=4 chars do nome
    - Precisa misturar letras + dígitos
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        raise PasswordPolicyError(
            f"Senha precisa ter pelo menos {MIN_PASSWORD_LENGTH} caracteres."
        )
    if not (any(c.isalpha() for c in password) and any(c.isdigit() for c in password)):
        raise PasswordPolicyError("Senha precisa conter letras e dígitos.")
    if email:
        local = email.split("@")[0].lower()
        if len(local) >= 4 and local in password.lower():
            raise PasswordPolicyError("Senha não pode conter parte do email.")
    if nome:
        for parte in nome.split():
            if len(parte) >= 4 and parte.lower() in password.lower():
                raise PasswordPolicyError("Senha não pode conter parte do nome.")


# ── Funções ──────────────────────────────────────────────────────────────────

def hash_password(
    password: str,
    *,
    validate: bool = True,
    email: str = "",
    nome: str = "",
) -> str:
    """Gera hash bcrypt da senha.

    Por padrão valida a política. Para hashing de senhas pré-validadas
    (ex.: migração ou fixtures de teste), passe validate=False.
    """
    if validate:
        validate_password(password, email=email, nome=nome)
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Verifica senha contra hash bcrypt."""
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Cria access token JWT curto (30min por padrão)."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode["exp"] = expire
    to_encode["type"] = "access"
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_refresh_token(data: dict) -> str:
    """Cria refresh token JWT longo (7 dias por padrão)."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode["exp"] = expire
    to_encode["type"] = "refresh"
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_token_pair(data: dict) -> TokenPair:
    """Gera par access + refresh token."""
    return TokenPair(
        access_token=create_access_token(data),
        refresh_token=create_refresh_token(data),
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


def verify_refresh_token(token: str) -> TokenData:
    """Valida refresh token e retorna dados do usuário.

    Rejeita access tokens usados como refresh (via claim 'type').
    """
    error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Refresh token inválido ou expirado.",
    )
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise error
        sub = payload.get("sub", "")
        if not sub:
            raise error
        return TokenData(
            sub=sub,
            email=payload.get("email", ""),
            role=payload.get("role", "user"),
        )
    except JWTError:
        raise error


def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    """Valida access token JWT e retorna dados do usuário autenticado."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido ou expirado.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        # Rejeitar refresh tokens usados como access
        if payload.get("type") == "refresh":
            raise credentials_exception
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
