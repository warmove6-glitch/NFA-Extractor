"""
Parser XML universal — NFSe · NF-e · NFA (Nota Fiscal Agropecuária).

Detecta automaticamente o tipo de nota, remove assinatura digital X.509
e extrai apenas os campos relevantes para auditoria fiscal.

Economia de tokens:
  XML bruto       → ~1.500 tokens  (inclui cert. X.509)
  XML sem assin.  → ~583  tokens
  Resumo auditoria→ ~109  tokens   ← padrão usado pelos agentes
"""
from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from typing import Optional
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)

# ── Namespaces reconhecidos ───────────────────────────────────────────────────
NS = {
    "nfse": "http://www.sped.fazenda.gov.br/nfse",
    "nfe":  "http://www.portalfiscal.inf.br/nfe",
    "nfa":  "http://www.fazenda.gov.br/nfa",          # NFA federal (MAPA)
    "sig":  "http://www.w3.org/2000/09/xmldsig#",
}

# ── Schemas de produto/serviço suportados ────────────────────────────────────
TIPO_NFSE = "NFSe"   # Nota Fiscal de Serviços
TIPO_NFE  = "NF-e"   # Nota Fiscal Eletrônica (mercadorias)
TIPO_NFA  = "NFA"    # Nota Fiscal Agropecuária
TIPO_DESCONHECIDO = "Desconhecido"


# ── Modelo de saída ───────────────────────────────────────────────────────────
@dataclass
class ItemNota:
    codigo:      str   = ""
    descricao:   str   = ""
    quantidade:  float = 0.0
    vlr_unitario:float = 0.0
    vlr_total:   float = 0.0
    unidade:     str   = ""


@dataclass
class NotaFiscalXML:
    """Representação unificada de qualquer nota fiscal eletrônica."""
    tipo:           str = TIPO_DESCONHECIDO   # NFSe | NF-e | NFA
    numero:         str = ""
    serie:          str = ""
    data_emissao:   str = ""
    municipio:      str = ""
    uf:             str = ""

    # Partes
    emitente_nome:  str = ""
    emitente_doc:   str = ""   # CNPJ/CPF
    emitente_ie:    str = ""   # IE ou IM
    emitente_regime:str = ""   # Simples / Lucro Presumido / Real

    tomador_nome:   str = ""
    tomador_doc:    str = ""

    # Valores
    valor_total:    float = 0.0
    valor_bc:       float = 0.0
    valor_imposto:  float = 0.0
    aliquota:       float = 0.0
    tipo_imposto:   str   = ""  # ICMS | ISS/ISSQN | IPI

    # Natureza / serviço
    natureza:       str = ""
    codigo_fiscal:  str = ""   # CFOP ou cTribNac

    itens: list[ItemNota] = field(default_factory=list)

    # Tokens estimados do resumo
    tokens_resumo: int = 0

    def resumo_auditoria(self, modo: str = "resumido") -> str:
        """
        Gera texto para os agentes.

        Modos:
          'resumido'  → ~100–130 tokens (padrão, suficiente para análise)
          'completo'  → todos os campos incluindo itens
        """
        imp = f"{self.tipo_imposto} {self.aliquota:.2f}% = R${self.valor_imposto:,.2f}"
        linhas = [
            f"{self.tipo} {self.numero} | {self.data_emissao} | {self.municipio}/{self.uf}",
            f"Emitente : {self.emitente_nome} ({self.emitente_doc})"
            + (f" | IE/IM: {self.emitente_ie}" if self.emitente_ie else "")
            + (f" | {self.emitente_regime}" if self.emitente_regime else ""),
            f"Tomador  : {self.tomador_nome} ({self.tomador_doc})",
            f"Natureza : [{self.codigo_fiscal}] {self.natureza[:120]}",
            f"Valores  : Total R${self.valor_total:,.2f} | BC R${self.valor_bc:,.2f} | {imp}",
        ]
        if modo == "completo" and self.itens:
            linhas.append(f"Itens ({len(self.itens)}):")
            for it in self.itens[:20]:   # máx 20 itens
                linhas.append(
                    f"  - {it.descricao[:60]} | Qtd: {it.quantidade} {it.unidade}"
                    f" | Unit: R${it.vlr_unitario:,.2f} | Total: R${it.vlr_total:,.2f}"
                )
        return "\n".join(linhas)


