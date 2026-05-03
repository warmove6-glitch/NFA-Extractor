r"""Bridge: NFA Extractor → Squad de auditoria do Horizon-Blue.

Estratégia híbrida:
- Tenta executar o squad real (Contador + Fiscalista + Jurista + Rurista)
  com Claude Anthropic (Sonnet/Haiku) via pydantic-ai.
- Se a chave estiver ausente/inválida ou houver erro de runtime, retorna None
  para o caller cair no fallback determinístico local (`analise_local.py`).

Variáveis de ambiente relevantes:
    ANTHROPIC_API_KEY=sk-ant-...                       (obrigatória)
    AUDITORIA_MODEL=anthropic:claude-sonnet-4-6         (default)
    AUDITORIA_MODEL_SIMPLES=anthropic:claude-haiku-4-5-20251001
    HORIZON_BLUE_PATH=D:\01_Projetos_Ativos\Horizon-Blue (default)
    ENABLE_HORIZON_SQUAD=true|false                    (default true se chave existir)
    HORIZON_SQUAD_TIMEOUT=180                           (segundos, default 180)

Uso:
    from src.integrations.horizon_squad import executar_squad_para_lote, status_squad

    info = status_squad()  # diagnóstico (sem chamar Claude)
    veredito = executar_squad_para_lote(notas, "ADELA", "12345678901")
    if veredito is None:
        # cai no fallback local
        veredito = gerar_veredito_local(...)
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_HORIZON_PATH = Path(os.getenv("HORIZON_BLUE_PATH", r"D:\01_Projetos_Ativos\Horizon-Blue"))
_TIMEOUT = float(os.getenv("HORIZON_SQUAD_TIMEOUT", "360"))

# Cache do squad carregado (evita reimportar a cada chamada)
_squad_modulo = None
_carregado = False
_erro_carga: str | None = None


def _enabled_by_env() -> bool:
    """Squad só roda se ANTHROPIC_API_KEY existir e ENABLE_HORIZON_SQUAD não for false explícito."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        return False
    flag = os.getenv("ENABLE_HORIZON_SQUAD", "true").strip().lower()
    return flag not in ("false", "0", "no", "off")


def _carregar_squad() -> Any:
    """Carrega lazy os agentes do Horizon-Blue. Cacheia resultado.

    Retorna o módulo `agents.auditores` (com contador/fiscalista/jurista/rurista)
    ou None se falhar.
    """
    global _squad_modulo, _carregado, _erro_carga

    if _carregado:
        return _squad_modulo

    _carregado = True  # marca tentativa, mesmo se falhar (lazy + idempotente)

    if not _HORIZON_PATH.exists():
        _erro_carga = f"Horizon-Blue não encontrado em {_HORIZON_PATH}"
        logger.warning(_erro_carga)
        return None

    # Coloca o Horizon-Blue no sys.path para que `from agents...` funcione.
    horizon_str = str(_HORIZON_PATH)
    if horizon_str not in sys.path:
        sys.path.insert(0, horizon_str)

    try:
        # Carrega .env do Horizon-Blue (não sobrescreve ANTHROPIC_API_KEY já definida)
        from dotenv import load_dotenv
        load_dotenv(_HORIZON_PATH / ".env", override=False)

        from agents import auditores  # type: ignore[import]
        _squad_modulo = auditores
        logger.info(
            "Horizon-Blue squad carregado: %s",
            ", ".join(["contador", "fiscalista", "jurista", "rurista"]),
        )
        return auditores
    except Exception as exc:
        _erro_carga = f"{type(exc).__name__}: {exc}"
        logger.warning("Falha ao carregar squad Horizon-Blue: %s", _erro_carga)
        return None


def status_squad() -> dict[str, Any]:
    """Diagnóstico do squad sem fazer chamada à API. Usado no /health."""
    enabled = _enabled_by_env()
    horizon_existe = _HORIZON_PATH.exists()
    info: dict[str, Any] = {
        "habilitado": enabled,
        "horizon_blue_path": str(_HORIZON_PATH),
        "horizon_blue_existe": horizon_existe,
        "anthropic_api_key_definida": bool(os.getenv("ANTHROPIC_API_KEY")),
        "modelo_principal": os.getenv("AUDITORIA_MODEL", "anthropic:claude-sonnet-4-6"),
        "modelo_simples": os.getenv("AUDITORIA_MODEL_SIMPLES", "anthropic:claude-haiku-4-5-20251001"),
    }
    if enabled and horizon_existe:
        squad = _carregar_squad()
        info["agentes_carregados"] = squad is not None
        if squad is None:
            info["erro_carga"] = _erro_carga
        else:
            info["agentes"] = ["contador", "fiscalista", "jurista", "rurista"]
    return info


