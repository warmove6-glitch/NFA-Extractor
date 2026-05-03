"""
Gerador de PDF Premium com WeasyPrint + Jinja2 (Fiscal Clarity Design).
Substitui ReportLab para qualidade visual superior.
"""
import logging
from datetime import datetime
from typing import Any

from src.domain.extractor import NFA, resumo_geral

logger = logging.getLogger(__name__)


def gerar_pdf_weasyprint(
    notas: list[NFA],
    saida: str,
    nome_contribuinte: str = "",
    cpf_contribuinte: str = "",
    risco_nivel: str = "BAIXO",
    score_risco: float = 0.0,
    modo_relatorio: str = "simples",
    **kwargs
) -> None:
    """
    Gera PDF de alta qualidade usando WeasyPrint + Jinja2.

    Args:
        notas: Lista de notas fiscais extraídas
        saida: Caminho do arquivo PDF de saída
        nome_contribuinte: Nome do contribuinte
        cpf_contribuinte: CPF/CNPJ do contribuinte
        risco_nivel: BAIXO, MÉDIO, ALTO, CRÍTICO
        score_risco: Score de risco (0-1)
        modo_relatorio: 'simples' ou 'detalhado'
    """
    try:
        from weasyprint import CSS, HTML
    except ImportError:
        logger.error("WeasyPrint não instalado. Use: pip install weasyprint")
        raise

    # Calcular resumo
    resumo = resumo_geral(notas, nome_contribuinte)

    # Preparar dados para template
    dados_template = {
        "titulo": "Planilha IRPF — Lei 8.023/90",
        "subtitulo": "Auditoria Fiscal de Notas Avulsas",
        "data_emissao": datetime.now().strftime("%d/%m/%Y"),
        "contribuinte": nome_contribuinte or "Não identificado",
        "cpf_cnpj": cpf_contribuinte or "N/A",
        "risco_nivel": risco_nivel,
        "risco_nivel_lower": risco_nivel.lower(),
        "score_risco": f"{score_risco:.1%}",
        "modo_relatorio": modo_relatorio,

        # KPIs
        "total_notas": resumo.get("total_notas", 0),
        "total_valor": resumo.get("total_valor", 0),
        "total_cabecas": resumo.get("total_cabecas", 0),
        "ticket_medio": resumo.get("ticket_medio", 0),

        # Detalhes
        "por_mes": resumo.get("por_mes", {}),
        "por_natureza": resumo.get("por_natureza", {}),
        "top_dest": resumo.get("top_dest", [])[:10],  # Top 10
    }

    # Renderizar template
    html_content = _renderizar_template_html(dados_template)

    # Gerar PDF
    try:
        HTML(string=html_content).write_pdf(saida)
        logger.info(f"[PDF WEASYPRINT] Gerado com sucesso: {saida}")
    except Exception as e:
        logger.error(f"Erro ao gerar PDF com WeasyPrint: {e}")
        raise


def _renderizar_template_html(dados: dict[str, Any]) -> str:
    """Renderiza HTML usando template Jinja2."""
    template_html = _obter_template_html()
    from jinja2 import Template

    template = Template(template_html)
    return template.render(**dados)


