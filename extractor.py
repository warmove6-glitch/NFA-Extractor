"""Lógica de extração de NFA do PDF SEFAZ-GO."""

import re
import logging
from collections import Counter, defaultdict
from typing import Optional

import pdfplumber
from pydantic import BaseModel, Field

# Configuração do Logger
logger = logging.getLogger('NFA_Extractor')
logger.setLevel(logging.INFO)
handler = logging.FileHandler('extractor.log', encoding='utf-8')
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
if not logger.handlers:
    logger.addHandler(handler)

class Parte(BaseModel):
    """Representa uma parte envolvida na NFA (remetente, destinatário, transportador)."""
    nome: str = ''
    ie: str = ''
    cpf_cnpj: str = ''
    municipio: str = ''


class Produto(BaseModel):
    """Representa um produto/item listado na NFA."""
    codigo: str = ''
    descricao: str = ''
    quantidade: float = 0.0
    vlr_icms: float = 0.0
    vlr_unitario: float = 0.0
    vlr_total: float = 0.0


class NFA(BaseModel):
    """Modelo principal de uma Nota Fiscal Avulsa extraída do PDF SEFAZ-GO.
    
    Attributes:
        chave_acesso (str): Chave de 44 dígitos da nota.
        numero (str): Número da nota.
        emissao (str): Data de emissão no formato DD/MM/AAAA.
        natureza (str): Natureza da operação (Ex: VENDA, TRANSFERENCIA).
        local_emissao (str): Agência Fazendária.
        remetente (Parte): Dados do produtor emissor.
        destinatario (Parte): Dados do comprador.
        transportador (Parte): Dados de quem fará o frete.
        produtos (list[Produto]): Lista de itens faturados.
    """
    chave_acesso: str = ''
    numero: str = ''
    emissao: str = ''
    natureza: str = ''
    local_emissao: str = ''
    remetente: Parte = Field(default_factory=Parte)
    destinatario: Parte = Field(default_factory=Parte)
    transportador: Parte = Field(default_factory=Parte)
    produtos: list[Produto] = Field(default_factory=list)

    @property
    def quantidade_total(self) -> float:
        """Calcula o somatório da quantidade de todos os produtos na nota."""
        return sum(p.quantidade for p in self.produtos)

    @property
    def valor_total(self) -> float:
        """Calcula o valor financeiro total da nota somando o VLR TOTAL dos produtos."""
        return sum(p.vlr_total for p in self.produtos)

    @property
    def resumo_produtos(self) -> str:
        return ' | '.join(f"{p.descricao} ({p.quantidade:.0f})" for p in self.produtos)


def _moeda(s: str, origin_info: str = "Desconhecido") -> float:
    """Converte string monetária brasileira em ponto flutuante (float).
    
    Args:
        s (str): A string contendo o valor financeiro (ex: 'R$ 1.234,56').
        origin_info (str): Informação de origem para rastreabilidade no log.
        
    Returns:
        float: O valor decimal. Levanta ValueError em falhas para não corromper BI silenciosamente.
    """
    orig_s = s
    s = re.sub(r'[R$\s]', '', s).replace('.', '').replace(',', '.')
    try:
        v = float(s)
        return v
    except ValueError as e:
        logger.error(f"Falha CRÍTICA ao converter valor: '{orig_s}' (Contexto: {origin_info})")
        raise ValueError(f"Valor monetário inválido: {orig_s}") from e


def validar_nfa(nfa: NFA) -> tuple[bool, list[str]]:
    """Valida a integridade lógica e referencial de uma nota fiscal extraída."""
    erros = []
    if len(nfa.chave_acesso) != 44:
        erros.append(f"Chave de acesso com {len(nfa.chave_acesso)} dígitos (esperado 44)")
    
    if not nfa.produtos:
        erros.append("Nenhum produto extraído na NFA (possível falha de parsing)")

    # Se a NFA tem valor total e produtos, o valor não deveria ser zero numa venda, mas pode ser zero numa remessa.
    if 'VENDA' in nfa.natureza.upper() and nfa.valor_total <= 0:
        erros.append("NFA de VENDA com valor monetário zerado")

    return len(erros) == 0, erros


