"""
ORGATEC – Limpeza periódica de PDFs de laudos antigos.

Evita crescimento indefinido do diretório data/laudos/.
TTL configurável via env LAUDOS_TTL_DAYS (default 90 dias — adequado
para retenção de auditoria fiscal de curto prazo).

Para retenção LONGA (5 anos LGPD/fiscal), mover laudos para object
storage com lifecycle policy ANTES de habilitar este cleanup.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_TTL_DAYS = 90
LAUDOS_DIR = Path("data") / "laudos"


def cleanup_laudos_antigos(ttl_days: int | None = None, dry_run: bool = False) -> dict:
    """Remove PDFs em data/laudos/ com mtime > ttl_days.

    Args:
        ttl_days: idade máxima em dias (default: env LAUDOS_TTL_DAYS ou 90).
        dry_run: se True, apenas conta sem deletar.

    Returns:
        {"escaneados": int, "removidos": int, "bytes_liberados": int, "erros": int}
    """
    if ttl_days is None:
        ttl_days = int(os.getenv("LAUDOS_TTL_DAYS", str(DEFAULT_TTL_DAYS)))

    if not LAUDOS_DIR.exists():
        return {"escaneados": 0, "removidos": 0, "bytes_liberados": 0, "erros": 0}

    cutoff = time.time() - (ttl_days * 86400)
    escaneados = removidos = bytes_liberados = erros = 0

    for pdf in LAUDOS_DIR.glob("*.pdf"):
        escaneados += 1
        try:
            stat = pdf.stat()
            if stat.st_mtime < cutoff:
                if not dry_run:
                    pdf.unlink()
                removidos += 1
                bytes_liberados += stat.st_size
        except OSError as exc:
            logger.warning("Falha ao processar %s: %s", pdf, exc)
            erros += 1

    if removidos:
        logger.info(
            "Laudos cleanup: %d arquivo(s) removido(s) (%.1f MB liberados)%s",
            removidos,
            bytes_liberados / 1024 / 1024,
            " [DRY-RUN]" if dry_run else "",
        )

    return {
        "escaneados": escaneados,
        "removidos": removidos,
        "bytes_liberados": bytes_liberados,
        "erros": erros,
    }
