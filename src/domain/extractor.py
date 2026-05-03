import hashlib
import logging
import re
from typing import Any

from pydantic import BaseModel, Field, field_validator

from .constants import REGEX

try:
    import fitz  # PyMuPDF — muito mais rápido que pdfplumber
except ImportError:
    fitz = None
    logging.getLogger('NFA_Extractor').warning("⚠️ PyMuPDF (fitz) não instalado! Usando pdfplumber (MUITO LENTO). Execute: pip install PyMuPDF")

logger = logging.getLogger('NFA_Extractor')

# Cache em memória para PDFs processados (file_hash -> notas)
_cache_extracoes: dict[str, tuple[list['NFA'], str, str]] = {}

def _hash_pdf(caminho_pdf: str) -> str:
    """Calcula hash do PDF para cache lendo em blocos para otimizar memória e tempo."""
    try:
        hasher = hashlib.md5()
        with open(caminho_pdf, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except OSError:
        return ""

# --- MODELS (Pydantic V2) ---

class Parte(BaseModel):
    nome: str = ""
    ie: str | None = None
    cpf_cnpj: str | None = None
    municipio: str | None = None

class Produto(BaseModel):
    codigo: str = ""
    descricao: str = ""
    quantidade: float = 0.0
    vlr_icms: float = 0.0
    vlr_unitario: float = 0.0
    vlr_total: float = 0.0

class NFA(BaseModel):
    numero: str = ""
    natureza: str = "OUTRAS"
    emissao: str = ""
    valor_total: float = 0.0
    valor_icms: float = 0.0
    quantidade_total: float = 0.0
    chave_acesso: str | None = None
    local_emissao: str | None = None

    remetente: Parte = Field(default_factory=Parte)
    destinatario: Parte = Field(default_factory=Parte)
    transportador: Parte = Field(default_factory=Parte)
    produtos: list[Produto] = Field(default_factory=list)

    @field_validator("valor_total", "valor_icms", mode="before")
    @classmethod
    def parse_currency(cls, v: Any) -> float:
        if isinstance(v, str):
            v = v.replace("R$", "").replace(".", "").replace(",", ".").strip()
            try: return float(v)
            except: return 0.0
        return float(v or 0.0)

# --- LOGIC ---

def classificar_natureza(natureza: str) -> str:
    natureza = natureza.upper()
    if 'VENDA' in natureza: return 'VENDA'
    if 'REMESSA' in natureza: return 'REMESSA'
    if 'TRANSFER' in natureza: return 'TRANSFERENCIA'
    return 'OUTRAS'

def extrair_notas(caminho_pdf: str) -> tuple[list[NFA], str, str]:
    """Extrai notas fiscais do PDF usando os padrões de constants.py.

    Otimizações:
    - PyMuPDF (fitz) para extração rápida de texto (~100x mais rápido que pdfplumber)
    - Cache em memória para PDFs já processados
    - Regex compilado apenas uma vez
    - Processa página por página
    - Limita a 500 notas por PDF
    """
    import time
    t0 = time.time()

    # Verifica cache
    pdf_hash = _hash_pdf(caminho_pdf)
    if pdf_hash and pdf_hash in _cache_extracoes:
        logger.info("[CACHE HIT] PDF encontrado no cache")
        return _cache_extracoes[pdf_hash]

    notas = []
    nome_produtor = ""
    cpf_produtor = ""
    max_notas = 500
    pattern_id = re.compile(r'IDENTIFICA.{1,2}AO DA NOTA', re.IGNORECASE)
    re.compile(r"CONTRIBUINTE:\s*(.*)", re.IGNORECASE)

    try:
        if fitz:
            # PyMuPDF (fitz) — muito mais rápido que pdfplumber
            doc = fitz.open(caminho_pdf)
            total_paginas = len(doc)
            paginas_processadas = 0
            max_paginas_processamento = 100  # Limitar a 100 páginas para evitar PDFs gigantes

            for page_idx in range(min(total_paginas, max_paginas_processamento)):
                if len(notas) >= max_notas:
                    break

                page = doc[page_idx]
                texto_pagina = page.get_text() or ""
                paginas_processadas += 1

                if not texto_pagina.strip():
                    continue

                # Extrai info do produtor da primeira página
                if page_idx == 0:
                    match_nome = re.search(r"CONTRIBUINTE:\s*(.*)", texto_pagina, re.IGNORECASE)
                    if match_nome:
                        nome_produtor = match_nome.group(1).split("CPF/CNPJ")[0].strip()

                    match_cpf = REGEX['cpf_ou_cnpj'].search(texto_pagina)
                    if match_cpf:
                        cpf_produtor = match_cpf.group(1)

                # Processa blocos de notas
                blocos = pattern_id.split(texto_pagina)
                for bloco in blocos[1:]:
                    if len(notas) >= max_notas:
                        break
                    notas.extend(_processar_bloco_nota(bloco))

            doc.close()

        else:
            # Fallback: pdfplumber se PyMuPDF não estiver disponível
            import pdfplumber
            with pdfplumber.open(caminho_pdf) as pdf:
                total_paginas = len(pdf.pages)
                paginas_processadas = 0
                max_paginas_processamento = 100

                for page_idx, page in enumerate(pdf.pages[:max_paginas_processamento]):
                    if len(notas) >= max_notas:
                        break

                    texto_pagina = page.extract_text() or ""
                    paginas_processadas += 1

                    if not texto_pagina.strip():
                        continue

                    if page_idx == 0:
                        match_nome = re.search(r"CONTRIBUINTE:\s*(.*)", texto_pagina, re.IGNORECASE)
                        if match_nome:
                            nome_produtor = match_nome.group(1).split("CPF/CNPJ")[0].strip()

                        match_cpf = REGEX['cpf_ou_cnpj'].search(texto_pagina)
                        if match_cpf:
                            cpf_produtor = match_cpf.group(1)

                    blocos = pattern_id.split(texto_pagina)
                    for bloco in blocos[1:]:
                        if len(notas) >= max_notas:
                            break
                        notas.extend(_processar_bloco_nota(bloco))

        t_elapsed = time.time() - t0
        logger.info(f"[PDF EXTRACT] {t_elapsed:.2f}s — {paginas_processadas}/{total_paginas} pag — {len(notas)} notas")

    except Exception as e:
        logger.error(f"Erro ao abrir PDF {caminho_pdf}: {e}")

    # Cache
    resultado = (notas, nome_produtor, cpf_produtor)
    if pdf_hash:
        _cache_extracoes[pdf_hash] = resultado

    return resultado


def _processar_bloco_nota(bloco: str) -> list[NFA]:
    """Processa um bloco de nota extraído do PDF."""
    notas = []

    try:
        nfa = NFA()

        # Número e Data
        m_num = re.search(r'(\d{6,10})\s+(\d{2}/\d{2}/\d{4})\s+(.+)', bloco)
        if m_num:
            nfa.numero = m_num.group(1)
            nfa.emissao = m_num.group(2)
            nfa.natureza = classificar_natureza(m_num.group(3))

        # Chave de Acesso
        m_chave = re.search(r'\d{44}', bloco)
        if m_chave:
            nfa.chave_acesso = m_chave.group(0)

        # Partes
        def extrair_parte_flex(termo_inicio, proximo_bloco, texto):
            match_start = re.search(termo_inicio, texto, re.IGNORECASE)
            if not match_start: return Parte()

            sub = texto[match_start.end():]
            match_end = re.search(proximo_bloco, sub, re.IGNORECASE)
            if match_end: sub = sub[:match_end.start()]

            linhas = [l.strip() for l in sub.split('\n') if l.strip()]
            p = Parte()
            if len(linhas) > 1:
                dados = linhas[1]
                m_id = REGEX['cpf_ou_cnpj'].search(sub)
                if m_id: p.cpf_cnpj = m_id.group(1)
                p.nome = re.split(r'\d', dados)[0].strip()
            elif linhas:
                p.nome = linhas[0].strip()
            return p

        nfa.remetente = extrair_parte_flex("REMETENTE", "DESTINAT.RIO", bloco)
        nfa.destinatario = extrair_parte_flex("DESTINAT.RIO", "TRANSPORTADOR", bloco)

        # Produtos
        for line in bloco.split('\n'):
            m_prod = REGEX['produto'].search(line)
            if m_prod:
                prod = Produto(
                    codigo=m_prod.group(1),
                    descricao=m_prod.group(2).strip(),
                    quantidade=float(m_prod.group(3).replace('.','').replace(',','.')),
                    vlr_unitario=float(m_prod.group(4).replace('.','').replace(',','.')),
                    vlr_icms=float(m_prod.group(5).replace('.','').replace(',','.')),
                    vlr_total=float(m_prod.group(6).replace('.','').replace(',','.'))
                )
                nfa.produtos.append(prod)

        nfa.quantidade_total = sum(p.quantidade for p in nfa.produtos)
        nfa.valor_total = sum(p.vlr_total for p in nfa.produtos)
        nfa.valor_icms = sum(p.vlr_icms for p in nfa.produtos)

        # Fallback: se valor zerou (regex single-line não pegou), tenta parser multi-linha
        if nfa.valor_total == 0 or nfa.quantidade_total == 0:
            _completar_produtos_multilinha(nfa, bloco)

        # Fallback: corrigir nome quando ficou como label do PDF ("CNPJ/CPF",
        # "INSCRI", "MUNIC", "INSCRIÇÃO ESTADUAL"). Procura nome real entre as linhas.
        for parte_attr, inicio, fim in (
            ("remetente", "REMETENTE", "DESTINAT"),
            ("destinatario", "DESTINAT.RIO", "TRANSPORTADOR"),
        ):
            parte = getattr(nfa, parte_attr)
            if _eh_label(parte.nome):
                nome_real = _extrair_nome_real(bloco, inicio, fim)
                if nome_real:
                    parte.nome = nome_real

        if nfa.numero:
            notas.append(nfa)

    except Exception as e:
        logger.warning(f"Erro ao processar bloco: {e}")

    return notas


# ── Fallbacks: nome e valor quando layout do PDF é multi-linha ───────────────
_LABELS_RUIDO = {
    "CNPJ/CPF", "INSCRIÇÃO ESTADUAL", "INSCRICAO ESTADUAL",
    "INSCRI��O ESTADUAL", "MUNICÍPIO", "MUNICIPIO", "MUNIC�PIO",
    "REMETENTE", "DESTINATÁRIO", "DESTINAT.RIO", "DESTINAT�RIO",
    "TRANSPORTADOR", "ENDEREÇO", "ENDERECO",
}


def _eh_label(nome: str) -> bool:
    """True se `nome` é provavelmente um label do PDF (não o nome real)."""
    if not nome:
        return True
    n = nome.upper().strip()
    if n in _LABELS_RUIDO:
        return True
    # Labels começam com palavras-chave conhecidas
    return any(n.startswith(p) for p in ("CNPJ", "CPF", "INSCRI", "MUNIC", "ENDER"))


def _extrair_nome_real(bloco: str, marca_inicio: str, marca_fim: str) -> str:
    """Acha o nome real (primeira linha que não é label e não começa com dígito)."""
    m_ini = re.search(marca_inicio, bloco, re.IGNORECASE)
    if not m_ini:
        return ""
    sub = bloco[m_ini.end():]
    m_fim = re.search(marca_fim, sub, re.IGNORECASE)
    if m_fim:
        sub = sub[:m_fim.start()]
    for raw in sub.split('\n'):
        ln = raw.strip()
        if not ln:
            continue
        # Pula linhas que são puramente numéricas (IE, CPF) ou começam com dígito
        if ln[0].isdigit():
            continue
        # Pula labels conhecidos
        if _eh_label(ln):
            continue
        # Pula linhas curtas/pontuação
        if len(ln) < 4:
            continue
        return ln
    return ""


def _completar_produtos_multilinha(nfa: "NFA", bloco: str) -> None:
    """Parser multi-linha para o formato GIEF/SEFAZ-GO:

        1070
        GADO BOVINO NELORE MACHO PARA CRIA ATE 12 MESES CB
        30,00
        2335,1300
        R$ 70.053,90
        R$ 0,00

    Encontra blocos de 6 linhas onde:
        - linha 1: código (3-6 dígitos puros)
        - linha 2: descrição (texto, não numérico)
        - linha 3: quantidade (n,nn)
        - linha 4: valor unitário (n.nnn,nnnn)
        - linha 5: R$ valor total
        - linha 6: R$ valor icms
    """
    linhas = [l.strip() for l in bloco.split('\n')]
    re_codigo = re.compile(r'^\d{3,6}$')
    re_qty = re.compile(r'^\d+(?:\.\d+)?,\d+$')
    re_unit = re.compile(r'^\d+(?:[\.\,]\d+)+$')
    re_money = re.compile(r'^R\$\s*([\d\.]+,\d{2})$')

    def parse_money(s: str) -> float:
        m = re_money.match(s)
        if not m:
            return 0.0
        return float(m.group(1).replace('.', '').replace(',', '.'))

    def parse_num_br(s: str) -> float:
        return float(s.replace('.', '').replace(',', '.'))

    produtos_novos: list[Produto] = []
    i = 0
    while i < len(linhas) - 5:
        l0 = linhas[i]
        if not re_codigo.match(l0):
            i += 1
            continue
        # Tenta casar 6 linhas seguintes
        ldesc = linhas[i + 1]
        lqty = linhas[i + 2]
        lunit = linhas[i + 3]
        ltotal = linhas[i + 4]
        licms = linhas[i + 5]
        if (
            ldesc and not ldesc[0].isdigit()
            and re_qty.match(lqty)
            and re_unit.match(lunit)
            and re_money.match(ltotal)
            and re_money.match(licms)
        ):
            try:
                produtos_novos.append(Produto(
                    codigo=l0,
                    descricao=ldesc,
                    quantidade=parse_num_br(lqty),
                    vlr_unitario=parse_num_br(lunit),
                    vlr_total=parse_money(ltotal),
                    vlr_icms=parse_money(licms),
                ))
                i += 6
                continue
            except (ValueError, TypeError):
                pass
        i += 1

    if produtos_novos:
        # Substitui produtos vazios pelos novos
        nfa.produtos = produtos_novos
        nfa.quantidade_total = sum(p.quantidade for p in produtos_novos)
        nfa.valor_total = sum(p.vlr_total for p in produtos_novos)
        nfa.valor_icms = sum(p.vlr_icms for p in produtos_novos)

def resumo_geral(notas: list[NFA], nome_contribuinte: str = "") -> dict[str, Any]:
    """Gera métricas consolidadas exigidas pelo dashboard e relatórios."""
    total_valor = 0.0
    total_cabecas = 0.0

    por_mes = {}
    por_natureza = {}
    por_categoria = {}
    destinatarios = {}

    for n in notas:
        total_valor += n.valor_total
        total_cabecas += n.quantidade_total
        nat = n.natureza or 'OUTRAS'

        # Mes
        mes_ano = n.emissao[3:] if len(n.emissao) == 10 else "N/I"
        if mes_ano not in por_mes:
            por_mes[mes_ano] = {'notas': 0, 'cabecas': 0.0, 'valor': 0.0, 'vendas_valor': 0.0, 'vendas_cabecas': 0.0, 'vnd_notas': 0, 'rem_valor': 0.0, 'rem_cabecas': 0.0, 'rem_notas': 0}

        por_mes[mes_ano]['notas'] += 1
        por_mes[mes_ano]['cabecas'] += n.quantidade_total
        por_mes[mes_ano]['valor'] += n.valor_total

        if nat == 'VENDA':
            por_mes[mes_ano]['vendas_valor'] += n.valor_total
            por_mes[mes_ano]['vendas_cabecas'] += n.quantidade_total
            por_mes[mes_ano]['vnd_notas'] += 1
        elif nat == 'REMESSA':
            por_mes[mes_ano]['rem_valor'] += n.valor_total
            por_mes[mes_ano]['rem_cabecas'] += n.quantidade_total
            por_mes[mes_ano]['rem_notas'] += 1

        # Natureza
        por_natureza[nat] = por_natureza.get(nat, 0) + 1

        # Categoria (Detalhada)
        if nat not in por_categoria:
            por_categoria[nat] = {'notas': 0, 'cabecas': 0.0, 'valor': 0.0}
        por_categoria[nat]['notas'] += 1
        por_categoria[nat]['cabecas'] += n.quantidade_total
        por_categoria[nat]['valor'] += n.valor_total

        # Destinatarios
        d_nome = n.destinatario.nome or "NÃO IDENTIFICADO"
        if d_nome not in destinatarios:
            destinatarios[d_nome] = {'nome': d_nome, 'notas': 0, 'cabecas': 0.0, 'valor': 0.0}
        destinatarios[d_nome]['notas'] += 1
        destinatarios[d_nome]['cabecas'] += n.quantidade_total
        destinatarios[d_nome]['valor'] += n.valor_total

    top_dest = sorted(destinatarios.values(), key=lambda x: x['valor'], reverse=True)

    vendas = por_categoria.get('VENDA', {'notas': 0, 'cabecas': 0.0, 'valor': 0.0})

    return {
        'total_notas': len(notas),
        'total_valor': total_valor,
        'total_cabecas': total_cabecas,
        'ticket_medio': total_valor / total_cabecas if total_cabecas > 0 else 0,
        'por_mes': por_mes,
        'por_natureza': por_natureza,
        'top_dest': top_dest,
        'vendas_notas': vendas['notas'],
        'vendas_cabecas': vendas['cabecas'],
        'vendas_valor': vendas['valor'],
        'por_categoria': por_categoria
    }
