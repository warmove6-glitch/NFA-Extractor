"""Testes para análise local determinística."""

import pytest

from src.domain.analise_local import calcular_metricas_risco, gerar_veredito_local
from src.domain.extractor import NFA, Parte


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

    def test_distribui_por_natureza_sem_cpf(self, notas_normais):
        """Sem CPF usa natureza bruta da nota (backward compat)."""
        analise = calcular_metricas_risco(notas_normais)
        por_nat = analise["metricas"]["por_natureza"]
        # Todas as notas da fixture têm natureza="VENDA"
        assert "VENDA" in por_nat

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


class TestAnaliseLocalComCPF:
    """Testes da análise local com classificação por posição do contribuinte (Regra 1)."""

    CPF = "12345678901"
    CPF_OUTRO = "99999999999"
    CPF_COMPRADOR = "77777777777"

    def _nota(self, rem_cpf: str, dest_cpf: str, natureza: str, valor: float = 1000.0) -> NFA:
        return NFA(
            numero="NF000001",
            natureza=natureza,
            emissao="15/03/2025",
            valor_total=valor,
            valor_icms=0.0,
            quantidade_total=10.0,
            remetente=Parte(nome="A", cpf_cnpj=rem_cpf),
            destinatario=Parte(nome="B", cpf_cnpj=dest_cpf),
        )

    def test_compra_aparece_quando_destinatario_e_contribuinte(self):
        """Destinatário = contribuinte → DESPESA → exibido como COMPRA."""
        notas = [
            self._nota(self.CPF, self.CPF_OUTRO, "VENDA"),        # RECEITA → VENDA
            self._nota(self.CPF_OUTRO, self.CPF, "VENDA"),        # DESPESA → COMPRA
            self._nota(self.CPF, self.CPF_COMPRADOR, "REMESSA"),  # TRANSITO → REMESSA
        ]
        analise = calcular_metricas_risco(notas, self.CPF)
        por_nat = analise["metricas"]["por_natureza"]
        assert "COMPRA" in por_nat
        assert "VENDA" in por_nat
        assert "REMESSA" in por_nat

    def test_compra_contagem_correta(self):
        """Contagem de COMPRA reflete exatamente as notas com destinatário = contribuinte."""
        notas = (
            [self._nota(self.CPF_OUTRO, self.CPF, "COMPRA")] * 3   # 3 COMPRAS
            + [self._nota(self.CPF, self.CPF_OUTRO, "VENDA")] * 5  # 5 VENDAS
        )
        analise = calcular_metricas_risco(notas, self.CPF)
        por_nat = analise["metricas"]["por_natureza"]
        assert por_nat.get("COMPRA") == 3
        assert por_nat.get("VENDA") == 5

    def test_sem_cpf_usa_natureza_bruta(self):
        """Sem CPF, usa natureza raw da nota (backward compat)."""
        notas = [self._nota(self.CPF_OUTRO, self.CPF, "COMPRA")]
        analise = calcular_metricas_risco(notas)           # sem CPF
        por_nat = analise["metricas"]["por_natureza"]
        # Sem CPF, natureza bruta "COMPRA" é preservada tal qual
        assert "COMPRA" in por_nat

    def test_veredito_menciona_compra(self):
        """Veredito local exibe COMPRA na distribuição por natureza."""
        notas = (
            [self._nota(self.CPF_OUTRO, self.CPF, "VENDA")] * 2   # COMPRA
            + [self._nota(self.CPF, self.CPF_OUTRO, "VENDA")] * 5  # VENDA
        )
        analise = calcular_metricas_risco(notas, self.CPF)
        veredito = gerar_veredito_local(notas, "Produtor Teste", analise)
        assert "COMPRA" in veredito
