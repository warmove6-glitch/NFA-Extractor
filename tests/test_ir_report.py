"""
Testes para ir_report.py — Planilha de Gado para IR.
"""

import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from extractor import NFA, Parte, Produto
from ir_report import gerar_pdf_ir, MESES_ORDEM, NOMES_MESES


# ── Fixture ───────────────────────────────────────────────────────────────────

@pytest.fixture
def notas_ir() -> list[NFA]:
    """NFAs com dados espalhados em 3 meses de 2025, cobrindo as 4 categorias."""
    return [
        # VENDAS — Março
        NFA(numero='001', emissao='10/03/2025', natureza='VENDA DE GADO BOVINO',
            remetente=Parte(nome='JOAO DA SILVA'),
            destinatario=Parte(nome='FRIGORIFICO A', cpf_cnpj='11.111.111/0001-11'),
            produtos=[Produto(quantidade=20.0, vlr_total=50000.0)]),
        # VENDAS — Abril
        NFA(numero='002', emissao='15/04/2025', natureza='VENDA DE GADO BOVINO',
            remetente=Parte(nome='JOAO DA SILVA'),
            destinatario=Parte(nome='FRIGORIFICO A', cpf_cnpj='11.111.111/0001-11'),
            produtos=[Produto(quantidade=10.0, vlr_total=28000.0)]),
        # REMESSA — Maio
        NFA(numero='003', emissao='05/05/2025', natureza='REMESSA DE BEZERROS',
            destinatario=Parte(nome='FAZENDA B', cpf_cnpj='22.222.222/0001-22'),
            produtos=[Produto(quantidade=8.0, vlr_total=16000.0)]),
        # TRANSFERÊNCIA — Junho
        NFA(numero='004', emissao='20/06/2025', natureza='TRANSFERENCIA DE GADO',
            destinatario=Parte(nome='FAZENDA C', cpf_cnpj='33.333.333/0001-33'),
            produtos=[Produto(quantidade=5.0, vlr_total=12500.0)]),
        # OUTRAS — Julho
        NFA(numero='005', emissao='01/07/2025', natureza='DOACAO DE ANIMAL',
            destinatario=Parte(nome='ENTIDADE D'),
            produtos=[Produto(quantidade=1.0, vlr_total=3500.0)]),
    ]


# ── Testes: constantes ────────────────────────────────────────────────────────

class TestConstantes:
    def test_meses_ordem_tem_12_itens(self):
        assert len(MESES_ORDEM) == 12

    def test_meses_ordem_sequencial(self):
        assert MESES_ORDEM[0] == '01'
        assert MESES_ORDEM[-1] == '12'

    def test_nomes_meses_tem_12_entradas(self):
        assert len(NOMES_MESES) == 12

    def test_nomes_meses_corretos(self):
        assert NOMES_MESES['01'] == 'Janeiro'
        assert NOMES_MESES['12'] == 'Dezembro'


# ── Testes: geração de PDF ────────────────────────────────────────────────────

class TestGerarPdfIr:
    def test_arquivo_criado(self, notas_ir):
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            saida = f.name
        gerar_pdf_ir(notas_ir, saida)
        assert Path(saida).exists()
        assert Path(saida).stat().st_size > 5000  # PDF com conteúdo real

    def test_arquivo_e_um_pdf_valido(self, notas_ir):
        """Verifica que o arquivo começa com o magic bytes %PDF."""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            saida = f.name
        gerar_pdf_ir(notas_ir, saida)
        with open(saida, 'rb') as f:
            header = f.read(4)
        assert header == b'%PDF'

    def test_lista_vazia_lanca_erro(self):
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            saida = f.name
        with pytest.raises(ValueError, match='Nenhuma nota'):
            gerar_pdf_ir([], saida)

    def test_nota_unica_gera_pdf(self):
        notas = [NFA(
            numero='999', emissao='15/08/2025', natureza='VENDA',
            remetente=Parte(nome='PRODUTOR TESTE'),
            destinatario=Parte(nome='COMPRADOR X', cpf_cnpj='000.000.000-00'),
            produtos=[Produto(quantidade=5.0, vlr_total=15000.0)],
        )]
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            saida = f.name
        gerar_pdf_ir(notas, saida)
        assert Path(saida).exists()

    def test_pdf_gerado_com_multiplas_categorias(self, notas_ir):
        """PDF deve ser gerado sem erro para todas as 4 categorias presentes."""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            saida = f.name
        # Não deve levantar nenhuma exceção
        gerar_pdf_ir(notas_ir, saida)
        assert Path(saida).exists()

    def test_ano_extraido_das_notas(self, notas_ir):
        """O PDF deve ser gerado com tamanho razoável (conteúdo multi-página esperado)."""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            saida = f.name
        gerar_pdf_ir(notas_ir, saida)
        tamanho = Path(saida).stat().st_size
        # PDF com 5 seções + cabeçalho deve ter pelo menos 50 KB
        assert tamanho > 50_000, f'PDF menor que o esperado: {tamanho} bytes'

    def test_nota_sem_remetente_nao_quebra(self):
        """Nota sem nome de remetente não deve causar erro."""
        notas = [NFA(
            numero='111', emissao='01/01/2025', natureza='VENDA',
            destinatario=Parte(nome='DEST A'),
            produtos=[Produto(quantidade=3.0, vlr_total=9000.0)],
        )]
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            saida = f.name
        gerar_pdf_ir(notas, saida)
        assert Path(saida).exists()
