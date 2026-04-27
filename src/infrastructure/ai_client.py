"""
Cliente IA — Produção Enxuto (2026).
Modo produção: Claude (primário) → Swift/KB Local (fallback).
Foco: Performance (<20s), simplicidade, custo controlado.
"""

import os
import logging
import requests
import anthropic
import json
from pathlib import Path
from src.domain.extractor import NFA, resumo_geral

logger = logging.getLogger(__name__)

CONFIG_PATH  = Path(__file__).parent.parent.parent / 'config.env'

def _carregar_env(chave: str) -> str:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            for linha in f:
                if '=' in linha and not linha.startswith('#'):
                    k, v = linha.strip().split('=', 1)
                    if k == chave: return v
    return os.getenv(chave, '')

# MODELOS (PRODUÇÃO)
CLAUDE_MODEL = 'claude-sonnet-4-6'




# ── SYSTEM PROMPTS ──────────────────────────────────────────────────────────

SYSTEM_GAMA = """Especialista Fiscal ORGATEC.
Analise Notas Fiscais com rigor tributário (CTN, LC 87/96, RICMS, legislação).
Retorne: veredito jurídico, cenários de risco e conclusão técnica."""

def _claude_disponivel() -> bool:
    key = _carregar_env('ANTHROPIC_API_KEY')
    return bool(key and key.startswith('sk-ant'))

def _azure_disponivel() -> bool:
    key      = _carregar_env('AZURE_OPENAI_KEY')
    endpoint = _carregar_env('AZURE_OPENAI_ENDPOINT')
    return bool(key and endpoint and 'openai.azure.com' in endpoint)

def _openai_disponivel() -> bool:
    key = _carregar_env('OPENAI_API_KEY')
    return bool(key and key.startswith('sk-') and key != 'your_key_here')

def _gemini_disponivel() -> bool:
    return bool(_carregar_env('GOOGLE_API_KEY'))




# ── LOGICA DE LOTE (CHUNKS) ────────────────────────────────────────────────

_PROMPT_SANITIZE = str.maketrans({
    "\x00": "",  # null byte
    "\r": " ",   # CR isolado
})

def _sanitizar_str(valor: str) -> str:
    """Remove caracteres que podem ser usados para prompt injection."""
    if not isinstance(valor, str):
        return str(valor)
    return (
        valor
        .translate(_PROMPT_SANITIZE)
        .replace("{{", "{ {")   # Jinja-like injection
        .replace("}}", "} }")
        .strip()
    )


def _montar_prompt(notas: list[NFA]) -> str:
    """Monta o prompt estruturado para análise das notas, com dados sanitizados."""
    if not notas:
        return "Nenhuma nota fiscal disponível para análise."
    corpo = "DADOS EXTRAÍDOS:\n"
    for i, n in enumerate(notas, 1):
        natureza = _sanitizar_str(n.natureza)
        emissao  = _sanitizar_str(n.emissao)
        corpo += (
            f"- NFA {i}: {natureza} | "
            f"Emissão: {emissao} | "
            f"Valor: R$ {n.valor_total:,.2f} | "
            f"Caps: {n.quantidade_total}\n"
        )
    return corpo

# ── MOTORES INDIVIDUAIS ─────────────────────────────────────────────────────

def _analisar_claude(prompt: str, sys: str, callback=None, timeout_segundos=15) -> str:
    api_key = _carregar_env('ANTHROPIC_API_KEY')
    if not api_key or not api_key.startswith('sk-ant'):
        logger.warning("Claude: API key ausente ou inválida.")
        return "[Claude Inativo]"
    cliente = anthropic.Anthropic(api_key=api_key, timeout=timeout_segundos)
    try:
        res = ""
        with cliente.messages.stream(
            model=CLAUDE_MODEL, max_tokens=2048, system=sys,
            messages=[{'role': 'user', 'content': prompt}]
        ) as stream:
            for t in stream.text_stream:
                res += t
                if callback: callback(t)
        return res
    except anthropic.AuthenticationError as e:
        logger.error(f"Claude: Chave API inválida ou expirada — {e}")
        return "[Claude Falhou: Auth Inválida]"
    except anthropic.RateLimitError as e:
        logger.warning(f"Claude: Rate limit atingido — {e}")
        return "[Claude Falhou: Rate Limit]"
    except anthropic.APIError as e:
        logger.error(f"Claude: Erro de API — {e}")
        return f"[Claude Falhou: {e}]"
    except Exception as e:
        logger.error(f"Claude: Erro inesperado — {e}")
        return f"[Claude Falhou: {e}]"


