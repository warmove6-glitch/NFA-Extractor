"""Testes da bateria forense T-01 a T-08 do OrgAudi 1.0."""
from __future__ import annotations

from src.domain.auditoria_forense import (
    SEV_ALTO,
    SEV_CRITICO,
    SEV_MEDIO,
    _cnpj_valido,
    _cpf_valido,
    auditar_lote,
    teste_t01_concentracao,
    teste_t02_smurfing,
    teste_t04_concentracao_pf,
    teste_t05_ie_inconsistente,
    teste_t06_sazonalidade,
    teste_t07_documental,
)
from src.domain.extractor import NFA, Parte


def _nfa(numero, valor, qty=10, data="01/01/2025", natureza="VENDA",
         rem_doc="06931195190", rem_nome="ADELA",
         dest_doc="11111111111", dest_nome="DEST", rem_ie=None) -> NFA:
    return NFA(
        numero=numero,
        emissao=data,
        natureza=natureza,
        valor_total=valor,
        quantidade_total=qty,
        remetente=Parte(nome=rem_nome, cpf_cnpj=rem_doc, ie=rem_ie),
        destinatario=Parte(nome=dest_nome, cpf_cnpj=dest_doc),
    )


class TestValidacaoDocumentos:
    def test_cpf_valido(self):
        assert _cpf_valido("06931195190")        # ADELA real
        assert _cpf_valido("069.311.951-90")     # com pontuação

    def test_cpf_invalido(self):
        assert not _cpf_valido("00000000000")    # todos iguais
        assert not _cpf_valido("12345678900")    # DV errado
        assert not _cpf_valido("12345")          # tamanho

    def test_cnpj_valido(self):
        assert _cnpj_valido("11.222.333/0001-81")
        assert _cnpj_valido("11222333000181")

    def test_cnpj_invalido(self):
        assert not _cnpj_valido("00.000.000/0000-00")
        assert not _cnpj_valido("11.222.333/0001-99")  # DV errado


class TestT01Concentracao:
    def test_nota_acima_de_10_pct_dispara(self):
        cli = "06931195190"
        # 20 notas pequenas (R$ 5k cada = R$ 100k, 5% cada) + 1 nota gigante (R$ 100k = 50%)
        notas = [_nfa(f"{i}", 5_000, rem_doc=cli) for i in range(20)]
        notas.append(_nfa("BIG", 100_000, rem_doc=cli))
        receita = 200_000
        achados = teste_t01_concentracao(notas, receita, cli)
        assert len(achados) == 1
        assert achados[0].severidade == SEV_CRITICO
        assert achados[0].teste == "T-01"

    def test_sem_concentracao_nao_dispara(self):
        cli = "06931195190"
        # 50 notas iguais → cada nota = 2% (longe do limiar 10%)
        notas = [_nfa(f"{i}", 10_000, rem_doc=cli) for i in range(50)]
        achados = teste_t01_concentracao(notas, 500_000, cli)
        assert achados == []


class TestT02Smurfing:
    def test_3_notas_mesmo_dest_dia_valor_identico(self):
        cli = "06931195190"
        dest = "11111111111"
        # 3 notas no mesmo dia, mesmo destinatário, mesmo valor
        notas = [
            _nfa("1", 13_210.00, data="09/11/2025", rem_doc=cli, dest_doc=dest),
            _nfa("2", 13_210.00, data="09/11/2025", rem_doc=cli, dest_doc=dest),
            _nfa("3", 13_210.00, data="09/11/2025", rem_doc=cli, dest_doc=dest),
        ]
        achados = teste_t02_smurfing(notas, cli)
        assert len(achados) == 1
        assert achados[0].severidade == SEV_CRITICO
        assert achados[0].teste == "T-02"
        assert "3" in achados[0].descricao or "smurfing" in achados[0].titulo.lower() or "Fragmentação" in achados[0].titulo

    def test_valores_diferentes_nao_dispara(self):
        cli = "06931195190"
        dest = "11111111111"
        notas = [
            _nfa("1", 10_000, data="09/11/2025", rem_doc=cli, dest_doc=dest),
            _nfa("2", 20_000, data="09/11/2025", rem_doc=cli, dest_doc=dest),
            _nfa("3", 30_000, data="09/11/2025", rem_doc=cli, dest_doc=dest),
        ]
        achados = teste_t02_smurfing(notas, cli)
        assert achados == []

    def test_destinatarios_diferentes_nao_dispara(self):
        cli = "06931195190"
        notas = [
            _nfa("1", 10_000, data="09/11/2025", rem_doc=cli, dest_doc="11111111111"),
            _nfa("2", 10_000, data="09/11/2025", rem_doc=cli, dest_doc="22222222222"),
            _nfa("3", 10_000, data="09/11/2025", rem_doc=cli, dest_doc="33333333333"),
        ]
        achados = teste_t02_smurfing(notas, cli)
        assert achados == []


