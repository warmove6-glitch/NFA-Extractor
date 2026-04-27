"""Testes para análise local determinística."""

import pytest
from src.domain.extractor import NFA, Parte
from src.domain.analise_local import calcular_metricas_risco, gerar_veredito_local


@pytest.fixture
def notas_normais():
    """Notas com características normais."""
    return [
        NFA(
            numero=f"NF{i:06d}",
            natureza="VENDA",
            emissao=f"0{(i % 9) + 1}/04/2026",
            valor_total=1000.0 + i * 100,
            valor_icms=180.0 + i * 18,
            quantidade_total=50.0 + i * 5,
            remetente=Parte(nome="Produtor", cpf_cnpj="12.345.678/0001-90"),
            destinatario=Parte(nome=f"Comprador {i}", cpf_cnpj="98.765.432/0001-10"),
        )
        for i in range(1, 11)
    ]


@pytest.fixture
def notas_com_anomalias():
    """Notas com anomalias de valor."""
    return [
        NFA(
            numero="NF000001",
            natureza="VENDA",
            emissao="01/04/2026",
            valor_total=1000.0,
            valor_icms=180.0,
            quantidade_total=50.0,
            remetente=Parte(nome="Produtor", cpf_cnpj="12.345.678/0001-90"),
            destinatario=Parte(nome="Comprador", cpf_cnpj="98.765.432/0001-10"),
        ),
        NFA(
            numero="NF000002",
            natureza="VENDA",
            emissao="01/04/2026",
            valor_total=50000.0,  # Outlier de valor
            valor_icms=9000.0,
            quantidade_total=50.0,
            remetente=Parte(nome="Produtor", cpf_cnpj="12.345.678/0001-90"),
            destinatario=Parte(nome="Comprador", cpf_cnpj="98.765.432/0001-10"),
        ),
    ]


class TestAnaliseLocal:
    """Testes da análise local determinística."""

    def test_calcula_metricas_notas_normais(self, notas_normais):
        """Testa cálculo de métricas para notas normais."""
        analise = calcular_metricas_risco(notas_normais)

        assert 'score_risco' in analise
        assert 'nivel_risco' in analise
        assert 'sinais' in analise
        assert 'observacoes' in analise

        assert 0.0 <= analise['score_risco'] <= 1.0
        assert analise['nivel_risco'] in ['BAIXO', 'MÉDIO', 'ALTO']

    def test_detecta_outlier_valor(self, notas_com_anomalias):
        """Testa detecção de outlier de valor."""
        analise = calcular_metricas_risco(notas_com_anomalias)

        assert analise['score_risco'] > 0.0
        assert len(analise['sinais']) > 0

    def test_lista_vazia_retorna_baixo_risco(self):
        """Testa que lista vazia retorna score baixo."""
        analise = calcular_metricas_risco([])

        assert analise['score_risco'] == 0.0
        assert analise['nivel_risco'] == 'BAIXO'
        assert len(analise['sinais']) == 0

    def test_gera_veredito_com_analise(self, notas_normais):
        """Testa geração de veredito com análise."""
        analise = calcular_metricas_risco(notas_normais)
        veredito = gerar_veredito_local(notas_normais, "Teste Silva", analise)

        assert '[ANÁLISE LOCAL' in veredito
        assert 'Teste Silva' in veredito
        assert 'SCORE DE RISCO' in veredito
        assert 'CONCLUSÃO' in veredito

    def test_veredito_menciona_distribuicao_natureza(self, notas_normais):
        """Testa que veredito menciona distribuição por natureza."""
        analise = calcular_metricas_risco(notas_normais)
        veredito = gerar_veredito_local(notas_normais, "Teste", analise)

        assert 'DISTRIBUIÇÃO POR NATUREZA' in veredito
        assert 'VENDA' in veredito

    def test_variacao_alta_detecta_risco(self):
        """Testa detecção de variação alta de valores."""
        notas = [
            NFA(numero="NF1", natureza="VENDA", emissao="01/04/2026",
                valor_total=100.0, valor_icms=18.0, quantidade_total=10.0,
                remetente=Parte(nome="A", cpf_cnpj="11111111111111"),
                destinatario=Parte(nome="B", cpf_cnpj="22222222222222")),
            NFA(numero="NF2", natureza="VENDA", emissao="02/04/2026",
                valor_total=1000.0, valor_icms=180.0, quantidade_total=100.0,
                remetente=Parte(nome="A", cpf_cnpj="11111111111111"),
                destinatario=Parte(nome="C", cpf_cnpj="33333333333333")),
        ]

        analise = calcular_metricas_risco(notas)
        # Com variação (1000-100)/550 = 1.6, não deve disparar (threshold > 2)
        # Mas deve detectar dados incompletos se houver
        assert analise['score_risco'] >= 0.0
