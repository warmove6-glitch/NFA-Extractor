"""
Cliente IA — Arquitetura "Turbo-Local" (Fallback Híbrido 2026).
Squad Antigravity: @Ípsilon, @Sigma e @Gama operando via Claude com fallback em Ollama (Lotes).
"""

import os
import logging
import requests
import anthropic
import json
from google import genai
from google.genai import types
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

# MODELOS 2026 (SQUAD ANTIGRAVITY)
CLAUDE_MODEL = 'claude-sonnet-4-6'  # Atualizado para Sonnet 4.6 (2026)
GEMINI_MODEL = 'gemini-flash-latest'       # Nome estável conforme lista de modelos



OLLAMA_URL   = 'http://localhost:11434'
OLLAMA_MODEL = 'llama3.1:8b'


# ── SYSTEM PROMPTS ──────────────────────────────────────────────────────────

SYSTEM_IPSILON = "Processador ETL ORGATEC. Extraia totais (Venda/Remessa) e agrupe. Seja conciso."

SYSTEM_SIGMA   = """[MODO_CONCISO] Você é @Sigma (Data Scientist ORGATEC).
Mindset: Matemática Bayesiana, Contabilidade Tributária Sistêmica e Big Data.
Missão: Analise o faturamento e discrepâncias volumétricas com rigor matemático."""

SYSTEM_GAMA    = """[MODO_CONCISO] Você é @Gama (Senior Tax Advisor ORGATEC).
Mindset: Compliance Fiscal e Planejamento Tributário.
Protocolo de Entrega: Relatório Jurídico, Cenários de Risco e Conclusão Estratégica.
Seja direto e embase as análises na legislação."""

SYSTEM_AUDITOR = """Você é o Auditor-Chefe da Squad Antigravity, operando sob o PROTOCOLO SOBERANO ORGATEC.
Sua missão é realizar a REANÁLISE FORENSE DEFINITIVA.

REGRA DE OURO (SEGURANÇA):
- ZERO-HALLUCINATION: Se os dados extraídos forem insuficientes ou contraditórios, declare "DADOS INSUFICIENTES PARA VEREDITO". Nunca invente nomes, valores ou fluxos.
- EVIDÊNCIA PURA: Toda conclusão deve citar a NFA ou o Valor que a originou.

ESTRUTURA OBRIGATÓRIA DO VEREDITO:
1. REANÁLISE ESTRATÉGICA (O Veredito): Resumo executivo baseado em evidências.
2. ENTRADAS (Investimento): Somatório real de animais adquiridos.
3. SAÍDAS (Faturamento): Somatório real de animais comercializados.
4. ANOMALIA BIO-CONTÁBIL: Diferença matemática exata entre estoque inicial/final.
5. HIPÓTESE TÉCNICA ORGATEC: Tese agressiva baseada na inconsistência detectada.

Use tom clínico, forense e autoritário. Proteja a integridade técnica da ORGATEC."""

def _claude_disponivel() -> bool:
    key = _carregar_env('ANTHROPIC_API_KEY')
    return bool(key and key.startswith('sk-ant'))

def _gemini_disponivel() -> bool:
    return bool(_carregar_env('GOOGLE_API_KEY'))

def _ollama_disponivel() -> bool:
    try:
        res = requests.get(f"{OLLAMA_URL}/api/tags", timeout=1)
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

