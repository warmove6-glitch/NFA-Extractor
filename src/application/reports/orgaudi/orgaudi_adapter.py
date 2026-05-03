"""
═══════════════════════════════════════════════════════════════════════════════
  Adapter: nfa-repo NFA  →  OrgAudi NotaFiscal
  ORGATEC CONTABILIDADE E AUDITORIA
═══════════════════════════════════════════════════════════════════════════════

Converte as notas extraídas pelo `nfa-repo` (Pydantic NFA) para o modelo
de auditoria forense `orgaudi_v4.NotaFiscal` e gera o laudo PDF de 11 páginas.

Uso:
    from src.application.reports.orgaudi import gerar_laudo_orgaudi

    pdf_path = gerar_laudo_orgaudi(
        notas=all_notas,                    # list[NFA]
        cliente_nome="Genis Carlos",
        cliente_cpf="019.925.771-02",
        saida=Path("data/laudos/Laudo_xxx.pdf"),
        veredito_ia=veredito_claude,         # opcional — texto do squad
    )
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from .orgaudi_v4 import (
    Achado,
    Contribuinte,
    LaudoOrgAudi,
    NaturezaNota,
    NotaFiscal,
    Periodo,
    Severidade,
)

logger = logging.getLogger(__name__)


# ─── Mapeamento natureza nfa-repo → OrgAudi ───────────────────────────────────
NATUREZA_MAP = {
    "VENDA":         NaturezaNota.VENDA,
    "REMESSA":       NaturezaNota.REMESSA,
    "LEILAO":        NaturezaNota.LEILAO,
    "LEILÃO":        NaturezaNota.LEILAO,
    "COMPRA":        NaturezaNota.COMPRA,
    "TRANSFERENCIA": NaturezaNota.TRANSFERENCIA,
    "OUTRAS":        NaturezaNota.REMESSA,   # mais conservador (não conta como receita)
}


def _parse_data(s: str | date | None) -> date:
    """Aceita 'DD/MM/YYYY', 'YYYY-MM-DD' ou date. Default: hoje."""
    if isinstance(s, date) and not isinstance(s, datetime):
        return s
    if isinstance(s, datetime):
        return s.date()
    if not s:
        return date.today()
    s = str(s).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    logger.warning("Data nao parseavel: %r — usando hoje", s)
    return date.today()


def _normalizar_doc(doc: str | None) -> str:
    """Remove pontuação de CPF/CNPJ. Retorna string limpa (11 ou 14 dígitos)."""
    if not doc:
        return ""
    return re.sub(r"\D", "", str(doc))


def _converter_nota(nfa: Any) -> NotaFiscal:
    """
    Converte uma NFA (Pydantic do nfa-repo) em NotaFiscal (OrgAudi).
    Aceita também ProdutoModel/dict com os mesmos campos.
    """
    # Suporta tanto Pydantic quanto dict
    def g(obj, *keys, default=""):
        for k in keys:
            if isinstance(obj, dict):
                if k in obj and obj[k] is not None:
                    return obj[k]
            else:
                v = getattr(obj, k, None)
                if v is not None and v != "":
                    return v
        return default

    # Quantidade total de cabeças (soma dos produtos)
    cabecas = 0
    produtos = g(nfa, "produtos", default=[])
    if produtos:
        try:
            cabecas = int(sum(float(g(p, "quantidade", default=0)) for p in produtos))
        except (TypeError, ValueError):
            cabecas = 0
    if not cabecas:
        try:
            cabecas = int(float(g(nfa, "quantidade_total", default=0)))
        except (TypeError, ValueError):
            cabecas = 0

    natureza_str = str(g(nfa, "natureza", default="OUTRAS")).upper()
    natureza = NATUREZA_MAP.get(natureza_str, NaturezaNota.REMESSA)

    rem = g(nfa, "remetente", default=None)
    dest = g(nfa, "destinatario", default=None)

    valor = g(nfa, "valor_total", default=0)
    try:
        valor_dec = Decimal(str(valor)).quantize(Decimal("0.01"))
    except Exception:
        valor_dec = Decimal("0")

    return NotaFiscal(
        numero=str(g(nfa, "numero", default="?")),
        data=_parse_data(g(nfa, "emissao", default=None)),
        natureza=natureza,
        valor=valor_dec,
        cabecas=cabecas,
        remetente_cpf=_normalizar_doc(g(rem, "cpf_cnpj", default="")),
        remetente_nome=str(g(rem, "nome", default="")),
        destinatario_cpf=_normalizar_doc(g(dest, "cpf_cnpj", default="")),
        destinatario_nome=str(g(dest, "nome", default="")),
    )


def _periodo_a_partir_de_notas(notas: list[NotaFiscal]) -> Periodo:
    """Calcula o período (min/max) a partir das datas das notas."""
    if not notas:
        hoje = date.today()
        return Periodo(inicio=date(hoje.year, 1, 1), fim=hoje)
    datas = [n.data for n in notas]
    return Periodo(inicio=min(datas), fim=max(datas))


def _fallback_cpf(cpf_raw: str | None, notas: list[NotaFiscal]) -> str:
    """
    Resolve o CPF do contribuinte para a Regra 1 do OrgAudi.

    Regra: o CPF precisa casar com remetente OU destinatário das notas para que
    a classificação contábil (RECEITA/TRÂNSITO/DESPESA) funcione. Se o CPF
    passado não aparece em NENHUMA nota (e.g. CPF fictício de teste), usa o
    documento mais frequente — pode ser CPF (11) ou CNPJ (14).
    """
    from collections import Counter
    cpf = _normalizar_doc(cpf_raw)

    # Conta TODOS os documentos (CPF 11 ou CNPJ 14) que aparecem nas notas
    cnt: Counter[str] = Counter()
    for n in notas:
        for c in (n.remetente_cpf, n.destinatario_cpf):
            cn = _normalizar_doc(c)
            if len(cn) in (11, 14):
                cnt[cn] += 1

    # Se o CPF passado é válido E aparece nas notas → usa ele
    if len(cpf) in (11, 14) and cpf in cnt:
        return cpf

    # Caso contrário, usa o documento mais frequente (provavelmente o contribuinte)
    if cnt:
        doc_top, freq = cnt.most_common(1)[0]
        logger.info(
            "CPF do contribuinte (%s) nao casa com notas; usando doc mais frequente "
            "%s (%d ocorrencias)",
            cpf or "vazio", doc_top, freq,
        )
        return doc_top

    return cpf or "00000000000"


def gerar_laudo_orgaudi(
    notas: list[Any],
    cliente_nome: str,
    cliente_cpf: str,
    saida: str | Path,
    veredito_ia: str | None = None,
    municipio: str = "",
    estado: str = "GO",
    ie: str = "",
) -> Path:
    """
    Gera laudo OrgAudi 1.0 (PDF de 11 páginas) a partir das NFAs extraídas
    pelo nfa-repo.

    Args:
        notas: lista de objetos NFA (do nfa-repo) ou dicts compatíveis.
        cliente_nome: nome do contribuinte.
        cliente_cpf: CPF do contribuinte (com ou sem máscara).
        saida: caminho do PDF de saída.
        veredito_ia: parecer textual do squad Claude (opcional). Se fornecido,
            será adicionado como achado de auditoria narrativa (severidade ATENÇÃO).
        municipio, estado, ie: dados opcionais do contribuinte.

    Returns:
        Path do PDF gerado.
    """
    saida = Path(saida)
    saida.parent.mkdir(parents=True, exist_ok=True)

    # 1) Converte notas
    notas_oa: list[NotaFiscal] = []
    for n in notas:
        try:
            notas_oa.append(_converter_nota(n))
        except Exception as exc:
            logger.warning("Nota ignorada na conversao OrgAudi: %s", exc)

    if not notas_oa:
        raise ValueError("Nenhuma nota convertida com sucesso para OrgAudi.")

    # 2) Resolve CPF (fallback se nao foi passado)
    cpf_final = _fallback_cpf(cliente_cpf, notas_oa)

    # 3) Monta contribuinte e periodo
    contribuinte = Contribuinte(
        nome=cliente_nome or "Contribuinte",
        cpf=cpf_final,
        ie=ie,
        municipio=municipio,
        estado=estado,
    )
    periodo = _periodo_a_partir_de_notas(notas_oa)

    # 4) Cria o laudo
    laudo = LaudoOrgAudi(
        contribuinte=contribuinte,
        periodo=periodo,
        notas=notas_oa,
    )
    laudo.processar()

    # 5) Anexa o veredito Claude como achado narrativo (se fornecido)
    if veredito_ia and veredito_ia.strip():
        # Limita o texto para nao explodir o PDF
        veredito_curto = veredito_ia.strip()[:5000]
        achado_ia = Achado(
            codigo="IA-01",
            titulo="Parecer interpretativo — Squad Horizon-Blue (Claude Sonnet 4.6)",
            descricao=(
                "<b>Análise multiagente</b> realizada por @Contador, @Fiscalista, "
                "@Jurista e @Rurista. Texto integral abaixo:<br/><br/>"
                + veredito_curto.replace("\n", "<br/>")
            ),
            severidade=Severidade.ATENCAO,
        )
        laudo.achados.append(achado_ia)

    # 6) Gera PDF
    laudo.gerar_pdf(str(saida))
    logger.info(
        "OrgAudi laudo gerado: %s | %s notas | %s achados | hash=%s",
        saida.name, len(notas_oa), len(laudo.achados), laudo.hash_doc,
    )
    return saida
