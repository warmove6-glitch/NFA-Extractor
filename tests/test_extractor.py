"""
Suíte de testes para o módulo extractor.py — @Delta (QA & SRE)
Valida os parsers de regex, classificação fiscal e resumo geral.
"""

import sys
from pathlib import Path

import pytest

# Garante que o diretório raiz do projeto está no path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.domain.extractor import (
    Parte, Produto, NFA,
    classificar_natureza, resumo_geral
)


# ─── Testes: _moeda() ────────────────────────────────────────────────────────

class TestMoeda:
    """Testa a conversão de strings monetárias brasileiras para float."""

    def test_formato_padrao(self):
        assert _moeda('1.234,56') == 1234.56

    def test_com_cifrao(self):
        assert _moeda('R$ 1.234,56') == 1234.56

    def test_com_cifrao_e_espacos(self):
        assert _moeda('R$  2.500,00') == 2500.00

    def test_sem_milhar(self):
        assert _moeda('250,00') == 250.00

    def test_valor_zero(self):
        assert _moeda('0,00') == 0.0

    def test_valor_grande(self):
        assert _moeda('R$ 33.529,58') == 33529.58

    def test_string_invalida(self):
        with pytest.raises(ValueError, match="inválido"):
            _moeda('abc')

    def test_string_vazia(self):
        with pytest.raises(ValueError, match="inválido"):
            _moeda('')


# ─── Testes: _extrair_parte() ────────────────────────────────────────────────

class TestExtrairParte:
    """Testa a extração de dados de remetente/destinatário/transportador."""

    def test_com_cpf(self):
        linha = 'JOAO DA SILVA 123456789 012.345.678-90 GOIANIA'
        p = _extrair_parte(linha)
        assert p.nome == 'JOAO DA SILVA'
        assert p.cpf_cnpj == '012.345.678-90'
        assert p.ie == '123456789'
        assert p.municipio == 'GOIANIA'

    def test_com_cnpj(self):
        linha = 'FRIGORIFICO XPTO LTDA 987654321 12.345.678/0001-90 ANAPOLIS'
        p = _extrair_parte(linha)
        assert p.nome == 'FRIGORIFICO XPTO LTDA'
        assert p.cpf_cnpj == '12.345.678/0001-90'
        assert p.ie == '987654321'
        assert p.municipio == 'ANAPOLIS'

    def test_sem_ie(self):
        linha = 'MARIA OLIVEIRA 123.456.789-00 JATAI'
        p = _extrair_parte(linha)
        assert p.nome == 'MARIA OLIVEIRA'
        assert p.cpf_cnpj == '123.456.789-00'
        assert p.ie == ''
        assert p.municipio == 'JATAI'

    def test_sem_documento(self):
        linha = 'TRANSPORTADORA ABC'
        p = _extrair_parte(linha)
        assert p.nome == 'TRANSPORTADORA ABC'
        assert p.cpf_cnpj == ''

    def test_retorna_modelo_pydantic(self):
        p = _extrair_parte('NOME QUALQUER')
        assert isinstance(p, Parte)


# ─── Testes: _parse_produto() ────────────────────────────────────────────────

class TestParseProduto:
    """Testa o parsing de linha de item/produto da NFA."""

    def test_linha_valida(self):
        linha = '1070 GADO BOVINO NELORE MACHO PARA CRIA ATE 12 MESES CB 14,00 R$ 0,00 2394,9700 R$ 33.529,58'
        p = _parse_produto(linha)
        assert p is not None
        assert p.codigo == '1070'
        assert 'NELORE' in p.descricao
        assert p.quantidade == 14.0
        assert p.vlr_icms == 0.0
        assert p.vlr_unitario == 2394.97
        assert p.vlr_total == 33529.58

    def test_linha_invalida(self):
        assert _parse_produto('esta linha nao eh um produto') is None

    def test_cabecalho_tabela(self):
        assert _parse_produto('CODIGO DESCRICAO QUANTIDADE VLR ICMS VLR UNITARIO VLR TOTAL') is None

    def test_linha_vazia(self):
        assert _parse_produto('') is None

    def test_retorna_modelo_pydantic(self):
        linha = '1070 GADO BOVINO NELORE 14,00 R$ 0,00 2394,9700 R$ 33.529,58'
        p = _parse_produto(linha)
        assert p is not None
        assert isinstance(p, Produto)


