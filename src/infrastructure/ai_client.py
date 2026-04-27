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
CLAUDE_MODEL_RÁPIDO = 'claude-haiku-4-5-20251001'  # Primário: 2-3x mais rápido
CLAUDE_MODEL_FALLBACK = 'claude-sonnet-4-6'  # Fallback: máxima qualidade




# ── SYSTEM PROMPTS ──────────────────────────────────────────────────────────

SYSTEM_GAMA = """Auditor Fiscal — Parecer Técnico Rápido.
Analise: Consistência, Riscos, Conclusão (máx 5 linhas)."""

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

def _analisar_claude(prompt: str, sys: str, callback=None, timeout_segundos=15) -> tuple[str, str]:
    """
    Tenta Claude Haiku (rápido) primeiro; fallback para Sonnet se falhar.
    Retorna: (resposta, modelo_usado)
    """
    import time
    api_key = _carregar_env('ANTHROPIC_API_KEY')
    if not api_key or not api_key.startswith('sk-ant'):
        logger.warning("Claude: API key ausente ou inválida.")
        return "[Claude Inativo]", "nenhum"

    # Tentar Haiku primeiro (rápido)
    cliente = anthropic.Anthropic(api_key=api_key, timeout=timeout_segundos)
    modelo_atual = CLAUDE_MODEL_RÁPIDO

    for tentativa, modelo in [(1, CLAUDE_MODEL_RÁPIDO), (2, CLAUDE_MODEL_FALLBACK)]:
        try:
            res = ""
            t0 = time.time()
            with cliente.messages.stream(
                model=modelo, max_tokens=1024, system=sys,
                messages=[{'role': 'user', 'content': prompt}]
            ) as stream:
                for t in stream.text_stream:
                    res += t
                    if callback: callback(t)
            t1 = time.time()
            model_nome = "Haiku" if modelo == CLAUDE_MODEL_RÁPIDO else "Sonnet"
            logger.info(f"⏱️  [CLAUDE {model_nome}] {t1-t0:.1f}s — {len(res)} chars")
            return res, modelo
        except anthropic.AuthenticationError as e:
            logger.error(f"Claude: Chave API inválida — {e}")
            return "[Claude Falhou: Auth Inválida]", modelo
        except anthropic.RateLimitError as e:
            if tentativa == 1:
                logger.warning(f"Haiku: Rate limit, tentando Sonnet...")
                continue
            else:
                logger.warning(f"Claude: Rate limit atingido em ambos modelos — {e}")
                return "[Claude Falhou: Rate Limit]", modelo
        except anthropic.APIError as e:
            if tentativa == 1:
                logger.warning(f"Haiku falhou com {type(e).__name__}, tentando Sonnet...")
                continue
            else:
                logger.error(f"Claude: Erro de API — {e}")
                return f"[Claude Falhou: {e}]", modelo
        except Exception as e:
            if tentativa == 1:
                logger.warning(f"Haiku timeout/erro, tentando Sonnet...")
                continue
            else:
                logger.error(f"Claude: Erro inesperado — {e}")
                return f"[Claude Falhou: {e}]", modelo

    return "[Claude Falhou: Todos os modelos]", "nenhum"


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
        # Tentar Haiku primeiro (rápido para extração de imagens); fallback para Sonnet
        response = None
        for tentativa, modelo in [(1, CLAUDE_MODEL_RÁPIDO), (2, CLAUDE_MODEL_FALLBACK)]:
            try:
                import time
                t0 = time.time()
                response = cliente.messages.create(
                    model=modelo,
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
                t1 = time.time()
                model_nome = "Haiku" if modelo == CLAUDE_MODEL_RÁPIDO else "Sonnet"
                logger.info(f"⏱️  [CLAUDE VISION {model_nome}] {t1-t0:.1f}s")
                break
            except anthropic.RateLimitError:
                if tentativa == 1:
                    logger.warning("Haiku rate limit, tentando Sonnet...")
                    continue
                raise
            except Exception as e:
                if tentativa == 1:
                    logger.warning(f"Haiku falhou, tentando Sonnet...")
                    continue
                raise

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
    Modo PRODUÇÃO OTIMIZADO (2026): Análise em paralelo com chunks.

    Otimizações:
    - Divide notas em chunks de 50 (análise em paralelo)
    - Combine resultados para veredito consolidado
    - Claude Haiku (2-3x mais rápido) → Fallback Sonnet
    - Timeout: 15s total
    """
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor, as_completed

    api_key = _carregar_env('ANTHROPIC_API_KEY')
    if not (api_key and api_key.startswith('sk-ant')):
        logger.error("Claude API key não configurada.")
        return "[ERRO] Claude não disponível — configure ANTHROPIC_API_KEY."

    if callback:
        callback(f"[PARALELO] Analisando {len(notas)} notas em chunks...\n")

    # Divide em chunks para análise paralela
    tamanho_chunk = 50
    chunks = [notas[i:i+tamanho_chunk] for i in range(0, len(notas), tamanho_chunk)]

    if len(chunks) == 1:
        # Uma única nota/pequeno lote — análise direta
        prompt = _montar_prompt(notas)
        if nome_produtor:
            prompt = f"PRODUTOR: {nome_produtor}\n\n" + prompt
        sys = system_override or SYSTEM_GAMA

        resultado = {'res': None, 'modelo': None, 'done': False}

        def executar_claude():
            try:
                res, modelo = _analisar_claude(prompt, sys, callback)
                resultado['res'] = res
                resultado['modelo'] = modelo
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
                logger.info(f"✅ Análise rápida com {resultado['modelo']}")
                return res

        return "[ERRO] Análise indisponível."

    # Múltiplos chunks — análise paralela
    sys = system_override or SYSTEM_GAMA
    analises = {}
    t0 = time.time()

    def analisar_chunk(chunk_id, chunk):
        """Analisa um chunk de notas."""
        prompt = _montar_prompt(chunk)
        if chunk_id == 0 and nome_produtor:
            prompt = f"PRODUTOR: {nome_produtor}\n\n" + prompt
        try:
            res, modelo = _analisar_claude(prompt, sys)
            return chunk_id, res, modelo
        except Exception as e:
            return chunk_id, f"[Erro chunk {chunk_id}: {e}]", "nenhum"

    # Executa chunks em paralelo (máx 3 threads para não sobrecarregar API)
    com_timeout = min(15, 15 / max(1, len(chunks)))  # Distribuir timeout entre chunks
    with ThreadPoolExecutor(max_workers=min(3, len(chunks))) as executor:
        futures = [
            executor.submit(analisar_chunk, i, chunk)
            for i, chunk in enumerate(chunks)
        ]

        for future in as_completed(futures, timeout=15):
            try:
                chunk_id, res, modelo = future.result()
                analises[chunk_id] = res
                if callback:
                    callback(f"[Chunk {chunk_id+1}/{len(chunks)}] Pronto ({modelo})\n")
            except Exception as e:
                logger.warning(f"Erro em chunk: {e}")

    t_elapsed = time.time() - t0
    logger.info(f"⏱️ [ANÁLISE PARALELA] {t_elapsed:.1f}s — {len(analises)}/{len(chunks)} chunks")

    if not analises:
        return "[ERRO] Nenhum chunk foi analisado."

    # Combina resultados dos chunks
    veredito_consolidado = "ANÁLISE CONSOLIDADA:\n\n"
    for i in sorted(analises.keys()):
        veredito_consolidado += f"--- Lote {i+1} ---\n{analises[i]}\n\n"

    logger.info(f"✅ Análise paralela concluída em {t_elapsed:.1f}s")
    return veredito_consolidado

