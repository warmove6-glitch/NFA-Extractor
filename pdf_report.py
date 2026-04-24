"""Geração de relatório PDF profissional com ReportLab."""

from datetime import datetime
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether, Image as RLImage
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate

import io
import matplotlib.pyplot as plt

from extractor import NFA, resumo_geral

LOGO_PATH = str(Path(__file__).parent / 'assets' / 'logo.png')

from constants import hex_cor

# ── Paleta de cores ──────────────────────────────────────────────────────────
AZUL_ESC  = colors.HexColor(hex_cor('BG2'))
AZUL_MED  = colors.HexColor(hex_cor('PRIMARY'))
AZUL_CLAR = colors.HexColor(hex_cor('BG4'))
VERDE     = colors.HexColor(hex_cor('GREEN'))
VERDE_CLAR= colors.HexColor('#D5F5E3')
CINZA     = colors.HexColor(hex_cor('GRAY'))
CINZA_ESC = colors.HexColor(hex_cor('BORDER'))
BRANCO    = colors.white
LARANJA   = colors.HexColor(hex_cor('ORANGE'))

W, H = A4


def _header_footer(canvas, doc):
    import os
    canvas.saveState()
    # Barra do cabeçalho
    canvas.setFillColor(AZUL_ESC)
    canvas.rect(0, H - 1.8*cm, W, 1.8*cm, fill=1, stroke=0)
    # Logo no canto esquerdo do cabeçalho
    logo_x = 0.3*cm
    logo_y = H - 1.65*cm
    logo_sz = 1.35*cm
    if os.path.exists(LOGO_PATH):
        canvas.drawImage(LOGO_PATH, logo_x, logo_y,
                         width=logo_sz, height=logo_sz,
                         preserveAspectRatio=True, mask='auto')
    # Título do cabeçalho
    canvas.setFillColor(BRANCO)
    canvas.setFont('Helvetica-Bold', 11)
    canvas.drawString(1.9*cm, H - 1.1*cm, 'OrgExtNF — SEFAZ')
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(colors.HexColor('#A9CCE3'))
    canvas.drawString(1.9*cm, H - 1.55*cm, 'OrgatecIA · Análise de Notas Fiscais Avulsas')
    canvas.setFillColor(BRANCO)
    canvas.drawRightString(W - 1.5*cm, H - 1.1*cm,
        f'Gerado em {datetime.now().strftime("%d/%m/%Y %H:%M")}')
    # Rodapé
    canvas.setFillColor(AZUL_ESC)
    canvas.rect(0, 0, W, 0.9*cm, fill=1, stroke=0)
    canvas.setFillColor(BRANCO)
    canvas.setFont('Helvetica', 8)
    canvas.drawString(1.5*cm, 0.3*cm, 'OrgatecIA')
    canvas.drawCentredString(W/2, 0.3*cm, f'Página {doc.page}')
    canvas.setFillColor(colors.HexColor('#A9CCE3'))
    canvas.drawRightString(W - 1.5*cm, 0.3*cm, 'Desenvolvimento > Warley Veloso')
    canvas.restoreState()