# ── Helpers ───────────────────────────────────────────────────────────────────
def _txt(el: Optional[ET.Element], path: str, ns_key: str = "") -> str:
    """Busca texto de um sub-elemento; retorna '' se não encontrado.

    O path pode usar prefixo 'n:' — será mapeado para o namespace indicado por ns_key.
    Exemplo: _txt(el, 'n:xNome', 'nfse')  → procura {http://www.sped...}xNome
    """
    if el is None:
        return ""
    # Mapeia sempre sob o alias 'n' para que os paths 'n:...' funcionem
    ns = {"n": NS[ns_key]} if ns_key and ns_key in NS else {}
    found = el.find(path, ns) if ns else el.find(path)
    return (found.text or "").strip() if found is not None else ""


def _float(v: str) -> float:
    try:
        return float(v.replace(",", "."))
    except Exception:
        return 0.0


def _regime_simples(codigo: str) -> str:
    mapa = {"1": "Simples Nacional", "2": "Simples Nacional — excesso receita",
            "3": "Simples Nacional", "4": "Lucro Presumido", "5": "Lucro Real"}
    return mapa.get(codigo, "")


def _remover_assinatura(xml_texto: str) -> str:
    """Remove bloco <Signature>...</Signature> (X.509) — economiza ~60% tokens."""
    return re.sub(r"<Signature[^>]*>.*?</Signature>", "", xml_texto,
                  flags=re.DOTALL | re.IGNORECASE).strip()


def _detectar_tipo(root: ET.Element) -> str:
    tag = root.tag.lower()
    if "nfse" in tag or "nfse" in root.get("xmlns", "").lower():
        return TIPO_NFSE
    if "nfe"  in tag or "portalfiscal" in root.get("xmlns", "").lower():
        return TIPO_NFE
    if "nfa"  in tag:
        return TIPO_NFA
    # verifica filho raiz
    primeiro = list(root)
    if primeiro:
        child_tag = primeiro[0].tag.lower()
        if "nfse" in child_tag:
            return TIPO_NFSE
        if "nfe"  in child_tag or "infnfe" in child_tag:
            return TIPO_NFE
        if "nfa"  in child_tag:
            return TIPO_NFA
    return TIPO_DESCONHECIDO


# ── Parsers por tipo ──────────────────────────────────────────────────────────

def _first(root: ET.Element, *xpaths: str) -> Optional[ET.Element]:
    """Retorna o primeiro elemento encontrado dentre os xpaths fornecidos."""
    for xpath in xpaths:
        el = root.find(xpath)
        if el is not None:
            return el
    return None


def _find_el(root: ET.Element, tag: str, ns_key: str = "nfse") -> Optional[ET.Element]:
    """Busca elemento por tag com namespace e depois sem, retornando o primeiro achado."""
    ns = {"n": NS[ns_key]} if ns_key in NS else {}
    found = root.find(f".//n:{tag}", ns) if ns else None
    if found is None:
        found = root.find(f".//{tag}")
    return found


