"""Bridge: NFA Extractor consome HARDENING modules do nfa-repo.

Estratégia híbrida pragmática:
- Modelos (NFA, Parte, Produto): permanecem locais (já existem aqui)
- Hardening (PII masking, audit trail, rate limit, circuit breaker): puxa do nfa-repo

Por que? Os modelos colidem em namespace `src.*` se ambos estão no PYTHONPATH.
Como ambos os modelos são equivalentes (verificado por test_compat_nfa_extractor),
mantemos o local e adicionamos só o hardening que o NFA Extractor não tem.

Migração futura: quando NFA Extractor virar consumidor PURO de nfa-repo,
basta deletar `src/domain/extractor.py` e `src/domain/schemas.py` locais.

Uso:
    from src.nfa_repo_bridge import (
        # Hardening do nfa-repo (não temos aqui)
        mask_cpf, mask_cnpj, audit_event, RateLimiter, CircuitBreaker,
        # Helpers de bootstrap
        info_bridge, configurar_hardening,
    )

    configurar_hardening()  # uma vez no startup
"""

from __future__ import annotations

import importlib.util
import logging
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

logger = logging.getLogger(__name__)

_NFA_REPO_PATH = Path(os.getenv("NFA_REPO_PATH", r"D:\nfa-repo"))
_HARDENING_DISPONIVEL = False

# Stubs default (caso nfa-repo indisponível, app continua funcionando)
def _stub_mask(v: Any) -> str:
    return "MASK_INDISPONIVEL"


def _stub_audit(*args: Any, **kwargs: Any) -> None:
    pass


class _StubBreaker:
    def __init__(self, *a, **kw): pass
    def __call__(self, fn): return fn
    def async_call(self, fn): return fn


# Variáveis exportadas (default = stubs)
mask_cpf: Any = _stub_mask
mask_cnpj: Any = _stub_mask
mask_cpf_cnpj: Any = _stub_mask
mask_email: Any = _stub_mask
remover_pii: Any = _stub_mask
MaskingFilter: Any = None

audit_event: Any = _stub_audit
correlation_context: Any = None
def configurar_audit_log(*a, **kw):
    return None
def query_audit(*a, **kw):
    return []

RateLimiter: Any = None
def get_limiter_global():
    return None
def rate_limit_dep(*a, **kw):
    return None

CircuitBreaker: Any = _StubBreaker
CircuitBreakerAberto: Any = Exception
EstadoCircuito: Any = None

parse_xml_seguro: Any = None
extrair_texto_otimizado: Any = None
extrair_notas_seguro: Any = None


def _carregar_modulo_isolado(nome: str, caminho: Path) -> ModuleType | None:
    """Carrega módulo Python com nome único para evitar colisão de namespace."""
    if not caminho.exists():
        return None
    try:
        spec = importlib.util.spec_from_file_location(nome, str(caminho))
        if spec is None or spec.loader is None:
            return None
        modulo = importlib.util.module_from_spec(spec)
        sys.modules[nome] = modulo
        spec.loader.exec_module(modulo)
        return modulo
    except Exception as e:
        logger.warning("Falha ao carregar %s de %s: %s", nome, caminho, e)
        return None