def _extrair_parte(linha: str) -> Parte:
    """Extrai os dados de uma parte envolvida (Ex: Remetente ou Destinatário).
    
    Tenta capturar o CPF/CNPJ, Inscrição Estadual e Município de uma linha de texto.
    
    Args:
        linha (str): Linha de texto extraída do PDF contendo os dados da pessoa.
        
    Returns:
        Parte: Modelo pydantic contendo nome, ie, cpf_cnpj e municipio.
    """
    p = Parte()
    m = re.search(r'(\d{3}\.\d{3}\.\d{3}-\d{2}|\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})', linha)
    if m:
        p.cpf_cnpj = m.group(1)
        antes = linha[:m.start()].strip()
        apos  = linha[m.end():].strip()
        m2 = re.search(r'(\d{6,12})\s*$', antes)
        if m2:
            p.ie   = m2.group(1)
            p.nome = antes[:m2.start()].strip()
        else:
            p.nome = antes
        p.municipio = apos
    else:
        logger.info(f"Nao foi possivel identificar CPF/CNPJ na linha: '{linha[:50]}...'")
        p.nome = linha.strip()
    return p


def _parse_produto(linha: str) -> Optional[Produto]:
    """Parseia uma linha contendo um produto/item comercializado na NFA.
    
    Args:
        linha (str): Texto contendo o código, descrição e métricas do item.
        
    Returns:
        Optional[Produto]: O modelo preenchido se o matching for um sucesso, ou None se falhar.
    """
    m = re.match(
        r'^(\d+)\s+(.+?)\s+(\d+[.,]\d+)\s+R\$\s*([\d.,]+)\s+([\d.,]+)\s+R\$\s*([\d.,]+)$',
        linha.strip()
    )
    if not m:
        return None
        
    info = f"Produto {m.group(1)}"
    try:
        return Produto(
            codigo=m.group(1),
            descricao=m.group(2).strip(),
            quantidade=_moeda(m.group(3), info),
            vlr_icms=_moeda(m.group(4), info),
            vlr_unitario=_moeda(m.group(5), info),
            vlr_total=_moeda(m.group(6), info),
        )
    except ValueError:
        return None


