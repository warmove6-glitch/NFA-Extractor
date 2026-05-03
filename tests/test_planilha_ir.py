"""Testes para geração de planilha IRPF."""

import pytest

from src.domain.extractor import NFA, Parte
from src.domain.planilha_ir import gerar_dados_planilha, gerar_html_planilha


@pytest.fixture
def notas_diversas():
    """Notas com diferentes naturezas e meses."""
    return [
        NFA(
            numero="NF000001",
            natureza="VENDA",
            emissao="15/01/2026",
            valor_total=5000.0,
            valor_icms=900.0,
            quantidade_total=100.0,
            remetente=Parte(nome="Fazenda XYZ", cpf_cnpj="12.345.678/0001-90"),
            destinatario=Parte(nome="Frigorífico ABC", cpf_cnpj="98.765.432/0001-10"),
        ),
        NFA(
            numero="NF000002",
            natureza="VENDA",
            emissao="20/01/2026",
            valor_total=3500.0,
            valor_icms=630.0,
            quantidade_total=70.0,
            remetente=Parte(nome="Fazenda XYZ", cpf_cnpj="12.345.678/0001-90"),
            destinatario=Parte(nome="Frigorífico DEF", cpf_cnpj="11.222.333/0001-44"),
        ),
        NFA(
            numero="NF000003",
            natureza="REMESSA",
            emissao="10/02/2026",
            valor_total=2000.0,
            valor_icms=360.0,
            quantidade_total=50.0,
            remetente=Parte(nome="Fazenda XYZ", cpf_cnpj="12.345.678/0001-90"),
            destinatario=Parte(nome="Fazenda Temporária", cpf_cnpj="55.666.777/0001-88"),
        ),
        NFA(
            numero="NF000004",
            natureza="TRANSFERENCIA",
            emissao="25/02/2026",
            valor_total=1500.0,
            valor_icms=270.0,
            quantidade_total=30.0,
            remetente=Parte(nome="Fazenda XYZ", cpf_cnpj="12.345.678/0001-90"),
            destinatario=Parte(nome="Fazenda Matriz", cpf_cnpj="12.345.678/0001-91"),
        ),
    ]


class TestPlanilhaIR:
    """Testes da planilha IRPF."""

    def test_gera_dados_planilha(self, notas_diversas):
        """Testa geração de dados estruturados da planilha."""
        dados = gerar_dados_planilha(notas_diversas, "João Silva")

        assert dados["produtor"] == "João Silva"
        assert "periodo" in dados
        assert dados["total_notas"] == 4
        assert dados["total_cabecas"] == 250.0
        assert dados["faturamento_total"] == 12000.0

    def test_totais_por_natureza(self, notas_diversas):
        """Testa cálculo de totais por natureza."""
        dados = gerar_dados_planilha(notas_diversas, "Teste")

        assert "totais_natureza" in dados
        assert "VENDA" in dados["totais_natureza"]
        assert "REMESSA" in dados["totais_natureza"]
        assert "TRANSFERENCIA" in dados["totais_natureza"]

        venda_total = dados["totais_natureza"]["VENDA"]
        assert venda_total["notas"] == 2
        assert venda_total["cabecas"] == 170.0
        assert venda_total["valor"] == 8500.0

    def test_organizacao_por_mes(self, notas_diversas):
        """Testa organização de dados por mês."""
        dados = gerar_dados_planilha(notas_diversas, "Teste")

        por_natureza_mes = dados["por_natureza_mes"]

        # Verificar janeiro (mês 01)
        venda_jan = por_natureza_mes["VENDA"][1]
        assert venda_jan["notas"] == 2
        assert venda_jan["cabecas"] == 170.0
        assert venda_jan["valor"] == 8500.0

        # Verificar fevereiro (mês 02)
        remessa_fev = por_natureza_mes["REMESSA"][2]
        assert remessa_fev["notas"] == 1
        assert remessa_fev["cabecas"] == 50.0
        assert remessa_fev["valor"] == 2000.0

    def test_gera_html_planilha(self, notas_diversas):
        """Testa geração de HTML da planilha."""
        dados = gerar_dados_planilha(notas_diversas, "Produtor Teste")
        html = gerar_html_planilha(dados)

        assert "<!DOCTYPE html>" in html
        assert "RELATÓRIO DE MOVIMENTAÇÃO" in html
        assert "Produtor Teste" in html
        assert "VENDA" in html
        assert "REMESSA" in html
        assert "Lei 8.023/90" in html

    def test_html_contem_valores_formatados(self, notas_diversas):
        """Testa que HTML contém valores formatados corretamente."""
        dados = gerar_dados_planilha(notas_diversas, "Teste")
        html = gerar_html_planilha(dados)

        # Verificar formatação de moeda
        assert "R$ 12.000,00" in html or "12000" in html
        assert "170" in html  # cabeças de VENDA
        assert "250" in html  # total de cabeças

    def test_lista_vazia_gera_html_valido(self):
        """Testa que lista vazia gera HTML válido."""
        dados = gerar_dados_planilha([], "Produtor")
        html = gerar_html_planilha(dados)

        assert "<!DOCTYPE html>" in html
        assert "Produtor" in html
        # Sem totais por natureza, não deve incluir tabelas de natureza
        assert "TOTAL DE NOTAS" in html or "total" in html.lower()