# ─── Testes: classificar_natureza() ──────────────────────────────────────────

class TestClassificarNatureza:
    """Testa a classificação da natureza da operação em categorias fiscais."""

    def test_venda(self):
        assert classificar_natureza('VENDA DE GADO BOVINO') == 'VENDA'

    def test_compra(self):
        assert classificar_natureza('COMPRA DE BEZERROS') == 'VENDA'

    def test_remessa(self):
        assert classificar_natureza('REMESSA DE BEZERRO PARA RECRIA') == 'REMESSA'

    def test_remessa_variante(self):
        assert classificar_natureza('REMESS. ENTRE PROPRIEDADES') == 'REMESSA'

    def test_transferencia(self):
        assert classificar_natureza('TRANSFERENCIA DE GADO ENTRE FAZENDAS') == 'TRANSFERENCIA'

    def test_transferencia_abreviada(self):
        assert classificar_natureza('TRANSF. DE SALDO') == 'TRANSFERENCIA'

    def test_outras(self):
        assert classificar_natureza('DOACAO DE ANIMAL') == 'OUTRAS'

    def test_case_insensitive(self):
        assert classificar_natureza('venda de boi gordo') == 'VENDA'

    def test_string_vazia(self):
        assert classificar_natureza('') == 'OUTRAS'


# ─── Testes: Modelos Pydantic ────────────────────────────────────────────────

class TestModelosPydantic:
    """Valida que os modelos Pydantic foram migrados corretamente."""

    def test_parte_default(self):
        p = Parte()
        assert p.nome == ''
        assert p.ie == ''
        assert p.cpf_cnpj == ''
        assert p.municipio == ''

    def test_parte_com_dados(self):
        p = Parte(nome='João', cpf_cnpj='123.456.789-00', municipio='Goiânia')
        assert p.nome == 'João'
        assert p.cpf_cnpj == '123.456.789-00'

    def test_produto_default(self):
        p = Produto()
        assert p.quantidade == 0.0
        assert p.vlr_total == 0.0

    def test_nfa_default(self):
        n = NFA()
        assert n.numero == ''
        assert isinstance(n.remetente, Parte)
        assert isinstance(n.produtos, list)
        assert len(n.produtos) == 0

    def test_nfa_quantidade_total(self):
        n = NFA(produtos=[
            Produto(quantidade=10.0, vlr_total=1000.0),
            Produto(quantidade=5.0, vlr_total=500.0),
        ])
        assert n.quantidade_total == 15.0

    def test_nfa_valor_total(self):
        n = NFA(produtos=[
            Produto(quantidade=10.0, vlr_total=1000.0),
            Produto(quantidade=5.0, vlr_total=500.0),
        ])
        assert n.valor_total == 1500.0

    def test_nfa_sem_compartilhar_estado(self):
        """Garante que duas instâncias NFA não compartilham o mesmo default mutável."""
        n1 = NFA()
        n2 = NFA()
        n1.produtos.append(Produto(codigo='001'))
        assert len(n2.produtos) == 0


# ─── Testes: resumo_geral() ──────────────────────────────────────────────────

