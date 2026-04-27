"""Geração de relatório PDF profissional com ReportLab."""

import re
import logging
import time
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors

logger = logging.getLogger(__name__)
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

# ── Paleta de cores (Design Moderno) ──────────────────────────────────────────
SIDEBAR    = colors.HexColor('#2d3436')  # Cinza escuro para sidebar
PRIMARIO   = colors.HexColor('#3b82f6')  # Azul moderno
PRIMARIO_LIGHT = colors.HexColor('#dbeafe')  # Azul claro
VERDE      = colors.HexColor('#10b981')
VERDE_CLAR = colors.HexColor('#d1fae5')
LARANJA    = colors.HexColor('#f59e0b')
VERMELHO   = colors.HexColor('#ef4444')
VERM_CLAR  = colors.HexColor('#fee2e2')
LARANJ_CLAR= colors.HexColor('#fef3c7')
CINZA_ESC  = colors.HexColor('#4b5563')
CINZA_MED  = colors.HexColor('#94a3b8')
CINZA_CLAR = colors.HexColor('#f8fafc')
BORDER     = colors.HexColor('#e2e8f0')
BRANCO     = colors.white
TEXTO      = colors.HexColor('#1e293b')

# Legacy colors para compatibilidade
AZUL_ESC   = SIDEBAR
AZUL_MED   = PRIMARIO
AZUL_CLAR  = PRIMARIO_LIGHT
CINZA      = CINZA_MED

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
    # Header minimalista
    canvas.setFillColor(BRANCO)
    canvas.rect(0, H - 1.6*cm, W, 1.6*cm, fill=1, stroke=0)
    # Linha decorativa em azul
    canvas.setFillColor(PRIMARIO)
    canvas.rect(0, H - 1.6*cm, W, 0.08*cm, fill=1, stroke=0)

    logo_sz = 1.0*cm
    if os.path.exists(LOGO_PATH):
        canvas.drawImage(LOGO_PATH, 0.5*cm, H - 1.45*cm,
                         width=logo_sz, height=logo_sz,
                         preserveAspectRatio=True, mask='auto')

    canvas.setFillColor(SIDEBAR)
    canvas.setFont('Helvetica-Bold', 12)
    canvas.drawString(1.7*cm, H - 0.9*cm, 'OrgAudi')
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(CINZA_MED)
    canvas.drawString(1.7*cm, H - 1.25*cm, 'Auditoria de Notas Fiscais Agropecuárias')

    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(CINZA_MED)
    canvas.drawRightString(W - 1.5*cm, H - 0.9*cm,
        f'{datetime.now().strftime("%d/%m/%Y")}')

    # Rodapé minimalista
    canvas.setFillColor(CINZA_CLAR)
    canvas.rect(0, 0, W, 0.8*cm, fill=1, stroke=0)
    canvas.setLineWidth(0.5)
    canvas.setStrokeColor(BORDER)
    canvas.line(0, 0.8*cm, W, 0.8*cm)

    canvas.setFillColor(CINZA_MED)
    canvas.setFont('Helvetica', 7)
    canvas.drawString(1.5*cm, 0.35*cm, 'OrgAudi — Sistema Soberano')
    canvas.drawCentredString(W/2, 0.35*cm, f'Página {doc.page}')
    canvas.drawRightString(W - 1.5*cm, 0.35*cm, 'Relatório Técnico de Auditoria')
    canvas.restoreState()


# ── Utilitários de estilo ──────────────────────────────────────────────────────

def _estilos():
    base = getSampleStyleSheet()
    return {
        'tit':    ParagraphStyle('Tit',    parent=base['Heading1'],
                                 alignment=TA_LEFT, fontSize=18,
                                 textColor=SIDEBAR, spaceAfter=12,
                                 fontName='Helvetica-Bold'),
        'sec':    ParagraphStyle('Sec',    parent=base['Heading2'],
                                 fontSize=11, textColor=SIDEBAR,
                                 spaceBefore=12, spaceAfter=8,
                                 fontName='Helvetica-Bold'),
        'txt':    ParagraphStyle('Txt',    parent=base['Normal'],
                                 fontSize=9, leading=13, textColor=TEXTO),
        'bullet': ParagraphStyle('Bul',    parent=base['Normal'],
                                 fontSize=9, leading=13, leftIndent=12,
                                 textColor=TEXTO),
        'small':  ParagraphStyle('Small',  parent=base['Normal'],
                                 fontSize=8, leading=10, textColor=CINZA_MED),
        'center': ParagraphStyle('Ctr',    parent=base['Normal'],
                                 fontSize=9, alignment=TA_CENTER, textColor=TEXTO),
        'th':     ParagraphStyle('TH',     fontName='Helvetica-Bold',
                                 fontSize=8, textColor=BRANCO,
                                 alignment=TA_CENTER),
        'td':     ParagraphStyle('TD',     fontName='Helvetica',
                                 fontSize=8, leading=10, textColor=TEXTO),
    }