def gerar_pdf(notas: list[NFA], saida: str, analise_ia: str = '') -> None:
    doc = SimpleDocTemplate(
        saida, pagesize=A4,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=2.4*cm, bottomMargin=1.5*cm,
        title='Relatorio NFA SEFAZ',
    )

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle('H1', parent=styles['Normal'],
        fontSize=16, fontName='Helvetica-Bold', textColor=AZUL_ESC,
        spaceAfter=6, spaceBefore=12)
    h2 = ParagraphStyle('H2', parent=styles['Normal'],
        fontSize=12, fontName='Helvetica-Bold', textColor=AZUL_MED,
        spaceAfter=4, spaceBefore=10)
    h3 = ParagraphStyle('H3', parent=styles['Normal'],
        fontSize=10, fontName='Helvetica-Bold', textColor=AZUL_ESC,
        spaceAfter=3, spaceBefore=6)
    normal = ParagraphStyle('N', parent=styles['Normal'],
        fontSize=9, fontName='Helvetica', leading=13, textColor=colors.black)
    small  = ParagraphStyle('S', parent=styles['Normal'],
        fontSize=8, fontName='Helvetica', leading=11, textColor=CINZA_ESC)
    center = ParagraphStyle('C', parent=normal, alignment=TA_CENTER)
    mono   = ParagraphStyle('M', parent=styles['Normal'],
        fontSize=8, fontName='Courier', leading=11)

    res = resumo_geral(notas)
    story = []

    # ── CAPA ─────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 1.5*cm))

    # Bloco título
    capa_data = [
        [Paragraph('<b>RELATORIO DE NOTAS FISCAIS AVULSAS</b>', ParagraphStyle(
            'CP', parent=styles['Normal'], fontSize=20, fontName='Helvetica-Bold',
            textColor=BRANCO, alignment=TA_CENTER))],
        [Paragraph('Estado de Goias — Secretaria de Estado da Fazenda', ParagraphStyle(
            'CP2', parent=styles['Normal'], fontSize=11, fontName='Helvetica',
            textColor=AZUL_CLAR, alignment=TA_CENTER, spaceBefore=4))],
    ]
    t_capa = Table(capa_data, colWidths=[W - 3*cm])
    t_capa.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), AZUL_ESC),
        ('TOPPADDING',    (0,0), (-1,-1), 18),
        ('BOTTOMPADDING', (0,0), (-1,-1), 18),
        ('LEFTPADDING',   (0,0), (-1,-1), 20),
        ('RIGHTPADDING',  (0,0), (-1,-1), 20),
        ('ROUNDEDCORNERS', (0,0), (-1,-1), [8,8,8,8]),
    ]))
    story.append(t_capa)
    story.append(Spacer(1, 0.6*cm))

    # Cards de resumo (linha 2x3)
    if notas:
        rem = notas[0].remetente
        periodo_min = min(n.emissao for n in notas if n.emissao)
        periodo_max = max(n.emissao for n in notas if n.emissao)
        story.append(Paragraph(
            f'<b>Produtor:</b> {rem.nome} — CPF: {rem.cpf_cnpj} — IE: {rem.ie} — {rem.municipio}',
            normal))
        story.append(Paragraph(
            f'<b>Periodo:</b> {periodo_min} a {periodo_max}', normal))
        story.append(Spacer(1, 0.4*cm))

    def _card(label, value, cor_bg=AZUL_CLAR):
        return Table(
            [[Paragraph(f'<b>{label}</b>', small),
              Paragraph(f'<b>{value}</b>', ParagraphStyle('CV', parent=styles['Normal'],
                fontSize=13, fontName='Helvetica-Bold', textColor=AZUL_ESC, alignment=TA_CENTER))]],
            colWidths=[None, None]
        )

    cards_data = [
        [_resumo_card('Total de Notas', str(res['total_notas']), AZUL_CLAR),
         _resumo_card('Cabecas Movimentadas', f"{res['total_cabecas']:.0f}", VERDE_CLAR),
         _resumo_card('Valor Total', f"R$ {res['total_valor']:,.2f}", CINZA)],
        [_resumo_card('Ticket Medio', f"R$ {res['ticket_medio']:,.2f}", CINZA),
         _resumo_card('Compradores Distintos', str(len(res['top_dest'])), AZUL_CLAR),
         _resumo_card('Meses de Operacao', str(len(res['por_mes'])), VERDE_CLAR)],
    ]
    t_cards = Table(cards_data, colWidths=[(W-3*cm)/3]*3, rowHeights=[2.0*cm, 2.0*cm])
    t_cards.setStyle(TableStyle([
        ('ALIGN',    (0,0), (-1,-1), 'CENTER'),
        ('VALIGN',   (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING',  (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING',   (0,0), (-1,-1), 4),
        ('BOTTOMPADDING',(0,0), (-1,-1), 4),
    ]))
    story.append(t_cards)
    story.append(Spacer(1, 0.5*cm))

    # Gráficos Dinâmicos
    graficos = _gerar_graficos(res)
    if graficos:
        if len(graficos) == 2:
            t_graficos = Table([[graficos[0], graficos[1]]], colWidths=[(W-3*cm)/2]*2)
            t_graficos.setStyle(TableStyle([
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ]))
            story.append(t_graficos)
        else:
            for g in graficos:
                story.append(g)
        story.append(Spacer(1, 0.5*cm))

    # Tipos de operação
    por_nat = res['por_natureza']
    nat_txt = '    '.join(f"{k}: {v}" for k, v in por_nat.items())
    story.append(Paragraph(f'<b>Tipos de operacao:</b>  {nat_txt}', normal))

    # ── ANÁLISE IA ────────────────────────────────────────────────────────────
    if analise_ia.strip():
        story.append(PageBreak())
        story.append(Paragraph('Analise Inteligente (IA)', h1))
        story.append(HRFlowable(width='100%', thickness=2, color=AZUL_MED))
        story.append(Spacer(1, 0.3*cm))
        for linha in analise_ia.split('\n'):
            if linha.strip():
                story.append(Paragraph(linha.strip(), normal))
            else:
                story.append(Spacer(1, 0.15*cm))

    # ── PRINCIPAIS COMPRADORES ───────────────────────────────────────────────
    story.append(PageBreak())
    story.append(Paragraph('Principais Compradores', h1))
    story.append(HRFlowable(width='100%', thickness=2, color=AZUL_MED))
    story.append(Spacer(1, 0.3*cm))

    cab_dest = [
        [_th('Comprador'), _th('CPF/CNPJ'), _th('Municipio'),
         _th('Notas'), _th('Cabecas'), _th('Valor Total (R$)')]
    ]
    for i, d in enumerate(sorted(
        [{**v} for v in res['top_dest']],
        key=lambda x: x['valor'], reverse=True
    )):
        bg = AZUL_CLAR if i % 2 == 0 else BRANCO
        cab_dest.append([
            Paragraph(d['nome'][:40], small),
            Paragraph('', small),
            Paragraph('', small),
            Paragraph(str(d['notas']), ParagraphStyle('RC', parent=small, alignment=TA_RIGHT)),
            Paragraph(f"{d['cabecas']:.0f}", ParagraphStyle('RC', parent=small, alignment=TA_RIGHT)),
            Paragraph(f"{d['valor']:,.2f}", ParagraphStyle('RC', parent=small, alignment=TA_RIGHT)),
        ])

    # buscar municipio dos destinatários
    dest_info: dict[str, dict] = {}
    for n in notas:
        k = n.destinatario.nome
        if k not in dest_info:
            dest_info[k] = {'cpf_cnpj': n.destinatario.cpf_cnpj, 'municipio': n.destinatario.municipio}

    cab_dest2 = [
        [_th('Comprador'), _th('CPF/CNPJ'), _th('Municipio'),
         _th('Notas'), _th('Cabecas'), _th('Valor Total (R$)')]
    ]
    for i, d in enumerate(sorted(res['top_dest'], key=lambda x: x['valor'], reverse=True)):
        bg = AZUL_CLAR if i % 2 == 0 else BRANCO
        info = dest_info.get(d['nome'], {})
        cab_dest2.append([
            Paragraph(d['nome'][:40], small),
            Paragraph(info.get('cpf_cnpj',''), small),
            Paragraph(info.get('municipio',''), small),
            Paragraph(str(d['notas']), ParagraphStyle('RC',parent=small,alignment=TA_RIGHT)),
            Paragraph(f"{d['cabecas']:.0f}", ParagraphStyle('RC',parent=small,alignment=TA_RIGHT)),
            Paragraph(f"{d['valor']:,.2f}", ParagraphStyle('RC',parent=small,alignment=TA_RIGHT)),
        ])

    t_dest = Table(cab_dest2, colWidths=[5.5*cm, 3.5*cm, 3.5*cm, 1.5*cm, 2*cm, 2.5*cm])
    _estilo_tabela(t_dest, len(cab_dest2))
    story.append(t_dest)

    # ── EVOLUÇÃO MENSAL ───────────────────────────────────────────────────────
    story.append(Spacer(1, 0.8*cm))
    story.append(Paragraph('Evolucao Mensal', h2))
    story.append(HRFlowable(width='100%', thickness=1, color=AZUL_MED))
    story.append(Spacer(1, 0.2*cm))

    mes_rows = [[_th('Mes/Ano'), _th('Qtd. Notas'), _th('Cabecas'), _th('Valor (R$)')]]
    for mes, v in res['por_mes'].items():
        mes_rows.append([
            Paragraph(mes, small),
            Paragraph(str(v['notas']), ParagraphStyle('RC',parent=small,alignment=TA_RIGHT)),
            Paragraph(f"{v['cabecas']:.0f}", ParagraphStyle('RC',parent=small,alignment=TA_RIGHT)),
            Paragraph(f"{v['valor']:,.2f}", ParagraphStyle('RC',parent=small,alignment=TA_RIGHT)),
        ])
    # Total
    mes_rows.append([
        Paragraph('<b>TOTAL</b>', small),
        Paragraph(f"<b>{res['total_notas']}</b>", ParagraphStyle('RC',parent=small,alignment=TA_RIGHT,fontName='Helvetica-Bold')),
        Paragraph(f"<b>{res['total_cabecas']:.0f}</b>", ParagraphStyle('RC',parent=small,alignment=TA_RIGHT,fontName='Helvetica-Bold')),
        Paragraph(f"<b>{res['total_valor']:,.2f}</b>", ParagraphStyle('RC',parent=small,alignment=TA_RIGHT,fontName='Helvetica-Bold')),
    ])

    t_mes = Table(mes_rows, colWidths=[3*cm, 3*cm, 3*cm, 4*cm])
    _estilo_tabela(t_mes, len(mes_rows), total_row=True)
    story.append(t_mes)

    # ── NOTAS FISCAIS (lista completa) ────────────────────────────────────────
    story.append(PageBreak())
    story.append(Paragraph('Relacao de Notas Fiscais Emitidas', h1))
    story.append(HRFlowable(width='100%', thickness=2, color=AZUL_MED))
    story.append(Spacer(1, 0.3*cm))

    nfa_rows = [[
        _th('Num.'), _th('Emissao'), _th('Natureza'), _th('Destinatario'),
        _th('Municipio'), _th('Cab.'), _th('Valor (R$)')
    ]]
    for n in notas:
        nfa_rows.append([
            Paragraph(n.numero, small),
            Paragraph(n.emissao, small),
            Paragraph(n.natureza[:14], small),
            Paragraph(n.destinatario.nome[:35], small),
            Paragraph(n.destinatario.municipio[:18], small),
            Paragraph(f"{n.quantidade_total:.0f}", ParagraphStyle('RC',parent=small,alignment=TA_RIGHT)),
            Paragraph(f"{n.valor_total:,.2f}", ParagraphStyle('RC',parent=small,alignment=TA_RIGHT)),
        ])

    t_nfa = Table(
        nfa_rows,
        colWidths=[1.8*cm, 2.2*cm, 3.2*cm, 4.8*cm, 3.2*cm, 1.4*cm, 2.4*cm],
        repeatRows=1
    )
    _estilo_tabela(t_nfa, len(nfa_rows))
    story.append(t_nfa)

    # ── ITENS DETALHADOS ─────────────────────────────────────────────────────
    story.append(PageBreak())
    story.append(Paragraph('Itens Detalhados por Nota', h1))
    story.append(HRFlowable(width='100%', thickness=2, color=AZUL_MED))
    story.append(Spacer(1, 0.3*cm))

    item_rows = [[
        _th('NFA'), _th('Data'), _th('Destinatario'),
        _th('Cod.'), _th('Descricao'), _th('Qtd.'), _th('Vlr.Unit.'), _th('Vlr.Total')
    ]]
    for n in notas:
        for p in n.produtos:
            item_rows.append([
                Paragraph(n.numero, small),
                Paragraph(n.emissao, small),
                Paragraph(n.destinatario.nome[:30], small),
                Paragraph(p.codigo, small),
                Paragraph(p.descricao[:45], small),
                Paragraph(f"{p.quantidade:.0f}", ParagraphStyle('RC',parent=small,alignment=TA_RIGHT)),
                Paragraph(f"{p.vlr_unitario:,.2f}", ParagraphStyle('RC',parent=small,alignment=TA_RIGHT)),
                Paragraph(f"{p.vlr_total:,.2f}", ParagraphStyle('RC',parent=small,alignment=TA_RIGHT)),
            ])

    t_item = Table(
        item_rows,
        colWidths=[1.8*cm, 2*cm, 4*cm, 1.2*cm, 5.5*cm, 1.2*cm, 2*cm, 2.3*cm],
        repeatRows=1
    )
    _estilo_tabela(t_item, len(item_rows))
    story.append(t_item)

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)