def _parse_nfse(root: ET.Element) -> NotaFiscalXML:
    """Parser para NFSe — namespace SPED/SEFAZ."""
    nota = NotaFiscalXML(tipo=TIPO_NFSE)
    ns   = {"n": NS["nfse"]}

    def f(tag: str) -> str:
        el = _find_el(root, tag, "nfse")
        return (el.text or "").strip() if el is not None else ""

    def _el(parent: ET.Element, tag: str) -> str:
        """Busca tag em parent: primeiro com ns, depois sem."""
        found = parent.find(f"n:{tag}", ns)
        if found is None:
            found = parent.find(tag)
        return (found.text or "").strip() if found is not None else ""

    nota.numero       = f("nNFSe")
    nota.serie        = f("serie")
    nota.data_emissao = f("dhEmi")[:10]
    loc_emi           = f("xLocEmi")
    nota.municipio    = loc_emi.split(" - ")[0]
    nota.uf           = loc_emi.split(" - ")[-1] if " - " in loc_emi else ""

    # ── Emitente (scoped a <emit>) ────────────────────────────────────────────
    emit_el = root.find(".//n:emit", ns)
    if emit_el is None:
        emit_el = root.find(".//emit")
    if emit_el is not None:
        nota.emitente_nome = _el(emit_el, "xNome") or _el(emit_el, "xFant")
        nota.emitente_doc  = _el(emit_el, "CNPJ")
        nota.emitente_ie   = _el(emit_el, "IM")

    # ── Regime tributário (dentro de <prest>) ─────────────────────────────────
    nota.emitente_regime = _regime_simples(f("opSimpNac"))

    # ── Tomador (scoped a <toma>) ────────────────────────────────────────────
    toma_el = root.find(".//n:toma", ns)
    if toma_el is None:
        toma_el = root.find(".//toma")
    if toma_el is not None:
        nota.tomador_nome = _el(toma_el, "xNome")
        nota.tomador_doc  = _el(toma_el, "CNPJ") or _el(toma_el, "CPF")

    # ── Serviço ───────────────────────────────────────────────────────────────
    nota.natureza      = f("xDescServ")
    nota.codigo_fiscal = f("cTribNac") or f("cServ")

    # ── Valores ───────────────────────────────────────────────────────────────
    nota.valor_total   = _float(f("vServ") or f("vLiq"))
    nota.valor_bc      = _float(f("vBC"))
    nota.aliquota      = _float(f("pAliqAplic") or f("pAliq"))
    nota.valor_imposto = _float(f("vISSQN"))
    nota.tipo_imposto  = "ISSQN"

    return nota


def _parse_nfe(root: ET.Element) -> NotaFiscalXML:
    """Parser para NF-e — namespace portalfiscal."""
    nota = NotaFiscalXML(tipo=TIPO_NFE)
    ns   = {"n": NS["nfe"]}

    def f(tag: str) -> str:
        el = _find_el(root, tag, "nfe")
        return (el.text or "").strip() if el is not None else ""

    def _el(parent: ET.Element, tag: str) -> str:
        found = parent.find(f"n:{tag}", ns)
        if found is None:
            found = parent.find(tag)
        return (found.text or "").strip() if found is not None else ""

    nota.numero        = f("nNF")
    nota.serie         = f("serie")
    nota.data_emissao  = (f("dhEmi") or f("dEmi"))[:10]
    nota.municipio     = f("xMun")
    nota.uf            = f("UF")
    nota.natureza      = f("natOp")
    nota.codigo_fiscal = f("CFOP")

    # ── Emitente ──────────────────────────────────────────────────────────────
    emit_el = root.find(".//n:emit", ns)
    if emit_el is None:
        emit_el = root.find(".//emit")
    if emit_el is not None:
        nota.emitente_nome = _el(emit_el, "xNome")
        nota.emitente_doc  = _el(emit_el, "CNPJ") or _el(emit_el, "CPF")
        nota.emitente_ie   = _el(emit_el, "IE")
        crt = _el(emit_el, "CRT")
        nota.emitente_regime = {"1": "Simples Nacional", "2": "Simples Nacional",
                                 "3": "Regime Normal"}.get(crt, "")

    # ── Destinatário ──────────────────────────────────────────────────────────
    dest_el = root.find(".//n:dest", ns)
    if dest_el is None:
        dest_el = root.find(".//dest")
    if dest_el is not None:
        nota.tomador_nome = _el(dest_el, "xNome")
        nota.tomador_doc  = _el(dest_el, "CNPJ") or _el(dest_el, "CPF")

    # ── Itens ─────────────────────────────────────────────────────────────────
    dets = root.findall(".//n:det", ns) or root.findall(".//det")
    for det in dets:
        prod = det.find("n:prod", ns)
        if prod is None:
            prod = det.find("prod")
        if prod is None:
            continue
        nota.itens.append(ItemNota(
            codigo       = _el(prod, "cProd"),
            descricao    = _el(prod, "xProd"),
            quantidade   = _float(_el(prod, "qCom")),
            vlr_unitario = _float(_el(prod, "vUnCom")),
            vlr_total    = _float(_el(prod, "vProd")),
            unidade      = _el(prod, "uCom"),
        ))

    # ── Totais ICMS ───────────────────────────────────────────────────────────
    total_el = root.find(".//n:ICMSTot", ns)
    if total_el is None:
        total_el = root.find(".//ICMSTot")
    if total_el is not None:
        nota.valor_total   = _float(_el(total_el, "vNF"))
        nota.valor_bc      = _float(_el(total_el, "vBC"))
        nota.valor_imposto = _float(_el(total_el, "vICMS"))
        nota.tipo_imposto  = "ICMS"

    return nota


