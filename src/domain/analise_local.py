"""Análise local determinística - sem dependência de agentes IA."""

from typing import Dict, Any
from src.domain.extractor import NFA


def calcular_metricas_risco(notas: list[NFA]) -> Dict[str, Any]:
    """Calcula métricas de risco baseadas em regras locais."""
    if not notas:
        return {
            'score_risco': 0.0,
            'nivel_risco': 'BAIXO',
            'sinais': [],
            'observacoes': []
        }

    sinais = []
    observacoes = []
    score_risco = 0.0

    # 1. Análise de valor
    valores = [n.valor_total for n in notas if n.valor_total > 0]
    if valores:
        valor_medio = sum(valores) / len(valores)
        valor_max = max(valores)
        valor_min = min(valores)
        variacao = (valor_max - valor_min) / valor_medio if valor_medio > 0 else 0

        if variacao > 2.0:
            sinais.append("Variação alta de valores entre notas")
            score_risco += 0.15

        # Detecta outliers de valor
        outliers = sum(1 for v in valores if v > valor_medio * 3 or v < valor_medio * 0.1)
        if outliers > 0:
            sinais.append(f"{outliers} nota(s) com valores atípicos")
            score_risco += 0.1

    # 2. Análise de quantidade
    quantidades = [n.quantidade_total for n in notas if n.quantidade_total > 0]
    if quantidades:
        qty_media = sum(quantidades) / len(quantidades)
        qty_max = max(quantidades)

        if qty_max > qty_media * 5:
            sinais.append("Nota com quantidade excepcional")
            score_risco += 0.08

    # 3. Análise de sequência e datas
    datas = [n.emissao for n in notas if n.emissao]
    if len(datas) > 1:
        datas_unicas = len(set(datas))
        if datas_unicas == 1:
            sinais.append("Todas as notas emitidas no mesmo dia")
            score_risco += 0.05

    # 4. Análise de natureza de operação
    por_natureza = {}
    for n in notas:
        natureza = n.natureza or 'OUTRAS'
        por_natureza[natureza] = por_natureza.get(natureza, 0) + 1

    total_notas = len(notas)
    for natureza, count in por_natureza.items():
        pct = (count / total_notas) * 100
        if pct > 95:
            observacoes.append(f"{pct:.0f}% das operações são {natureza}")

    # 5. Análise de ICMS
    icms_valores = [n.valor_icms for n in notas if n.valor_icms > 0]
    if icms_valores and valores:
        total_icms = sum(icms_valores)
        total_valor = sum(valores)
        aliquota_media = (total_icms / total_valor * 100) if total_valor > 0 else 0

        if aliquota_media < 5:
            observacoes.append(f"ICMS médio baixo ({aliquota_media:.1f}%)")
        elif aliquota_media > 25:
            observacoes.append(f"ICMS médio elevado ({aliquota_media:.1f}%)")
            score_risco += 0.05

    # 6. Análise de conformidade básica
    notas_sem_info = sum(1 for n in notas if not n.remetente.nome or not n.destinatario.nome)
    if notas_sem_info > 0:
        sinais.append(f"{notas_sem_info} nota(s) com dados incompletos")
        score_risco += 0.1

    # Normaliza score (0.0 a 1.0)
    score_risco = min(max(score_risco, 0.0), 1.0)

    # Define nível de risco
    if score_risco >= 0.7:
        nivel_risco = 'ALTO'
    elif score_risco >= 0.4:
        nivel_risco = 'MÉDIO'
    else:
        nivel_risco = 'BAIXO'

    return {
        'score_risco': score_risco,
        'nivel_risco': nivel_risco,
        'sinais': sinais,
        'observacoes': observacoes,
        'metricas': {
            'total_notas': total_notas,
            'por_natureza': por_natureza,
            'icms_medio': aliquota_media if icms_valores else 0,
        }
    }


def gerar_veredito_local(notas: list[NFA], nome_contribuinte: str, analise: Dict[str, Any]) -> str:
    """Gera veredito baseado em análise local determinística."""

    if not notas:
        return "[ANÁLISE LOCAL] Nenhuma nota fiscal para análise."

    score = analise['score_risco']
    nivel = analise['nivel_risco']
    sinais = analise['sinais']
    observacoes = analise['observacoes']
    metricas = analise['metricas']

    veredito = f"""[ANÁLISE LOCAL - SISTEMA DETERMINÍSTICO]

CONTRIBUINTE: {nome_contribuinte}
TOTAL DE NOTAS: {metricas['total_notas']}
SCORE DE RISCO: {score:.3f} ({nivel})

DISTRIBUIÇÃO POR NATUREZA:
"""

    for natureza, count in metricas['por_natureza'].items():
        pct = (count / metricas['total_notas']) * 100
        veredito += f"- {natureza}: {count} ({pct:.1f}%)\n"

    if metricas['icms_medio'] > 0:
        veredito += f"\nICMS MÉDIO: {metricas['icms_medio']:.2f}%\n"

    if sinais:
        veredito += "\nSINAIS DETECTADOS:\n"
        for sinal in sinais:
            veredito += f"⚠ {sinal}\n"
    else:
        veredito += "\nSINAIS: Nenhum sinal crítico detectado\n"

    if observacoes:
        veredito += "\nOBSERVAÇÕES:\n"
        for obs in observacoes:
            veredito += f"• {obs}\n"

    veredito += f"\nCONCLUSÃO:\n"

    if nivel == 'ALTO':
        veredito += "Recomenda-se análise manual detalhada. Lote apresenta sinais de não-conformidade."
    elif nivel == 'MÉDIO':
        veredito += "Lote apresenta algumas inconsistências. Recomenda-se verificação de pontos específicos."
    else:
        veredito += "Lote apresenta conformidade adequada. Sem sinais críticos de não-conformidade."

    veredito += f"\n\nAnálise realizada pelo sistema de auditoria local (determinístico)."

    return veredito
