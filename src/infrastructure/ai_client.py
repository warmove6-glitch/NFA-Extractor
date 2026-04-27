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

# Motor local ms-swift (OpenAI-compatible — porta padrão do swift deploy)
SWIFT_URL    = 'http://localhost:8000/v1'
SWIFT_MODEL  = 'Qwen/Qwen2.5-7B-Instruct'  # Substituível via SWIFT_MODEL no config.env

OLLAMA_URL   = 'http://localhost:11434'
OLLAMA_MODEL = 'llama3.1:8b'


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

def _ollama_disponivel() -> bool:
    try:
        res = requests.get(f"{OLLAMA_URL}/api/tags", timeout=1)
        return res.status_code == 200
    except:
        return False

def _swift_disponivel() -> bool:
    url = _carregar_env('SWIFT_URL') or SWIFT_URL
    try:
        res = requests.get(f"{url}/models", timeout=2)
        return res.status_code == 200
    except:
        return False


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


def _analisar_ollama(prompt: str, sys: str, callback=None) -> str:
    """Motor Local com Streaming para evitar hangs."""
    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": f"System: {sys}\nUser: {prompt}", "stream": True},
            stream=True,
            timeout=8,
        )
        full_text = ""
        for line in response.iter_lines():
            if line:
                chunk = json.loads(line.decode('utf-8'))
                token = chunk.get("response", "")
                full_text += token
                if callback: callback(token)
                if chunk.get("done"): break
        return full_text
    except Exception as e:
        return f"[Ollama Erro: {e}]"


def _analisar_swift(prompt: str, sys: str, callback=None) -> str:
    """Motor local ms-swift — API compatível com OpenAI (swift deploy)."""
    try:
        from openai import OpenAI
    except ImportError:
        logger.error("Swift: pacote 'openai' não instalado. Execute: pip install openai")
        return "[Swift Inativo: pacote 'openai' não instalado]"

    url    = _carregar_env('SWIFT_URL')   or SWIFT_URL
    modelo = _carregar_env('SWIFT_MODEL') or SWIFT_MODEL

    try:
        cliente = OpenAI(api_key='EMPTY', base_url=url)
        res = ""
        stream = cliente.chat.completions.create(
            model=modelo,
            messages=[
                {"role": "system", "content": sys},
                {"role": "user",   "content": prompt},
            ],
            max_tokens=4096,
            stream=True,
        )
        for chunk in stream:
            token = (chunk.choices[0].delta.content or "") if chunk.choices else ""
            res += token
            if callback and token:
                callback(token)
        return res
    except Exception as e:
        logger.error(f"Swift: Erro — {e}")
        return f"[Swift Falhou: {e}]"


def _analisar_local_kb(pergunta: str, callback=None) -> str:
    """
    Motor de Conhecimento Local — alternativa offline ao Ollama.

    Usa a base de conhecimento fiscal ORGATEC (local_kb.py) para responder
    perguntas sobre NFA, ICMS, FUNRURAL, CTN, LC 87/96, EC 132/23, GTA, etc.

    Vantagens:
    - Zero dependência de servidor externo
    - Resposta instantânea (< 5ms)
    - Sem alucinações — apenas conteúdo pré-validado
    """
    from src.infrastructure.local_kb import responder as kb_responder
    try:
        resposta = kb_responder(pergunta)
        if callback:
            callback(resposta)
        return resposta
    except Exception as e:
        logger.error(f"KB Local: erro inesperado — {e}")
        return f"[KB Local Erro: {e}]"


def _local_kb_disponivel() -> bool:
    """Sempre disponível (sem dependências externas)."""
    try:
        from src.infrastructure.local_kb import KB
        return len(KB) > 0
    except Exception:
        return False

# ── ORQUESTRADOR RESILIENTE ────────────────────────────────────────────────