def extrair_notas(pdf_path: str, callback=None) -> list[NFA]:
    """Extrai todas as NFAs do PDF SEFAZ-GO e mapeia para a estrutura de dados NFA.
    
    Args:
        pdf_path (str): Caminho absoluto para o arquivo PDF.
        callback (callable, opcional): Função base para relato de progresso.
        
    Returns:
        list[NFA]: Lista de Notas Fiscais validadas pelo Pydantic.
        
    Raises:
        Exception: Repassa exceções estruturais (ex: PDF corrompido/senha).
    """
    linhas_todas: list[str] = []

    logger.info(f"Iniciando extracao do arquivo: {pdf_path}")
    try:
        with pdfplumber.open(pdf_path) as pdf:
            total = len(pdf.pages)
            for i, page in enumerate(pdf.pages):
                if callback:
                    callback(i + 1, total)
                txt = page.extract_text(layout=False) or ''
                linhas_todas.extend(txt.splitlines())
    except Exception as e:
        logger.error(f"Erro catastrofico ao tentar ler o PDF {pdf_path}: {e}")
        raise ValueError(f"Não foi possível abrir o arquivo PDF: {e}")

    blocos: list[list[str]] = []
    bloco_atual: list[str] = []
    for linha in linhas_todas:
        if re.search(r'IDENTIFICA[ÇC][ÃA]O DA NOTA', linha, re.IGNORECASE):
            if bloco_atual:
                blocos.append(bloco_atual)
            bloco_atual = [linha]
        else:
            bloco_atual.append(linha)
    if bloco_atual:
        blocos.append(bloco_atual)

    notas: list[NFA] = []
    for bloco in blocos:
        nfa = NFA()
        linhas = [l.strip() for l in bloco if l.strip()]
        i = 0
        while i < len(linhas):
            l = linhas[i]

            if re.fullmatch(r'\d{44}', l):
                nfa.chave_acesso = l; i += 1; continue

            m = re.match(r'^(\d{6,10})\s+(\d{2}/\d{2}/\d{4})\s+(.+)$', l)
            if m and not nfa.numero:
                nfa.numero = m.group(1); nfa.emissao = m.group(2); nfa.natureza = m.group(3).strip()
                i += 1; continue

            if re.search(r'AGENCIA FAZENDARIA|NOTA EMITIDA PELO', l, re.IGNORECASE):
                nfa.local_emissao = l; i += 1; continue

            if re.search(r'REMETENTE', l, re.IGNORECASE) and i + 1 < len(linhas):
                i += 1; nfa.remetente = _extrair_parte(linhas[i]); i += 1; continue

            if re.search(r'DESTINAT[AÁ]RIO', l, re.IGNORECASE) and i + 1 < len(linhas):
                i += 1; nfa.destinatario = _extrair_parte(linhas[i]); i += 1; continue

            if re.search(r'TRANSPORTADOR', l, re.IGNORECASE) and i + 1 < len(linhas):
                proximo = linhas[i + 1] if i + 1 < len(linhas) else ''
                if proximo and not re.search(r'DESCRI', proximo, re.IGNORECASE):
                    i += 1; nfa.transportador = _extrair_parte(linhas[i])
                i += 1; continue

            p = _parse_produto(l)
            if p:
                nfa.produtos.append(p)
            i += 1

        if nfa.numero or nfa.chave_acesso:
            valida, errs = validar_nfa(nfa)
            if not valida:
                logger.warning(f"Integridade NFA {nfa.numero or nfa.chave_acesso}: {', '.join(errs)}")
            notas.append(nfa)

    return notas


def classificar_natureza(nat: str) -> str:
    """Classifica a natureza da operação em categorias financeiras macro (BI).
    
    Args:
        nat (str): Texto cru da natureza da operação da SEFAZ.
        
    Returns:
        str: Uma das categorias chaves para BI: 'VENDA', 'REMESSA', 'TRANSFERENCIA', 'OUTRAS'.
    """
    nat = nat.upper()
    if 'VENDA' in nat or 'COMPRA' in nat:
        return 'VENDA'
    if 'REMESS' in nat:
        return 'REMESSA'
    if 'TRANSF' in nat:
        return 'TRANSFERENCIA'
    return 'OUTRAS'


