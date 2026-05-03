"""Geração de planilha de gado para IRPF - modelo simplificado."""

from src.domain.auditoria_forense import _natureza_categoria
from src.domain.extractor import NFA

# Mapeamento das categorias internas (Regra 1) para labels de exibição
_CATEGORIA_LABEL: dict[str, str] = {
    "RECEITA": "VENDA",
    "TRANSITO": "REMESSA",
    "TRANSFERENCIA": "TRANSFERENCIA",
    "DESPESA": "COMPRA",
    "OUTRA": "OUTRAS",
}


def gerar_dados_planilha(notas: list[NFA], nome_produtor: str, cliente_cpf: str | None = None) -> dict:
    """Extrai dados para planilha no formato IRPF (Lei 8.023/90)."""

    # Organiza notas por natureza e mês
    por_natureza_mes = {}

    for natureza in ['VENDA', 'REMESSA', 'COMPRA', 'TRANSFERENCIA', 'OUTRAS']:
        por_natureza_mes[natureza] = {}
        for mes in range(1, 13):
            por_natureza_mes[natureza][mes] = {
                'notas': 0,
                'cabecas': 0.0,
                'valor': 0.0
            }

    # Processa cada nota
    for nota in notas:
        # Extrai mês da data (DD/MM/YYYY)
        if nota.emissao and len(nota.emissao) >= 5:
            try:
                mes = int(nota.emissao[3:5])
            except (ValueError, TypeError):
                continue
        else:
            continue

        # Quando CPF do cliente disponível, classifica pela posição (Regra 1)
        if cliente_cpf:
            cat = _natureza_categoria(nota, cliente_cpf)
            natureza = _CATEGORIA_LABEL.get(cat, "OUTRAS")
        else:
            natureza = nota.natureza or 'OUTRAS'
        if natureza not in por_natureza_mes:
            natureza = 'OUTRAS'

        entry = por_natureza_mes[natureza][mes]
        entry['notas'] += 1
        entry['cabecas'] += nota.quantidade_total
        entry['valor'] += nota.valor_total

    # Calcula totais gerais
    total_geral = {
        'notas': len(notas),
        'cabecas': sum(n.quantidade_total for n in notas),
        'valor': sum(n.valor_total for n in notas),
    }

    # Calcula totais por natureza
    totais_natureza = {}
    for natureza in por_natureza_mes.keys():
        total_notas = sum(por_natureza_mes[natureza][mes]['notas'] for mes in range(1, 13))
        total_cabecas = sum(por_natureza_mes[natureza][mes]['cabecas'] for mes in range(1, 13))
        total_valor = sum(por_natureza_mes[natureza][mes]['valor'] for mes in range(1, 13))

        if total_notas > 0:  # Só inclui se houver dados
            totais_natureza[natureza] = {
                'notas': total_notas,
                'cabecas': total_cabecas,
                'valor': total_valor,
            }

    datas = [n.emissao for n in notas if n.emissao]
    periodo = f"{min(datas)} a {max(datas)}" if datas else "N/A"

    return {
        'produtor': nome_produtor,
        'periodo': periodo,
        'total_notas': total_geral['notas'],
        'total_cabecas': total_geral['cabecas'],
        'faturamento_total': total_geral['valor'],
        'por_natureza_mes': por_natureza_mes,
        'totais_natureza': totais_natureza,
    }


