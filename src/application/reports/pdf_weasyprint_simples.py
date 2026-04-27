"""
Gerador de PDF Simplificado com WeasyPrint (Fiscal Clarity — Minimalista).
Foco em KPIs essenciais apenas.
"""
import logging
from datetime import datetime
from typing import List, Dict, Any

from src.domain.extractor import NFA, resumo_geral

logger = logging.getLogger(__name__)


def gerar_pdf_simples(
    notas: List[NFA],
    saida: str,
    nome_contribuinte: str = "",
    cpf_contribuinte: str = "",
    risco_nivel: str = "BAIXO",
    score_risco: float = 0.0,
    **kwargs
) -> None:
    """
    Gera PDF minimalista com apenas informações essenciais.

    Args:
        notas: Lista de notas fiscais extraídas
        saida: Caminho do arquivo PDF de saída
        nome_contribuinte: Nome do contribuinte
        cpf_contribuinte: CPF/CNPJ do contribuinte
        risco_nivel: BAIXO, MÉDIO, ALTO, CRÍTICO
        score_risco: Score de risco (0-1)
    """
    try:
        from weasyprint import HTML
    except ImportError:
        logger.error("WeasyPrint não instalado")
        raise

    # Calcular resumo
    resumo = resumo_geral(notas, nome_contribuinte)

    # Preparar dados
    dados = {
        "titulo": "Planilha IRPF",
        "data_emissao": datetime.now().strftime("%d/%m/%Y"),
        "contribuinte": nome_contribuinte or "Não identificado",
        "cpf_cnpj": cpf_contribuinte or "N/A",
        "risco_nivel": risco_nivel,
        "risco_nivel_lower": risco_nivel.lower(),
        "score_risco": f"{score_risco:.0%}",
        "total_notas": resumo.get("total_notas", 0),
        "total_valor": resumo.get("total_valor", 0),
        "total_cabecas": resumo.get("total_cabecas", 0),
        "ticket_medio": resumo.get("ticket_medio", 0),
        "por_natureza": resumo.get("por_natureza", {}),
    }

    # Renderizar e gerar
    html_content = _template_minimalista(dados)
    try:
        HTML(string=html_content).write_pdf(saida)
        logger.info(f"[PDF SIMPLES] Gerado: {saida}")
    except Exception as e:
        logger.error(f"Erro ao gerar PDF: {e}")
        raise