def _obter_template_html() -> str:
    """Retorna template HTML inline (Fiscal Clarity)."""
    return """<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>{{ titulo }}</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            color: #1a202c;
            line-height: 1.6;
            background: #f8fafb;
        }

        @page {
            size: A4;
            margin: 20mm 15mm;
            @bottom-center {
                content: "Página " counter(page) " de " counter(pages);
                font-size: 10px;
                color: #718096;
            }
        }

        .container {
            max-width: 210mm;
            height: auto;
            background: white;
            padding: 30px;
        }

        /* HEADER */
        .header {
            border-bottom: 3px solid #0f3a66;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }

        .header h1 {
            font-size: 24px;
            font-weight: 700;
            color: #0f3a66;
            margin-bottom: 5px;
        }

        .header p {
            font-size: 13px;
            color: #718096;
        }

        /* METADATA */
        .metadata-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 30px;
            padding: 20px;
            background: #f7fafc;
            border-left: 4px solid #4db8ff;
            border-radius: 4px;
        }

        .metadata-item {
            font-size: 12px;
        }

        .metadata-label {
            color: #718096;
            text-transform: uppercase;
            font-size: 10px;
            letter-spacing: 0.5px;
            font-weight: 600;
            margin-bottom: 5px;
        }

        .metadata-value {
            font-size: 14px;
            font-weight: 600;
            color: #2d3748;
        }

        /* KPI CARDS */
        .kpi-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 15px;
            margin-bottom: 30px;
        }

        .kpi-card {
            background: white;
            padding: 15px;
            border: 1px solid #e2e8f0;
            border-top: 3px solid #4db8ff;
            border-radius: 4px;
        }

        .kpi-label {
            font-size: 10px;
            color: #718096;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            font-weight: 600;
            margin-bottom: 8px;
        }

        .kpi-value {
            font-size: 18px;
            font-weight: 700;
            color: #0f3a66;
            word-break: break-word;
        }

        /* RISCO BADGE */
        .risco-badge {
            display: inline-block;
            padding: 8px 16px;
            border-radius: 4px;
            font-weight: 600;
            font-size: 12px;
            text-transform: uppercase;
            margin-bottom: 20px;
            letter-spacing: 0.5px;
        }

        .risco-baixo {
            background: #d4f4dd;
            color: #22543d;
        }

        .risco-medio {
            background: #fed7aa;
            color: #78350f;
        }

        .risco-alto {
            background: #fee2e2;
            color: #991b1b;
        }

        .risco-critico {
            background: #fecaca;
            color: #7f1d1d;
        }

        /* SEÇÕES */
        h2 {
            font-size: 16px;
            font-weight: 700;
            margin-top: 30px;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #e2e8f0;
            color: #0f3a66;
        }

        /* TABELAS */
        table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
            font-size: 12px;
        }

        thead {
            background: #f7fafc;
            border-bottom: 2px solid #cbd5e0;
        }

        th {
            padding: 12px;
            text-align: left;
            font-weight: 600;
            color: #2d3748;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        td {
            padding: 10px 12px;
            border-bottom: 1px solid #e2e8f0;
        }

        tbody tr:nth-child(odd) {
            background: #f9fafb;
        }

        .num {
            text-align: right;
            font-family: 'Courier New', monospace;
        }

        /* BADGES */
        .badge {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 3px;
            font-size: 10px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.3px;
        }

        .badge-venda {
            background: #d4f4dd;
            color: #22543d;
        }

        .badge-remessa {
            background: #fed7aa;
            color: #78350f;
        }

        .badge-transferencia {
            background: #a7f3d0;
            color: #064e3b;
        }

        .badge-outras {
            background: #ddd6fe;
            color: #3f0f5c;
        }

        /* FOOTER */
        .footer {
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #e2e8f0;
            font-size: 11px;
            color: #718096;
            text-align: center;
        }

        @media print {
            body { background: white; }
            .container { padding: 0; }
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- HEADER -->
        <div class="header">
            <h1>{{ titulo }}</h1>
            <p>{{ subtitulo }} — Emitido em {{ data_emissao }}</p>
        </div>

        <!-- METADATA -->
        <div class="metadata-grid">
            <div class="metadata-item">
                <div class="metadata-label">Contribuinte</div>
                <div class="metadata-value">{{ contribuinte }}</div>
            </div>
            <div class="metadata-item">
                <div class="metadata-label">CPF/CNPJ</div>
                <div class="metadata-value">{{ cpf_cnpj }}</div>
            </div>
            <div class="metadata-item">
                <div class="metadata-label">Total de Notas</div>
                <div class="metadata-value">{{ "{:,}".format(total_notas) }}</div>
            </div>
            <div class="metadata-item">
                <div class="metadata-label">Período</div>
                <div class="metadata-value">Múltiplos meses</div>
            </div>
        </div>

        <!-- RISCO -->
        <div class="risco-badge risco-{{ risco_nivel_lower }}">
            Nível: {{ risco_nivel }} ({{ score_risco }})
        </div>

        <!-- KPIs -->
        <div class="kpi-grid">
            <div class="kpi-card">
                <div class="kpi-label">Total Cabeças</div>
                <div class="kpi-value">{{ "{:,.0f}".format(total_cabecas) }}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Valor Total</div>
                <div class="kpi-value">R$ {{ "{:,.0f}".format(total_valor) }}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Ticket Médio</div>
                <div class="kpi-value">R$ {{ "{:,.0f}".format(ticket_medio) }}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Tipo Ops</div>
                <div class="kpi-value">{{ por_natureza|length }}</div>
            </div>
        </div>

        <!-- TABELA MENSAL -->
        <h2>Resumo por Mês</h2>
        <table>
            <thead>
                <tr>
                    <th>Período</th>
                    <th class="num">Notas</th>
                    <th class="num">Cabeças</th>
                    <th class="num">Valor (R$)</th>
                </tr>
            </thead>
            <tbody>
                {% for mes, dados in por_mes.items() %}
                <tr>
                    <td>{{ mes }}</td>
                    <td class="num">{{ dados.get('notas', 0) }}</td>
                    <td class="num">{{ "{:,.0f}".format(dados.get('cabecas', 0)) }}</td>
                    <td class="num">R$ {{ "{:,.0f}".format(dados.get('valor', 0)) }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>

        <!-- TABELA NATUREZA -->
        <h2>Operações por Tipo</h2>
        <table>
            <thead>
                <tr>
                    <th>Tipo</th>
                    <th class="num">Quantidade</th>
                    <th class="num">%</th>
                </tr>
            </thead>
            <tbody>
                {% for natureza, qtd in por_natureza.items() %}
                <tr>
                    <td><span class="badge badge-{{ natureza|lower }}">{{ natureza }}</span></td>
                    <td class="num">{{ qtd }}</td>
                    <td class="num">{{ "{:.1f}".format((qtd / total_notas * 100) if total_notas else 0) }}%</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>

        <!-- TOP DESTINATÁRIOS -->
        {% if top_dest %}
        <h2>Principais Destinatários</h2>
        <table>
            <thead>
                <tr>
                    <th>Empresa</th>
                    <th class="num">Notas</th>
                    <th class="num">Cabeças</th>
                    <th class="num">Valor (R$)</th>
                </tr>
            </thead>
            <tbody>
                {% for dest in top_dest %}
                <tr>
                    <td>{{ dest.nome[:50] }}</td>
                    <td class="num">{{ dest.notas }}</td>
                    <td class="num">{{ "{:,.0f}".format(dest.cabecas) }}</td>
                    <td class="num">R$ {{ "{:,.0f}".format(dest.valor) }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% endif %}

        <!-- FOOTER -->
        <div class="footer">
            <p><strong>ORGATEC Sovereign Audit Platform</strong></p>
            <p>Documento confidencial — Lei 8.023/90 (IRPF Atividade Rural)</p>
        </div>
    </div>
</body>
</html>
"""