class TestResumoGeral:
    """Testa a agregação de dados para o resumo geral."""

    @pytest.fixture
    def notas_mock(self) -> list[NFA]:
        """Cria um conjunto mínimo de notas para teste."""
        return [
            NFA(
                numero='000001', emissao='15/01/2025',
                natureza='VENDA DE GADO BOVINO',
                destinatario=Parte(nome='FRIGORIFICO A', cpf_cnpj='12.345.678/0001-90', municipio='GOIANIA'),
                produtos=[Produto(quantidade=20.0, vlr_total=50000.0)],
            ),
            NFA(
                numero='000002', emissao='20/02/2025',
                natureza='REMESSA DE BEZERROS',
                destinatario=Parte(nome='FAZENDA B', cpf_cnpj='98.765.432/0001-10', municipio='JATAI'),
                produtos=[Produto(quantidade=15.0, vlr_total=30000.0)],
            ),
            NFA(
                numero='000003', emissao='10/01/2025',
                natureza='VENDA DE GADO BOVINO',
                destinatario=Parte(nome='FRIGORIFICO A', cpf_cnpj='12.345.678/0001-90', municipio='GOIANIA'),
                produtos=[Produto(quantidade=10.0, vlr_total=25000.0)],
            ),
        ]

    def test_total_notas(self, notas_mock):
        res = resumo_geral(notas_mock)
        assert res['total_notas'] == 3

    def test_total_cabecas(self, notas_mock):
        res = resumo_geral(notas_mock)
        assert res['total_cabecas'] == 45.0

    def test_total_valor(self, notas_mock):
        res = resumo_geral(notas_mock)
        assert res['total_valor'] == 105000.0

    def test_ticket_medio(self, notas_mock):
        res = resumo_geral(notas_mock)
        assert res['ticket_medio'] == 35000.0

    def test_vendas_filtradas(self, notas_mock):
        res = resumo_geral(notas_mock)
        assert res['vendas_notas'] == 2
        assert res['vendas_cabecas'] == 30.0
        assert res['vendas_valor'] == 75000.0

    def test_por_categoria(self, notas_mock):
        res = resumo_geral(notas_mock)
        assert 'VENDA' in res['por_categoria']
        assert 'REMESSA' in res['por_categoria']
        assert res['por_categoria']['VENDA']['notas'] == 2
        assert res['por_categoria']['REMESSA']['notas'] == 1

    def test_top_dest_ordenado_por_valor(self, notas_mock):
        res = resumo_geral(notas_mock)
        top = res['top_dest']
        assert len(top) >= 2
        assert top[0]['valor'] >= top[1]['valor']

    def test_por_mes(self, notas_mock):
        res = resumo_geral(notas_mock)
        assert '01/2025' in res['por_mes']
        assert '02/2025' in res['por_mes']

    def test_lista_vazia(self):
        res = resumo_geral([])
        assert res['total_notas'] == 0
        assert res['total_valor'] == 0.0
        assert res['ticket_medio'] == 0

# ─── Testes: validar_nfa() ───────────────────────────────────────────────────

class TestValidarNFA:
    """Testa o validador lógico de NFA."""
    
    def test_nfa_valida(self):
        n = NFA(chave_acesso='1'*44, natureza='VENDA', produtos=[Produto(vlr_total=100)])
        valida, erros = validar_nfa(n)
        assert valida is True
        assert len(erros) == 0

    def test_chave_curta(self):
        n = NFA(chave_acesso='123', produtos=[Produto(vlr_total=100)])
        valida, erros = validar_nfa(n)
        assert valida is False
        assert any("tamanho incorreto" in e or "44" in e for e in erros)

    def test_sem_produtos(self):
        n = NFA(chave_acesso='1'*44, natureza='REMESSA', produtos=[])
        valida, erros = validar_nfa(n)
        assert valida is False
        assert any("Nenhum produto" in e for e in erros)

    def test_venda_zerada(self):
        # VENDA com valor zero
        n = NFA(chave_acesso='1'*44, natureza='VENDA', produtos=[Produto(vlr_total=0)])
        valida, erros = validar_nfa(n)
        assert valida is False
        assert any("zerado" in e for e in erros)

    def test_remessa_zerad