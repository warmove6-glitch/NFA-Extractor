import re
import logging
import hashlib
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from .constants import REGEX

try:
    import fitz  # PyMuPDF — muito mais rápido que pdfplumber
except ImportError:
    import pdfplumber  # Fallback se PyMuPDF não estiver disponível
    fitz = None

logger = logging.getLogger('NFA_Extractor')

# Cache em memória para PDFs processados (file_hash -> notas)
_cache_extracoes: Dict[str, tuple[List['NFA'], str, str]] = {}

def _hash_pdf(caminho_pdf: str) -> str:
    """Calcula hash do PDF para cache."""
    try:
        with open(caminho_pdf, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    except:
        return ""

# --- MODELS (Pydantic V2) ---

class Parte(BaseModel):
    nome: str = ""
    ie: Optional[str] = None
    cpf_cnpj: Optional[str] = None
    municipio: Optional[str] = None

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
    chave_acesso: Optional[str] = None
    local_emissao: Optional[str] = None
    
    remetente: Parte = Field(default_factory=Parte)
    destinatario: Parte = Field(default_factory=Parte)
    transportador: Parte = Field(default_factory=Parte)
    produtos: List[Produto] = Field(default_factory=list)

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

def extrair_notas(caminho_pdf: str) -> tuple[List[NFA], str, str]:
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
        logger.info(f"[CACHE HIT] PDF encontrado no cache")
        return _cache_extracoes[pdf_hash]

    notas = []
    nome_produtor = ""
    cpf_produtor = ""
    max_notas = 500
    pattern_id = re.compile(r'IDENTIFICA.{1,2}AO DA NOTA', re.IGNORECASE)
    pattern_contribuinte = re.compile(r"CONTRIBUINTE:\s*(.*)", re.IGNORECASE)

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


def _processar_bloco_nota(bloco: str) -> List[NFA]:
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

        if nfa.numero:
            notas.append(nfa)

    except Exception as e:
        logger.warning(f"Erro ao processar bloco: {e}")

    return notas

def resumo_geral(notas: List[NFA], nome_contribuinte: str = "") -> Dict[str, Any]:
    """Gera métricas consolidadas exigidas pelo dashboard e relatórios."""
    total_valor = sum(n.valor_total for n in notas)
    total_cabecas = sum(n.quantidade_total for n in notas)
    
    por_mes = {}
    por_natureza = {}
    destinatarios = {}
    
    for n in notas:
        # Mes
        mes_ano = n.emissao[3:] if len(n.emissao) == 10 else "N/I"
        if mes_ano not in por_mes:
            por_mes[mes_ano] = {'notas': 0, 'cabecas': 0.0, 'valor': 0.0, 'vendas_valor': 0.0, 'vendas_cabecas': 0.0, 'vnd_notas': 0, 'rem_valor': 0.0, 'rem_cabecas': 0.0, 'rem_notas': 0}
        
        por_mes[mes_ano]['notas'] += 1
        por_mes[mes_ano]['cabecas'] += n.quantidade_total
        por_mes[mes_ano]['valor'] += n.valor_total
        
        if n.natureza == 'VENDA':
            por_mes[mes_ano]['vendas_valor'] += n.valor_total
            por_mes[mes_ano]['vendas_cabecas'] += n.quantidade_total
            por_mes[mes_ano]['vnd_notas'] += 1
        elif n.natureza == 'REMESSA':
            por_mes[mes_ano]['rem_valor'] += n.valor_total
            por_mes[mes_ano]['rem_cabecas'] += n.quantidade_total
            por_mes[mes_ano]['rem_notas'] += 1

        # Natureza
        por_natureza[n.natureza] = por_natureza.get(n.natureza, 0) + 1
        
        # Destinatarios
        d_nome = n.destinatario.nome or "NÃO IDENTIFICADO"
        if d_nome not in destinatarios:
            destinatarios[d_nome] = {'nome': d_nome, 'notas': 0, 'cabecas': 0.0, 'valor': 0.0}
        destinatarios[d_nome]['notas'] += 1
        destinatarios[d_nome]['cabecas'] += n.quantidade_total
        destinatarios[d_nome]['valor'] += n.valor_total

    top_dest = sorted(destinatarios.values(), key=lambda x: x['valor'], reverse=True)

    return {
        'total_notas': len(notas),
        'total_valor': total_valor,
        'total_cabecas': total_cabecas,
        'ticket_medio': total_valor / total_cabecas if total_cabecas > 0 else 0,
        'por_mes': por_mes,
        'por_natureza': por_natureza,
        'top_dest': top_dest,
        'vendas_notas': sum(1 for n in notas if n.natureza == 'VENDA'),
        'vendas_cabecas': sum(n.quantidade_total for n in notas if n.natureza == 'VENDA'),
        'vendas_valor': sum(n.valor_total for n in notas if n.natureza == 'VENDA'),
        'por_categoria': {
            'VENDA': {'notas': sum(1 for n in notas if n.natureza == 'VENDA'), 'cabecas': sum(n.quantidade_total for n in notas if n.natureza == 'VENDA'), 'valor': sum(n.valor_total for n in notas if n.natureza == 'VENDA')},
            'REMESSA': {'notas': sum(1 for n in notas if n.natureza == 'REMESSA'), 'cabecas': sum(n.quantidade_total for n in notas if n.natureza == 'REMESSA'), 'valor': sum(n.valor_total for n in notas if n.natureza == 'REMESSA')}
        }
    }
