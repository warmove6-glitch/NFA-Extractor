"""
ORGATEC — Cliente Supabase centralizado.
Fornece acesso ao banco (via DATABASE_URL), Storage e Auth.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Carrega variáveis do config.env se não estiverem no ambiente ─────────────
def _load_env() -> None:
    env_path = Path(__file__).resolve().parent.parent.parent / "config.env"
    if env_path.exists() and not os.getenv("SUPABASE_URL"):
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())

_load_env()

SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_KEY: str = os.getenv("SUPABASE_SERVICE_KEY", "")
SUPABASE_JWT_SECRET: str = os.getenv("SUPABASE_JWT_SECRET", "")

STORAGE_BUCKET = "laudos"


def supabase_configurado() -> bool:
    return bool(SUPABASE_URL and SUPABASE_SERVICE_KEY and "AQUI" not in SUPABASE_SERVICE_KEY)


@lru_cache(maxsize=1)
def get_client():
    """Retorna cliente Supabase com service_role (backend only)."""
    if not supabase_configurado():
        raise RuntimeError(
            "Supabase não configurado. Preencha SUPABASE_URL e SUPABASE_SERVICE_KEY no config.env."
        )
    from supabase import create_client
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


# ── Storage ──────────────────────────────────────────────────────────────────

def garantir_bucket() -> None:
    """Cria o bucket 'laudos' se não existir (idempotente)."""
    sb = get_client()
    buckets = [b.name for b in sb.storage.list_buckets()]
    if STORAGE_BUCKET not in buckets:
        sb.storage.create_bucket(STORAGE_BUCKET, options={"public": False})
        logger.info(f"Bucket '{STORAGE_BUCKET}' criado no Supabase Storage.")


def upload_laudo(nome_arquivo: str, conteudo: bytes, content_type: str = "application/pdf") -> str:
    """
    Faz upload de um laudo para o Supabase Storage.
    Retorna a URL pública assinada (válida por 7 dias).
    """
    sb = get_client()
    caminho = f"{nome_arquivo}"

    sb.storage.from_(STORAGE_BUCKET).upload(
        caminho,
        conteudo,
        {"content-type": content_type, "upsert": "true"},
    )

    resposta = sb.storage.from_(STORAGE_BUCKET).create_signed_url(caminho, expires_in=604800)
    url = resposta.get("signedURL") or resposta.get("signedUrl", "")
    logger.info(f"Laudo '{nome_arquivo}' salvo no Supabase Storage.")
    return url


def download_laudo(nome_arquivo: str) -> bytes | None:
    """Baixa bytes de um laudo do Storage. Retorna None se não encontrado."""
    try:
        sb = get_client()
        return sb.storage.from_(STORAGE_BUCKET).download(nome_arquivo)
    except Exception as exc:
        logger.warning(f"Arquivo '{nome_arquivo}' não encontrado no Storage: {exc}")
        return None


def url_assinada(nome_arquivo: str, expires_in: int = 3600) -> str | None:
    """Retorna URL assinada para download direto. None se falhar."""
    try:
        sb = get_client()
        resposta = sb.storage.from_(STORAGE_BUCKET).create_signed_url(nome_arquivo, expires_in=expires_in)
        return resposta.get("signedURL") or resposta.get("signedUrl")
    except Exception as exc:
        logger.warning(f"Erro ao gerar URL assinada para '{nome_arquivo}': {exc}")
        return None