def _parse_nfa(root: ET.Element) -> NotaFiscalXML:
    """
    Parser para NFA — Nota Fiscal Agropecuária.
    O schema varia por estado; tenta heurísticas comuns escopo por bloco.
    """
    nota = NotaFiscalXML(tipo=TIPO_NFA)

    def f(tag: str) -> str:
        el = root.find(f".//{tag}")
        return (el.text or "").strip() if el is not None else ""

    def _el(parent: Optional[ET.Element], tag: str) -> str:
        if parent is None:
            return ""
        found = parent.find(tag)
        return (found.text or "").strip() if found is not None else ""

    nota.numero        = f("nNF") or f("numero")
    nota.serie         = f("serie")
    nota.data_emissao  = (f("dhEmi") or f("dEmi") or f("dataEmissao"))[:10]
    nota.natureza      = f("natOp") or f("naturezaOperacao")
    nota.codigo_fiscal = f("CFOP") or f("cfop")

    # ── Emitente (scoped a <emit> ou <emitente>) ──────────────────────────────
    emit_el = _first(root, ".//emit", ".//emitente")
    if emit_el is not None:
        nota.emitente_nome = _el(emit_el, "xNome") or _el(emit_el, "nomeEmitente")
        nota.emitente_doc  = (_el(emit_el, "CNPJ") or _el(emit_el, "CPF")
                              or _el(emit_el, "cpfCnpjEmitente"))
        nota.emitente_ie   = _el(emit_el, "IE") or _el(emit_el, "ieEmitente")
        ender = _first(emit_el, ".//enderEmit", "enderEmit")
        if ender is not None:
            nota.municipio = _el(ender, "xMun") or _el(ender, "municipio")
            nota.uf        = _el(ender, "UF")   or _el(ender, "uf")
    else:
        # Fallback: primeiro xNome / CNPJ / CPF do documento
        nota.emitente_nome = f("xNome") or f("nomeEmitente")
        nota.emitente_doc  = f("CNPJ")  or f("CPF") or f("cpfCnpjEmitente")
        nota.emitente_ie   = f("IE")    or f("ieEmitente")

    if not nota.municipio:
        nota.municipio = f("xMun") or f("municipio")
        nota.uf        = f("UF")   or f("uf")

    # ── Destinatário (scoped a <dest> ou <destinatario>) ─────────────────────
    dest_el = _first(root, ".//dest", ".//destinatario")
    if dest_el is not None:
        nota.tomador_nome = _el(dest_el, "xNome") or _el(dest_el, "nomeDestinatario")
        nota.tomador_doc  = _el(dest_el, "CNPJ")  or _el(dest_el, "CPF")

    # ── Valores ICMS ──────────────────────────────────────────────────────────
    total_el = _first(root, ".//ICMSTot", ".//total")
    if total_el is not None:
        nota.valor_total   = _float(_el(total_el, "vNF")   or _el(total_el, "valorTotal"))
        nota.valor_imposto = _float(_el(total_el, "vICMS") or _el(total_el, "valorICMS"))
        nota.valor_bc      = _float(_el(total_el, "vBC")   or _el(total_el, "baseCalculo"))
    else:
        nota.valor_total   = _float(f("vNF")   or f("valorTotal"))
        nota.valor_imposto = _float(f("vICMS") or f("valorICMS"))
        nota.valor_bc      = _float(f("vBC")   or f("baseCalculo"))

    nota.tipo_imposto = "ICMS"
    return nota