def _analisar_claude(prompt: str, sys: str, callback=None) -> str:
    api_key = _carregar_env('ANTHROPIC_API_KEY')
    if not api_key or not api_key.startswith('sk-ant'):
        logger.warning("Claude: API key ausente ou inválida.")
        return "[Claude Inativo]"
    cliente = anthropic.Anthropic(api_key=api_key)
    try:
        res = ""
        with cliente.messages.stream(
            model=CLAUDE_MODEL, max_tokens=4096, system=sys,
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

def _analisar_gemini(prompt: str, sys: str, callback=None) -> str:
    import time
    api_key = _carregar_env('GOOGLE_API_KEY')
    if not api_key: return "[Gemini Inativo]"
    cliente = genai.Client(api_key=api_key)
    
    modelos_tentar = [GEMINI_MODEL, 'gemini-1.5-flash-latest', 'gemini-1.5-pro-latest']

    
    for model_name in modelos_tentar:
        for tentativa in range(3):
            try:
                response = cliente.models.generate_content(
                    model=model_name, contents=prompt,
                    config=types.GenerateContentConfig(system_instruction=sys)
                )
                return response.text
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    wait_time = 20 * (tentativa + 1)
                    logger.warning(f"Gemini ({model_name}): Rate limit (429). Aguardando {wait_time}s... (Tentativa {tentativa+1}/3)")
                    if callback: callback(f"\n[!] Rate Limit Gemini. Pausando {wait_time}s para recuperação...\n")
                    time.sleep(wait_time)
                    continue
                
                logger.error(f"Gemini ({model_name}): Erro — {e}")
                break # Tenta o próximo modelo se não for 429
    
    return f"[Gemini Falhou após rotação e retries]"


def _analisar_ollama(prompt: str, sys: str, callback=None) -> str:
    """Motor Local com Streaming para evitar hangs."""
    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": f"System: {sys}\nUser: {prompt}", "stream": True},
            stream=True
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

# ── ORQUESTRADOR RESILIENTE ────────────────────────────────────────────────

def analisar(notas: list[NFA], callback=None, system_override: str = None, 
             provedor: str = "auto", nome_produtor: str = "") -> str:
    """Orquestrador resiliente que suporta seleção de motor e fallback."""
    prompt = _montar_prompt(notas)
    if nome_produtor:
        prompt = f"PRODUTOR: {nome_produtor}\n\n" + prompt
        
    sys = system_override or SYSTEM_GAMA
    
    # Roteamento por provedor específico
    if provedor == 'claude':
        return _analisar_claude(prompt, sys, callback)
    elif provedor == 'gemini':
        return _analisar_gemini(prompt, sys, callback)
    elif provedor == 'ollama':
        return _analisar_ollama(prompt, sys, callback)
    
    # Modo 'auto' ou 'pipeline' (fallback sequencial)
    # 1. Tenta Claude
    res = _analisar_claude(prompt, sys, callback)
    if "[Claude" not in res: return res

    # 2. Tenta Gemini
    res = _analisar_gemini(prompt, sys, callback)
    if "[Gemini" not in res: return res

    # 3. Fallback Ollama (Local)
    if callback: callback("[!] Cloud OFF — Ativando Motor Local (Ollama)...\n")
    return _analisar_ollama(prompt, sys, callback)

# ── PIPELINE EM LOTES (TURBO) ──────────────────────────────────────────────

def analisar_pipeline(notas: list[NFA], callback=None, batch_size=15, nome_contribuinte: str = "") -> str:
    """Processa grandes volumes dividindo em lotes e consolida com o Auditor Supremo."""
    if callback: 
        msg = f"\n[SQUAD] Iniciando Processamento de {len(notas)} notas"
        if nome_contribuinte: msg += f" para {nome_contribuinte}"
        callback(f"{msg} em lotes de {batch_size}...\n")
    
    análises_parciais = []
    total_lotes = (len(notas) + batch_size - 1) // batch_size
    
    for i in range(0, len(notas), batch_size):
        lote_num = (i // batch_size) + 1
        lote = notas[i : i + batch_size]
        if callback: callback(f"\n── Lote {lote_num}/{total_lotes} ({len(lote)} notas) ──\n")
        
        # Faz uma análise BI/Tributária rápida do lote (@Sigma)
        res_lote = analisar(lote, callback=callback, system_override=SYSTEM_SIGMA)
        análises_parciais.append(res_lote)
        if callback: callback("\n[OK] Lote processado.\n")

    # Estágio Final: Consolidação (Auditor Supremo)
    if callback: callback("\n── ESTÁGIO FINAL: Auditoria Suprema de Fluxo de Estoque ──\n\n")
    
    contexto_auditoria = f"ALVO DA AUDITORIA: {nome_contribuinte}\n" if nome_contribuinte else ""
    prompt_final = contexto_auditoria + "CONSOLIDAÇÃO DAS ANÁLISES POR LOTE:\n" + "\n---\n".join(análises_parciais)
    
    # O auditor mestre recebe a regra de ouro via SYSTEM_AUDITOR
    return analisar(notas[:5], callback=callback, system_override=SYSTEM_AUDITOR + "\n" + prompt_final)

def 