class TestT04ConcentracaoPF:
    def test_pf_recorrente_dispara(self):
        cli = "06931195190"
        notas = []
        # 100% PFs (10 vendas a 1 PF = 3+ aquisições)
        for i in range(10):
            notas.append(_nfa(f"{i}", 50_000, rem_doc=cli, dest_doc="11111111111", dest_nome="LARANJA SUSPEITO"))
        achados = teste_t04_concentracao_pf(notas, cli)
        assert len(achados) == 1
        assert achados[0].severidade == SEV_ALTO

    def test_so_pj_nao_dispara(self):
        cli = "06931195190"
        notas = [
            _nfa(f"{i}", 50_000, rem_doc=cli, dest_doc="11222333000181")
            for i in range(5)
        ]
        achados = teste_t04_concentracao_pf(notas, cli)
        assert achados == []


class TestT05IEInconsistente:
    def test_2_ies_disparam(self):
        cli = "06931195190"
        notas = [
            _nfa("1", 10_000, rem_doc=cli, dest_doc="11111111111", rem_ie=None),
            # Mesmo CPF do remetente em duas notas, mas com IEs diferentes
        ]
        # Ajusta — duas notas onde o MESMO CPF aparece com IE diferente
        notas = [
            NFA(numero="1", valor_total=1000,
                remetente=Parte(nome="A", cpf_cnpj="06931195190", ie="11111"),
                destinatario=Parte(nome="X", cpf_cnpj="22222222222")),
            NFA(numero="2", valor_total=1000,
                remetente=Parte(nome="A", cpf_cnpj="06931195190", ie="22222"),
                destinatario=Parte(nome="X", cpf_cnpj="22222222222")),
        ]
        achados = teste_t05_ie_inconsistente(notas, cli)
        assert len(achados) == 1
        assert achados[0].severidade == SEV_ALTO


class TestT06Sazonalidade:
    def test_concentracao_out_dez_acima_45pct(self):
        cli = "06931195190"
        notas = []
        # 10% Jan
        notas.append(_nfa("1", 100_000, data="15/01/2025", rem_doc=cli))
        # 50% Outubro
        notas.append(_nfa("2", 500_000, data="15/10/2025", rem_doc=cli))
        # 40% Dezembro
        notas.append(_nfa("3", 400_000, data="15/12/2025", rem_doc=cli))
        achados = teste_t06_sazonalidade(notas, cli, receita_imediata=1_000_000)
        # Out-Dez = 90% → dispara
        assert len(achados) == 1
        assert achados[0].severidade == SEV_ALTO

    def test_distribuicao_uniforme_nao_dispara(self):
        cli = "06931195190"
        notas = [_nfa(f"{m}", 100_000, data=f"15/{m:02d}/2025", rem_doc=cli) for m in range(1, 13)]
        achados = teste_t06_sazonalidade(notas, cli, receita_imediata=1_200_000)
        assert achados == []


class TestT07Documental:
    def test_todos_validos_zero_achados(self):
        notas = [
            _nfa("1", 1000, rem_doc="06931195190", dest_doc="04812287138"),  # ambos válidos
        ]
        achados, cont = teste_t07_documental(notas)
        assert achados == []
        assert cont["invalidos"] == 0

    def test_doc_invalido_dispara(self):
        notas = [
            _nfa("1", 1000, rem_doc="00000000000", dest_doc="04812287138"),
        ]
        achados, cont = teste_t07_documental(notas)
        assert len(achados) == 1
        assert achados[0].severidade == SEV_MEDIO


class TestPipelineCompleto:
    def test_auditar_lote_calcula_sintese(self):
        cli = "06931195190"
        notas = [
            _nfa("1", 100_000, rem_doc=cli, dest_doc="04812287138"),  # venda
            _nfa("2", 50_000, rem_doc=cli, dest_doc="11222333000181", natureza="REMESSA LEILAO"),
            _nfa("3", 30_000, rem_doc="22222222222", dest_doc=cli),  # compra
        ]
        r = auditar_lote(notas, "ADELA", cli)
        assert r.total_notas == 3
        assert r.receita_imediata == 100_000
        assert r.transito_leilao == 50_000
        assert r.valor_compras == 30_000
        assert r.funrural_estimado == 100_000 * 0.015

    def test_auditar_lote_score_baixo_sem_anomalias(self):
        cli = "06931195190"
        # 50 vendas pequenas (2% cada) a destinatários únicos (sem padrões)
        notas = []
        for i in range(50):
            notas.append(_nfa(
                f"{i}",
                10_000,
                rem_doc=cli,
                dest_doc=f"{i:02d}222333000181",  # CNPJs diferentes (PJ, não dispara T-04)
                natureza="VENDA",
                data=f"{(i % 28) + 1:02d}/{(i % 12) + 1:02d}/2025",
            ))
        r = auditar_lote(notas, "ADELA", cli)
        # Sem anomalias críticas — só achados informativos M-01, M-02
        criticos = [a for a in r.achados if a.severidade == SEV_CRITICO]
        assert len(criticos) == 0

    def test_pdf_gera_sem_erro(self, tmp_path):
        """Smoke test: bateria + geração do PDF não lançam exceção."""
        from src.application.reports.relatorio_tecnico_orgatec import gerar_relatorio_tecnico_pdf

        cli = "06931195190"
        notas = [_nfa(f"{i}", 50_000, rem_doc=cli, dest_doc="04812287138") for i in range(5)]
        r = auditar_lote(notas, "ADELA TESTE", cli)
        out = tmp_path / "relatorio.pdf"
        gerar_relatorio_tecnico_pdf(r, out)
        assert out.exists()
        # Header PDF
        assert out.read_bytes()[:4] == b"%PDF"