def formatar_moeda(valor: float) -> str:
    """Formata valor como moeda brasileira."""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def gerar_html_planilha(dados: dict) -> str:
    """Gera HTML da planilha no modelo IRPF."""

    meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
             "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

    cores = {
        'VENDA': '#10b981',         # Verde
        'REMESSA': '#f59e0b',       # Amarelo
        'COMPRA': '#ef4444',        # Vermelho (despesa/investimento)
        'TRANSFERENCIA': '#06b6d4', # Cyan
        'OUTRAS': '#a855f7',        # Roxo
    }

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Planilha de Gado - IRPF</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
        .container {{ max-width: 1000px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; }}
        .header {{ margin-bottom: 30px; }}
        .header h1 {{ color: #1e293b; margin: 0; font-size: 24px; }}
        .header p {{ color: #64748b; margin: 5px 0; font-size: 14px; }}
        .info-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 30px; }}
        .info-item {{ padding: 10px; background: #f0f9ff; border-radius: 4px; }}
        .info-label {{ font-weight: bold; color: #475569; font-size: 12px; }}
        .info-value {{ font-size: 18px; color: #1e293b; font-weight: bold; }}
        table {{ width: 100%; border-collapse: collapse; margin-bottom: 30px; }}
        th {{ background: #1e293b; color: white; padding: 12px; text-align: left; font-weight: bold; }}
        td {{ padding: 10px; border-bottom: 1px solid #e2e8f0; }}
        tr:nth-child(even) {{ background: #f8fafc; }}
        .section-header {{ background: #1e293b; color: white; padding: 12px; font-weight: bold; }}
        .section-color-venda {{ background: #10b981; }}
        .section-color-remessa {{ background: #f59e0b; }}
        .section-color-compra {{ background: #ef4444; }}
        .section-color-transferencia {{ background: #06b6d4; }}
        .section-color-outras {{ background: #a855f7; }}
        .total-row {{ background: #1e293b; color: white; font-weight: bold; }}
        .valor {{ text-align: right; }}
        .numero {{ text-align: center; }}
        @media print {{ body {{ margin: 0; }} .container {{ border-radius: 0; }} }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>RELATÓRIO DE MOVIMENTAÇÃO — IRPF</h1>
            <p>Lei 8.023/90 - IRPF Atividade Rural</p>
        </div>

        <div class="info-grid">
            <div class="info-item">
                <div class="info-label">PRODUTOR / REMETENTE</div>
                <div class="info-value">{dados['produtor']}</div>
            </div>
            <div class="info-item">
                <div class="info-label">PERÍODO</div>
                <div class="info-value">{dados['periodo']}</div>
            </div>
            <div class="info-item">
                <div class="info-label">TOTAL DE NOTAS</div>
                <div class="info-value">{dados['total_notas']}</div>
            </div>
            <div class="info-item">
                <div class="info-label">TOTAL DE CABEÇAS</div>
                <div class="info-value">{dados['total_cabecas']:.0f}</div>
            </div>
            <div class="info-item" style="grid-column: 1 / -1;">
                <div class="info-label">FATURAMENTO TOTAL</div>
                <div class="info-value">{formatar_moeda(dados['faturamento_total'])}</div>
            </div>
        </div>
"""

    # Gera tabelas por natureza
    for natureza, cor in cores.items():
        if natureza not in dados['totais_natureza']:
            continue

        html += f"""
        <table>
            <tr class="section-header section-color-{natureza.lower()}">
                <th style="background: {cor};">{natureza.upper()}</th>
                <th style="background: {cor}; text-align: center;">Q NOTAS</th>
                <th style="background: {cor}; text-align: center;">CABEÇAS</th>
                <th style="background: {cor}; text-align: right;">VALOR (R$)</th>
            </tr>
"""

        for mes_num in range(1, 13):
            entry = dados['por_natureza_mes'][natureza][mes_num]
            if entry['notas'] == 0:
                html += f"""
            <tr>
                <td>{meses[mes_num-1]}</td>
                <td class="numero"></td>
                <td class="numero"></td>
                <td class="valor"></td>
            </tr>
"""
            else:
                html += f"""
            <tr>
                <td>{meses[mes_num-1]}</td>
                <td class="numero">{entry['notas']}</td>
                <td class="numero">{entry['cabecas']:.0f}</td>
                <td class="valor">{formatar_moeda(entry['valor'])}</td>
            </tr>
"""

        total = dados['totais_natureza'][natureza]
        html += f"""
            <tr class="total-row" style="background: {cor};">
                <td>TOTAL</td>
                <td class="numero">{total['notas']}</td>
                <td class="numero">{total['cabecas']:.0f}</td>
                <td class="valor">{formatar_moeda(total['valor'])}</td>
            </tr>
        </table>
"""

    html += """
    </div>
</body>
</html>
"""
    return html
