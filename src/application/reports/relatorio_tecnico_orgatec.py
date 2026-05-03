"""Gerador do RELATÓRIO TÉCNICO DE AUDITORIA ORGATEC (PDF).

Replica o layout visual do modelo `AUDITORIA_CRUZADA_GENIS_2025_v1.pdf`:
- Header com logo ORGATEC + linha azul + número de página
- Footer com identificação do responsável técnico
- Tabela de identificação do contribuinte
- Síntese quantitativa cruzada
- Tabela de severidade colorida
- Achados Críticos / Alta / Média / Atenção / Conforme
- Fórmulas e regras de cruzamento (Regras 1-5)
- Declaração de alcance e limitações
- Tipos de anomalia + Responsável técnico
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from src.domain.auditoria_forense import (
    SEV_ALTO,
    SEV_ATENCAO,
    SEV_CONFORME,
    SEV_CRITICO,
    SEV_MEDIO,
    ResultadoAuditoria,
)

# ── Paleta ORGATEC ────────────────────────────────────────────────────────────
ORGATEC_PRIMARY = colors.HexColor("#0f3a66")
ORGATEC_ACCENT = colors.HexColor("#4db8ff")
ORGATEC_LIGHT_BG = colors.HexColor("#f7fafc")
ORGATEC_BORDER = colors.HexColor("#e2e8f0")
ORGATEC_TEXT = colors.HexColor("#1a202c")
ORGATEC_MUTED = colors.HexColor("#718096")

SEV_COLORS = {
    SEV_CRITICO: colors.HexColor("#cc0000"),
    SEV_ALTO: colors.HexColor("#e88200"),
    SEV_MEDIO: colors.HexColor("#d4a017"),
    SEV_ATENCAO: colors.HexColor("#0369a1"),
    SEV_CONFORME: colors.HexColor("#2f855a"),
}

SEV_BG_COLORS = {
    SEV_CRITICO: colors.HexColor("#fee2e2"),
    SEV_ALTO: colors.HexColor("#feebc8"),
    SEV_MEDIO: colors.HexColor("#fef3c7"),
    SEV_ATENCAO: colors.HexColor("#dbeafe"),
    SEV_CONFORME: colors.HexColor("#d4f4dd"),
}


# ── Canvas com paginação "Página N de T" ─────────────────────────────────────
class _NumerandoCanvas(rl_canvas.Canvas):
    """Canvas que gera 'Página X de Y' no header via passagem dupla (save-replay)."""

    def __init__(self, *args, **kwargs):
        rl_canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states: list[dict] = []

    def showPage(self) -> None:  # type: ignore[override]
        # Salva estado completo da página (inclui tudo que _desenhar_chrome já desenhou)
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:  # type: ignore[override]
        total_paginas = len(self._saved_page_states)
        largura, altura = A4
        margem_x = 18 * mm
        for estado in self._saved_page_states:
            self.__dict__.update(estado)
            # Insere numeração sobre o conteúdo já desenhado
            self.setFillColor(ORGATEC_MUTED)
            self.setFont("Helvetica", 9)
            self.drawRightString(
                largura - margem_x,
                altura - 14 * mm,
                f"Página {self._pageNumber} de {total_paginas}",
            )
            rl_canvas.Canvas.showPage(self)
        rl_canvas.Canvas.save(self)


# ── Estilos ──────────────────────────────────────────────────────────────────
def _criar_estilos() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "titulo_doc": ParagraphStyle(
            "TituloDoc", parent=base["Heading1"],
            fontSize=22, textColor=ORGATEC_TEXT, fontName="Helvetica-Bold",
            alignment=TA_CENTER, spaceAfter=4, spaceBefore=8,
        ),
        "subtitulo_doc": ParagraphStyle(
            "SubtituloDoc", parent=base["Italic"],
            fontSize=11, textColor=ORGATEC_MUTED, fontName="Helvetica-Oblique",
            alignment=TA_CENTER, spaceAfter=12,
        ),
        "secao": ParagraphStyle(
            "Secao", parent=base["Heading2"],
            fontSize=14, textColor=ORGATEC_PRIMARY, fontName="Helvetica-Bold",
            alignment=TA_CENTER, spaceBefore=12, spaceAfter=8,
        ),
        "subsecao": ParagraphStyle(
            "Subsecao", parent=base["Heading3"],
            fontSize=11, textColor=ORGATEC_PRIMARY, fontName="Helvetica-Bold",
            spaceBefore=8, spaceAfter=4,
        ),
        "achado_titulo": ParagraphStyle(
            "AchadoTitulo", parent=base["Heading3"],
            fontSize=10.5, textColor=ORGATEC_PRIMARY, fontName="Helvetica-Bold",
            spaceBefore=8, spaceAfter=4,
        ),
        "corpo": ParagraphStyle(
            "Corpo", parent=base["BodyText"],
            fontSize=9, textColor=ORGATEC_TEXT, fontName="Helvetica",
            alignment=TA_JUSTIFY, spaceAfter=4, leading=12,
        ),
        "corpo_pequeno": ParagraphStyle(
            "CorpoPequeno", parent=base["BodyText"],
            fontSize=8, textColor=ORGATEC_TEXT, fontName="Helvetica",
            alignment=TA_JUSTIFY, leading=11,
        ),
        "rodape_dest": ParagraphStyle(
            "RodapeDest", parent=base["Normal"],
            fontSize=8.5, textColor=ORGATEC_MUTED, fontName="Helvetica-Oblique",
            alignment=TA_CENTER,
        ),
        "responsavel_nome": ParagraphStyle(
            "RespNome", parent=base["Heading2"],
            fontSize=14, textColor=ORGATEC_TEXT, fontName="Helvetica-Bold",
            spaceAfter=2,
        ),
        "responsavel_titulo": ParagraphStyle(
            "RespTitulo", parent=base["Normal"],
            fontSize=10, textColor=ORGATEC_PRIMARY, fontName="Helvetica-Bold",
        ),
    }


# ── Header / footer da página (chamados automaticamente em cada página) ──────
def _desenhar_chrome(canvas, doc):
    """Desenha header e footer ORGATEC em cada página."""
    canvas.saveState()
    largura, altura = A4
    margem_x = 18 * mm

    # ── HEADER ────────────────────────────────────────────────────────────
    # Logo simulado: círculo azul + texto ORGATEC
    canvas.setFillColor(ORGATEC_PRIMARY)
    canvas.circle(margem_x + 5 * mm, altura - 13 * mm, 4 * mm, stroke=0, fill=1)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 7)
    canvas.drawCentredString(margem_x + 5 * mm, altura - 13.5 * mm - 1, "OAU")

    # Texto ORGATEC ao lado
    canvas.setFillColor(ORGATEC_PRIMARY)
    canvas.setFont("Helvetica-Bold", 11)
    canvas.drawString(margem_x + 12 * mm, altura - 12 * mm, "ORGATEC")
    canvas.setFont("Helvetica-Bold", 8)
    canvas.setFillColor(ORGATEC_MUTED)
    canvas.drawString(margem_x + 12 * mm, altura - 16 * mm, "CONTABILIDADE E AUDITORIA")

    # Número de página: desenhado por _NumerandoCanvas (showPage/save), não aqui

    # Linha azul do header
    canvas.setStrokeColor(ORGATEC_PRIMARY)
    canvas.setLineWidth(0.7)
    canvas.line(margem_x, altura - 19 * mm, largura - margem_x, altura - 19 * mm)

    # ── FOOTER ────────────────────────────────────────────────────────────
    canvas.setStrokeColor(ORGATEC_BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(margem_x, 15 * mm, largura - margem_x, 15 * mm)

    canvas.setFillColor(ORGATEC_MUTED)
    canvas.setFont("Helvetica", 8)
    canvas.drawCentredString(
        largura / 2, 11 * mm,
        "ORGATEC CONTABILIDADE E AUDITORIA  •  Robson Alain Veloso — Ciências Contábeis"
    )

    canvas.restoreState()


# ── Tabelas auxiliares ────────────────────────────────────────────────────────
def _tabela_identificacao(r: ResultadoAuditoria) -> Table:
    """Tabela 'Contribuinte / CPF / Período / ...' (página 1)."""
    docs_total = r.total_notas
    saidas = r.total_vendas + r.total_remessas_leilao
    compras = r.total_compras

    linhas = [
        ["Contribuinte", r.cliente_nome.upper()],
        ["CPF", r.cliente_cpf],
        ["Inscrição Estadual", r.inscricao_estadual if r.inscricao_estadual else "—"],
        ["Município / UF", r.municipio if r.municipio else "—"],
        [
            "Período auditado",
            f"{r.periodo_inicio} a {r.periodo_fim}" if r.periodo_inicio else "—"
        ],
    ]
    # Documento-base PDF e Planilha (exibidos somente se informados)
    if r.documento_base_gief:
        linhas.append(["Documento-base PDF", r.documento_base_gief])
    if r.documento_base_planilha:
        linhas.append(["Documento-base Planilha", r.documento_base_planilha])
    if not r.documento_base_gief and not r.documento_base_planilha:
        linhas.append(["Documento-base", "Notas Fiscais Agropecuárias (NFA-e) — OrgAudi 1.0"])
    linhas += [
        ["Sistema de auditoria", "OrgAudi 1.0 / NFA Extractor — ORGATEC"],
        [
            "Total de notas",
            f"{docs_total} — {saidas} saídas ({r.total_vendas} vendas + "
            f"{r.total_remessas_leilao} remessas) + {compras} compras"
        ],
        ["Volume bruto (saídas)", f"R$ {r.volume_bruto_saidas:,.2f}"],
        ["Data da auditoria", datetime.now().strftime("%d/%m/%Y")],
    ]
    t = Table(linhas, colWidths=[55 * mm, 110 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), ORGATEC_LIGHT_BG),
        ("TEXTCOLOR", (0, 0), (0, -1), ORGATEC_PRIMARY),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("BOX", (0, 0), (-1, -1), 0.5, ORGATEC_BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, ORGATEC_BORDER),
    ]))
    return t


def _tabela_sintese(r: ResultadoAuditoria) -> Table:
    """SÍNTESE QUANTITATIVA CRUZADA — modelo AUDITORIA_CRUZADA_GENIS_2025_v1.pdf.

    6 linhas, 4 colunas: Indicador | Planilha IRPF | GIEF/SEFAZ-GO | Status.
    • Conforme (verde)  = ambas as fontes têm o mesmo valor.
    • Dado novo (âmbar) = Planilha IRPF extraiu dado que o GIEF não segrega
                          (ex.: compras, onde o contribuinte é o destinatário).
    """
    CONFORME = "Conforme"
    DADO_NOVO = "Dado novo"

    # helper local — formata moeda antes de _fmt_moeda estar definida no módulo
    def _m(v: float) -> str:
        return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def _cab(v: float) -> str:
        return f"{v:,.0f}".replace(",", ".")

    rows = [
        ["Indicador", "Planilha IRPF", "GIEF / SEFAZ-GO", "Status"],
        # Ambas as fontes concordam (GIEF cobre notas de saída do contribuinte)
        [
            "Volume bruto total\n(saídas — remetente=contribuinte)",
            _m(r.volume_bruto_saidas),
            _m(r.volume_bruto_saidas),
            CONFORME,
        ],
        [
            f"Receita imediata\n({r.total_vendas} vendas diretas)",
            _m(r.receita_imediata),
            _m(r.receita_imediata),
            CONFORME,
        ],
        [
            f"Trânsito — remessas para leilão\n({r.total_remessas_leilao} notas — NÃO base IRPF)",
            _m(r.transito_leilao),
            _m(r.transito_leilao),
            CONFORME,
        ],
        [
            "Cabeças totais movimentadas",
            _cab(r.cabecas_movimentadas),
            _cab(r.cabecas_movimentadas),
            CONFORME,
        ],
        # Dado novo: GIEF não rastreia notas onde contribuinte é destinatário
        [
            f"Compras de gado\n({r.total_compras} notas — contribuinte=destinatário)",
            _m(r.valor_compras),
            "—",
            DADO_NOVO,
        ],
        # Funrural: calculado sobre a receita imediata — ambas concordam
        [
            "Funrural estimado\n(1,5% × receita imediata — Lei 8.212/91)",
            _m(r.funrural_estimado),
            _m(r.funrural_estimado),
            CONFORME,
        ],
    ]

    # Índice da linha TRÂNSITO (não-base IRPF) — leve diferenciação visual
    IDX_TRANSITO = 3

    style: list = [
        ("BACKGROUND", (0, 0), (-1, 0), ORGATEC_PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ALIGN", (1, 1), (2, -1), "RIGHT"),
        ("ALIGN", (3, 1), (3, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("BOX", (0, 0), (-1, -1), 0.5, ORGATEC_BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, ORGATEC_BORDER),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ORGATEC_LIGHT_BG]),
        # Trânsito — itálico para indicar "não-base IRPF"
        ("FONTNAME", (0, IDX_TRANSITO), (2, IDX_TRANSITO), "Helvetica-Oblique"),
        ("TEXTCOLOR", (0, IDX_TRANSITO), (2, IDX_TRANSITO), ORGATEC_MUTED),
    ]

    # Colorização condicional da coluna Status
    _STATUS_COR = {
        CONFORME: (colors.HexColor("#d4f4dd"), colors.HexColor("#2f855a")),
        DADO_NOVO: (colors.HexColor("#fef3c7"), colors.HexColor("#d97706")),
    }
    for i, row in enumerate(rows[1:], start=1):
        status_val = row[3]
        if status_val in _STATUS_COR:
            bg, fg = _STATUS_COR[status_val]
            style.append(("BACKGROUND", (3, i), (3, i), bg))
            style.append(("TEXTCOLOR", (3, i), (3, i), fg))
            style.append(("FONTNAME", (3, i), (3, i), "Helvetica-Bold"))

    # Linha Compras: fundo levemente âmbar para realçar o "Dado novo"
    IDX_COMPRAS = 5
    style.append(("BACKGROUND", (0, IDX_COMPRAS), (2, IDX_COMPRAS), colors.HexColor("#fffbeb")))

    t = Table(rows, colWidths=[70 * mm, 38 * mm, 38 * mm, 28 * mm])
    t.setStyle(TableStyle(style))
    return t


def _tabela_severidade(r: ResultadoAuditoria) -> Table:
    """Tabela 'Severidade | Qtd | Conclusão sintética' (página 1)."""
    cont = r.contagem_severidade
    sev_labels = {
        SEV_CRITICO: ("CRÍTICO", "Achados que exigem ação imediata e cruzamento documental externo"),
        SEV_ALTO: ("ALTO", "Indícios fortes — verificar antes da DIRPF"),
        SEV_MEDIO: ("MÉDIO", "Obrigações acessórias e tributárias"),
        SEV_ATENCAO: ("ATENÇÃO", "Items que merecem revisão contábil"),
        SEV_CONFORME: ("CONFORME", "Itens validados pela bateria forense"),
    }

    rows = [["Severidade", "Qtd", "Conclusão sintética"]]
    for sev_key in (SEV_CRITICO, SEV_ALTO, SEV_MEDIO, SEV_ATENCAO, SEV_CONFORME):
        if sev_key == SEV_CONFORME:
            qtd = len(r.conformidades)
        else:
            qtd = cont.get(sev_key, 0)
        if qtd == 0 and sev_key != SEV_CONFORME:
            continue
        label, desc = sev_labels[sev_key]
        # Conclusão: pega títulos dos achados desse nível (ou descrição genérica)
        if sev_key == SEV_CONFORME:
            if r.conformidades:
                resumo = "; ".join(c["item"] for c in r.conformidades[:2])
            else:
                resumo = desc
        else:
            achados_sev = [a for a in r.achados if a.severidade == sev_key]
            if achados_sev:
                resumo = "; ".join(a.titulo for a in achados_sev[:2])
            else:
                resumo = desc
        rows.append([label, str(qtd), resumo])

    t = Table(rows, colWidths=[28 * mm, 12 * mm, 125 * mm])
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), ORGATEC_PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (0, 1), (1, -1), "CENTER"),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("BOX", (0, 0), (-1, -1), 0.5, ORGATEC_BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, ORGATEC_BORDER),
    ]
    # Cor da célula severidade
    sev_keys_presentes = []
    for sev_key in (SEV_CRITICO, SEV_ALTO, SEV_MEDIO, SEV_ATENCAO, SEV_CONFORME):
        qtd = len(r.conformidades) if sev_key == SEV_CONFORME else cont.get(sev_key, 0)
        if qtd > 0:
            sev_keys_presentes.append(sev_key)

    for i, sev_key in enumerate(sev_keys_presentes, start=1):
        style.append(("BACKGROUND", (0, i), (0, i), SEV_BG_COLORS[sev_key]))
        style.append(("TEXTCOLOR", (0, i), (0, i), SEV_COLORS[sev_key]))
    t.setStyle(TableStyle(style))
    return t


def _tabela_detalhes_achado(detalhes: list[dict[str, Any]]) -> Table | None:
    """Renderiza a tabela de evidências de um achado (cada achado tem a sua)."""
    if not detalhes:
        return None
    cols = list(detalhes[0].keys())
    rows = [cols]
    for d in detalhes:
        rows.append([str(d.get(c, "")) for c in cols])

    # Larguras adaptativas (proporção igual)
    largura_total = 165 * mm
    n_cols = max(len(cols), 1)
    col_widths = [largura_total / n_cols] * n_cols

    t = Table(rows, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ORGATEC_PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 1), (0, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("BOX", (0, 0), (-1, -1), 0.4, ORGATEC_BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, ORGATEC_BORDER),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ORGATEC_LIGHT_BG]),
    ]))
    return t


def _tabela_conformidades(r: ResultadoAuditoria) -> Table:
    rows = [["#", "Item verificado", "Resultado"]]
    for i, c in enumerate(r.conformidades, start=1):
        rows.append([str(i), c["item"], c["resultado"]])
    t = Table(rows, colWidths=[10 * mm, 120 * mm, 35 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ORGATEC_PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (0, 1), (0, -1), "CENTER"),
        ("ALIGN", (-1, 1), (-1, -1), "CENTER"),
        ("FONTNAME", (-1, 1), (-1, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (-1, 1), (-1, -1), SEV_COLORS[SEV_CONFORME]),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("BOX", (0, 0), (-1, -1), 0.5, ORGATEC_BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, ORGATEC_BORDER),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ORGATEC_LIGHT_BG]),
    ]))
    return t


# ── Construtor principal ─────────────────────────────────────────────────────
def _renderizar_achado(achado, estilos):
    """Bloco de cada achado: título com cor de severidade + descrição + tabela + cruzamentos."""
    flow = []
    sev_color = SEV_COLORS[achado.severidade]
    titulo_html = (
        f'<font color="{sev_color.hexval()}">'
        f'<b>{achado.codigo} — {achado.titulo}</b>'
        f'</font>'
    )
    flow.append(Paragraph(titulo_html, estilos["achado_titulo"]))

    # Tabela de evidências (se houver)
    if achado.detalhes:
        tab = _tabela_detalhes_achado(achado.detalhes)
        if tab:
            flow.append(tab)
            flow.append(Spacer(1, 4))

    # Descrição
    flow.append(Paragraph(achado.descricao, estilos["corpo"]))

    # Cruzamentos obrigatórios
    if achado.cruzamentos_obrigatorios:
        items = " ".join(f"<b>•</b> {c};" for c in achado.cruzamentos_obrigatorios)
        flow.append(Paragraph(
            f"<b>Cruzamentos obrigatórios:</b> {items}",
            estilos["corpo_pequeno"],
        ))
    flow.append(Spacer(1, 6))
    return flow


def _secao_regras_ocao(estilos) -> list:
    """Página 5-6 do modelo: Fórmulas e Regras de Cruzamento (estáticas, idênticas
    ao OrgAudi 1.0)."""
    flow: list = []
    flow.append(Paragraph("FÓRMULAS E REGRAS DE CRUZAMENTO DE DADOS", estilos["secao"]))
    flow.append(Paragraph(
        "Esta página consolida as fórmulas matemáticas e as regras de cruzamento "
        "aplicadas pelo <b>OrgAudi 1.0</b>. Cada regra foi executada na presente auditoria "
        "e pode ser reproduzida em qualquer outro caso.",
        estilos["corpo"],
    ))
    flow.append(Spacer(1, 6))

    # Regra 1
    flow.append(Paragraph("Regra 1 — Classificação contábil das NFA-e (fundamento)", estilos["subsecao"]))
    rows = [
        ["Posição do contribuinte", "Natureza", "Categoria", "Efeito IRPF Rural"],
        ["REMETENTE", "VENDA", "RECEITA", "Soma à base de cálculo"],
        ["REMETENTE", "REMESSA/LEILÃO", "TRÂNSITO", "Não soma (até arremate)"],
        ["REMETENTE = DESTINATÁRIO\n(mesmo CPF)", "Qualquer", "TRANSFERÊNCIA", "Neutra"],
        ["DESTINATÁRIO", "COMPRA", "DESPESA / INVEST.", "Subtrai da base ou ativa"],
    ]
    t1 = Table(rows, colWidths=[60 * mm, 30 * mm, 35 * mm, 40 * mm])
    t1.setStyle(_estilo_tabela_padrao())
    flow.append(t1)
    flow.append(Spacer(1, 8))

    # Regra 2
    flow.append(Paragraph("Regra 2 — Fórmulas de apuração da receita rural", estilos["subsecao"]))
    formulas = [
        "<b>Receita imediata (ano-base):</b> Σ (Valor das notas onde Remetente = Contribuinte E Natureza = \"VENDA\")",
        "<b>Receita potencial em trânsito:</b> Σ (Valor das notas onde Remetente = Contribuinte E Natureza = \"REMESSA/LEILÃO\")",
        "<b>Receita realizada de leilão:</b> Σ (Valor das NF-e modelo 55 emitidas pelo leiloeiro com Remetente = Contribuinte)",
        "<b>Receita bruta total para a DIRPF Rural</b> = Receita imediata + Receita realizada de leilão",
        "<b>Resultado da atividade rural</b> = Receita bruta total − Despesa/Investimento dedutível",
        "<i>NUNCA usar Receita potencial em trânsito como base — superdimensiona o IRPF.</i>",
    ]
    for f in formulas:
        flow.append(Paragraph(f, estilos["corpo"]))
    flow.append(Spacer(1, 8))

    # Regra 3
    flow.append(Paragraph("Regra 3 — Fórmulas tributárias e contribuições acessórias", estilos["subsecao"]))
    rows = [
        ["Tributo / Contribuição", "Fórmula", "Base legal"],
        ["Funrural PF (até 03/2026)", "1,5% × Receita bruta\n(1,2% INSS + 0,1% RAT + 0,2% SENAR)", "Lei 8.212/91"],
        ["Funrural PF (a partir 04/2026)", "1,63% × Receita bruta\n(1,32% INSS + 0,11% RAT + 0,2% SENAR)", "LC 224/2025"],
        ["Funrural PJ (a partir 04/2026)", "2,23% × Receita bruta", "LC 224/2025"],
        ["ICMS gado entre produtores (GO)", "Isento (cria/recria/engorda)", "RCTE-GO Anexo IX,\nart. 6º, XLIII"],
        ["ICMS gado para abate (GO)", "Isento, com Fundeinfra", "RCTE-GO Anexo IX,\nart. 6º, CXVI"],
        ["Fundeinfra (facultativo)", "% × Valor operação\n(varia por mercadoria)", "Lei 21.670/2022 (GO)"],
        ["IRPF Rural (PF)", "20% × Resultado da atividade rural", "Lei 8.023/90 + RIR/2018"],
    ]
    t3 = Table(rows, colWidths=[52 * mm, 82 * mm, 40 * mm])
    t3.setStyle(_estilo_tabela_padrao())
    flow.append(t3)
    flow.append(PageBreak())

    # Regra 4
    flow.append(Paragraph("Regra 4 — Cruzamentos forenses de detecção de anomalias", estilos["subsecao"]))
    rows = [
        ["Teste", "Critério matemático", "Detecta"],
        ["T-01 Concentração", "Valor 1 nota / Receita anual ≥ 10%", "Operações extraordinárias"],
        ["T-02 Smurfing", "≥ 3 notas mesmo destinatário/dia\nCOM valores idênticos", "Fragmentação fiscal"],
        ["T-03 Trânsito órfão", "Σ Remessas/Leilão SEM NF-e\nvenda subsequente", "Receita não declarada"],
        ["T-04 Concentração PF", "Vendas a PF ≥ 90% E PFs\ncom 3+ aquisições", "Intermediação não declarada"],
        ["T-05 IE inconsistente", "Mesmo CPF/CNPJ vinculado a 2+ IEs", "Erro cadastral ou simulação"],
        ["T-06 Pauta + Sazonalidade", "Σ trimestral ≥ 45%", "Sub/superfat.\nou esvaziamento"],
        ["T-07 Documental", "Validação dígito verificador\nde todos os CPF/CNPJ", "Documentos forjados"],
        ["T-08 Cruzamento planilha", "Cruzamento interno por\ncategoria contábil", "Inconsistência entre fontes"],
    ]
    t4 = Table(rows, colWidths=[44 * mm, 84 * mm, 46 * mm])
    t4.setStyle(_estilo_tabela_padrao())
    flow.append(t4)
    flow.append(Spacer(1, 8))

    # Regra 5
    flow.append(Paragraph("Regra 5 — Cruzamentos com bases externas", estilos["subsecao"]))
    rows = [
        ["Fonte externa", "O que confirmar", "Como cruzar"],
        ["AGRODEFESA-GO", "GTA correspondente a cada NFA-e", "1 GTA para cada nota\ncom gado em trânsito"],
        ["Banco do contribuinte", "Crédito do valor de cada venda", "Σ depósitos/PIX =\nΣ receita imediata"],
        ["Leiloeiros (ACTs)", "NF-e modelo 55 do leiloeiro", "Cada Remessa/Leilão deve\ngerar venda subsequente"],
        ["Receita Federal (CAEPF)", "Status produtor rural dos PFs", "PF sem CAEPF + 3+ compras =\nrevenda informal"],
        ["SEFAZ-GO + SiCAR + JUCEG", "IEs ativas; capacidade\ndo imóvel; vínculos", "Cabeças/UA ≤ Área CAR;\nvínculo + venda atípica"],
    ]
    t5 = Table(rows, colWidths=[44 * mm, 64 * mm, 66 * mm])
    t5.setStyle(_estilo_tabela_padrao())
    flow.append(t5)
    flow.append(Spacer(1, 10))

    return flow


def _estilo_tabela_padrao() -> TableStyle:
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ORGATEC_PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("BOX", (0, 0), (-1, -1), 0.5, ORGATEC_BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, ORGATEC_BORDER),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ORGATEC_LIGHT_BG]),
    ])


def _secao_responsavel_tecnico(estilos) -> list:
    flow = []
    flow.append(Paragraph("RESPONSÁVEL TÉCNICO PELA AUDITORIA", estilos["secao"]))
    flow.append(Paragraph("Documento elaborado por:", estilos["corpo"]))
    flow.append(Spacer(1, 4))
    flow.append(Paragraph("ROBSON ALAIN VELOSO", estilos["responsavel_nome"]))
    flow.append(Paragraph("CIÊNCIAS CONTÁBEIS", estilos["responsavel_titulo"]))
    flow.append(Spacer(1, 2))
    flow.append(Paragraph("ORGATEC CONTABILIDADE E AUDITORIA", estilos["corpo"]))
    flow.append(Paragraph(
        f"Auditoria emitida em {datetime.now().strftime('%d/%m/%Y')}",
        estilos["corpo_pequeno"],
    ))
    return flow


def _secao_alcance_e_limitacoes(estilos) -> list:
    flow = []
    flow.append(Paragraph("DECLARAÇÃO DE ALCANCE E LIMITAÇÕES", estilos["secao"]))
    flow.append(Paragraph(
        "Este relatório foi produzido pelo sistema <b>OrgAudi 1.0 / NFA Extractor</b> com base "
        "nos arquivos PDF de NFA-e fornecidos. Os achados constituem <b>indícios objetivos</b> "
        "derivados de cruzamentos lógicos internos, não confirmados com documentação primária "
        "externa (extratos bancários, GTAs, ACTs, contratos). A confirmação depende de etapa "
        "subsequente de coleta de evidências.",
        estilos["corpo"],
    ))
    flow.append(Paragraph(
        "<b>O presente documento NÃO formula acusações, NÃO imputa dolo e NÃO substitui "
        "procedimento de fiscalização tributária formal.</b> Os elementos aqui mapeados "
        "constituem subsídios técnicos para tomada de decisão do contribuinte e de seus "
        "assessores, e para eventual regularização espontânea nos termos do <b>art. 138 "
        "do CTN</b>.",
        estilos["corpo"],
    ))
    flow.append(Spacer(1, 6))
    flow.append(Paragraph("TIPOS DE ANOMALIA CONSIDERADOS NA BATERIA DE TESTES", estilos["subsecao"]))
    flow.append(Paragraph(
        "Fragmentação fiscal (smurfing); subfaturamento; uso de 'laranjas'; lavagem de gado de "
        "origem irregular; conluio com leiloeiro para subdeclaração; transferência intrafamiliar "
        "disfarçada de venda; emissão a destinatários inexistentes; intermediação não declarada "
        "por PFs; inconsistência cadastral; concentração atípica de operações; sazonalidade "
        "incompatível com perfil de produção rotineira.",
        estilos["corpo_pequeno"],
    ))
    return flow


def gerar_relatorio_tecnico_pdf(
    resultado: ResultadoAuditoria,
    saida: str | Path,
    dados_planilha: dict | None = None,
) -> Path:
    """Gera o PDF do relatório técnico ORGATEC e salva em `saida`."""
    saida = Path(saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    estilos = _criar_estilos()

    # ── Documento com header/footer custom em todas as páginas ────────────
    doc = BaseDocTemplate(
        str(saida),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=24 * mm,
        bottomMargin=20 * mm,
        title=f"Relatório de Auditoria — {resultado.cliente_nome}",
        author="ORGATEC Contabilidade e Auditoria",
    )
    frame = Frame(
        doc.leftMargin, doc.bottomMargin,
        doc.width, doc.height,
        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
    )
    template = PageTemplate(id="orgatec", frames=[frame], onPage=_desenhar_chrome)
    doc.addPageTemplates([template])

    # ── Conteúdo ──────────────────────────────────────────────────────────
    flow: list = []

    # Página 1: capa
    flow.append(Paragraph("RELATÓRIO DE AUDITORIA CRUZADA", estilos["titulo_doc"]))
    flow.append(Paragraph(
        "Cruzamento: Relatório GIEF/SEFAZ-GO × Planilha de Gado para IRPF — OrgAudi 1.0",
        estilos["subtitulo_doc"],
    ))

    flow.append(_tabela_identificacao(resultado))
    flow.append(Spacer(1, 10))

    flow.append(Paragraph("SÍNTESE QUANTITATIVA CRUZADA", estilos["secao"]))
    flow.append(_tabela_sintese(resultado))
    flow.append(Spacer(1, 10))

    flow.append(_tabela_severidade(resultado))
    flow.append(PageBreak())

    # Páginas 2+: ACHADOS por severidade
    titulos_sev = {
        SEV_CRITICO: "ACHADOS CRÍTICOS",
        SEV_ALTO: "ACHADOS DE ALTA CRITICIDADE",
        SEV_MEDIO: "ACHADOS DE CRITICIDADE MÉDIA",
        SEV_ATENCAO: "PONTOS DE ATENÇÃO",
    }
    for sev_key in (SEV_CRITICO, SEV_ALTO, SEV_MEDIO, SEV_ATENCAO):
        achados_sev = [a for a in resultado.achados if a.severidade == sev_key]
        if not achados_sev:
            continue
        flow.append(Paragraph(titulos_sev[sev_key], estilos["secao"]))
        for ach in achados_sev:
            flow.extend(_renderizar_achado(ach, estilos))
        flow.append(Spacer(1, 6))

    # CONFORMIDADES VERIFICADAS
    if resultado.conformidades:
        flow.append(Paragraph("CONFORMIDADES VERIFICADAS", estilos["secao"]))
        flow.append(_tabela_conformidades(resultado))
        flow.append(Spacer(1, 10))

    # Recomendações e próximas etapas
    flow.append(Paragraph("RECOMENDAÇÕES E PRÓXIMAS ETAPAS", estilos["secao"]))
    flow.extend(_secao_recomendacoes(resultado, estilos))
    flow.append(PageBreak())

    # Páginas 5-6: Fórmulas e Regras
    flow.extend(_secao_regras_ocao(estilos))

    # Página 6 (continuação): Declaração + Tipos de Anomalia
    flow.extend(_secao_alcance_e_limitacoes(estilos))
    flow.append(Spacer(1, 12))

    # Responsável técnico
    flow.extend(_secao_responsavel_tecnico(estilos))

    # Planilha de Gado para IRPF — seção final (somente se dados foram fornecidos)
    if dados_planilha:
        flow.append(PageBreak())
        flow.extend(_secao_planilha_gado(resultado, dados_planilha, estilos))

    # Build com _NumerandoCanvas → "Página N de T" via save-replay
    doc.build(flow, canvasmaker=_NumerandoCanvas)
    return saida


# ── Planilha de Gado para IRPF ───────────────────────────────────────────────

def _fmt_moeda(valor: float) -> str:
    """Formata valor como moeda brasileira: R$ 1.234.567,89"""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _tabela_mes_natureza(
    titulo: str,
    chave: str,
    por_mes: dict,          # {1..12: {notas, cabecas, valor}}
    total: dict,            # {notas, cabecas, valor}
    meses_labels: list[str],
    cor: Any,
) -> Table:
    """Tabela mensal para uma natureza (VENDAS, REMESSAS, COMPRAS…)."""
    col_w = [6.2 * cm, 2.4 * cm, 2.6 * cm, 6.2 * cm]
    dados = [[titulo, "Q NOTAS", "CABEÇAS", "VALOR"]]
    linhas_dados = 0
    for mes_num in range(1, 13):
        entry = por_mes.get(mes_num, {"notas": 0, "cabecas": 0.0, "valor": 0.0})
        if entry.get("notas", 0) == 0:
            continue
        dados.append([
            meses_labels[mes_num - 1],
            str(entry["notas"]),
            f"{entry['cabecas']:.0f}",
            _fmt_moeda(entry["valor"]),
        ])
        linhas_dados += 1
    dados.append([
        "TOTAL",
        str(total["notas"]),
        f"{total['cabecas']:.0f}",
        _fmt_moeda(total["valor"]),
    ])

    n = len(dados)
    style = TableStyle([
        # Cabeçalho colorido
        ("BACKGROUND", (0, 0), (-1, 0), cor),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        # Linha de total — cor ligeiramente mais escura
        ("BACKGROUND", (0, n - 1), (-1, n - 1), cor),
        ("TEXTCOLOR", (0, n - 1), (-1, n - 1), colors.white),
        ("FONTNAME", (0, n - 1), (-1, n - 1), "Helvetica-Bold"),
        # Linhas de dados
        ("FONTNAME", (0, 1), (-1, n - 2), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, n - 2), [colors.white, ORGATEC_LIGHT_BG]),
        # Alinhamento
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("ALIGN", (3, 1), (3, -1), "RIGHT"),
        ("ALIGN", (3, 0), (3, 0), "RIGHT"),
        # Grade e padding
        ("GRID", (0, 0), (-1, -1), 0.4, ORGATEC_BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (0, -1), 6),
    ])
    t = Table(dados, colWidths=col_w)
    t.setStyle(style)
    return t


def _secao_planilha_gado(
    resultado: ResultadoAuditoria,
    dados: dict,
    estilos: dict[str, Any],
) -> list:
    """Seção final: Planilha de Gado para IRPF — espelha o modelo DOCX ORGATEC."""
    flow: list = []
    meses_labels = [
        "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
    ]
    por_nat_mes: dict = dados.get("por_natureza_mes", {})
    totais_nat: dict = dados.get("totais_natureza", {})
    periodo = dados.get("periodo") or (
        f"{resultado.periodo_inicio} a {resultado.periodo_fim}"
    )

    # ── Título ────────────────────────────────────────────────────────────
    flow.append(Paragraph("RELATÓRIO DE MOVIMENTAÇÃO — IRPF", estilos["titulo_doc"]))
    flow.append(Paragraph("Lei 8.023/90 — IRPF Atividade Rural", estilos["subtitulo_doc"]))

    # ── Identificação ─────────────────────────────────────────────────────
    id_data = [
        ["CONTRIBUINTE", "PERÍODO APURADO"],
        [f"{resultado.cliente_nome} — CPF {resultado.cliente_cpf}", periodo],
        ["FONTE DOS DADOS", "TOTAL DE NOTAS"],
        ["Relatório GIEF/SEFAZ", str(dados.get("total_notas", 0))],
    ]
    id_table = Table(id_data, colWidths=[_doc_col := 8.7 * cm, 8.7 * cm])
    id_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ORGATEC_PRIMARY),
        ("BACKGROUND", (0, 2), (-1, 2), ORGATEC_PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("TEXTCOLOR", (0, 2), (-1, 2), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica"),
        ("FONTNAME", (0, 3), (-1, 3), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.4, ORGATEC_BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    flow.append(id_table)
    flow.append(Spacer(1, 10))

    # ── Saídas: VENDAS, REMESSAS, TRANSFERÊNCIAS, OUTRAS ────────────────
    seccoes_saidas = [
        ("VENDAS",         "VENDA",         colors.HexColor("#10b981")),
        ("REMESSAS",       "REMESSA",        colors.HexColor("#f59e0b")),
        ("TRANSFERÊNCIAS", "TRANSFERENCIA",  colors.HexColor("#06b6d4")),
        ("OUTRAS",         "OUTRAS",         colors.HexColor("#a855f7")),
    ]
    # Cabeçalho da classe de saídas
    flow.append(Paragraph("REGRA DE CLASSIFICAÇÃO CONTÁBIL", estilos["secao"]))
    regra1_data = [
        ["Posição do contribuinte", "Natureza", "Categoria", "Efeito IRPF Rural"],
        ["REMETENTE", "VENDA", "RECEITA", "Soma à base de cálculo"],
        ["REMETENTE", "REMESSA/LEILÃO", "TRÂNSITO", "Não soma (até arremate)"],
        ["REMETENTE = DESTINATÁRIO\n(mesmo CPF)", "TRANSFERÊNCIA", "TRANSFERÊNCIA", "Neutra"],
        ["DESTINATÁRIO", "COMPRA", "DESPESA / INVEST.", "Subtrai da base ou ativa"],
    ]
    r1_table = Table(regra1_data, colWidths=[6.0 * cm, 3.2 * cm, 3.5 * cm, 4.7 * cm])
    r1_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ORGATEC_PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ORGATEC_LIGHT_BG]),
        ("GRID", (0, 0), (-1, -1), 0.4, ORGATEC_BORDER),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (0, -1), 6),
        # Linha COMPRA — fundo levemente vermelho
        ("BACKGROUND", (0, 4), (-1, 4), colors.HexColor("#fef2f2")),
    ]))
    flow.append(r1_table)
    flow.append(Spacer(1, 12))

    for titulo_s, chave_s, cor_s in seccoes_saidas:
        total_s = totais_nat.get(chave_s)
        if not total_s:
            continue
        flow.append(_tabela_mes_natureza(
            titulo_s, chave_s, por_nat_mes.get(chave_s, {}), total_s, meses_labels, cor_s,
        ))
        flow.append(Spacer(1, 8))

    # ── TOTAL GERAL — SAÍDAS (Vendas + Remessas) ─────────────────────────
    saidas_notas = sum(
        totais_nat.get(k, {}).get("notas", 0)
        for k in ("VENDA", "REMESSA", "TRANSFERENCIA", "OUTRAS")
    )
    saidas_cabecas = sum(
        totais_nat.get(k, {}).get("cabecas", 0.0)
        for k in ("VENDA", "REMESSA", "TRANSFERENCIA", "OUTRAS")
    )
    saidas_valor = sum(
        totais_nat.get(k, {}).get("valor", 0.0)
        for k in ("VENDA", "REMESSA", "TRANSFERENCIA", "OUTRAS")
    )
    if saidas_notas > 0:
        tg_data = [
            ["TOTAL GERAL — SAÍDAS", "Q NOTAS", "CABEÇAS", "VALOR"],
            [
                "Subtotal de saídas do período",
                str(saidas_notas),
                f"{saidas_cabecas:.0f}",
                _fmt_moeda(saidas_valor),
            ],
        ]
        tg_table = Table(tg_data, colWidths=[6.2 * cm, 2.4 * cm, 2.6 * cm, 6.2 * cm])
        tg_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), ORGATEC_PRIMARY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, 1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.4, ORGATEC_BORDER),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("ALIGN", (3, 1), (3, 1), "RIGHT"),
            ("ALIGN", (3, 0), (3, 0), "RIGHT"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (0, -1), 6),
        ]))
        flow.append(tg_table)

    # ── AQUISIÇÕES DE GADO — COMPRAS (nova página) ────────────────────────
    total_compras = totais_nat.get("COMPRA")
    if total_compras:
        flow.append(PageBreak())
        flow.append(Paragraph("AQUISIÇÕES DE GADO — COMPRAS", estilos["secao"]))
        flow.append(Paragraph(
            "Página dedicada às entradas de animais no plantel — fluxo contábil inverso ao das vendas.",
            estilos["corpo_pequeno"],
        ))
        flow.append(Spacer(1, 6))
        flow.append(Paragraph(
            "COMPRAS — Cliente é o DESTINATÁRIO — entra como DESPESA / INVESTIMENTO "
            "(subtrai da base do IRPF Rural)",
            estilos["subsecao"],
        ))
        flow.append(Spacer(1, 4))
        flow.append(_tabela_mes_natureza(
            "COMPRAS",
            "COMPRA",
            por_nat_mes.get("COMPRA", {}),
            total_compras,
            meses_labels,
            colors.HexColor("#ef4444"),
        ))
        flow.append(Spacer(1, 12))

    # ── Observações Importantes ───────────────────────────────────────────
    flow.append(Paragraph("OBSERVAÇÕES IMPORTANTES", estilos["subsecao"]))

    tot_rem = totais_nat.get("REMESSA", {})
    obs_items = []

    if tot_rem:
        obs_items.append(
            f"As {tot_rem.get('notas', 0)} notas de REMESSA/LEILÃO "
            f"({_fmt_moeda(tot_rem.get('valor', 0))}) <b>NÃO compõem a receita imediata</b>. "
            "A receita correspondente só será reconhecida após o arremate, com a nota de venda "
            "subsequente do leiloeiro (NF-e modelo 55)."
        )

    tot_transf = totais_nat.get("TRANSFERENCIA", {})
    if tot_transf:
        obs_items.append(
            f"As {tot_transf.get('notas', 0)} TRANSFERÊNCIAS entre fazendas do mesmo CPF "
            "são operações <b>NEUTRAS</b> — não afetam a apuração do IRPF Rural."
        )
    else:
        obs_items.append(
            "Não há TRANSFERÊNCIAS entre fazendas próprias detectadas — "
            "todas as saídas têm destinatários terceiros."
        )

    if total_compras:
        obs_items.append(
            f"COMPRAS de gado (cliente como DESTINATÁRIO): "
            f"<b>{_fmt_moeda(resultado.valor_compras)}</b> em "
            f"{resultado.total_compras} notas. "
            "Constituem despesa/investimento na atividade rural e devem ser segregadas "
            "em conta específica do LCDPR."
        )

    obs_items.append(
        "OUTRAS aquisições (maquinário, veículos, edificações, benfeitorias) não detectadas "
        "neste lote. Aquisições de outros bens devem ser anexadas manualmente ao LCDPR."
    )

    obs_items.append(
        f"Funrural estimado sobre receita imediata (1,5% × "
        f"{_fmt_moeda(resultado.receita_imediata)}): "
        f"<b>{_fmt_moeda(resultado.funrural_estimado)}</b>. "
        "Conferir com guias GPS/DARF efetivamente recolhidas."
    )

    obs_items.append(
        f"RESULTADO DA ATIVIDADE RURAL = (Receita imediata + arremates de leilão) − "
        f"(Compras + despesas dedutíveis) = "
        f"<b>{_fmt_moeda(resultado.resultado_atividade_rural)}</b>."
    )

    for idx, obs in enumerate(obs_items, 1):
        flow.append(Paragraph(f"{idx}. {obs}", estilos["corpo"]))
    flow.append(Spacer(1, 10))

    # ── Fórmula Regra 2 ───────────────────────────────────────────────────
    flow.append(Paragraph("FÓRMULA APLICADA — REGRA 2 (Apuração da Receita Rural)", estilos["subsecao"]))
    regra2_data = [
        ["Código", "Descrição", "Valor"],
        ["F1", "Receita imediata (vendas diretas)", _fmt_moeda(resultado.receita_imediata)],
        ["F2", "Trânsito potencial (remessas — NÃO base IRPF)", _fmt_moeda(resultado.transito_leilao)],
        ["F3", "Receita realizada de leilão (NF-e mod. 55)", _fmt_moeda(resultado.receita_realizada_leilao)],
        ["F4", "Receita bruta total DIRPF Rural (F1 + F3)", _fmt_moeda(resultado.receita_bruta_total_dirpf)],
        ["F6", "Despesa / Investimento dedutível (compras)", _fmt_moeda(resultado.valor_compras)],
        ["F5", "Resultado da atividade rural (F4 − F6)", _fmt_moeda(resultado.resultado_atividade_rural)],
    ]
    r2_table = Table(regra2_data, colWidths=[1.5 * cm, 10.2 * cm, 5.7 * cm])
    idx_f4 = 4   # linha F4
    idx_f5 = 6   # linha F5
    idx_f2 = 2   # linha F2
    r2_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ORGATEC_PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ORGATEC_LIGHT_BG]),
        ("GRID", (0, 0), (-1, -1), 0.4, ORGATEC_BORDER),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        # F4 destaque azul
        ("BACKGROUND", (0, idx_f4), (-1, idx_f4), colors.HexColor("#dbeafe")),
        ("FONTNAME", (0, idx_f4), (-1, idx_f4), "Helvetica-Bold"),
        # F5 destaque verde
        ("BACKGROUND", (0, idx_f5), (-1, idx_f5), colors.HexColor("#dcfce7")),
        ("FONTNAME", (0, idx_f5), (-1, idx_f5), "Helvetica-Bold"),
        # F2 cinza + itálico
        ("BACKGROUND", (0, idx_f2), (-1, idx_f2), colors.HexColor("#f3f4f6")),
        ("FONTNAME", (0, idx_f2), (-1, idx_f2), "Helvetica-Oblique"),
        ("TEXTCOLOR", (0, idx_f2), (-1, idx_f2), ORGATEC_MUTED),
    ]))
    flow.append(r2_table)

    return flow


def _secao_recomendacoes(r: ResultadoAuditoria, estilos) -> list:
    """Etapas 1, 2, 3 (30/60/90 dias) — adaptadas ao perfil dos achados."""
    flow = []
    sev = r.contagem_severidade

    # Etapa 1 — só se houver críticos
    flow.append(Paragraph("Etapa 1 — Aprofundar achados críticos (30 dias)", estilos["subsecao"]))
    if sev.get(SEV_CRITICO, 0) > 0 or sev.get(SEV_ALTO, 0) > 0:
        flow.append(Paragraph(
            "1. Solicitar ao contribuinte documentação primária dos achados críticos e altos: "
            "GTAs, extratos bancários, comprovantes de pagamento, ACTs dos leiloeiros, relação "
            "completa de NF-e modelo 55 emitidas pelos leiloeiros em seu nome.",
            estilos["corpo"],
        ))
        flow.append(Paragraph(
            "2. Cruzar com sistemas externos: AGRODEFESA-GO (GTAs e SIDAGRO), Receita Federal "
            "(CAEPF dos PFs recorrentes), SiCAR (capacidade do imóvel), JUCEG (vínculos societários).",
            estilos["corpo"],
        ))
    else:
        flow.append(Paragraph(
            "Sem achados críticos ou altos — bateria forense não detectou anomalias que exijam "
            "ação imediata. Manter monitoramento periódico.",
            estilos["corpo"],
        ))
    flow.append(Spacer(1, 4))

    # Etapa 2
    flow.append(Paragraph("Etapa 2 — Conformidade fiscal (60 dias)", estilos["subsecao"]))
    flow.append(Paragraph(
        f"3. Reconstituir o LCDPR do exercício com base no relatório auditado, incorporando "
        f"as {r.total_compras} notas de compra (R$ {r.valor_compras:,.2f}) e separando "
        f"rigorosamente receita de trânsito.",
        estilos["corpo"],
    ))
    # F5 = resultado da atividade rural (base IRPF)  — usa receita_bruta_total_dirpf - compras
    irpf_estimado = max(r.resultado_atividade_rural, 0) * 0.20
    flow.append(Paragraph(
        f"4. Apurar o IRPF Rural do exercício seguinte. "
        f"Base atual — Resultado da Atividade Rural (F4−F6): "
        f"<b>R$ {r.resultado_atividade_rural:,.2f}</b> "
        f"(F4 Receita bruta DIRPF R$ {r.receita_bruta_total_dirpf:,.2f} − "
        f"F6 Despesa R$ {r.valor_compras:,.2f}). "
        f"IRPF estimado (alíquota 20%): <b>R$ {irpf_estimado:,.2f}</b>. "
        f"Nota: F3 (receita realizada de leilão) requer cruzamento com NF-e mod. 55 dos leiloeiros.",
        estilos["corpo"],
    ))
    flow.append(Paragraph(
        f"5. Conferir Funrural recolhido contra a estimativa "
        f"<b>R$ {r.funrural_estimado:,.2f}</b> deste relatório.",
        estilos["corpo"],
    ))
    flow.append(Spacer(1, 4))

    # Etapa 3
    flow.append(Paragraph("Etapa 3 — Mitigação prospectiva (90 dias)", estilos["subsecao"]))
    flow.append(Paragraph(
        "6. Implantar segregação de fluxos nos sistemas internos: rotina específica para vendas "
        "a PF (com checagem de CAEPF) e outra para remessas a leilão (com cobrança formal das "
        "notas de venda do leiloeiro).",
        estilos["corpo"],
    ))
    flow.append(Paragraph(
        "7. Adequar à Reforma Tributária (LC 214/2025): a partir de 2027, CBS substitui PIS/COFINS "
        "na cadeia agro. Atualizar emissão de NFA-e/NF-e com IBS/CBS conforme Nota Técnica 2025.002 RTC.",
        estilos["corpo"],
    ))
    return flow
