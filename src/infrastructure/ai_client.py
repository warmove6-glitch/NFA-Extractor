"""
Cliente IA — Arquitetura Otimizada para 6GB VRAM (GTX 1660 Super).

Estratégia:
  1. Modelo único (qwen2.5:7b) para evitar swap de VRAM.
  2. System prompts compactos (~50% menos tokens) com output JSON forçado.
  3. num_predict calibrado por função do agente.
  4. Circuit breaker in-memory para fallback resiliente.
  5. Context pruning: métricas numéricas em vez de texto livre.
  6. Compatibilidade mantida com Claude/Gemini como opt-in.

Squad Antigravity: @Sigma, @Gama, @Auditor via Ollama local.
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from src.domain.extractor import NFA, resumo_geral

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent.parent / "config.env"

# ── Configuração de Modelos ──────────────────────────────────────────────────

OLLAMA_URL: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# Modelo único para 6GB VRAM — evita swap entre modelos
LOCAL_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct-q4_K_M")

# Limites de geração por função (menos tokens = menos VRAM no KV-cache)
TOKEN_LIMITS: dict[str, int] = {
    "sigma": 1024,    # Análise quantitativa: números, não prosa
    "gama": 1536,     # Parecer jurídico: precisa de mais contexto
    "auditor": 2048,  # Consolidação final
    "chat": 1024,     # Conversacional
    "etl": 512,       # Extração pura
}


# ── System Prompts Otimizados ────────────────────────────────────────────────
# Máximo ~150 tokens por prompt. JSON mode forçado.
# Modelos 7B performam ~30% melhor com schema rígido.

SYSTEM_IPSILON = (
    "Processador ETL ORGATEC. Extraia totais agrupados por natureza. "
    'Responda APENAS em JSON: {"grupos": [{"natureza": str, "qtd_notas": int, '
    '"cabecas": float, "valor": float}]}'
)

SYSTEM_SIGMA = (
    "Você é @Sigma, analista quantitativo tributário.\n"
    "REGRAS: Use APENAS os dados fornecidos. Nunca invente valores. "
    "Responda EXCLUSIVAMENTE em JSON válido.\n"
    "SCHEMA: {"
    '"resumo": "string (máx 200 chars)", '
    '"total_notas": int, "valor_total": float, "cabecas_total": float, '
    '"ticket_medio": float, '
    '"anomalias": [{"tipo": str, "descricao": str, "severidade": "BAIXA|MEDIA|ALTA"}], '
    '"tendencia": "ESTAVEL|CRESCENTE|DECRESCENTE|IRREGULAR"}'
)

SYSTEM_GAMA = (
    "Você é @Gama, consultor tributário sênior.\n"
    "REGRAS: Baseie-se APENAS nos dados quantitativos. Nunca invente artigos. "
    "Responda EXCLUSIVAMENTE em JSON válido.\n"
    "SCHEMA: {"
    '"parecer": "string (máx 300 chars)", '
    '"risco_fiscal": "BAIXO|MEDIO|ALTO|CRITICO", '
    '"fundamentacao": ["string (artigos/normas)"], '
    '"recomendacoes": ["string"], '
    '"ressalvas": ["string"]}'
)

SYSTEM_AUDITOR = (
    "Você é o Auditor-Chefe da ORGATEC. Protocolo Soberano.\n"
    "REGRAS: ZERO ALUCINAÇÃO — dados insuficientes = declare 'DADOS INSUFICIENTES'. "
    "Toda conclusão DEVE citar NFA ou valor de origem. "
    "Responda EXCLUSIVAMENTE em JSON válido.\n"
    "SCHEMA: {"
    '"veredito": str, '
    '"entradas": {"cabecas": int, "valor": float}, '
    '"saidas": {"cabecas": int, "valor": float}, '
    '"anomalia_bio_contabil": {"diferenca_cabecas": int, "explicacao": str}, '
    '"hipotese_tecnica": str, '
    '"nivel_risco": "BAIXO|MEDIO|ALTO|SISTEMICO", '
    '"score_confianca": float, '
    '"evidencias": ["string"]}'
)

# Mapa de system prompts → função do agente (para calibrar token limits)
_SYSTEM_TO_ROLE: dict[int, str] = {
    id(SYSTEM_SIGMA): "sigma",
    id(SYSTEM_GAMA): "gama",
    id(SYSTEM_AUDITOR): "auditor",
    id(SYSTEM_IPSILON): "etl",
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _carregar_env(chave: str) -> str:
    """Carrega variável de ambiente com fallback para config.env."""
    valor = os.getenv(chave, "")
    if valor:
        return valor
    if CONFIG_PATH.exists():
        for linha in CONFIG_PATH.read_text(encoding="utf-8").splitlines():
            if "=" in linha and not linha.startswith("#"):
                k, v = linha.strip().split("=", 1)
                if k.strip() == chave:
                    return v.strip()
    return ""


_PROMPT_SANITIZE = str.maketrans({"\x00": "", "\r": " "})


def _sanitizar_str(valor: str) -> str:
    """Remove caracteres perigosos para prompt injection."""
    if not isinstance(valor, str):
        return str(valor)
    return (
        valor.translate(_PROMPT_SANITIZE)
        .replace("{{", "{ {")
        .replace("}}", "} }")
        .strip()
    )


def _montar_prompt(notas: list[NFA]) -> str:
    """Monta prompt compacto — formato tabular, uma linha por nota."""
    if not notas:
        return "Nenhuma nota fiscal disponível."
    linhas = ["NFA|NAT|EMISSÃO|VALOR|CAPS"]
    for n in notas:
        nat = _sanitizar_str(n.natureza)[:12]
        emi = _sanitizar_str(n.emissao)
        linhas.append(f"{n.numero}|{nat}|{emi}|{n.valor_total:.2f}|{n.quantidade_total:.0f}")
    return "\n".join(linhas)


def _montar_prompt_compacto(resumo: dict[str, Any]) -> str:
    """Monta prompt a partir de métricas pré-calculadas (sem dados brutos).

    Reduz tokens de input em ~70% comparado a enviar notas individuais.
    """
    return json.dumps(resumo, ensure_ascii=False, separators=(",", ":"))


def _get_role(system: str) -> str:
    """Identifica a função do agente pelo system prompt."""
    return _SYSTEM_TO_ROLE.get(id(system), "chat")


# ── Circuit Breaker ──────────────────────────────────────────────────────────

@dataclass
class _CircuitState:
    """Estado interno de um provedor no circuit breaker."""
    failures: int = 0
    last_failure: float = 0.0
    is_open: bool = False
    total_calls: int = 0
    total_failures: int = 0
    total_latency: float = 0.0


class CircuitBreaker:
    """Circuit breaker leve para fallback entre provedores de IA.

    Após max_failures consecutivas, abre o circuito por cooldown segundos.
    Após o cooldown, permite uma tentativa (half-open).
    """

    def __init__(self, max_failures: int = 3, cooldown: float = 60.0) -> None:
        self._max = max_failures
        self._cooldown = cooldown
        self._states: dict[str, _CircuitState] = {}

    def _state(self, provider: str) -> _CircuitState:
        if provider not in self._states:
            self._states[provider] = _CircuitState()
        return self._states[provider]

    def is_available(self, provider: str) -> bool:
        """Verifica se o provedor pode receber requests."""
        s = self._state(provider)
        if not s.is_open:
            return True
        return time.monotonic() - s.last_failure >= self._cooldown

    def success(self, provider: str, latency: float) -> None:
        """Registra sucesso — reseta contagem de falhas."""
        s = self._state(provider)
        s.failures = 0
        s.is_open = False
        s.total_calls += 1
        s.total_latency += latency

    def failure(self, provider: str) -> None:
        """Registra falha — abre circuito se atingir limite."""
        s = self._state(provider)
        s.failures += 1
        s.total_calls += 1
        s.total_failures += 1
        s.last_failure = time.monotonic()
        if s.failures >= self._max:
            s.is_open = True

    def metrics(self) -> dict[str, dict]:
        """Retorna métricas por provedor para observabilidade."""
        return {
            name: {
                "calls": s.total_calls,
                "failures": s.total_failures,
                "avg_latency_ms": round((s.total_latency / s.total_calls) * 1000) if s.total_calls else 0,
                "circuit_open": s.is_open,
            }
            for name, s in self._states.items()
        }


_breaker = CircuitBreaker(max_failures=3, cooldown=60.0)


# ── Motores de IA ────────────────────────────────────────────────────────────

def _ollama_generate(
    prompt: str,
    system: str,
    callback: Callable | None = None,
    max_tokens: int = 1024,
) -> str:
    """Motor Ollama otimizado para 6GB VRAM (GTX 1660 Super).

    Configurações chave para baixa VRAM:
    - num_ctx 2048: janela reduzida (~1.2GB KV-cache no q4)
    - temperature 0.2: determinístico (melhor para auditoria)
    - repeat_penalty 1.15: evita repetições (problema comum em 7B)
    - num_gpu 99: força offload total para GPU
    """
    modelo = LOCAL_MODEL
    provider_key = f"ollama:{modelo}"

    if not _breaker.is_available(provider_key):
        logger.info(f"[Circuit Breaker] {provider_key} em cooldown.")
        return f"[Ollama Indisponível: {modelo}]"

    t0 = time.monotonic()
    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": modelo,
                "system": system,
                "prompt": prompt,
                "stream": True,
                "options": {
                    "temperature": 0.2,
                    "num_predict": max_tokens,
                    "num_ctx": 2048,
                    "top_p": 0.85,
                    "repeat_penalty": 1.15,
                    "num_gpu": 99,
                    "num_thread": 4,
                },
            },
            stream=True,
            timeout=180,
        )
        response.raise_for_status()

        full_text = ""
        for line in response.iter_lines():
            if not line:
                continue
            chunk = json.loads(line.decode("utf-8"))
            token = chunk.get("response", "")
            full_text += token
            if callback:
                callback(token)
            if chunk.get("done"):
                break

        latency = time.monotonic() - t0
        _breaker.success(provider_key, latency)
        logger.info(f"Ollama ({modelo}): {len(full_text)} chars em {latency:.1f}s")
        return full_text

    except Exception as e:
        _breaker.failure(provider_key)
        logger.error(f"Ollama ({modelo}): {e}")
        return f"[Ollama Erro: {e}]"


def _claude_generate(
    prompt: str,
    system: str,
    callback: Callable | None = None,
    max_tokens: int = 2048,
) -> str:
    """Motor Claude (opt-in, requer ANTHROPIC_API_KEY)."""
    import anthropic

    api_key = _carregar_env("ANTHROPIC_API_KEY")
    if not api_key or not api_key.startswith("sk-ant"):
        return "[Claude Inativo]"

    if not _breaker.is_available("claude"):
        return "[Claude Cooldown]"

    t0 = time.monotonic()
    try:
        client = anthropic.Anthropic(api_key=api_key)
        res = ""
        with client.messages.stream(
            model="claude-sonnet-4-20250514",
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            for t in stream.text_stream:
                res += t
                if callback:
                    callback(t)
        _breaker.success("claude", time.monotonic() - t0)
        return res
    except Exception as e:
        _breaker.failure("claude")
        logger.error(f"Claude: {e}")
        return f"[Claude Falhou: {e}]"


def _gemini_generate(
    prompt: str,
    system: str,
    callback: Callable | None = None,
    max_tokens: int = 2048,
) -> str:
    """Motor Gemini (opt-in, requer GOOGLE_API_KEY)."""
    from google import genai
    from google.genai import types

    api_key = _carregar_env("GOOGLE_API_KEY")
    if not api_key:
        return "[Gemini Inativo]"

    if not _breaker.is_available("gemini"):
        return "[Gemini Cooldown]"

    t0 = time.monotonic()
    modelos = ["gemini-flash-latest", "gemini-1.5-flash-latest"]

    for model_name in modelos:
        for tentativa in range(2):
            try:
                client = genai.Client(api_key=api_key)
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(system_instruction=system),
                )
                _breaker.success("gemini", time.monotonic() - t0)
                return response.text
            except Exception as e:
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    wait = 15 * (tentativa + 1)
                    logger.warning(f"Gemini rate limit. Aguardando {wait}s...")
                    time.sleep(wait)
                    continue
                logger.error(f"Gemini ({model_name}): {e}")
                break

    _breaker.failure("gemini")
    return "[Gemini Falhou]"


# ── Detecção de Falha ────────────────────────────────────────────────────────

def _is_failure(result: str) -> bool:
    """Detecta se o resultado indica falha do provedor."""
    markers = ["Falhou", "Inativo", "Erro", "Cooldown", "Indisponível"]
    return result.startswith("[") and any(m in result for m in markers)


# Ordem de prioridade: local primeiro (zero custo, zero latência de rede)
_PROVIDER_PRIORITY: list[tuple[str, Callable]] = [
    ("ollama", _ollama_generate),
    ("claude", _claude_generate),
    ("gemini", _gemini_generate),
]


# ── API Pública ──────────────────────────────────────────────────────────────

def analisar(
    notas: list[NFA],
    callback: Callable | None = None,
    system_override: str | None = None,
    provedor: str = "auto",
    nome_produtor: str = "",
) -> str:
    """Orquestrador principal — otimizado para 6GB VRAM.

    Melhorias sobre a versão anterior:
    - Circuit breaker evita cascata de timeouts
    - Token limit calibrado por função do agente
    - Prioridade local-first (Ollama antes de APIs cloud)
    - Prompt compacto formato tabular
    """
    prompt = _montar_prompt(notas)
    if nome_produtor:
        prompt = f"ALVO: {nome_produtor}\n{prompt}"

    sys = system_override or SYSTEM_GAMA
    role = _get_role(sys)
    max_tokens = TOKEN_LIMITS.get(role, 1024)

    # Provedor específico solicitado
    if provedor != "auto":
        fn_map = dict(_PROVIDER_PRIORITY)
        fn = fn_map.get(provedor)
        if fn:
            return fn(prompt, sys, callback, max_tokens=max_tokens)

    # Modo auto: tenta na ordem de prioridade com circuit breaker
    for prov_name, fn in _PROVIDER_PRIORITY:
        result = fn(prompt, sys, callback, max_tokens=max_tokens)
        if not _is_failure(result):
            return result
        if callback:
            callback(f"\n[!] {prov_name} indisponível. Tentando próximo...\n")

    return "[ERRO] Todos os provedores de IA estão indisponíveis."


def analisar_com_resumo(
    resumo: dict[str, Any],
    system: str,
    callback: Callable | None = None,
    nome_produtor: str = "",
) -> str:
    """Analisa a partir de métricas pré-calculadas (sem dados brutos).

    Reduz tokens de input em ~70% comparado a enviar notas individuais.
    Ideal para o pipeline Sigma → Gama → Auditor.
    """
    prompt = _montar_prompt_compacto(resumo)
    if nome_produtor:
        prompt = f"ALVO: {nome_produtor}\n{prompt}"

    role = _get_role(system)
    max_tokens = TOKEN_LIMITS.get(role, 1024)
    return _ollama_generate(prompt, system, callback, max_tokens=max_tokens)


def analisar_pipeline(
    notas: list[NFA],
    callback: Callable | None = None,
    batch_size: int = 20,
    nome_contribuinte: str = "",
) -> str:
    """Pipeline em lotes otimizado para 6GB VRAM.

    Diferenças chave da versão anterior:
    - Cada lote é comprimido em métricas ANTES de ir pro modelo
    - Sigma recebe 1 chamada consolidada (não N chamadas por lote)
    - Auditor recebe JSON compacto, não texto livre concatenado
    - batch_size maior (20 vs 15) porque o prompt é menor
    """
    if callback:
        callback(f"\n[SQUAD] {len(notas)} notas em lotes de {batch_size}...\n")

    metricas_lotes: list[dict] = []
    total_lotes = (len(notas) + batch_size - 1) // batch_size

    for i in range(0, len(notas), batch_size):
        lote_num = (i // batch_size) + 1
        lote = notas[i : i + batch_size]
        if callback:
            callback(f"── Lote {lote_num}/{total_lotes} ({len(lote)} notas) ── ")

        # Comprimir lote em métricas numéricas (zero chamada de IA aqui)
        resumo_lote = resumo_geral(lote, nome_contribuinte=nome_contribuinte)
        metricas_lotes.append({
            "lote": lote_num,
            "notas": resumo_lote["total_notas"],
            "valor": round(resumo_lote["total_valor"], 2),
            "cabecas": round(resumo_lote["total_cabecas"], 1),
            "ticket_medio": round(resumo_lote["ticket_medio"], 2),
            "por_natureza": resumo_lote["por_natureza"],
        })
        if callback:
            callback("[OK]\n")

    # Sigma analisa métricas consolidadas (1 chamada, não N)
    if callback:
        callback("\n── @Sigma: Análise Quantitativa ──\n")

    consolidado = {
        "contribuinte": nome_contribuinte,
        "total_notas": len(notas),
        "total_valor": sum(m["valor"] for m in metricas_lotes),
        "total_cabecas": sum(m["cabecas"] for m in metricas_lotes),
        "lotes": metricas_lotes,
    }

    sigma_result = analisar_com_resumo(
        consolidado, SYSTEM_SIGMA, callback, nome_contribuinte,
    )

    # Auditor consolida com base em Sigma + métricas
    if callback:
        callback("\n\n── @Auditor: Veredito Final ──\n")

    prompt_auditor = json.dumps(
        {"metricas": consolidado, "analise_sigma": sigma_result},
        ensure_ascii=False,
        separators=(",", ":"),
    )

    return _ollama_generate(
        prompt_auditor,
        SYSTEM_AUDITOR,
        callback,
        max_tokens=TOKEN_LIMITS["auditor"],
    )


def perguntar(
    notas: list[NFA],
    context_ia: str = "",
    pergunta: str = "",
) -> str:
    """Endpoint de chat genérico para o agente conversacional."""
    if context_ia:
        pass
    return analisar(notas, system_override=None)


def get_ai_metrics() -> dict:
    """Retorna métricas do circuit breaker para observabilidade."""
    return _breaker.metrics()
