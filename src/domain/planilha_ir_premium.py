"""
Gerador de planilha IRPF com design premium (Fiscal Clarity).
"""
from typing import List, Dict, Any
from src.domain.extractor import NFA


def gerar_html_planilha_premium(dados: Dict[str, Any]) -> str:
    """Gera HTML com design moderno e profissional."""

    nome_contribuinte = dados.get('nome_contribuinte', 'Contribuinte')
    por_mes = dados.get('por_mes', {})
    por_natureza = dados.get('por_natureza', {})
    top_dest = dados.get('top_dest', [])

    # Calcular KPIs
    total_notas = sum(m.get('notas', 0) for m in por_mes.values())
    total_cabecas = sum(m.get('cabecas', 0) for m in por_mes.values())
    total_valor = sum(m.get('valor', 0) for m in por_mes.values())

    meses_processados = len(por_mes)

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Planilha IRPF - Lei 8.023/90</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #f8fafb;
            color: #1a202c;
            line-height: 1.6;
        }}

        .container {{
            display: grid;
            grid-template-columns: 280px 1fr;
            min-height: 100vh;
        }}

        /* SIDEBAR */
        .sidebar {{
            background: linear-gradient(135deg, #0f3a66 0%, #1a4d7a 100%);
            color: white;
            padding: 40px 24px;
            box-shadow: 2px 0 8px rgba(0,0,0,0.1);
        }}

        .sidebar h1 {{
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            opacity: 0.7;
            margin-bottom: 24px;
            font-weight: 600;
        }}

        .metadata {{
            background: rgba(255,255,255,0.08);
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 32px;
            border-left: 3px solid #4db8ff;
        }}

        .metadata-label {{
            font-size: 11px;
            text-transform: uppercase;
            opacity: 0.6;
            letter-spacing: 0.8px;
            margin-bottom: 6px;
            font-weight: 600;
        }}

        .metadata-value {{
            font-size: 15px;
            font-weight: 500;
            margin-bottom: 16px;
        }}

        /* MAIN CONTENT */
        .main {{
            padding: 48px;
            overflow-y: auto;
        }}

        .header {{
            margin-bottom: 48px;
        }}

        .header h1 {{
            font-size: 32px;
            font-weight: 700;
            margin-bottom: 8px;
            color: #0f3a66;
        }}

        .header p {{
            font-size: 14px;
            color: #718096;
        }}

        /* KPI CARDS */
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 48px;
        }}

        .kpi-card {{
            background: white;
            padding: 24px;
            border-radius: 12px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
            border-top: 4px solid #4db8ff;
            transition: transform 0.2s, box-shadow 0.2s;
        }}

        .kpi-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.12);
        }}

        .kpi-label {{
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #718096;
            margin-bottom: 12px;
            font-weight: 600;
        }}

        .kpi-value {{
            font-size: 28px;
            font-weight: 700;
            color: #0f3a66;
            word-break: break-word;
        }}

        /* SECTION TITLES */
        h2 {{
            font-size: 18px;
            font-weight: 700;
            margin-top: 48px;
            margin-bottom: 20px;
            padding-bottom: 12px;
            border-bottom: 2px solid #e2e8f0;
            color: #0f3a66;
        }}

        /* TABLES */
        table {{
            width: 100%;
            border-collapse: collapse;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
            margin-bottom: 32px;
        }}

        th {{
            background: #f7fafc;
            padding: 16px;
            text-align: left;
            font-weight: 600;
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            color: #2d3748;
            border-bottom: 2px solid #e2e8f0;
        }}

        td {{
            padding: 16px;
            border-bottom: 1px solid #edf2f7;
            font-size: 14px;
        }}

        tr:last-child td {{
            border-bottom: none;
        }}

        tbody tr:nth-child(odd) {{
            background: #f9fafb;
        }}

        tbody tr:hover {{
            background: #edf2f7;
        }}

        /* OPERAÇÃO COLORS */
        .badge {{
            display: inline-block;
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
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

        .num {{
            text-align: right;
            font-variant-numeric: tabular-nums;
            font-family: 'Inter', monospace;
        }}

        /* FOOTER */
        .footer {{
            margin-top: 48px;
            padding-top: 24px;
            border-top: 1px solid #e2e8f0;
            font-size: 12px;
            color: #718096;
            text-align: center;
        }}

        /* RESPONSIVO */
        @media (max-width: 768px) {{
            .container {{
                grid-template-columns: 1fr;
            }}

            .sidebar {{
                padding: 24px;
            }}

            .main {{
                padding: 24px;
            }}

            .header h1 {{
                font-size: 24px;
            }}

            .kpi-grid {{
                grid-template-columns: 1fr;
            }}

            table {{
                font-size: 12px;
            }}

            th, td {{
                padding: 12px;
            }}
        }}

        @media print {{
            body {{
                background: white;
            }}

            .container {{
                display: block;
            }}

            .sidebar {{
                display: none;
            }}

            .main {{
                padding: 0;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- SIDEBAR -->
        <div class="sidebar">
            <h1>Auditoria Fiscal</h1>

            <div class="metadata">
                <div class="metadata-label">Contribuinte</div>
                <div class="metadata-value">{nome_contribuinte}</div>

                <div class="metadata-label">Período</div>
                <div class="metadata-value">{meses_processados} mês(es)</div>

                <div class="metadata-label">Total de Notas</div>
                <div class="metadata-value">{total_notas:,}</div>
            </div>

            <div style="text-align: center; font-size: 11px; opacity: 0.5; margin-top: 48px;">
                Lei 8.023/90<br>
                Atividade Rural<br>
                IRPF
            </div>
        </div>

        <!-- MAIN -->
        <div class="main">
            <div class="header">
                <h1>Planilha IRPF</h1>
                <p>Análise consolidada de notas fiscais — Lei 8.023/90</p>
            </div>

            <!-- KPIs -->
            <div class="kpi-grid">
                <div class="kpi-card">
                    <div class="kpi-label">Total Cabeças</div>
                    <div class="kpi-value">{total_cabecas:,.0f}</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-label">Valor Total</div>
                    <div class="kpi-value">R$ {total_valor:,.0f}</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-label">Ticket Médio</div>
                    <div class="kpi-value">R$ {(total_valor/total_cabecas if total_cabecas > 0 else 0):,.0f}</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-label">Tipos de Op.</div>
                    <div class="kpi-value">{len(por_natureza)}</div>
                </div>
            </div>

            <!-- TABELA MENSAL -->
            <h2>Resumo por Mês</h2>
            <table>
                <thead>
                    <tr>
                        <th>Mês</th>
                        <th class="num">Notas</th>
                        <th class="num">Cabeças</th>
                        <th class="num">Valor (R$)</th>
                        <th class="num">Venda %</th>
                        <th class="num">Remessa %</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(f'''
                    <tr>
                        <td>{mes}</td>
                        <td class="num">{dados.get("notas", 0)}</td>
                        <td class="num">{dados.get("cabecas", 0):,.0f}</td>
                        <td class="num">R$ {dados.get("valor", 0):,.0f}</td>
                        <td class="num">{(dados.get("vendas_notas", 0)/dados.get("notas", 1)*100 if dados.get("notas") else 0):.0f}%</td>
                        <td class="num">{(dados.get("rem_notas", 0)/dados.get("notas", 1)*100 if dados.get("notas") else 0):.0f}%</td>
                    </tr>
                    ''' for mes, dados in por_mes.items())}
                </tbody>
            </table>

            <!-- TABELA POR NATUREZA -->
            <h2>Operações por Tipo</h2>
            <table>
                <thead>
                    <tr>
                        <th>Tipo</th>
                        <th class="num">Quantidade</th>
                        <th class="num">Percentual</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(f'''
                    <tr>
                        <td><span class="badge badge-{natureza.lower()}">{natureza}</span></td>
                        <td class="num">{qtd}</td>
                        <td class="num">{(qtd/total_notas*100 if total_notas else 0):.1f}%</td>
                    </tr>
                    ''' for natureza, qtd in por_natureza.items())}
                </tbody>
            </table>

            <!-- TOP DESTINATÁRIOS -->
            {f'''
            <h2>Principais Destinatários</h2>
            <table>
                <thead>
                    <tr>
                        <th>Destinatário</th>
                        <th class="num">Notas</th>
                        <th class="num">Cabeças</th>
                        <th class="num">Valor (R$)</th>
                    </tr>
                </thead>
                <tbody>
                    {' '.join(f'''
                    <tr>
                        <td>{dest.get("nome", "N/A")[:40]}</td>
                        <td class="num">{dest.get("notas", 0)}</td>
                        <td class="num">{dest.get("cabecas", 0):,.0f}</td>
                        <td class="num">R$ {dest.get("valor", 0):,.0f}</td>
                    </tr>
                    ''' for dest in top_dest[:10])}
                </tbody>
            </table>
            ''' if top_dest else ''}

            <div class="footer">
                <p>Documento gerado automaticamente pelo sistema ORGATEC</p>
                <p style="margin-top: 8px; opacity: 0.6;">Confidencial — Lei 8.023/90</p>
            </div>
        </div>
    </div>
</body>
</html>"""
