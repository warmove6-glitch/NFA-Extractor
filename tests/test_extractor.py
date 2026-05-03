"""
Suíte de testes para src/domain/extractor.py
Cobre: classificar_natureza(), modelos Pydantic (Parte, Produto, NFA).
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.domain.extractor import (
    NFA,
    Parte,
    Produto,
    classificar_natureza,
)

# ─── Testes: classificar_natureza() ──────────────────────────────────────────

class TestClassificarNatureza:
    """Testa a classificação da natureza da operação em categorias fiscais."""

    def test_venda(self):
        assert classificar_natureza('VENDA DE GADO BOVINO') == 'VENDA'

    def test_compra_nao_e_venda(self):
        # "COMPRA" não contém "VENDA" → deve cair em OUTRAS
        assert classificar_natureza('COMPRA DE BEZERROS') == 'OUTRAS'

    def test_remessa(self):
        assert classificar_natureza('REMESSA DE BEZERRO PARA RECRIA') == 'REMESSA'

    def test_transferencia(self):
        assert classificar_natureza('TRANSFERENCIA DE GADO ENTRE FAZENDAS') == 'TRANSFERENCIA'

    def test_outras(self):
        assert classificar_natureza('DOACAO DE ANIMAL') == 'OUTRAS'

    def test_case_insensitive(self):
        assert classificar_natureza('venda de boi gordo') == 'VENDA'

    def test_string_vazia(self):
        assert classificar_natureza('') == 'OUTRAS'

    def test_transfer_abreviado(self):
        # 'TRANSF.' não contém 'TRANSFER' → cai em OUTRAS (comportamento documentado)
        assert classificar_natureza('TRANSF. DE SALDO') == 'OUTRAS'

    def test_transfer_completo(self):
        assert classificar_natureza('TRANSFERENCIA DE GADO') == 'TRANSFERENCIA'


# ─── Testes: Modelos Pydantic ────────────────────────────────────────────────

class TestModelosPydantic:
    """Valida que os modelos Pydantic estão corretamente definidos."""

    def test_parte_default(self):
        p = Parte()
        assert p.nome == ''

    def test_parte_com_dados(self):
        p = Parte(nome='João', cpf_cnpj='123.456.789-00', municipio='Goiânia')
        assert p.nome == 'João'
        assert p.cpf_cnpj == '123.456.789-00'

    def test_produto_default(self):
        p = Produto()
        assert p.quantidade == 0.0
        assert p.vlr_total == 0.0

    def test_produto_com_dados(self):
        p = Produto(
            codigo='1070',
            descricao='NELORE MACHO',
            quantidade=10.0,
            vlr_total=25000.0,
        )
        assert p.codigo == '1070'
        assert p.quantidade == 10.0
        assert p.vlr_total == 25000.0

    def test_nfa_default(self):
        n = NFA()
        assert n.numero == ''
        assert isinstance(n.remetente, Parte)
        assert isinstance(n.produtos, list)
        assert len(n.produtos) == 0

    def test_nfa_com_produtos(self):
        n = NFA(
            numero='123456',
            natureza='VENDA',
            produtos=[
                Produto(quantidade=10.0, vlr_total=25000.0),
                Produto(quantidade=5.0, vlr_total=12500.0),
            ],
        )
        assert n.numero == '123456'
        assert len(n.produtos) == 2

    def test_nfa_sem_compartilhar_estado(self):
        """Garante que duas instâncias NFA não compartilham o mesmo default mutável."""
        n1 = NFA()
        n2 = NFA()
        n1.produtos.append(Produto(codigo='001'))
        assert len(n2.produtos) == 0

    def test_nfa_parse_currency_str(self):
        """valor_total aceita string no formato BR e converte para float."""
        n = NFA(valor_total='R$ 1.234,56')
        assert n.valor_total == pytest.approx(1234.56)

    def test_nfa_parse_currency_zero(self):
        n = NFA(valor_total='0,00')
        assert n.valor_total == 0.0

    def test_nfa_chave_acesso_44_digitos(self):
        """Chave de acesso com 44 dígitos deve ser aceita."""
        n = NFA(chave_acesso='1' * 44)
        assert n.chave_acesso == '1' * 44

    def test_nfa_natureza_default(self):
        n = NFA()
        assert n.natureza == 'OUTRAS'
