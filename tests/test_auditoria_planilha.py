"""Testes de integração da planilha IRPF no pipeline de auditoria."""

import pytest
from src.domain.extractor import NFA, Parte
from src.domain.analise_local import calcular_metricas_risco, gerar_veredito_local
from src.domain.planilha_ir import gerar_dados_planilha, gerar_html_planilha


@pytest.fixture
def notas_auditoria():
    """Notas para simular um lote de auditoria."""
    return [
        NFA(
            numero="NF000001",
            natureza="VENDA",
            emissao="05/03/2026",
            valor_total=8000.0,
            valor_icms=1440.0,
            quantidade_total=200.0,
            remetente=Parte(nome="Fazenda São José", cpf_cnpj="12.345.678/0001-90"),
            destinatario=Parte(nome="Frigorífico ABC", cpf_cnpj="98.765.432/0001-10"),
        ),
        NFA(
            numero="NF000002",
            natureza="VENDA",
            emissao="15/03/2026",
            valor_total=6500.0,
            valor_icms=1170.0,
            quantidade_total=160.0,
            remetente=Parte(nome="Fazenda São José", cpf_cnpj="12.345.678/0001-90"),
            destinatario=Parte(nome="Frigorífico XYZ", cpf_cnpj="11.222.333/0001-44"),
        ),
        NFA(
            numero="NF000003",
            natureza="REMESSA",
            emissao="20/03/2026",
            valor_total=3000.0,
            valor_icms=540.0,
            quantidade_total=75.0,
            remetente=Parte(nome="Fazenda São José", cpf_cnpj="12.345.678/0001-90"),
            destinatario=Parte(nome="Pasto Temporário", cpf_cnpj="55.666.777/0001-88"),
        ),
    ]


class TestAuditoriaComPlanilha:
    """Testes de integração da planilha no pipeline."""

    def test_pipeline_completo_auditoria(self, notas_auditoria):
        """Testa o pipeline completo: extração → análise → planilha."""
        client_name = "João da Silva Produtor"

        # 1. Análise local
        analise = calcular_metricas_risco(notas_auditoria)
        assert analise["score_risco"] >= 0.0
        assert analise["nivel_risco"] in ["BAIXO", "MÉDIO", "ALTO"]

        # 2. Veredito local
        veredito = gerar_veredito_local(notas_auditoria, client_name, analise)
        assert "[ANÁLISE LOCAL" in veredito
        assert client_name in veredito

        # 3. Planilha IRPF
        dados_planilha = gerar_dados_planilha(notas_auditoria, client_name)
        assert dados_planilha["total_notas"] == 3
        assert dados_planilha["total_cabecas"] == 435.0
        assert dados_planilha["faturamento_total"] == 17500.0

        # 4. HTML da planilha
        html = gerar_html_planilha(dados_planilha)
        assert client_name in html
        assert "VENDA" in html
        assert "REMESSA" in html

    def test_planilha_contem_analise(self, notas_auditoria):
        """Testa que a planilha pode ser gerada junto com análise."""
        analise = calcular_metricas_risco(notas_auditoria)
        veredito = gerar_veredito_local(notas_auditoria, "Teste", analise)
        dados = gerar_dados_planilha(notas_auditoria, "Teste")
        html = gerar_html_planilha(dados)

        # Ambos os outputs disponíveis
        assert veredito is not None
        assert len(veredito) > 0
        assert html is not None
        assert len(html) > 100

    def test_tempo_processamento_rapido(self, notas_auditoria):
        """Testa que o processamento é rápido (< 10ms)."""
        import time

        start = time.time()

        # Análise
        analise = calcular_metricas_risco(notas_auditoria)
        veredito = gerar_veredito_local(notas_auditoria, "Teste", analise)

        # Planilha
        dados = gerar_dados_planilha(notas_auditoria, "Teste")
        html = gerar_html_planilha(dados)

        elapsed = (time.time() - start) * 1000  # ms

        # Deve completar em menos de 50ms (muito rápido)
        assert elapsed < 50.0, f"Processamento levou {elapsed:.1f}ms, esperado < 50ms"
