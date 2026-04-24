"""
Módulo IAanalitic — Inteligência Analítica e Auditoria (Claude-Only 2026).
"""

from ai_client import analisar, analisar_pipeline, SYSTEM_SIGMA, SYSTEM_GAMA, SYSTEM_AUDITOR
from extractor import NFA

def resumo_analitico_comercializacao(notas: list[NFA], callback=None) -> str:
    """Executa a análise de BI focada em comercialização (@Sigma)."""
    if callback:
        callback("\n\n[SQUAD] Invocando @Sigma (Claude) para Análise de Comercialização...\n\n")
    return analisar(notas, callback=callback, system_override=SYSTEM_SIGMA)

def resumo_geral_preditivo(notas: list[NFA], callback=None) -> str:
    """Executa a análise de riscos e probabilidades (@Gama)."""
    if callback:
        callback("\n\n[SQUAD] Invocando @Gama (Claude) para Predições e Riscos...\n\n")
    return analisar(notas, callback=callback, system_override=SYSTEM_GAMA)

def auditoria_consolidada(notas: list[NFA], callback=None) -> str:
    """Orquestra a Auditoria Completa: Ípsilon -> Sigma -> Gama -> Auditor Diretor."""
    if callback:
        callback("\n\n[SQUAD] INICIANDO AUDITORIA TRIPARTITE UNIFICADA (CLAUDE)...\n")
    
    # Agora usamos o pipeline consolidado no ai_client que já faz os 3 estágios
    return analisar_pipeline(notas, callback=callback)
