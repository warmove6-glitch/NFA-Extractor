import re
import pdfplumber
import logging
import hashlib
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from .constants import REGEX

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
    - Cache em memória para PDFs já processados
    - Processa página por página (evita carregar tudo em memória)
    - Limita a 500 notas por PDF para evitar gargalos
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

    try:
        with pdfplumber.open(caminho_pdf) as pdf:
            pattern_id = re.compile(r'IDENTIFICA.{1,2}AO DA NOTA', re.IGNORECASE)
            total_paginas = len(pdf.pages)

            # Processa página por página (evita carregar tudo em memória)
            paginas_processadas = 0
            for page_idx, page in enumerate(pdf.pages):
                if len(notas) >= max_notas:
                    logger.info(f"[PDF EXTRACT] Limite de {max_notas} notas atingido após {page_idx} páginas")
                    break

                texto_pagina = page.extract_text() or ""
                if not texto_pagina.strip():
                    continue

                # Extrai informações do produtor apenas da primeira página
                if page_idx == 0:
                    match_nome = re.search(r"CONTRIBUINTE:\s*(.*)", texto_pagina, re.IGNORECASE)
                    if match_nome:
                        nome_produtor = match_nome.group(1).split("CPF/CNPJ")[0].strip()

                    match_cpf = REGEX['cpf_ou_cnpj'].search(texto_pagina)
                    if match_cpf:
                        cpf_produtor = match_cpf.group(1)

                # Divide página por notas
                blocos = pattern_id.split(texto_pagina)
                paginas_processadas += 1

                # Processa blocos de notas nesta página
                for bloco in blocos[1:]:
                    if len(notas) >= max_notas:
                        break

                    try:
                        nfa = NFA()

                        # Número e Data
                        # Padrão: 24925316 19/02/2025 REMESSA/LEILAO
                        m_num = re.search(r'(\d{6,10})\s+(\d{2}/\d{2}/\d{4})\s+(.+)', bloco)
                        if m_num:
                            nfa.numero = m_num.group(1)
                            nfa.emissao = m_num.group(2)
                            nfa.natureza = classificar_natureza(m_num.group(3))

                        # Chave de Acesso
                        m_chave = re.search(r'\d{44}', bloco)
                        if m_chave:
                            nfa.chave_acesso = m_chave.group(0)

                        # Partes (Remetente, Destinatário, Transportador)
                        def extrair_parte_flex(termo_inicio, proximo_bloco, texto):
                            # Procura o termo de início (ex: REMETENTE)
                            match_start = re.search(termo_inicio, texto, re.IGNORECASE)
                            if not match_start: return Parte()

                            # Texto a partir do início
                            sub = texto[match_start.end():]

                            # Procura o próximo bloco para delimitar
                            match_end = re.search(proximo_bloco, sub, re.IGNORECASE)
                            if match_end: sub = sub[:match_end.start()]

                            # Extrai informações da linha
                            # Formato: NOME IE CPF/CNPJ MUNICIPIO
                            linhas = [l.strip() for l in sub.split('\n') if l.strip()]
                            p = Parte()
                            if len(linhas) > 1:
                                # Pula o cabeçalho (ex: INSCRIÇÃO ESTADUAL...) e pega os dados na próxima linha
                                dados = linhas[1]
                                # Tenta capturar CPF/CNPJ
                                m_id = REGEX['cpf_ou_cnpj'].search(sub)
                                if m_id: p.cpf_cnpj = m_id.group(1)

                                # O nome costuma ser o início da linha antes dos números
                                p.nome = re.split(r'\d', dados)[0].strip()
                            elif linhas:
                                p.nome = linhas[0].strip()
                            return p

                        nfa.remetente = extrair_parte_flex("REMETENTE", "DESTINAT.RIO", bloco)
                        nfa.destinatario = extrair_parte_flex("DESTINAT.RIO", "TRANSPORTADOR", bloco)

                        # Itens / Produtos
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
                        logger.warning(f"Erro ao processar bloco de nota: {e}")
                        continue

            t_elapsed = time.time() - t0
            logger.info(f"[PDF EXTRACT OTI] {t_elapsed:.1f}s — {paginas_processadas}/{total_paginas} pag — {len(notas)} notas")

    except Exception as e:
        logger.error(f"Erro ao abrir PDF {caminho_pdf}: {e}")

    # Salva no cache antes de retornar
    resultado = (notas, nome_produtor, cpf_produtor)
    if pdf_hash:
        _cache_extracoes[pdf_hash] = resultado
        logger.info(f"[CACHE SAVE] PDF armazenado em cache")

    return resultado

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