def extrair_com_claude_vision(imagem_base64: str, mime_type: str = "image/png", prompt_extracao: str = None) -> dict:
    """
    Extrai dados de uma imagem (PNG/JPEG/PDF) usando Claude Vision.
    Ideal para extrair tabelas, campos e valores de NFAs em formato visual.

    Args:
        imagem_base64: Conteúdo da imagem em base64
        mime_type: Tipo MIME (image/png, image/jpeg, image/webp, image/gif)
        prompt_extracao: Prompt customizado para extração

    Returns:
        dict com dados extraídos
    """
    api_key = _carregar_env('ANTHROPIC_API_KEY')
    if not api_key or not api_key.startswith('sk-ant'):
        logger.warning("Claude Vision: API key ausente ou inválida.")
        return {"status": "erro", "mensagem": "Claude Vision inativo"}

    if not prompt_extracao:
        prompt_extracao = """
Analise esta imagem de Nota Fiscal Agropecuária (NFA) e extraia:
1. Número da NF
2. Data de emissão
3. CNPJ/CPF e nome do emitente
4. CNPJ/CPF e nome do destinatário
5. Natureza da operação (venda, remessa, devolução, etc.)
6. Quantidade total de animais
7. Valor total
8. CFOP principal
9. Itens (especificar produto, quantidade, valor unitário)
10. Impostos (ICMS, PIS, COFINS, se visível)

Retorne em JSON estruturado.
"""

    cliente = anthropic.Anthropic(api_key=api_key)
    try:
        response = cliente.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=2048,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": mime_type,
                                "data": imagem_base64
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt_extracao
                        }
                    ]
                }
            ]
        )

        # Parsear resposta JSON
        texto_resposta = response.content[0].text
        try:
            # Tentar extrair JSON do texto
            import re
            json_match = re.search(r'\{.*\}', texto_resposta, re.DOTALL)
            if json_match:
                dados = json.loads(json_match.group())
                return {"status": "sucesso", "dados": dados, "raw": texto_resposta}
        except json.JSONDecodeError:
            pass

        return {"status": "sucesso", "raw": texto_resposta}

    except anthropic.AuthenticationError as e:
        logger.error(f"Claude Vision: Chave API inválida — {e}")
        return {"status": "erro", "mensagem": f"Auth inválida: {e}"}
    except anthropic.RateLimitError as e:
        logger.warning(f"Claude Vision: Rate limit — {e}")
        return {"status": "erro", "mensagem": f"Rate limit: {e}"}
    except anthropic.APIError as e:
        logger.error(f"Claude Vision: Erro de API — {e}")
        return {"status": "erro", "mensagem": f"Erro API: {e}"}
    except Exception as e:
        logger.error(f"Claude Vision: Erro inesperado — {e}")
        return {"status": "erro", "mensagem": f"Erro: {e}"}





# ── ORQUESTRADOR RESILIENTE ────────────────────────────────────────────────


def analisar_producao(notas: list[NFA], callback=None, system_override: str = None,
                     nome_produtor: str = "") -> str:
    """
    Modo PRODUÇÃO (2026): Claude Vision apenas.

    Motor: Claude (15s timeout) — qualidade máxima

    Nota: Swift e KB Local removidos para máxima simplicidade e custo controlado.
    """
    import threading
    import time

    prompt = _montar_prompt(notas)
    if nome_produtor:
        prompt = f"PRODUTOR: {nome_produtor}\n\n" + prompt

    sys = system_override or SYSTEM_GAMA

    # 1. CLAUDE (PRIMARY) — timeout de 15s
    api_key = _carregar_env('ANTHROPIC_API_KEY')
    if api_key and api_key.startswith('sk-ant'):
        if callback: callback("[PRODUÇÃO] Claude (qualidade máxima) ativo...\n")

        resultado = {'res': None, 'done': False}

        def executar_claude():
            try:
                resultado['res'] = _analisar_claude(prompt, sys, callback)
                resultado['done'] = True
            except Exception as e:
                resultado['res'] = f"[Claude Error: {e}]"
                resultado['done'] = True

        thread = threading.Thread(target=executar_claude, daemon=True)
        thread.start()
        thread.join(timeout=15)

        if resultado['done'] and resultado['res']:
            res = resultado['res']
            if "[Claude Falhou" not in res and "[Claude Error" not in res:
                return res

        logger.error("Análise falhou: Claude indisponível.")
        return "[ERRO] Análise indisponível: Claude não respondeu."

    logger.error("Análise falhou: Claude API key não configurada.")
    return "[ERRO] Claude não disponível — configure ANTHROPIC_API_KEY."

