"""Geração de relatório PDF profissional com ReportLab."""

import re
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable, KeepTogether,
    PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from src.domain.constants import hex_cor
from src.domain.extractor import NFA, resumo_geral

LOGO_PATH = str(Path(__file__).parent / 'assets' / 'logo.png')

# ── Paleta de cores ────────────────────────────────────────────────────────────
AZUL_ESC   = colors.HexColor(hex_cor('BG2'))
AZUL_MED   = colors.HexColor(hex_cor('PRIMARY'))
AZUL_CLAR  = colors.HexColor(hex_cor('BG4'))
VERDE      = colors.HexColor(hex_cor('GREEN'))
VERDE_CLAR = colors.HexColor('#D5F5E3')
LARANJA    = colors.HexColor(hex_cor('ORANGE'))
VERMELHO   = colors.HexColor(hex_cor('RED'))
VERM_CLAR  = colors.HexColor('#FDECEA')
LARANJ_CLAR= colors.HexColor('#FEF3C7')
CYAN       = colors.HexColor(hex_cor('CYAN'))
CINZA      = colors.HexColor(hex_cor('GRAY'))
CINZA_CLAR = colors.HexColor('#F1F5F9')
BRANCO     = colors.white
TEXTO      = colors.black

W, H = A4

_RISCO_BG = {
    'ALTO':    VERM_CLAR,
    'CRÍTICO': colors.HexColor('#FCE4E4'),
    'MÉDIO':   LARANJ_CLAR,
    'BAIXO':   VERDE_CLAR,
}
_RISCO_FG = {
    'ALTO':    VERMELHO,
    'CRÍTICO': colors.HexColor('#B91C1C'),
    'MÉDIO':   LARANJA,
    'BAIXO':   VERDE,
}


# ── Cabeçalho/Rodapé ──────────────────────────────────────────────────────────

def _header_footer(canvas, doc):
    import os
    canvas.saveState()
    canvas.setFillColor(AZUL_ESC)
    canvas.rect(0, H - 1.8*cm, W, 1.8*cm, fill=1, stroke=0)
    logo_sz = 1.35*cm
    if os.path.exists(LOGO_PATH):
        canvas.drawImage(LOGO_PATH, 0.3*cm, H - 1.65*cm,
                         width=logo_sz, height=logo_sz,
                         preserveAspectRatio=True, mask='auto')
    canvas.setFillColor(BRANCO)
    canvas.setFont('Helvetica-Bold', 11)
    canvas.drawString(1.9*cm, H - 1.1*cm, 'OrgAudi — SEFAZ')
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(colors.HexColor('#A9CCE3'))
    canvas.drawString(1.9*cm, H - 1.55*cm, 'OrgAudi · Análise de Notas Fiscais Avulsas')
    canvas.setFillColor(BRANCO)
    canvas.drawRightString(W - 1.5*cm, H - 1.1*cm,
        f'Gerado em {datetime.now().strftime("%d/%m/%Y %H:%M")}')
    # Rodapé
    canvas.setFillColor(AZUL_ESC)
    canvas.rect(0, 0, W, 0.9*cm, fill=1, stroke=0)
    canvas.setFillColor(BRANCO)
    canvas.setFont('Helvetica', 8)
    canvas.drawString(1.5*cm, 0.3*cm, 'OrgAudi')
    canvas.drawCentredString(W/2, 0.3*cm, f'Página {doc.page}')
    canvas.setFillColor(colors.HexColor('#A9CCE3'))
    canvas.drawRightString(W - 1.5*cm, 0.3*cm, 'OrgAudi — Sistema de Auditoria Agronegócio')
    canvas.restoreState()


# ── Utilitários de estilo ──────────────────────────────────────────────────────