def _template_minimalista(dados: Dict[str, Any]) -> str:
    """Template HTML minimalista."""
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>{dados['titulo']}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            color: #1a202c;
            line-height: 1.6;
        }}

        @page {{
            size: A4;
            margin: 30mm 20mm;
            @bottom-center {{
                content: "Página " counter(page);
                font-size: 9px;
                color: #a0aec0;
            }}
        }}

        .container {{
            max-width: 100%;
        }}

        /* HEADER MINIMALISTA */
        .header {{
            margin-bottom: 40px;
            padding-bottom: 20px;
            border-bottom: 2px solid #0f3a66;
        }}

        .header h1 {{
            font-size: 28px;
            font-weight: 700;
            color: #0f3a66;
            margin-bottom: 3px;
        }}

        .header-meta {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-top: 15px;
            font-size: 12px;
        }}

        .header-meta-item {{
            display: flex;
            justify-content: space-between;
        }}

        .header-meta-label {{
            color: #718096;
            font-weight: 600;
            text-transform: uppercase;
            font-size: 10px;
            letter-spacing: 0.5px;
        }}

        .header-meta-value {{
            color: #2d3748;
            font-weight: 500;
        }}

        /* RISCO */
        .risco {{
            display: inline-block;
            padding: 8px 16px;
            border-radius: 4px;
            font-weight: 600;
            font-size: 11px;
            text-transform: uppercase;
            margin: 20px 0;
            letter-spacing: 0.5px;
        }}

        .risco-baixo {{
            background: #d4f4dd;
            color: #22543d;
        }}

        .risco-medio {{
            background: #fed7aa;
            color: #78350f;
        }}

        .risco-alto {{
            background: #fee2e2;
            color: #991b1b;
        }}

        .risco-critico {{
            background: #fecaca;
            color: #7f1d1d;
        }}

        /* KPI GRID */
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin: 30px 0;
        }}

        .kpi {{
            padding: 20px;
            background: #f7fafc;
            border-left: 4px solid #0f3a66;
            border-radius: 4px;
        }}

        .kpi-label {{
            font-size: 10px;
            color: #718096;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            font-weight: 600;
            margin-bottom: 8px;
        }}

        .kpi-value {{
            font-size: 20px;
            font-weight: 700;
            color: #0f3a66;
            word-break: break-word;
        }}

        /* OPERAÇÕES */
        .operacoes {{
            margin-top: 30px;
        }}

        .operacoes h2 {{
            font-size: 14px;
            font-weight: 700;
            color: #0f3a66;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid #cbd5e0;
        }}

        .operacoes-list {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
        }}

        .op-item {{
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #e2e8f0;
            font-size: 12px;
        }}

        .op-nome {{
            font-weight: 600;
            color: #2d3748;
        }}

        .op-qtd {{
            color: #718096;
            font-family: 'Courier New', monospace;
        }}

        /* BADGE */
        .badge {{
            display: inline-block;
            padding: 2px 6px;
            border-radius: 2px;
            font-size: 9px;
            font-weight: 600;
            text-transform: uppercase;
            margin-right: 4px;
            letter-spacing: 0.3px;
        }}

        .badge-venda {{
            background: #d4f4dd;
            color: #22543d;
        }}

        .badge-remessa {{
            background: #fed7aa;
            color: #78350f;
        }}

        .badge-transferencia {{
            background: #a7f3d0;
            color: #064e3b;
        }}

        .badge-outras {{
            background: #ddd6fe;
            color: #3f0f5c;
        }}

        /* FOOTER */
        .footer {{
            margin-top: 50px;
            padding-top: 20px;
            border-top: 1px solid #cbd5e0;
            font-size: 10px;
            color: #718096;
            text-align: center;
        }}

        @media print {{
            body {{ background: white; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- HEADER -->
        <div class="header">
            <h1>{dados['titulo']}</h1>
            <div class="header-meta">
                <div class="header-meta-item">
                    <span class="header-meta-label">Contribuinte</span>
                    <span class="header-meta-value">{dados['contribuinte']}</span>
                </div>
                <div class="header-meta-item">
                    <span class="header-meta-label">CPF/CNPJ</span>
                    <span class="header-meta-value">{dados['cpf_cnpj']}</span>
                </div>
                <div class="header-meta-item">
                    <span class="header-meta-label">Data</span>
                    <span class="header-meta-value">{dados['data_emissao']}</span>
                </div>
                <div class="header-meta-item">
                    <span class="header-meta-label">Lei</span>
                    <span class="header-meta-value">8.023/90</span>
                </div>
            </div>
        </div>

        <!-- RISCO -->
        <div class="risco risco-{dados['risco_nivel_lower']}">
            Nível de Risco: {dados['risco_nivel']} ({dados['score_risco']})
        </div>

        <!-- KPIs -->
        <div class="kpi-grid">
            <div class="kpi">
                <div class="kpi-label">Total de Notas</div>
                <div class="kpi-value">{dados['total_notas']:,}</div>
            </div>
            <div class="kpi">
                <div class="kpi-label">Cabeças</div>
                <div class="kpi-value">{dados['total_cabecas']:,.0f}</div>
            </div>
            <div class="kpi">
                <div class="kpi-label">Valor Total</div>
                <div class="kpi-value">R$ {dados['total_valor']:,.0f}</div>
            </div>
            <div class="kpi">
                <div class="kpi-label">Ticket Médio</div>
                <div class="kpi-value">R$ {dados['ticket_medio']:,.0f}</div>
            </div>
        </div>

        <!-- OPERAÇÕES -->
        <div class="operacoes">
            <h2>Resumo por Operação</h2>
            <div class="operacoes-list">
                {_gerar_operacoes(dados['por_natureza'], dados['total_notas'])}
            </div>
        </div>

        <!-- FOOTER -->
        <div class="footer">
            <p><strong>ORGATEC Sovereign Audit</strong> — Confidencial</p>
        </div>
    </div>
</body>
</html>"""


def _gerar_operacoes(por_natureza: Dict[str, int], total: int) -> str:
    """Gera linhas de operações."""
    html = ""
    for natureza, qtd in por_natureza.items():
        pct = (qtd / total * 100) if total else 0
        badge_class = f"badge-{natureza.lower()}"
        html += f"""
        <div class="op-item">
            <span>
                <span class="badge {badge_class}">{natureza}</span>
                <span class="op-qtd">{qtd}</span>
            </span>
            <span class="op-qtd">{pct:.0f}%</span>
        </div>
        """
    return html