def _th(txt: str) -> Paragraph:
    return Paragraph(f'<b>{txt}</b>', ParagraphStyle(
        'TH', fontName='Helvetica-Bold', fontSize=8,
        textColor=BRANCO, alignment=TA_CENTER))


def _resumo_card(label: str, value: str, bg: colors.Color) -> Table:
    t = Table([
        [Paragraph(f'<font size=8 color="#566573">{label}</font>', ParagraphStyle('CL', parent=getSampleStyleSheet()['Normal'], alignment=TA_CENTER))],
        [Paragraph(f'<b><font size=13 color="#0D2137">{value}</font></b>', ParagraphStyle('CV', parent=getSampleStyleSheet()['Normal'], alignment=TA_CENTER))],
    ], colWidths=['100%'])
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,-1), bg),
        ('TOPPADDING',    (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING',   (0,0), (-1,-1), 6),
        ('RIGHTPADDING',  (0,0), (-1,-1), 6),
        ('ROUNDEDCORNERS', (0,0), (-1,-1), [6,6,6,6]),
    ]))
    return t


def _estilo_tabela(t: Table, n_rows: int, total_row: bool = False):
    style = [
        ('BACKGROUND',    (0,0), (-1,0), AZUL_MED),
        ('TEXTCOLOR',     (0,0), (-1,0), BRANCO),
        ('ROWBACKGROUNDS',(0,1), (-1,-1), [CINZA, BRANCO]),
        ('FONTNAME',      (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE',      (0,0), (-1,-1), 8),
        ('TOPPADDING',    (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING',   (0,0), (-1,-1), 5),
        ('RIGHTPADDING',  (0,0), (-1,-1), 5),
        ('LINEBELOW',     (0,0), (-1,-1), 0.5, colors.HexColor('#BDC3C7')),
        ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
    ]
    if total_row and n_rows > 1:
        style += [
            ('BACKGROUND',  (0, n_rows-1), (-1, n_rows-1), AZUL_ESC),
            ('TEXTCOLOR',   (0, n_rows-1), (-1, n_rows-1), BRANCO),
            ('FONTNAME',    (0, n_rows-1), (-1, n_rows-1), 'Helvetica-Bold'),
        ]
    t.setStyle(TableStyle(style))

def _gerar_graficos(res: dict) -> list:
    graficos = []
    
    # Gráfico 1: Evolução Mensal (Barras)
    meses_dict = res.get('por_mes', {})
    if len(meses_dict) > 1:
        fig_bar = None
        try:
            meses = list(meses_dict.keys())
            valores = [v['valor'] for v in meses_dict.values()]
            
            fig_bar, ax = plt.subplots(figsize=(6, 3))
            ax.bar(meses, valores, color=hex_cor('PRIMARY'), width=0.5)
            ax.set_title('Evolucao Mensal de Faturamento (R$)', fontsize=10, fontweight='bold', color=hex_cor('BG2'))
            ax.tick_params(axis='x', rotation=45, labelsize=8)
            ax.tick_params(axis='y', labelsize=8)
            fig_bar.tight_layout()
            
            buf = io.BytesIO()
            fig_bar.savefig(buf, format='png', dpi=150)
            buf.seek(0)
            graficos.append(RLImage(buf, width=15*cm, height=7.5*cm))
        except Exception:
            pass
        finally:
            if fig_bar:
                plt.close(fig_bar)

    # Gráfico 2: Market Share (Pizza)
    top_dest = res.get('top_dest', [])
    if len(top_dest) > 1:
        fig_pie = None
        try:
            labels = [d['nome'][:15] for d in top_dest[:5]]
            valores = [d['valor'] for d in top_dest[:5]]
            
            outros_val = sum(d['valor'] for d in top_dest[5:])
            if outros_val > 0:
                labels.append('Outros')
                valores.append(outros_val)
                
            fig_pie, ax = plt.subplots(figsize=(5, 5))
            cores = [hex_cor('PRIMARY'), hex_cor('ORANGE'), hex_cor('GREEN'), hex_cor('BORDER'), hex_cor('CYAN'), hex_cor('GRAY')]
            ax.pie(valores, labels=labels, autopct='%1.1f%%', colors=cores, startangle=140, textprops={'fontsize': 8})
            ax.set_title('Market Share por Comprador (Top 5)', fontsize=10, fontweight='bold', color=hex_cor('BG2'))
            fig_pie.tight_layout()
            
            buf = io.BytesIO()
            fig_pie.savefig(buf, format='png', dpi=150)
            buf.seek(0)
            graficos.append(RLImage(buf, width=10*cm, height=10*cm))
        except Exception:
            pass
        finally:
            if fig_pie:
                plt.close(fig_pie)

    return graficos