def _estilos():
    base = getSampleStyleSheet()
    return {
        'tit':    ParagraphStyle('Tit',    parent=base['Heading1'],
                                 alignment=TA_CENTER, fontSize=16,
                                 textColor=AZUL_ESC, spaceAfter=16),
        'sec':    ParagraphStyle('Sec',    parent=base['Heading2'],
                                 fontSize=11, textColor=AZUL_MED,
                                 spaceBefore=14, spaceAfter=8),
        'txt':    ParagraphStyle('Txt',    parent=base['Normal'],
                                 fontSize=9, leading=13),
        'bullet': ParagraphStyle('Bul',    parent=base['Normal'],
                                 fontSize=9, leading=13, leftIndent=12),
        'small':  ParagraphStyle('Small',  parent=base['Normal'],
                                 fontSize=8, leading=10),
        'center': ParagraphStyle('Ctr',    parent=base['Normal'],
                                 fontSize=9, alignment=TA_CENTER),
        'th':     ParagraphStyle('TH',     fontName='Helvetica-Bold',
                                 fontSize=8, textColor=BRANCO,
                                 alignment=TA_CENTER),
        'td':     ParagraphStyle('TD',     fontName='Helvetica',
                                 fontSize=8, leading=10),
    }


def _estilo_tabela_base(t: Table, n_rows: int, total_row: bool = False):
    style = [
        ('BACKGROUND',    (0, 0), (-1, 0), AZUL_MED),
        ('TEXTCOLOR',     (0, 0), (-1, 0), BRANCO),
        ('FONTNAME',      (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',      (0, 0), (-1, -1), 8),
        ('ROWBACKGROUNDS',(0, 1), (-1, -1), [BRANCO, CINZA_CLAR]),
        ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING',   (0, 0), (-1, -1), 5),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 5),
        ('LINEBELOW',     (0, 0), (-1, -1), 0.4, colors.HexColor('#CBD5E1')),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
    ]
    if total_row and n_rows > 1:
        style += [
            ('BACKGROUND', (0, n_rows - 1), (-1, n_rows - 1), AZUL_ESC),
            ('TEXTCOLOR',  (0, n_rows - 1), (-1, n_rows - 1), BRANCO),
            ('FONTNAME',   (0, n_rows - 1), (-1, n_rows - 1), 'Helvetica-Bold'),
        ]
    t.setStyle(TableStyle(style))


# ── Cards KPI ─────────────────────────────────────────────────────────────────

def _card(label: str, value: str, bg: colors.Color,
          fg_value: colors.Color = None) -> Table:
    fg = fg_value or AZUL_ESC
    base = getSampleStyleSheet()
    t = Table([
        [Paragraph(f'<font size=7 color="#64748B">{label}</font>',
                   ParagraphStyle('CL', parent=base['Normal'], alignment=TA_CENTER))],
        [Paragraph(f'<b><font size=12 color="{fg.hexval()}">{value}</font></b>',
                   ParagraphStyle('CV', parent=base['Normal'], alignment=TA_CENTER))],
    ], colWidths=['100%'])
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), bg),
        ('TOPPADDING',    (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LEFTPADDING',   (0, 0), (-1, -1), 5),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 5),
        ('ROUNDEDCORNERS',(0, 0), (-1, -1), [5, 5, 5, 5]),
    ]))
    return t