def resumo_geral(notas: list[NFA]) -> dict:
    """Consolida as notas ficais gerando um pacote de Business Intelligence.
    
    Agrega vendas, remessas, cálcula o Índice de Concentração de Mercado (HHI)
    e computa os preços médios globais.
    
    Args:
        notas (list[NFA]): Lista contendo os objetos NFA extraídos.
        
    Returns:
        dict: Dicionário com dezenas de KPIs consolidados.
    """
    # Totais gerais
    total_valor   = sum(n.valor_total for n in notas)
    total_cabecas = sum(n.quantidade_total for n in notas)

    # Totais por categoria fiscal
    por_categoria: dict = defaultdict(lambda: {'notas': 0, 'cabecas': 0.0, 'valor': 0.0})
    for n in notas:
        cat = classificar_natureza(n.natureza)
        por_categoria[cat]['notas']   += 1
        por_categoria[cat]['cabecas'] += n.quantidade_total
        por_categoria[cat]['valor']   += n.valor_total

    # Totais somente de VENDAS (base tributável)
    vendas = [n for n in notas if classificar_natureza(n.natureza) == 'VENDA']
    total_valor_vendas   = sum(n.valor_total for n in vendas)
    total_cabecas_vendas = sum(n.quantidade_total for n in vendas)

    por_natureza: Counter = Counter(n.natureza for n in notas)
    por_dest: dict = defaultdict(lambda: {'nome':'','cabecas':0.0,'valor':0.0,'notas':0,'categoria':'', 'vendas_valor': 0.0})
    por_mes: dict = defaultdict(lambda: {
        'notas':0, 'valor':0.0, 'cabecas':0.0,
        'vendas_valor':0.0, 'vendas_cabecas':0.0, 'vnd_notas':0,
        'rem_valor':0.0,    'rem_cabecas':0.0,    'rem_notas':0,
        'trf_valor':0.0,    'trf_cabecas':0.0,    'trf_notas':0,
        'out_valor':0.0,    'out_cabecas':0.0,    'out_notas':0,
    })

    for n in notas:
        k = n.destinatario.cpf_cnpj or n.destinatario.nome
        cat = classificar_natureza(n.natureza)
        
        por_dest[k]['nome']      = n.destinatario.nome
        por_dest[k]['cabecas']  += n.quantidade_total
        por_dest[k]['valor']    += n.valor_total
        por_dest[k]['notas']    += 1
        por_dest[k]['categoria'] = cat
        if cat == 'VENDA':
            por_dest[k]['vendas_valor'] += n.valor_total

        if n.emissao and len(n.emissao) == 10:
            mes_ano = n.emissao[3:]
            por_mes[mes_ano]['notas']   += 1
            por_mes[mes_ano]['valor']   += n.valor_total
            por_mes[mes_ano]['cabecas'] += n.quantidade_total
            if cat == 'VENDA':
                por_mes[mes_ano]['vendas_valor']   += n.valor_total
                por_mes[mes_ano]['vendas_cabecas'] += n.quantidade_total
                por_mes[mes_ano]['vnd_notas']      += 1
            elif cat == 'REMESSA':
                por_mes[mes_ano]['rem_valor']      += n.valor_total
                por_mes[mes_ano]['rem_cabecas']    += n.quantidade_total
                por_mes[mes_ano]['rem_notas']      += 1
            elif cat == 'TRANSFERENCIA':
                por_mes[mes_ano]['trf_valor']      += n.valor_total
                por_mes[mes_ano]['trf_cabecas']    += n.quantidade_total
                por_mes[mes_ano]['trf_notas']      += 1
            else:
                por_mes[mes_ano]['out_valor']      += n.valor_total
                por_mes[mes_ano]['out_cabecas']    += n.quantidade_total
                por_mes[mes_ano]['out_notas']      += 1

    # Business Intelligence: Cálculo do HHI (Índice Herfindahl-Hirschman) sobre VENDAS
    hhi = 0.0
    if total_valor_vendas > 0:
        for d in por_dest.values():
            if d['vendas_valor'] > 0:
                share = (d['vendas_valor'] / total_valor_vendas) * 100
                hhi += (share ** 2)
                
    risco_hhi = 'Baixo (Competitivo)'
    if hhi > 2500:
        risco_hhi = 'Crítico (Altamente Concentrado)'
    elif hhi > 1500:
        risco_hhi = 'Médio (Concentração Moderada)'

    top_dest = sorted(por_dest.values(), key=lambda x: x['valor'], reverse=True)[:10]

    return {
        'total_notas':          len(notas),
        'total_cabecas':        total_cabecas,
        'total_valor':          total_valor,
        'ticket_medio':         total_valor / len(notas) if notas else 0,
        # Somente vendas (base tributável)
        'vendas_notas':         len(vendas),
        'vendas_cabecas':       total_cabecas_vendas,
        'vendas_valor':         total_valor_vendas,
        'vendas_ticket_medio':  total_valor_vendas / len(vendas) if vendas else 0,
        # Business Intelligence
        'preco_medio_cabeca':   total_valor_vendas / total_cabecas_vendas if total_cabecas_vendas else 0,
        'hhi':                  hhi,
        'risco_hhi':            risco_hhi,
        # Breakdown por agrupamento
        'por_categoria':        dict(por_categoria),
        'por_natureza':         dict(por_natureza),
        'top_dest':             top_dest,
        'por_mes':              dict(sorted(por_mes.items())),
    }