# ── API pública ───────────────────────────────────────────────────────────────

def parse_xml(conteudo: bytes | str, modo_resumo: str = "resumido") -> NotaFiscalXML:
    """
    Processa qualquer nota fiscal eletrônica em XML.

    Args:
        conteudo:    bytes ou str do arquivo XML
        modo_resumo: 'resumido' (padrão, ~110 tokens) | 'completo' (todos os itens)

    Returns:
        NotaFiscalXML com campo .resumo_auditoria() pronto para os agentes
    """
    if isinstance(conteudo, bytes):
        conteudo = conteudo.decode("utf-8", errors="replace")

    # 1. Remove assinatura digital — economiza ~60% dos tokens
    limpo = _remover_assinatura(conteudo)

    # 2. Parse do XML
    try:
        root = ET.fromstring(limpo)
    except ET.ParseError as exc:
        logger.error(f"XML inválido: {exc}")
        raise ValueError(f"XML malformado: {exc}") from exc

    # 3. Detecta tipo e despacha parser correto
    tipo = _detectar_tipo(root)
    if tipo == TIPO_NFSE:
        nota = _parse_nfse(root)
    elif tipo == TIPO_NFE:
        nota = _parse_nfe(root)
    elif tipo == TIPO_NFA:
        nota = _parse_nfa(root)
    else:
        # Tenta NF-e como fallback (schema mais comum)
        logger.warning("Tipo de nota não reconhecido — tentando parser NF-e")
        nota = _parse_nfe(root)
        nota.tipo = f"Desconhecido (tentativa NF-e)"

    # 4. Calcula tokens estimados
    resumo = nota.resumo_auditoria(modo_resumo)
    nota.tokens_resumo = len(resumo) // 4

    logger.info(
        f"XML parseado: {nota.tipo} #{nota.numero} | "
        f"{nota.emitente_nome} → {nota.tomador_nome} | "
        f"R${nota.valor_total:,.2f} | ~{nota.tokens_resumo} tokens"
    )
    return nota


def parse_xml_lote(arquivos: list[bytes | str], modo_resumo: str = "resumido") -> list[NotaFiscalXML]:
    """Processa múltiplos XMLs e retorna lista de NotaFiscalXML."""
    resultados = []
    for i, arq in enumerate(arquivos):
        try:
            resultados.append(parse_xml(arq, modo_resumo))
        except Exception as exc:
            logger.error(f"Erro no arquivo #{i+1}: {exc}")
    return resultados


def resumo_lote_para_agentes(notas: list[NotaFiscalXML], modo: str = "resumido") -> str:
    """
    Consolida lista de notas em um único bloco de texto para os agentes.
    Inclui estatísticas do lote (totais, tipos, emitentes).
    """
    if not notas:
        return "Nenhuma nota fiscal disponível para análise."

    total_valor   = sum(n.valor_total for n in notas)
    total_imposto = sum(n.valor_imposto for n in notas)
    tipos_count   = {}
    for n in notas:
        tipos_count[n.tipo] = tipos_count.get(n.tipo, 0) + 1

    linhas = [
        f"=== LOTE: {len(notas)} nota(s) fiscal(is) ===",
        f"Tipos    : " + " | ".join(f"{t}: {q}" for t, q in tipos_count.items()),
        f"Total    : R${total_valor:,.2f} | Impostos: R${total_imposto:,.2f}",
        "",
    ]
    for i, nota in enumerate(notas, 1):
        linhas.append(f"--- Nota {i}/{len(notas)} ---")
        linhas.append(nota.resumo_auditoria(modo))
        linhas.append("")

    return "\n".join(linhas)