def _row_cards(cards: list, usable_w: float) -> Table:
    n = len(cards)
    w = (usable_w - 0.3*cm * (n - 1)) / n
    t = Table([cards], colWidths=[w]*n, hAlign='LEFT')
    t.setStyle(TableStyle([
        ('ALIGN',   (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN',  (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING',  (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
    ]))
    return t


# ── Markdown → ReportLab ──────────────────────────────────────────────────────

def _inline(text: str) -> str:
    """Escapa HTML e converte **bold** e *italic*."""
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
    return text


def _render_markdown(texto: str, st: dict) -> list:
    """Converte texto Markdown simples em lista de Flowables."""
    elements = []
    texto = re.sub(r'^\s*#{1,6}\s*', '', texto, flags=re.MULTILINE)
    buffer: list[str] = []

    def _flush():
        if buffer:
            para = ' '.join(buffer).strip()
            if para:
                elements.append(Paragraph(_inline(para), st['txt']))
                elements.append(Spacer(1, 0.2*cm))
            buffer.clear()

    for linha in texto.split('\n'):
        linha = linha.rstrip()
        is_bullet   = bool(re.match(r'^\s*[-*•]\s+', linha))
        is_numbered = bool(re.match(r'^\s*\d+\.\s', linha))

        if (is_bullet or is_numbered) and buffer:
            _flush()

        if is_bullet:
            content = re.sub(r'^\s*[-*•]\s+', '', linha)
            elements.append(Paragraph(f'• &nbsp; {_inline(content)}', st['bullet']))
        elif is_numbered:
            elements.append(Paragraph(_inline(linha.strip()), st['txt']))
        elif linha.strip():
            buffer.append(linha.strip())
        else:
            _flush()

    _flush()
    return elements


# ── Tabelas de dados ───────────────────────────────────────────────────────────

def _tabela_natureza(res: dict, st: dict, usable_w: float) -> Table:
    total_val = res['total_valor'] or 1
    total_cab = res['total_cabecas'] or 1
    total_not = res['total_notas'] or 1

    rows = [[
        Paragraph('<b>Natureza</b>', st['th']),
        Paragraph('<b>Notas</b>',   st['th']),
        Paragraph('<b>Cabeças</b>', st['th']),
        Paragraph('<b>Valor (R$)</b>', st['th']),
        Paragraph('<b>% Valor</b>', st['th']),
    ]]
    por_nat = res.get('por_natureza', {})
    for nat, qtd in sorted(por_nat.items(), key=lambda x: -x[1]):
        cab = sum(n.quantidade_total for n in [])  # calculado abaixo via por_categoria
        val_nat = 0.0
        cab_nat = 0.0
        if nat in res.get('por_categoria', {}):
            val_nat = res['por_categoria'][nat].get('valor', 0)
            cab_nat = res['por_categoria'][nat].get('cabecas', 0)
        rows.append([
            Paragraph(nat, st['td']),
            Paragraph(str(qtd), st['td']),
            Paragraph(f'{cab_nat:,.0f}', st['td']),
            Paragraph(f'{val_nat:,.2f}', st['td']),
            Paragraph(f'{val_nat/total_val*100:.1f}%', st['td']),
        ])

    w = usable_w
    cols = [w*0.28, w*0.14, w*0.16, w*0.26, w*0.16]
    t = Table(rows, colWidths=cols)
    _estilo_tabela_base(t, len(rows))
    return t


def _tabela_top_dest(res: dict, st: dict, usable_w: float) -> Table:
    top = res.get('top_dest', [])[:6]
    total_val = res['total_valor'] or 1
    rows = [[
        Paragraph('<b>#</b>',           st['th']),
        Paragraph('<b>Destinatário</b>',st['th']),
        Paragraph('<b>Notas</b>',       st['th']),
        Paragraph('<b>Cabeças</b>',     st['th']),
        Paragraph('<b>Valor (R$)</b>',  st['th']),
        Paragraph('<b>Market Share</b>',st['th']),
    ]]
    for i, d in enumerate(top, 1):
        share = d['valor'] / total_val * 100
        rows.append([
            Paragraph(str(i), st['td']),
            Paragraph(d['nome'][:30], st['td']),
            Paragraph(str(d['notas']), st['td']),
            Paragraph(f"{d['cabecas']:,.0f}", st['td']),
            Paragraph(f"{d['valor']:,.2f}", st['td']),
            Paragraph(f'{share:.1f}%', st['td']),
        ])

    w = usable_w
    cols = [w*0.06, w*0.30, w*0.09, w*0.13, w*0.24, w*0.18]
    t = Table(rows, colWidths=cols)
    _estilo_tabela_base(t, len(rows))
    return t


def _tabela_mensal(res: dict, st: dict, usable_w: float) -> Table:
    meses = res.get('por_mes', {})
    if not meses:
        return None
    rows = [[
        Paragraph('<b>Mês/Ano</b>',        st['th']),
        Paragraph('<b>Notas</b>',           st['th']),
        Paragraph('<b>Cabeças</b>',         st['th']),
        Paragraph('<b>Valor Total (R$)</b>',st['th']),
        Paragraph('<b>Vendas (R$)</b>',     st['th']),
        Paragraph('<b>Remessas (R$)</b>',   st['th']),
    ]]
    for mes, v in sorted(meses.items()):
        rows.append([
            Paragraph(mes, st['td']),
            Paragraph(str(v['notas']), st['td']),
            Paragraph(f"{v['cabecas']:,.0f}", st['td']),
            Paragraph(f"{v['valor']:,.2f}", st['td']),
            Paragraph(f"{v.get('vendas_valor', 0):,.2f}", st['td']),
            Paragraph(f"{v.get('rem_valor', 0):,.2f}", st['td']),
        ])
    # Linha de totais
    rows.append([
        Paragraph('<b>TOTAL</b>', st['th']),
        Paragraph(f"<b>{res['total_notas']}</b>", st['th']),
        Paragraph(f"<b>{res['total_cabecas']:,.0f}</b>", st['th']),
        Paragraph(f"<b>{res['total_valor']:,.2f}</b>", st['th']),
        Paragraph(f"<b>{res.get('vendas_valor', 0):,.2f}</b>", st['th']),
        Paragraph('—', st['th']),
    ])

    w = usable_w
    cols = [w*0.13, w*0.09, w*0.13, w*0.22, w*0.22, w*0.21]
    t = Table(rows, colWidths=cols)
    _estilo_tabela_base(t, len(rows), total_row=True)
    return t


def _tabela_anomalias(anomalias: list, st: dict, usable_w: float) -> Table:
    header = [[
        Paragraph('<b>NFA</b>',               st['th']),
        Paragraph('<b>Data</b>',              st['th']),
        Paragraph('<b>Natureza</b>',          st['th']),
        Paragraph('<b>Valor (R$)</b>',        st['th']),
        Paragraph('<b>Nível</b>',             st['th']),
        Paragraph('<b>Risco Detectado</b>',   st['th']),
    ]]
    data_rows = []
    for a in anomalias:
        nivel = str(a.get('Nivel', a.get('nivel', 'MÉDIO'))).upper()
        data_rows.append([
            Paragraph(str(a.get('NFA', '')), st['td']),
            Paragraph(str(a.get('Data', '')), st['td']),
            Paragraph(str(a.get('Natureza', '')), st['td']),
            Paragraph(f"{a.get('Valor', 0):,.2f}", st['td']),
            Paragraph(f'<b>{nivel}</b>', st['td']),
            Paragraph(str(a.get('Motivo', '')), st['td']),
        ])

    w = usable_w
    cols = [w*0.10, w*0.10, w*0.13, w*0.14, w*0.10, w*0.43]
    t = Table(header + data_rows, colWidths=cols)

    style_cmds = [
        ('BACKGROUND',    (0, 0), (-1, 0), AZUL_ESC),
        ('TEXTCOLOR',     (0, 0), (-1, 0), BRANCO),
        ('FONTNAME',      (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',      (0, 0), (-1, -1), 8),
        ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING',   (0, 0), (-1, -1), 5),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 5),
        ('LINEBELOW',     (0, 0), (-1, -1), 0.4, colors.HexColor('#CBD5E1')),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
    ]
    for i, a in enumerate(anomalias, 1):
        nivel = str(a.get('Nivel', a.get('nivel', 'MÉDIO'))).upper()
        bg = _RISCO_BG.get(nivel, CINZA_CLAR)
        style_cmds.append(('BACKGROUND', (0, i), (-1, i), bg))

    t.setStyle(TableStyle(style_cmds))
    return t


def _tabela_vendas_remessas(res: dict, st: dict, usable_w: float) -> Table:
    """Tabela comparativa de vendas vs remessas por categoria."""
    cat = res.get('por_categoria', {})
    total_val = res['total_valor'] or 1
    total_cab = res['total_cabecas'] or 1

    rows = [[
        Paragraph('<b>Categoria</b>',      st['th']),
        Paragraph('<b>Notas</b>',          st['th']),
        Paragraph('<b>Cabeças</b>',        st['th']),
        Paragraph('<b>Valor (R$)</b>',     st['th']),
        Paragraph('<b>% Valor</b>',        st['th']),
        Paragraph('<b>Ticket Med.</b>',    st['th']),
    ]]
    total_row_data = [0, 0.0, 0.0]
    for categoria in ['VENDA', 'REMESSA', 'TRANSFERÊNCIA']:
        if categoria in cat:
            d = cat[categoria]
            notas = d.get('notas', 0)
            cab = d.get('cabecas', 0)
            val = d.get('valor', 0)
            pct = val / total_val * 100 if total_val > 0 else 0
            ticket = val / cab if cab > 0 else 0
            total_row_data[0] += notas
            total_row_data[1] += cab
            total_row_data[2] += val
            rows.append([
                Paragraph(categoria, st['td']),
                Paragraph(str(notas), st['td']),
                Paragraph(f'{cab:,.0f}', st['td']),
                Paragraph(f'{val:,.2f}', st['td']),
                Paragraph(f'{pct:.1f}%', st['td']),
                Paragraph(f'{ticket:,.2f}', st['td']),
            ])

    w = usable_w
    cols = [w*0.20, w*0.12, w*0.15, w*0.24, w*0.14, w*0.15]
    t = Table(rows, colWidths=cols)
    _estilo_tabela_base(t, len(rows))
    return t


def _tabela_resumo_analise(res: dict, st: dict, usable_w: float) -> Table:
    """Resumo analítico com métricas-chave do lote."""
    rows = [[
        Paragraph('<b>Métrica</b>',        st['th']),
        Paragraph('<b>Valor</b>',          st['th']),
        Paragraph('<b>Observação</b>',     st['th']),
    ]]

    total_cab = res['total_cabecas'] or 1
    ticket_med = res['total_valor'] / total_cab

    # Análise por natureza
    por_nat = res.get('por_natureza', {})
    vendas_pct = 0
    if por_nat.get('VENDA', 0) > 0:
        vendas_pct = por_nat['VENDA'] / res['total_notas'] * 100

    rows.append([
        Paragraph('Total de Notas', st['td']),
        Paragraph(f"{res['total_notas']}", st['td']),
        Paragraph('Documentos processados', st['td']),
    ])
    rows.append([
        Paragraph('Volume Total', st['td']),
        Paragraph(f"{res['total_cabecas']:,.0f} cabeças", st['td']),
        Paragraph('Animais movimentados', st['td']),
    ])
    rows.append([
        Paragraph('Faturamento Total', st['td']),
        Paragraph(f"R$ {res['total_valor']:,.2f}", st['td']),
        Paragraph('Montante financeiro', st['td']),
    ])
    rows.append([
        Paragraph('Ticket Médio', st['td']),
        Paragraph(f"R$ {ticket_med:,.2f} / cabeça", st['td']),
        Paragraph('Valor médio por animal', st['td']),
    ])
    rows.append([
        Paragraph('% de Vendas', st['td']),
        Paragraph(f"{vendas_pct:.1f}%", st['td']),
        Paragraph('Proporção de vendas no lote', st['td']),
    ])

    w = usable_w
    cols = [w*0.22, w*0.28, w*0.50]
    t = Table(rows, colWidths=cols)
    _estilo_tabela_base(t, len(rows))
    return t


# ── Função principal ───────────────────────────────────────────────────────────

def gerar_pdf(
    notas: list[NFA],
    saida: str,
    analise_ia: str = '',
    nome_contribuinte: str = '',
    cpf_contribuinte: str = '',
    anomalias: list = None,
    risco_nivel: str = '',
    score_risco: float = 0.0,
) -> None:
    """Gera Laudo Técnico de Auditoria Forense profissional."""
    usable_w = W - 4*cm  # margens 2cm cada lado

    doc = SimpleDocTemplate(
        saida, pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2.5*cm, bottomMargin=2*cm,
    )
    st = _estilos()
    res = resumo_geral(notas, nome_contribuinte=nome_contribuinte)
    elements = []

    # ── Título ────────────────────────────────────────────────────────────────
    elements.append(Paragraph(
        "LAUDO TÉCNICO DE AUDITORIA FISCAL E COMPLIANCE", st['tit']))

    # ── Ficha de identificação ────────────────────────────────────────────────
    periodo = "N/A"
    if notas:
        try:
            periodo = f"{min(n.emissao for n in notas)} a {max(n.emissao for n in notas)}"
        except Exception:
            pass

    info_data = [
        ["CLIENTE AUDITADO:", nome_contribuinte.upper() or "—"],
        ["CPF/CNPJ:",         cpf_contribuinte or "—"],
        ["PERÍODO:",          periodo],
        ["EMISSÃO DO LAUDO:", datetime.now().strftime("%d/%m/%Y %H:%M")],
    ]
    t_info = Table(info_data, colWidths=[4*cm, usable_w - 4*cm])
    t_info.setStyle(TableStyle([
        ('FONTNAME',    (0, 0), (-1, -1), 'Helvetica'),
        ('FONTNAME',    (0, 0), (0, -1),  'Helvetica-Bold'),
        ('FONTSIZE',    (0, 0), (-1, -1), 9),
        ('GRID',        (0, 0), (-1, -1), 0.4, colors.HexColor('#CBD5E1')),
        ('BACKGROUND',  (0, 0), (0, -1),  colors.HexColor('#EFF6FF')),
        ('PADDING',     (0, 0), (-1, -1), 5),
        ('VALIGN',      (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(t_info)
    elements.append(Spacer(1, 0.4*cm))

    # ── Cards KPI — linha 1: Notas / Cabeças / Valor ──────────────────────────
    row1 = [
        _card('TOTAL DE NOTAS',   str(res['total_notas']),
              colors.HexColor('#EFF6FF')),
        _card('CABEÇAS',          f"{res['total_cabecas']:,.0f}",
              VERDE_CLAR),
        _card('VALOR TOTAL',      f"R$ {res['total_valor']:,.2f}",
              CINZA_CLAR),
    ]
    elements.append(_row_cards(row1, usable_w))
    elements.append(Spacer(1, 0.25*cm))

    # ── Cards KPI — linha 2: Ticket Médio / Nível de Risco ────────────────────
    nivel_up = (risco_nivel or 'N/A').upper()
    risco_bg = _RISCO_BG.get(nivel_up, CINZA_CLAR)
    risco_fg = _RISCO_FG.get(nivel_up, CINZA)
    score_txt = f"{score_risco:.3f}" if score_risco else "—"

    row2 = [
        _card('TICKET MÉDIO / CABEÇA', f"R$ {res['ticket_medio']:,.2f}",
              CINZA_CLAR),
        _card('SCORE DE RISCO', score_txt, CINZA_CLAR),
        _card('NÍVEL DE RISCO', nivel_up or '—', risco_bg, fg_value=risco_fg),
    ]
    elements.append(_row_cards(row2, usable_w))
    elements.append(Spacer(1, 0.5*cm))

    # ── Seção 1: Distribuição por Natureza ────────────────────────────────────
    por_nat = res.get('por_natureza', {})
    if por_nat:
        elements.append(Paragraph("1. DISTRIBUIÇÃO POR NATUREZA DE OPERAÇÃO", st['sec']))
        elements.append(_tabela_natureza(res, st, usable_w))
        elements.append(Spacer(1, 0.4*cm))

    # ── Seção 2: Top Destinatários ────────────────────────────────────────────
    top_dest = res.get('top_dest', [])
    if top_dest:
        elements.append(Paragraph("2. PRINCIPAIS DESTINATÁRIOS", st['sec']))
        elements.append(_tabela_top_dest(res, st, usable_w))
        elements.append(Spacer(1, 0.4*cm))

    # ── Seção 3: Parecer Técnico (IA) ─────────────────────────────────────────
    secnum = 3
    if analise_ia:
        elements.append(Paragraph(f"{secnum}. PARECER TÉCNICO E VEREDITO DE RISCO", st['sec']))
        elements.extend(_render_markdown(analise_ia, st))
        elements.append(Spacer(1, 0.3*cm))
        secnum += 1

    # ── Seção 4: Evidências de Fraude ─────────────────────────────────────────
    if anomalias:
        elements.append(Paragraph(f"{secnum}. EVIDÊNCIAS DE FRAUDE E INCONSISTÊNCIAS", st['sec']))
        elements.append(Paragraph(
            f"Foram identificadas <b>{len(anomalias)}</b> inconsistência(s) no lote auditado.",
            st['txt']))
        elements.append(Spacer(1, 0.2*cm))
        elements.append(_tabela_anomalias(anomalias, st, usable_w))
        secnum += 1

    # ── Anexos: tabelas analíticas ────────────────────────────────────────────
    tab_mensal = _tabela_mensal(res, st, usable_w)
    tab_vnd_rem = _tabela_vendas_remessas(res, st, usable_w)
    tab_resumo = _tabela_resumo_analise(res, st, usable_w)

    if tab_mensal or tab_vnd_rem or tab_resumo:
        elements.append(PageBreak())
        elements.append(Paragraph("ANEXO I — ANÁLISE TABULAR DETALHADA", st['sec']))

        if tab_resumo:
            elements.append(Paragraph("Resumo Analítico:", st['txt']))
            elements.append(Spacer(1, 0.2*cm))
            elements.append(tab_resumo)
            elements.append(Spacer(1, 0.4*cm))

        if tab_vnd_rem:
            elements.append(Paragraph("Análise Comparativa — Vendas vs Remessas:", st['txt']))
            elements.append(Spacer(1, 0.2*cm))
            elements.append(tab_vnd_rem)
            elements.append(Spacer(1, 0.4*cm))

        if tab_mensal:
            elements.append(Paragraph("Evolução Mensal Detalhada:", st['txt']))
            elements.append(Spacer(1, 0.2*cm))
            elements.append(tab_mensal)
            elements.append(Spacer(1, 0.4*cm))

    # ── Encerramento ──────────────────────────────────────────────────────────
    elements.append(Spacer(1, 1.5*cm))
    elements.append(HRFlowable(width="100%", thickness=1, color=AZUL_ESC))
    elements.append(Spacer(1, 0.2*cm))
    elements.append(Paragraph(
        f"Documento gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')} · "
        "OrgAudi — Sistema Soberano de Auditoria Fiscal · Protocolo Sovereign",
        ParagraphStyle('End', parent=st['small'], alignment=TA_CENTER,
                       textColor=colors.grey)))

    doc.build(elements, onFirstPage=_header_footer, onLaterPages=_header_footer)


# ── Relatório de auditoria de gado (delegação) ────────────────────────────────

def gerar_pdf_auditoria(
    notas: list[NFA],
    saida: str,
    nome_contribuinte: str = "",
    analise_ia: str = "",
    risco_nivel: str = "",
    score_risco: float = 0.0,
) -> None:
    """Wrapper de auditoria pecuária — delega para gerar_pdf()."""
    cpf = getattr(notas[0].remetente, 'cpf_cnpj', '') if notas else ''
    gerar_pdf(
        notas=notas,
        saida=saida,
        analise_ia=analise_ia,
        nome_contribuinte=nome_contribuinte,
        cpf_contribuinte=cpf,
        risco_nivel=risco_nivel,
        score_risco=score_risco,
    )


# ── Legado: mantido para compatibilidade de imports ───────────────────────────

def _th(txt: str) -> Paragraph:
    return Paragraph(f'<b>{txt}</b>', ParagraphStyle(
        'TH', fontName='Helvetica-Bold', fontSize=8,
        textColor=BRANCO, alignment=TA_CENTER))


def _resumo_card(label: str, value: str, bg: colors.Color) -> Table:
    return _card(label, value, bg)


def _estilo_tabela(t: Table, n_rows: int, total_row: bool = False):
    _estilo_tabela_base(t, n_rows, total_row)