def configurar_hardening() -> bool:
    """Carrega módulos de hardening do nfa-repo.

    Returns:
        True se carregou com sucesso
    """
    global mask_cpf, mask_cnpj, mask_cpf_cnpj, mask_email, remover_pii, MaskingFilter
    global audit_event, correlation_context, configurar_audit_log, query_audit
    global RateLimiter, get_limiter_global, rate_limit_dep
    global CircuitBreaker, CircuitBreakerAberto, EstadoCircuito
    global parse_xml_seguro, extrair_texto_otimizado
    global _HARDENING_DISPONIVEL

    if not _NFA_REPO_PATH.exists():
        logger.warning("nfa-repo não encontrado em %s", _NFA_REPO_PATH)
        return False

    # 1) PII Masking — sem dependências externas
    pii = _carregar_modulo_isolado(
        "_nfarepo_pii", _NFA_REPO_PATH / "src" / "infrastructure" / "pii_masking.py"
    )
    if pii:
        mask_cpf = pii.mask_cpf
        mask_cnpj = pii.mask_cnpj
        mask_cpf_cnpj = pii.mask_cpf_cnpj
        mask_email = pii.mask_email
        remover_pii = pii.remover_pii
        MaskingFilter = pii.MaskingFilter

    # 2) Rate Limit — sem dependências externas
    rate = _carregar_modulo_isolado(
        "_nfarepo_rate", _NFA_REPO_PATH / "src" / "infrastructure" / "rate_limit.py"
    )
    if rate:
        RateLimiter = rate.RateLimiter
        get_limiter_global = rate.get_limiter_global
        rate_limit_dep = rate.rate_limit_dep

    # 3) Circuit Breaker — sem dependências externas
    cb = _carregar_modulo_isolado(
        "_nfarepo_cb", _NFA_REPO_PATH / "src" / "infrastructure" / "circuit_breaker.py"
    )
    if cb:
        CircuitBreaker = cb.CircuitBreaker
        CircuitBreakerAberto = cb.CircuitBreakerAberto
        EstadoCircuito = cb.EstadoCircuito

    # 4) Audit Trail — depende de pii_masking
    if pii:
        # Registra com nome esperado para imports relativos do audit_trail
        sys.modules["src.infrastructure.pii_masking"] = pii
        audit = _carregar_modulo_isolado(
            "_nfarepo_audit",
            _NFA_REPO_PATH / "src" / "infrastructure" / "audit_trail.py",
        )
        if audit:
            audit_event = audit.audit_event
            correlation_context = audit.correlation_context
            configurar_audit_log = audit.configurar_audit_log
            query_audit = audit.query_audit

    # 5) Parsers (XXE defense) — depende de lxml/defusedxml
    parsers = _carregar_modulo_isolado(
        "_nfarepo_parsers",
        _NFA_REPO_PATH / "src" / "infrastructure" / "parsers.py",
    )
    if parsers:
        parse_xml_seguro = parsers.parse_xml_seguro

    # 6) PDF Cache — depende de pdfplumber/pymupdf
    cache = _carregar_modulo_isolado(
        "_nfarepo_cache",
        _NFA_REPO_PATH / "src" / "infrastructure" / "pdf_cache.py",
    )
    if cache:
        extrair_texto_otimizado = cache.extrair_texto_otimizado

    _HARDENING_DISPONIVEL = bool(pii and rate and cb and audit)
    if _HARDENING_DISPONIVEL:
        logger.info("✅ nfa-repo hardening carregado de %s", _NFA_REPO_PATH)
    else:
        logger.warning("⚠️  nfa-repo hardening parcialmente carregado")

    return _HARDENING_DISPONIVEL


def info_bridge() -> dict[str, Any]:
    """Diagnóstico: status da bridge."""
    return {
        "hardening_disponivel": _HARDENING_DISPONIVEL,
        "nfa_repo_path": str(_NFA_REPO_PATH),
        "path_existe": _NFA_REPO_PATH.exists(),
        "modulos_carregados": {
            "pii_masking": mask_cpf is not _stub_mask,
            "audit_trail": audit_event is not _stub_audit,
            "rate_limit": RateLimiter is not None,
            "circuit_breaker": CircuitBreaker is not _StubBreaker,
            "parsers_xml": parse_xml_seguro is not None,
            "pdf_cache": extrair_texto_otimizado is not None,
        },
    }


# Auto-bootstrap (pode ser desligado com NFA_REPO_AUTOLOAD=0)
if os.getenv("NFA_REPO_AUTOLOAD", "1") == "1":
    configurar_hardening()


__all__ = [
    # PII Masking
    "mask_cpf", "mask_cnpj", "mask_cpf_cnpj", "mask_email",
    "remover_pii", "MaskingFilter",
    # Audit Trail
    "audit_event", "correlation_context", "configurar_audit_log", "query_audit",
    # Rate Limit
    "RateLimiter", "get_limiter_global", "rate_limit_dep",
    # Circuit Breaker
    "CircuitBreaker", "CircuitBreakerAberto", "EstadoCircuito",
    # Outros
    "parse_xml_seguro", "extrair_texto_otimizado",
    # Helpers
    "info_bridge", "configurar_hardening",
]
