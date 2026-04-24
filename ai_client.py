"""
Cliente IA — Arquitetura "Turbo-Local" (Fallback Híbrido 2026).
Squad Antigravity: @Ípsilon, @Sigma e @Gama operando via Claude com fallback em Ollama (Lotes).
"""

import os
import requests
import anthropic
import json
from google import genai
from google.genai import types
from pydantic import SecretStr
from pathlib import Path
from extractor import NFA, resumo_geral

CONFIG_PATH  = Path(__file__).parent / 'config.env'

# MODELOS 2026
CLAUDE_MODEL = 'claude-3-haiku-20240307' # Backup sugerido pelo usuário
GEMINI_MODEL = 'gemini-flash-lite-latest'
OLLAMA_URL   = 'http://localhost:11434'
OLLAMA_MODEL = 'llama3.1:8b'

def _carregar_env(chave: str) -> str:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            for linha in f:
                if '=' in linha and not linha.startswith('#'):
                    k, v = linha.strip().split('=', 1)
                    if k == chave: return v
    return os.getenv(chave, '')

# ── SYSTEM PROMPTS ──────────────────────────────────────────────────────────

SYSTEM_IPSILON = "Processador ETL. Extraia totais (Venda/Remessa) e agrupe. Seja conciso."
SYSTEM_SIGMA   = "Cientista Tributário. Analise BI, preços médios e tendências mensais."
SYSTEM_GAMA    = "Consultor Jurídico. Avalie riscos de autuação e conformidade fiscal."
SYSTEM_AUDITOR = "AUDITOR-CHEFE. Consolide as análises parciais em um Laudo Executivo Final."

# ── LOGICA DE LOTE (CHUNKS) ────────────────────────────────────────────────

def _montar_prompt(notas: list[NFA]) -> str:
    if not notas: return "Nenhuma nota."
    corpo = "DADOS EXTRAÍDOS:\n"
    for i, n in enumerate(notas, 1):
        corpo += f"- NFA {i}: {n.natureza} | Emissão: {n.emissao} | Valor: R$ {n.valor_total:,.2f} | Caps: {n.quantidade_total}\n"
    return corpo

# ── MOTORES INDIVIDUAIS ─────────────────────────────────────────────────────

def _analisar_claude(prompt: str, sys: str, callback=None) -> str:
    api_key = _carregar_env('ANTHROPIC_API_KEY')
    if not api_key or not api_key.startswith('sk-ant'): return "[Claude Inativo]"
    cliente = anthropic.Anthropic(api_key=SecretStr(api_key).get_secret_value())
    try:
        res = ""
        with cliente.messages.stream(
            model=CLAUDE_MODEL, max_tokens=2000, system=sys,
            messages=[{'role': 'user', 'content': prompt}]
        ) as stream:
            for t in stream.text_stream:
                res += t
                if callback: callback(t)
        return res
    except: return "[Claude Falhou]"

def _analisar_gemini(prompt: str, sys: str, callback=None) -> str:
    api_key = _carregar_env('GOOGLE_API_KEY')
    if not api_key: return "[Gemini Inativo]"
    cliente = genai.Client(api_key=api_key)
    try:
        res = ""
        for chunk in cliente.models.generate_content_stream(
            model=GEMINI_MODEL, contents=prompt,
            config=types.GenerateContentConfig(system_instruction=sys)
        ):
            res += chunk.text
            if callback: callback(chunk.text)
        return res
    except: return "[Gemini Falhou]"

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

def analisar(notas: list[NFA], callback=None, system_override: str = None) -> str:
    prompt = _montar_prompt(notas)
    sys = system_override or SYSTEM_GAMA
    
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

def analisar_pipeline(notas: list[NFA], callback=None, batch_size=15) -> str:
    """Processa grandes volumes dividindo em lotes."""
    if callback: callback(f"\n[SQUAD] Iniciando Processamento de {len(notas)} notas em lotes de {batch_size}...\n")
    
    análises_parciais = []
    total_lotes = (len(notas) + batch_size - 1) // batch_size
    
    for i in range(0, len(notas), batch_size):
        lote_num = (i // batch_size) + 1
        lote = notas[i : i + batch_size]
        if callback: callback(f"\n── Lote {lote_num}/{total_lotes} ({len(lote)} notas) ──\n")
        
        # Faz uma análise BI/Tributária rápida do lote
        res_lote = analisar(lote, callback=callback, system_override=SYSTEM_SIGMA)
        análises_parciais.append(res_lote)
        if callback: callback("\n[OK] Lote processado.\n")

    # Estágio Final: Consolidação (Auditor-Chefe)
    if callback: callback("\n── ESTÁGIO FINAL: Consolidação da Auditoria 360º ──\n\n")
    prompt_final = "CONSOLIDAÇÃO DAS ANÁLISES POR LOTE:\n" + "\n---\n".join(análises_parciais)
    
    # O auditor chefe recebe o resumo de todos os lotes para dar o veredito
    # Para o auditor chefe, usamos apenas a lista de conclusões dos lotes como 'prompt'
    # mas mantemos a assinatura de receber 'notas' (passaremos as primeiras para contexto)
    return analisar(notas[:5], callback=callback, system_override=SYSTEM_AUDITOR + "\n" + prompt_final)