def _estilo_tabela_base(t: Table, n_rows: int, total_row: bool = False):
    style = [
        ('BACKGROUND',    (0, 0), (-1, 0), PRIMARIO),
        ('TEXTCOLOR',     (0, 0), (-1, 0), BRANCO),
        ('FONTNAME',      (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',      (0, 0), (-1, -1), 8),
        ('ROWBACKGROUNDS',(0, 1), (-1, -1), [BRANCO, CINZA_CLAR]),
        ('TOPPADDING',    (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING',   (0, 0), (-1, -1), 6),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 6),
        ('LINEBELOW',     (0, 0), (-1, -1), 0.5, BORDER),
        ('LINEBEFORE',    (0, 0), (-1, -1), 0.5, BORDER),
        ('LINEAFTER',     (0, 0), (-1, -1), 0.5, BORDER),
        ('LINEABOVE',     (0, 0), (-1, 0), 0.5, BORDER),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
    ]
    if total_row and n_rows > 1:
        style += [
            ('BACKGROUND', (0, n_rows - 1), (-1, n_rows - 1), PRIMARIO),
            ('TEXTCOLOR',  (0, n_rows - 1), (-1, n_rows - 1), BRANCO),
            ('FONTNAME',   (0, n_rows - 1), (-1, n_rows - 1), 'Helvetica-Bold'),
        ]
    t.setStyle(TableStyle(style))


# ── Cards KPI ─────────────────────────────────────────────────────────────────

def _card(label: str, value: str, bg: colors.Color,
          fg_value: colors.Color = None) -> Table:
    fg = fg_value or PRIMARIO
    base = getSampleStyleSheet()
    t = Table([
        [Paragraph(f'<font size=7 color="#64748B">{label}</font>',
                   ParagraphStyle('CL', parent=base['Normal'], alignment=TA_CENTER))],
        [Paragraph(f'<b><font size=13 color="{fg.hexval()}">{value}</font></b>',
                   ParagraphStyle('CV', parent=base['Normal'], alignment=TA_CENTER))],
    ], colWidths=['100%'])
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), bg),
        ('TOPPADDING',    (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('LEFTPADDING',   (0, 0), (-1, -1), 8),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 8),
        ('ROUNDEDCORNERS',(0, 0), (-1, -1), [8, 8, 8, 8]),
        ('LINEABOVE',     (0, 0), (-1, -1), 1, BORDER),
        ('LINEBELOW',     (0, 0), (-1, -1), 1, BORDER),
        ('LINELEFT',      (0, 0), (-1, -1), 1, BORDER),
        ('LINERIGHT',     (0, 0), (-1, -1), 1, BORDER),
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

def _tabela_natureza(res: dict, st: dict, usable_w: float, max_rows: int = None) -> Table:
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
    nat_sorted = sorted(por_nat.items(), key=lambda x: -x[1])
    total_naturezas = len(nat_sorted)
    nat_exibir = nat_sorted[:max_rows] if max_rows else nat_sorted

    for nat, qtd in nat_exibir:
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

    if max_rows and total_naturezas > max_rows:
        rows.append([
            Paragraph(f'<i>... {total_naturezas - max_rows} mais</i>', st['td']),
            Paragraph('', st['td']),
            Paragraph('', st['td']),
            Paragraph('', st['td']),
            Paragraph('', st['td']),
        ])

    w = usable_w
    cols = [w*0.28, w*0.14, w*0.16, w*0.26, w*0.16]
    t = Table(rows, colWidths=cols)
    _estilo_tabela_base(t, len(rows))
    return t


def _tabela_top_dest(res: dict, st: dict, usable_w: float, max_rows: int = None) -> Table:
    top_all = res.get('top_dest', [])
    max_display = max_rows or 6
    top = top_all[:max_display]
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

    if len(top_all) > max_display:
        rows.append([
            Paragraph('', st['td']),
            Paragraph(f'<i>... {len(top_all) - max_display} mais</i>', st['td']),
            Paragraph('', st['td']),
            Paragraph('', st['td']),
            Paragraph('', st['td']),
            Paragraph('', st['td']),
        ])

    w = usable_w
    cols = [w*0.06, w*0.30, w*0.09, w*0.13, w*0.24, w*0.18]
    t = Table(rows, colWidths=cols)
    _estilo_tabela_base(t, len(rows))
    return t


def _tabela_mensal(res: dict, st: dict, usable_w: float, max_rows: int = None) -> Table:
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
    meses_sorted = sorted(meses.items())
    total_meses = len(meses_sorted)
    meses_exibir = meses_sorted[:max_rows] if max_rows else meses_sorted

    for mes, v in meses_exibir:
        rows.append([
            Paragraph(mes, st['td']),
            Paragraph(str(v['notas']), st['td']),
            Paragraph(f"{v['cabecas']:,.0f}", st['td']),
            Paragraph(f"{v['valor']:,.2f}", st['td']),
            Paragraph(f"{v.get('vendas_valor', 0):,.2f}", st['td']),
            Paragraph(f"{v.get('rem_valor', 0):,.2f}", st['td']),
        ])

    if max_rows and total_meses > max_rows:
        rows.append([
            Paragraph(f'<i>... {total_meses - max_rows} mais</i>', st['td']),
            Paragraph('', st['td']),
            Paragraph('', st['td']),
            Paragraph('', st['td']),
            Paragraph('', st['td']),
            Paragraph('', st['td']),
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


def _tabela_anomalias(anomalias: list, st: dict, usable_w: float, max_rows: int = None) -> Table:
    header = [[
        Paragraph('<b>NFA</b>',               st['th']),
        Paragraph('<b>Data</b>',              st['th']),
        Paragraph('<b>Natureza</b>',          st['th']),
        Paragraph('<b>Valor (R$)</b>',        st['th']),
        Paragraph('<b>Nível</b>',             st['th']),
        Paragraph('<b>Risco Detectado</b>',   st['th']),
    ]]
    data_rows = []
    total_anomalias = len(anomalias)
    anomalias_exibir = anomalias[:max_rows] if max_rows else anomalias

    for a in anomalias_exibir:
        nivel = str(a.get('Nivel', a.get('nivel', 'MÉDIO'))).upper()
        data_rows.append([
            Paragraph(str(a.get('NFA', '')), st['td']),
            Paragraph(str(a.get('Data', '')), st['td']),
            Paragraph(str(a.get('Natureza', '')), st['td']),
            Paragraph(f"{a.get('Valor', 0):,.2f}", st['td']),
            Paragraph(f'<b>{nivel}</b>', st['td']),
            Paragraph(str(a.get('Motivo', '')), st['td']),
        ])

    if max_rows and total_anomalias > max_rows:
        data_rows.append([
            Paragraph(f'<i>... {total_anomalias - max_rows} mais</i>', st['td']),
            Paragraph('', st['td']),
            Paragraph('', st['td']),
            Paragraph('', st['td']),
            Paragraph('', st['td']),
            Paragraph('', st['td']),
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
    anomalias_check = anomalias_exibir  # Para aplicar estilos
    for i, a in enumerate(anomalias_check, 1):
        nivel = str(a.get('Nivel', a.get('nivel', 'MÉDIO'))).upper()
        bg = _RISCO_BG.get(nivel, CINZA_CLAR)
        style_cmds.append(('BACKGROUND', (0, i), (-1, i), bg))

    t.setStyle(TableStyle(style_cmds))
    return t


def _tabela_vendas_remessas(res: dict, st: dict, usable_w: float, max_rows: int = None) -> Table:
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


def _tabela_resumo_analise(res: dict, st: dict, usable_w: float, max_rows: int = None) -> Table:
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
    modo_relatorio: str = 'detalhado',
    formato: str = 'pdf',
) -> None:
    """Gera Laudo Técnico de Auditoria em PDF ou HTML.

    Args:
        formato: 'pdf' (ReportLab, padrão) ou 'html' (moderno, Ctrl+P para gerar PDF)

    Modos:
    - 'simples': Apenas título, KPIs e parecer IA (rápido ~2s)
    - 'detalhado': Tudo incluindo tabelas detalhadas (padrão ~3-5s)

    Otimizações automáticas:
    - > 50 notas: força modo 'simples' para manter < 10s
    - > 100 notas: tabelas limitadas a top 20 registros
    """
    # Redireciona para HTML se formato='html'
    if formato == 'html':
        saida_html = saida.replace('.pdf', '.html') if saida.endswith('.pdf') else saida + '.html'
        return gerar_html_relatorio(
            notas, saida_html, analise_ia, nome_contribuinte,
            cpf_contribuinte, risco_nivel, score_risco, modo_relatorio
        )

    t0 = time.time()

    # Otimização automática para PDFs grandes
    qtd_notas = len(notas) if notas else 0
    if qtd_notas > 50 and modo_relatorio == 'detalhado':
        logger.info(f"[PDF OTI] {qtd_notas} notas > 50 — forçando modo 'simples' (estava '{modo_relatorio}')")
        modo_relatorio = 'simples'
    usable_w = W - 4*cm  # margens 2cm cada lado

    doc = SimpleDocTemplate(
        saida, pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2.5*cm, bottomMargin=2*cm,
    )
    st = _estilos()
    # Mini-resumo rápido (sem cálculos pesados)
    res = {
        'total_notas': len(notas),
        'total_cabecas': sum(n.quantidade_total for n in notas) if notas else 0,
        'total_valor': sum(n.valor_total for n in notas) if notas else 0,
        'ticket_medio': (sum(n.valor_total for n in notas) / sum(n.quantidade_total for n in notas)) if notas and sum(n.quantidade_total for n in notas) > 0 else 0,
        'por_natureza': {},
        'top_dest': [],
    }
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

    secnum = 1
    # Limita tabelas para PDFs com >100 notas
    max_rows_tabelas = 20 if qtd_notas > 100 else None

    # ── Seções detalhadas (apenas em modo 'detalhado') ────────────────────────
    if modo_relatorio == 'detalhado':
        # Seção 1: Distribuição por Natureza
        por_nat = res.get('por_natureza', {})
        if por_nat:
            elements.append(Paragraph("1. DISTRIBUIÇÃO POR NATUREZA DE OPERAÇÃO", st['sec']))
            elements.append(_tabela_natureza(res, st, usable_w, max_rows=max_rows_tabelas))
            elements.append(Spacer(1, 0.4*cm))
            secnum += 1

        # Seção 2: Top Destinatários
        top_dest = res.get('top_dest', [])
        if top_dest:
            elements.append(Paragraph(f"{secnum}. PRINCIPAIS DESTINATÁRIOS", st['sec']))
            elements.append(_tabela_top_dest(res, st, usable_w, max_rows=max_rows_tabelas))
            elements.append(Spacer(1, 0.4*cm))
            secnum += 1

    # ── Parecer Técnico (IA) ──────────────────────────────────────
    if analise_ia:
        elements.append(Paragraph(f"{secnum}. PARECER TÉCNICO E VEREDITO DE RISCO", st['sec']))
        elements.extend(_render_markdown(analise_ia, st))
        elements.append(Spacer(1, 0.3*cm))
        secnum += 1

    # ── Seções detalhadas apenas em modo 'detalhado' ──────────────────────────
    if modo_relatorio == 'detalhado':
        secnum_det = secnum

        # Seção 4: Evidências de Fraude
        if anomalias:
            elements.append(Paragraph(f"{secnum_det}. EVIDÊNCIAS DE FRAUDE E INCONSISTÊNCIAS", st['sec']))
            elements.append(Paragraph(
                f"Foram identificadas <b>{len(anomalias)}</b> inconsistência(s) no lote auditado.",
                st['txt']))
            elements.append(Spacer(1, 0.2*cm))
            elements.append(_tabela_anomalias(anomalias, st, usable_w, max_rows=max_rows_tabelas))
            secnum_det += 1

        # Anexo: tabelas analíticas
        tab_mensal = _tabela_mensal(res, st, usable_w, max_rows=max_rows_tabelas)
        tab_vnd_rem = _tabela_vendas_remessas(res, st, usable_w, max_rows=max_rows_tabelas)
        tab_resumo = _tabela_resumo_analise(res, st, usable_w, max_rows=max_rows_tabelas)

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

    t1 = time.time()
    logger.info(f"⏱️ [PDF MONTAGEM] {t1-t0:.1f}s — {len(elements)} elementos, modo={modo_relatorio}")

    doc.build(elements, onFirstPage=_header_footer, onLaterPages=_header_footer)

    t2 = time.time()
    logger.info(f"⏱️ [PDF RENDERIZAÇÃO] {t2-t1:.1f}s — total {t2-t0:.1f}s")


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


def gerar_html_relatorio(
    notas: list[NFA],
    saida: str,
    analise_ia: str = '',
    nome_contribuinte: str = '',
    cpf_contribuinte: str = '',
    risco_nivel: str = '',
    score_risco: float = 0.0,
    modo_relatorio: str = 'detalhado',
) -> None:
    """Gera relatório em HTML moderno com design profissional.

    Saída é um arquivo .html que pode ser impresso em PDF via Ctrl+P no navegador.
    Design: sidebar #2d3436, Inter font, cards brancos com sombras, tabelas com bordas.
    """
    t0 = time.time()

    qtd_notas = len(notas) if notas else 0
    resumo = resumo_geral(notas, nome_contribuinte)

    periodo = "N/A"
    if notas:
        try:
            datas = sorted([n.emissao for n in notas if n.emissao])
            if datas:
                periodo = f"{datas[0]} a {datas[-1]}"
        except Exception:
            pass

    # Gera tabela de top destinatários (máx 10)
    top_dest_html = ""
    top_dest = resumo.get('top_dest', [])[:10]
    if top_dest:
        top_dest_html = "<tr>" + "".join([
            f"<td>{d['nome'][:30]}</td>"
            f"<td style='text-align:right'>{d['notas']}</td>"
            f"<td style='text-align:right'>{d['cabecas']:,.0f}</td>"
            f"<td style='text-align:right'>R$ {d['valor']:,.2f}</td>"
            for d in top_dest
        ]) + "</tr>"

    # Gera tabela de natureza
    por_cat = resumo.get('por_categoria', {})
    natureza_rows = ""
    for cat_nome in ['VENDA', 'REMESSA']:
        cat_data = por_cat.get(cat_nome, {})
        natureza_rows += (
            f"<tr>"
            f"<td>{cat_nome}</td>"
            f"<td style='text-align:right'>{cat_data.get('notas', 0)}</td>"
            f"<td style='text-align:right'>{cat_data.get('cabecas', 0):,.0f}</td>"
            f"<td style='text-align:right'>R$ {cat_data.get('valor', 0):,.2f}</td>"
            f"</tr>"
        )

    nivel_risco_upper = (risco_nivel or 'N/A').upper()
    risco_cor = {'ALTO': '#ef4444', 'MÉDIO': '#f59e0b', 'BAIXO': '#10b981'}.get(nivel_risco_upper, '#94a3b8')

    parecer_html = analise_ia.replace('\n', '<br/>') if analise_ia else "—"

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Laudo de Auditoria - {nome_contribuinte}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #f8fafc;
            color: #1e293b;
            line-height: 1.6;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 40px 20px;
        }}

        .header {{
            text-align: center;
            margin-bottom: 40px;
            border-bottom: 3px solid #3b82f6;
            padding-bottom: 20px;
        }}

        .header h1 {{
            font-size: 28px;
            font-weight: 700;
            margin-bottom: 10px;
            color: #1e293b;
        }}

        .header p {{
            color: #64748b;
            font-size: 14px;
        }}

        .info-box {{
            background: white;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 30px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }}

        .info-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-top: 15px;
        }}

        .info-item {{
            padding: 10px 0;
            border-bottom: 1px solid #f1f5f9;
        }}

        .info-item:last-child {{
            border-bottom: none;
        }}

        .info-label {{
            font-size: 12px;
            font-weight: 600;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .info-value {{
            font-size: 16px;
            font-weight: 600;
            color: #1e293b;
            margin-top: 5px;
        }}

        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}

        .kpi-card {{
            background: white;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }}

        .kpi-label {{
            font-size: 12px;
            font-weight: 600;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 10px;
        }}

        .kpi-value {{
            font-size: 28px;
            font-weight: 700;
            color: #3b82f6;
        }}

        .section {{
            background: white;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 25px;
            margin-bottom: 30px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }}

        .section h2 {{
            font-size: 18px;
            font-weight: 700;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 2px solid #3b82f6;
            color: #1e293b;
        }}

        .section h3 {{
            font-size: 14px;
            font-weight: 600;
            margin-top: 20px;
            margin-bottom: 10px;
            color: #1e293b;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }}

        th {{
            background: #3b82f6;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
            font-size: 13px;
            border: none;
        }}

        td {{
            padding: 12px;
            border-bottom: 1px solid #e2e8f0;
        }}

        tr:nth-child(even) {{
            background: #f8fafc;
        }}

        tr:hover {{
            background: #f1f5f9;
        }}

        .parecer {{
            background: #f0f9ff;
            border-left: 4px solid #3b82f6;
            padding: 15px;
            border-radius: 4px;
            line-height: 1.8;
            font-size: 14px;
        }}

        .risco-badge {{
            display: inline-block;
            padding: 6px 12px;
            border-radius: 4px;
            font-weight: 600;
            font-size: 13px;
            color: white;
            background: {risco_cor};
        }}

        .footer {{
            text-align: center;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #e2e8f0;
            color: #64748b;
            font-size: 12px;
        }}

        @media print {{
            body {{
                background: white;
            }}

            .container {{
                max-width: 100%;
                padding: 0;
            }}

            .section, .info-box, .kpi-card {{
                page-break-inside: avoid;
                box-shadow: none;
                border: 1px solid #e2e8f0;
            }}

            @page {{
                margin: 2cm;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>LAUDO TÉCNICO DE AUDITORIA FISCAL</h1>
            <p>OrgAudi — Sistema Soberano de Auditoria Fiscal</p>
        </div>

        <div class="info-box">
            <div class="info-grid">
                <div class="info-item">
                    <div class="info-label">Cliente Auditado</div>
                    <div class="info-value">{nome_contribuinte.upper() or '—'}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">CPF/CNPJ</div>
                    <div class="info-value">{cpf_contribuinte or '—'}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Período</div>
                    <div class="info-value">{periodo}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Data de Emissão</div>
                    <div class="info-value">{datetime.now().strftime('%d/%m/%Y %H:%M')}</div>
                </div>
            </div>
        </div>

        <div class="kpi-grid">
            <div class="kpi-card">
                <div class="kpi-label">Total de Notas</div>
                <div class="kpi-value">{resumo['total_notas']}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Cabeças</div>
                <div class="kpi-value">{resumo['total_cabecas']:,.0f}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Valor Total</div>
                <div class="kpi-value">R$ {resumo['total_valor']:,.2f}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Ticket Médio</div>
                <div class="kpi-value">R$ {resumo['ticket_medio']:,.2f}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Score de Risco</div>
                <div class="kpi-value">{score_risco:.3f}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Nível de Risco</div>
                <div class="kpi-value"><span class="risco-badge">{nivel_risco_upper}</span></div>
            </div>
        </div>

        <div class="section">
            <h2>Distribuição por Natureza de Operação</h2>
            <table>
                <thead>
                    <tr>
                        <th>Natureza</th>
                        <th style="text-align:right">Notas</th>
                        <th style="text-align:right">Cabeças</th>
                        <th style="text-align:right">Valor Total</th>
                    </tr>
                </thead>
                <tbody>
                    {natureza_rows}
                </tbody>
            </table>
        </div>

        {'<div class="section"><h2>Principais Destinatários</h2><table><thead><tr><th>Destinatário</th><th style="text-align:right">Notas</th><th style="text-align:right">Cabeças</th><th style="text-align:right">Valor Total</th></tr></thead><tbody>' + top_dest_html + '</tbody></table></div>' if top_dest_html else ''}

        <div class="section">
            <h2>Parecer Técnico e Veredito de Risco</h2>
            <div class="parecer">
                {parecer_html}
            </div>
        </div>

        <div class="footer">
            <p>Documento gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')} — Para imprimir em PDF, use Ctrl+P no navegador</p>
        </div>
    </div>
</body>
</html>"""

    with open(saida, 'w', encoding='utf-8') as f:
        f.write(html)

    t1 = time.time()
    logger.info(f"⏱️ [HTML RELATÓRIO] {t1-t0:.2f}s — {saida}")