def _resumir_lote_para_prompt(notas: list[Any], cliente_nome: str, cpf: str) -> str:
    """Monta o prompt agregado que cada agente recebe.

    Mantém pequeno (truncar se necessário) — Claude tem context window grande,
    mas pagamos por token.
    """
    if not notas:
        return f"Cliente {cliente_nome} ({cpf}) — sem notas para auditar."

    valor_total = sum(n.valor_total or 0 for n in notas)
    qtd_total = sum(getattr(n, "quantidade_total", 0) or 0 for n in notas)

    # Distribuição por natureza
    natureza_count: dict[str, int] = {}
    for n in notas:
        nat = (getattr(n, "natureza", None) or "INDEFINIDA").upper()
        natureza_count[nat] = natureza_count.get(nat, 0) + 1
    distrib = ", ".join(f"{n}: {c}" for n, c in sorted(natureza_count.items(), key=lambda x: -x[1]))

    # Amostra das primeiras 5 notas (para não inflar contexto)
    amostra_lines = []
    for n in notas[:5]:
        amostra_lines.append(
            f"  - Nº {getattr(n, 'numero', '?')} | {getattr(n, 'natureza', '?')} | "
            f"{getattr(n, 'emissao', '?')} | R$ {n.valor_total or 0:,.2f}"
        )
    amostra = "\n".join(amostra_lines)

    return f"""AUDITORIA FISCAL — PRODUTOR RURAL PESSOA FÍSICA

CONTRIBUINTE: {cliente_nome}
CPF: {cpf}
TOTAL DE NOTAS: {len(notas)}
VALOR TOTAL: R$ {valor_total:,.2f}
QUANTIDADE TOTAL: {qtd_total:,.0f} cabeças/unidades
DISTRIBUIÇÃO POR NATUREZA: {distrib}

AMOSTRA DAS PRIMEIRAS NOTAS:
{amostra}

DEMANDA:
Forneça parecer técnico em sua especialidade (3-5 pontos críticos),
com fundamentos legais aplicáveis (CTN, LC 87/96, RICMS-GO, NBC TG quando contábil,
Lei 8.023/90 para atividade rural, etc.).
Foque em risco de autuação, conformidade e oportunidades de planejamento.
"""


async def _executar_squad_async(notas: list[Any], cliente_nome: str, cpf: str) -> dict[str, Any]:
    """Roda os 4 agentes sequencialmente com delay para respeitar rate limit.
    Execução sequencial evita o 429 (8.000 tokens/min no Tier 1).
    """
    auditores = _carregar_squad()
    if auditores is None:
        raise RuntimeError(f"Squad indisponível: {_erro_carga}")

    # ProjetoDeps do Horizon-Blue
    horizon_str = str(_HORIZON_PATH)
    if horizon_str not in sys.path:
        sys.path.insert(0, horizon_str)
    from core.context import ProjetoDeps  # type: ignore[import]

    deps = ProjetoDeps(diretorio_base=horizon_str)
    prompt = _resumir_lote_para_prompt(notas, cliente_nome, cpf)

    # Sequencial com delay de 15s entre agentes — evita 429 no Tier 1 (8k tokens/min)
    agentes = [
        ("contador",   auditores.contador),
        ("fiscalista", auditores.fiscalista),
        ("jurista",    auditores.jurista),
        ("rurista",    auditores.rurista),
    ]

    resultados: dict[str, Any] = {}
    for i, (nome, agente) in enumerate(agentes):
        if i > 0:
            # Aguarda para não ultrapassar rate limit de tokens/min (Tier 1: 8k tokens/min)
            await asyncio.sleep(8)
        try:
            saida = await agente.run(prompt, deps=deps)
            resultados[nome] = saida.output
            logger.info("Agente @%s concluido com sucesso.", nome.capitalize())
        except Exception as exc:
            logger.warning(
                "Agente @%s falhou: %s | tipo: %s",
                nome.capitalize(), str(exc)[:300], type(exc).__name__,
            )
            resultados[nome] = {"erro": str(exc)[:300]}

    return resultados