def analisar_producao(notas: list[NFA], callback=None, system_override: str = None,
                     nome_produtor: str = "") -> str:
    """
    Modo PRODUÇÃO (2026): Claude com fallback rápido.

    Hierarquia OTIMIZADA:
    1. Claude Vision/Text (15s timeout) — qualidade máxima
    2. Swift (10s timeout) — fallback local rápido
    3. KB Local (instantâneo) — contingência final

    Nota: Ollama removido do fluxo (muito lento em produção).
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
            else:
                if callback: callback("[!] Claude falhou — fallback ativado\n")

    # 2. SWIFT (FALLBACK LOCAL) — timeout de 10s
    if _swift_disponivel():
        if callback: callback("[FALLBACK] Swift local (rápido)...\n")

        resultado = {'res': None, 'done': False}

        def executar_swift():
            try:
                resultado['res'] = _analisar_swift(prompt, sys, callback)
                resultado['done'] = True
            except Exception as e:
                resultado['res'] = f"[Swift Error: {e}]"
                resultado['done'] = True

        thread = threading.Thread(target=executar_swift, daemon=True)
        thread.start()
        thread.join(timeout=10)

        if resultado['done'] and resultado['res']:
            res = resultado['res']
            if "[Swift" not in res:
                return res

    # 3. KB LOCAL (CONTINGÊNCIA FINAL) — instantâneo
    if callback: callback("[KB] Base de Conhecimento Local (instantâneo)...\n")
    return _analisar_local_kb(prompt, callback)

# ── PIPELINE EM LOTES (TURBO) ──────────────────────────────────────────────

# ── FUNÇÃO perguntar() — Endpoint /agente/chat ─────────────────────────────

def perguntar(
    notas: list,
    pergunta: str,
    context_ia: str = "",
    callback=None,
) -> str:
    """
    Responde perguntas sobre NFA, direito tributário e auditoria fiscal.

    Cascata de fallback (mais rápido → mais completo):
    1. KB Local (offline, instantâneo) — responde perguntas conhecidas
    2. Cloud (Claude/Gemini/Azure) — para perguntas complexas / fora da KB
    3. Ollama local — se configurado e disponível

    Parâmetros:
        notas       : lista de NFA para contexto (pode ser vazia)
        pergunta    : texto da pergunta do usuário
        context_ia  : contexto adicional (laudos anteriores, etc.)
        callback    : função chamada com tokens parciais (streaming opcional)
    """
    if not pergunta or not pergunta.strip():
        return "Por favor, faça uma pergunta sobre NFA, ICMS, FUNRURAL ou direito tributário."

    # 1. Tenta KB Local primeiro — é instantâneo e não falha
    from src.infrastructure.local_kb import buscar as kb_buscar, responder as kb_responder
    resultados_kb = kb_buscar(pergunta, top_k=1, min_score=0.07)

    if resultados_kb:
        # Match encontrado na KB — retorna direto (sem cloud)
        resposta_kb = kb_responder(pergunta)
        logger.info(f"perguntar: respondido via KB Local para '{pergunta[:50]}'")
        return resposta_kb

    # 2. Pergunta não está na KB — tenta cloud
    sys_consultor = (
        "Você é o Consultor Tributário ORGATEC, especialista em NFA, ICMS, FUNRURAL, "
        "CTN, LC 87/96 e Reforma Tributária (EC 132/23). "
        "Responda de forma clara, objetiva e embasada na legislação brasileira. "
        "Se não souber, diga 'Dados insuficientes' em vez de inventar."
    )

    prompt_consulta = pergunta.strip()
    if context_ia:
        prompt_consulta = f"Contexto:\n{context_ia}\n\nPergunta: {pergunta}"
    if notas:
        ctx_notas = _montar_prompt(notas)
        prompt_consulta = f"{ctx_notas}\n\nPergunta: {pergunta}"

    # 2. Pergunta complexa — tenta motores locais primeiro, depois cloud
    if _swift_disponivel():
        res = _analisar_swift(prompt_consulta, sys_consultor, callback)
        if "[Swift" not in res:
            return res

    if _ollama_disponivel():
        res = _analisar_ollama(prompt_consulta, sys_consultor, callback)
        if "[Ollama Erro" not in res:
            return res

    # Cloud como fallback de último recurso (custo apenas se locais falharem)
    if _claude_disponivel():
        res = _analisar_claude(prompt_consulta, sys_consultor, callback)
        if "[Claude" not in res:
            return res

    if _gemini_disponivel():
        res = _analisar_gemini(prompt_consulta, sys_consultor, callback)
        if "[Gemini" not in res:
            return res

    if _azure_disponivel():
        res = _analisar_azure_openai(prompt_consulta, sys_consultor, callback)
        if "[Azure" not in res:
            return res

    logger.warning("perguntar: todos os motores falharam, retornando KB genérica")
    return _analisar_local_kb(pergunta, callback)
