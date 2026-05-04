"""
ORGATEC – Rate Limiting Middleware.

Usa um contador in-memory por IP. Simples, sem dependência de Redis.
Para produção multi-instance, substituir por slowapi ou redis-based.

Quando rodando atrás de proxy reverso (Nginx, Cloudflare, ALB), define
TRUSTED_PROXIES (CSV de IPs ou CIDRs) para que o middleware leia
X-Forwarded-For e use o IP real do cliente.
"""

from __future__ import annotations

import ipaddress
import os
import time
from collections import defaultdict
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

# Configuração padrão: 60 requests por minuto por IP
DEFAULT_RATE_LIMIT = 60
DEFAULT_WINDOW_SECONDS = 60


def _parse_trusted_proxies(raw: str) -> list[ipaddress._BaseNetwork]:
    """Parse CSV de IPs/CIDRs em redes para checagem de containment."""
    redes: list[ipaddress._BaseNetwork] = []
    for entry in (raw or "").split(","):
        entry = entry.strip()
        if not entry:
            continue
        try:
            redes.append(ipaddress.ip_network(entry, strict=False))
        except ValueError:
            # Aceita single IPs como /32 (IPv4) ou /128 (IPv6)
            try:
                ip = ipaddress.ip_address(entry)
                redes.append(ipaddress.ip_network(f"{ip}/{ip.max_prefixlen}"))
            except ValueError:
                pass
    return redes


_TRUSTED_PROXIES = _parse_trusted_proxies(os.getenv("TRUSTED_PROXIES", ""))


def _ip_em_proxies(ip: str) -> bool:
    if not _TRUSTED_PROXIES:
        return False
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(addr in rede for rede in _TRUSTED_PROXIES)


def get_client_ip(request: Request) -> str:
    """Retorna o IP do cliente, lendo X-Forwarded-For se vier de proxy confiável.

    - Sem TRUSTED_PROXIES: usa request.client.host direto (deploy sem proxy).
    - Com TRUSTED_PROXIES: se o IP imediato for de proxy whitelist, lê o
      primeiro IP de X-Forwarded-For. Caso contrário, ignora o header.
    """
    direct = request.client.host if request.client else "unknown"
    if not _ip_em_proxies(direct):
        return direct
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip() or direct
    return direct


class _TokenBucket:
    """Token bucket simples para rate limiting por IP."""

    def __init__(self, rate: int, window: float):
        self._rate = rate
        self._window = window
        self._buckets: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str) -> tuple[bool, int]:
        """Retorna (permitido, requests_restantes)."""
        now = time.monotonic()
        bucket = self._buckets[key]
        # Remove timestamps fora da janela
        self._buckets[key] = [t for t in bucket if now - t < self._window]
        bucket = self._buckets[key]

        if len(bucket) >= self._rate:
            return False, 0

        bucket.append(now)
        return True, self._rate - len(bucket)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware de rate limiting por IP."""

    def __init__(self, app, rate: int = DEFAULT_RATE_LIMIT, window: float = DEFAULT_WINDOW_SECONDS):
        super().__init__(app)
        self._bucket = _TokenBucket(rate, window)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting para health check
        if request.url.path == "/ping":
            return await call_next(request)

        client_ip = get_client_ip(request)
        allowed, remaining = self._bucket.is_allowed(client_ip)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Limite de requisições excedido. Tente novamente em breve."},
                headers={"Retry-After": str(int(DEFAULT_WINDOW_SECONDS))},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