def _consolidar_pareceres(resultados: dict[str, Any], cliente_nome: str, total_notas: int) -> str:
    """Consolida os 4 pareceres num veredito textual para o laudo PDF."""
    secoes = [
        "[ANÁLISE MULTIAGENTE — HORIZON-BLUE SQUAD]",
        "",
        f"CONTRIBUINTE: {cliente_nome}",
        f"TOTAL DE NOTAS AUDITADAS: {total_notas}",
        "",
    ]

    nomes_legiveis = {
        "contador": "📊 @CONTADOR — Auditoria Contábil",
        "fiscalista": "💰 @FISCALISTA — Auditoria Tributária",
        "jurista": "⚖️ @JURISTA — Análise Jurídica",
        "rurista": "🌾 @RURISTA — Conformidade Rural",
    }

    riscos_globais: list[str] = []

    for chave, titulo in nomes_legiveis.items():
        secoes.append(titulo)
        secoes.append("─" * 60)
        out = resultados.get(chave)
        if out is None or (isinstance(out, dict) and "erro" in out):
            erro = out.get("erro", "indisponível") if isinstance(out, dict) else "indisponível"
            secoes.append(f"  [agente {chave} indisponível: {erro}]")
        else:
            # Cada agente tem seu schema; extraímos campos conhecidos
            parecer_field_map = {
                "contador": ("parecer_contabil", "score_conformidade"),
                "fiscalista": ("parecer_fiscal", "score_risco_fiscal"),
                "jurista": ("parecer_juridico", "score_risco_juridico"),
                "rurista": ("parecer_rural", "score_conformidade_ambiental"),
            }
            parecer_attr, score_attr = parecer_field_map[chave]
            parecer = getattr(out, parecer_attr, None) or "(sem parecer)"
            score = getattr(out, score_attr, None)
            secoes.append(parecer.strip())
            if score is not None:
                secoes.append(f"  → Score: {score:.1f}/10")
            # Coleta riscos para sumário consolidado
            for atr in ("riscos_autuacao", "riscos_escrituracao", "riscos_juridicos", "riscos_ambientais"):
                lst = getattr(out, atr, None)
                if isinstance(lst, list):
                    riscos_globais.extend(lst)
        secoes.append("")

    if riscos_globais:
        secoes.append("⚠️ RISCOS CONSOLIDADOS:")
        secoes.append("─" * 60)
        for r in riscos_globais[:10]:  # top-10 para não inflar
            secoes.append(f"  • {r}")

    return "\n".join(secoes)


def executar_squad_para_lote(
    notas: list[Any],
    cliente_nome: str,
    cpf: str,
) -> str | None:
    """API principal usada por `auditoria.py`. Síncrona — usa asyncio.run internamente.

    Retorna:
        - str: veredito consolidado pronto para entrar no laudo PDF
        - None: squad indisponível ou erro fatal — caller deve cair no fallback local
    """
    if not _enabled_by_env():
        logger.info("Horizon-Blue squad desabilitado (sem ANTHROPIC_API_KEY ou flag desativada).")
        return None

    if _carregar_squad() is None:
        logger.info("Horizon-Blue squad não carregado: %s", _erro_carga)
        return None

    try:
        resultados = asyncio.run(
            asyncio.wait_for(
                _executar_squad_async(notas, cliente_nome, cpf),
                timeout=_TIMEOUT,
            )
        )
    except asyncio.TimeoutError:
        logger.error("Squad Horizon-Blue: timeout após %.0fs", _TIMEOUT)
        return None
    except Exception as exc:
        logger.error("Squad Horizon-Blue falhou: %s: %s", type(exc).__name__, exc)
        return None

    # Se TODOS os agentes falharam, cair no fallback local em vez de
    # devolver um laudo cheio de "[agente indisponível]". Caller usa local.
    erros = sum(1 for r in resultados.values() if isinstance(r, dict) and "erro" in r)
    if erros == len(resultados):
        # Loga primeiro erro pra ajudar debug — sem detalhes sensíveis
        primeiro_erro = next(
            (r.get("erro", "?") for r in resultados.values() if isinstance(r, dict)),
            "?",
        )
        # Trunca pra evitar log gigante e remove possíveis fragmentos de chave
        resumo_erro = primeiro_erro.split("body:")[0].strip()[:120]
        logger.warning(
            "Squad Horizon-Blue: todos os 4 agentes falharam (%s). "
            "Caindo no fallback local determinístico.",
            resumo_erro,
        )
        return None

    return _consolidar_pareceres(resultados, cliente_nome, len(notas))