class TestPlanilhaIRComCPF:
    """Testes da planilha com classificação por posição do contribuinte (Regra 1)."""

    CPF = "12345678901"
    CPF_OUTRO = "99999999999"

    def _nota(
        self,
        rem_cpf: str,
        dest_cpf: str,
        natureza: str,
        valor: float = 2000.0,
        mes: str = "15/01/2026",
    ) -> NFA:
        return NFA(
            numero="NF000001",
            natureza=natureza,
            emissao=mes,
            valor_total=valor,
            valor_icms=0.0,
            quantidade_total=20.0,
            remetente=Parte(nome="A", cpf_cnpj=rem_cpf),
            destinatario=Parte(nome="B", cpf_cnpj=dest_cpf),
        )

    def test_compra_aparece_nos_totais(self):
        """Nota com destinatário = contribuinte gera COMPRA nos totais."""
        notas = [
            self._nota(self.CPF, self.CPF_OUTRO, "VENDA"),   # RECEITA → VENDA
            self._nota(self.CPF_OUTRO, self.CPF, "COMPRA"),  # DESPESA → COMPRA
        ]
        dados = gerar_dados_planilha(notas, "Produtor", self.CPF)
        assert "COMPRA" in dados["totais_natureza"]
        assert "VENDA" in dados["totais_natureza"]

    def test_compra_valores_corretos(self):
        """Valor da COMPRA corresponde ao da nota onde contribuinte é destinatário."""
        notas = [
            self._nota(self.CPF_OUTRO, self.CPF, "VENDA", valor=3500.0),   # COMPRA
            self._nota(self.CPF, self.CPF_OUTRO, "VENDA", valor=7000.0),   # VENDA
        ]
        dados = gerar_dados_planilha(notas, "Produtor", self.CPF)
        assert dados["totais_natureza"]["COMPRA"]["valor"] == pytest.approx(3500.0)
        assert dados["totais_natureza"]["VENDA"]["valor"] == pytest.approx(7000.0)

    def test_compra_no_html(self):
        """HTML gerado menciona COMPRA e usa cor vermelha (#ef4444)."""
        notas = [
            self._nota(self.CPF, self.CPF_OUTRO, "VENDA"),
            self._nota(self.CPF_OUTRO, self.CPF, "COMPRA"),
        ]
        dados = gerar_dados_planilha(notas, "Produtor", self.CPF)
        html = gerar_html_planilha(dados)
        assert "COMPRA" in html
        assert "#ef4444" in html  # cor vermelha reservada para COMPRA

    def test_sem_cpf_nao_quebra(self, notas_diversas):
        """Sem CPF, comportamento legacy inalterado."""
        dados = gerar_dados_planilha(notas_diversas, "Produtor")
        assert "VENDA" in dados["totais_natureza"]
        assert "REMESSA" in dados["totais_natureza"]
        assert "TRANSFERENCIA" in dados["totais_natureza"]

    def test_compra_na_tabela_por_mes(self):
        """COMPRA aparece nas colunas mensais corretamente."""
        notas = [
            self._nota(self.CPF_OUTRO, self.CPF, "COMPRA", mes="10/03/2026"),
            self._nota(self.CPF_OUTRO, self.CPF, "COMPRA", mes="20/03/2026"),
        ]
        dados = gerar_dados_planilha(notas, "Produtor", self.CPF)
        # Mês 3 deve ter 2 notas de COMPRA
        assert dados["por_natureza_mes"]["COMPRA"][3]["notas"] == 2
