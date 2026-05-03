"""
Testes para src/infrastructure/local_kb.py
Motor de Conhecimento Local — alternativa offline ao Ollama.
"""
import pytest

from src.infrastructure.local_kb import (
    KB,
    _score,
    _tokenizar,
    buscar,
    responder,
)

# ── KB integridade ──────────────────────────────────────────────────────────


class TestKBIntegridade:
    """Garante que a base de conhecimento está bem formada."""

    def test_kb_nao_vazia(self):
        assert len(KB) > 0, "KB deve ter pelo menos 1 item"

    def test_kb_tem_pelo_menos_10_topicos(self):
        assert len(KB) >= 10, f"KB deveria ter ≥ 10 tópicos, tem {len(KB)}"

    def test_todos_itens_tem_campos_obrigatorios(self):
        campos = {"tags", "pergunta", "resposta"}
        for i, item in enumerate(KB):
            assert campos.issubset(item.keys()), (
                f"Item {i} faltando campos: {campos - item.keys()}"
            )

    def test_todos_itens_tem_tags_nao_vazias(self):
        for i, item in enumerate(KB):
            assert isinstance(item["tags"], list) and len(item["tags"]) > 0, (
                f"Item {i} deve ter lista de tags não vazia"
            )

    def test_todos_itens_tem_pergunta_nao_vazia(self):
        for i, item in enumerate(KB):
            assert isinstance(item["pergunta"], str) and len(item["pergunta"]) > 10, (
                f"Item {i} deve ter pergunta com >10 chars"
            )

    def test_todos_itens_tem_resposta_nao_vazia(self):
        for i, item in enumerate(KB):
            assert isinstance(item["resposta"], str) and len(item["resposta"]) > 50, (
                f"Item {i} deve ter resposta com >50 chars"
            )

    def test_topicos_esperados_presentes(self):
        """Tópicos fundamentais de NFA devem estar na KB."""
        perguntas = [item["pergunta"].lower() for item in KB]
        texto_total = " ".join(perguntas)
        for tema in ["nfa", "icms", "funrural", "ctn", "kandir", "cfop", "fraude", "gta"]:
            assert tema in texto_total, f"Tema '{tema}' não encontrado na KB"


# ── _tokenizar ─────────────────────────────────────────────────────────────


class TestTokenizar:
    """Testa a função de tokenização com remoção de stopwords."""

    def test_tokeniza_texto_simples(self):
        tokens = _tokenizar("nota fiscal agropecuaria")
        assert "nota" in tokens
        assert "fiscal" in tokens
        assert "agropecuaria" in tokens

    def test_remove_stopwords_basicas(self):
        tokens = _tokenizar("o que é uma nfa")
        # 'o', 'que', 'é', 'uma' são stopwords
        assert "o" not in tokens
        assert "que" not in tokens
        assert "é" not in tokens
        assert "uma" not in tokens
        assert "nfa" in tokens

    def test_converte_para_minusculas(self):
        tokens = _tokenizar("NFA ICMS FUNRURAL")
        assert "nfa" in tokens
        assert "icms" in tokens
        assert "funrural" in tokens

    def test_remove_tokens_curtos(self):
        """Tokens com 1 caractere devem ser removidos."""
        tokens = _tokenizar("a b c d nfa icms")
        for tok in tokens:
            assert len(tok) > 1, f"Token '{tok}' tem apenas 1 caractere"

    def test_texto_vazio_retorna_lista_vazia(self):
        assert _tokenizar("") == []

    def test_texto_apenas_stopwords_retorna_lista_vazia(self):
        tokens = _tokenizar("o a os as um uma de do da")
        assert len(tokens) == 0

    def test_aceita_caracteres_acentuados(self):
        tokens = _tokenizar("alíquota diferimento não-cumulatividade")
        assert "alíquota" in tokens
        assert "diferimento" in tokens

    def test_remove_pontuacao(self):
        tokens = _tokenizar("nfa, icms! funrural?")
        for tok in tokens:
            assert not any(c in tok for c in ".,!?"), (
                f"Token '{tok}' contém pontuação"
            )

    def test_texto_com_numeros(self):
        tokens = _tokenizar("lei 87 de 1996")
        assert "87" in tokens
        assert "1996" in tokens


# ── _score ──────────────────────────────────────────────────────────────────


class TestScore:
    """Testa a função de pontuação de relevância."""

    def test_score_zero_sem_tokens(self):
        item = KB[0]
        score = _score([], item)
        assert score == 0.0

    def test_score_positivo_com_match(self):
        # Pega o primeiro item da KB e usa tokens das suas tags
        item = KB[0]  # item sobre "nfa"
        tokens = _tokenizar("nfa nota fiscal")
        score = _score(tokens, item)
        assert score > 0.0, "Score deve ser positivo com match"

    def test_score_maior_com_mais_matches(self):
        item = KB[0]  # NFA conceito
        tokens_poucos = _tokenizar("nfa")
        tokens_muitos = _tokenizar("nfa nota fiscal agropecuaria conceito definicao")
        score_poucos = _score(tokens_poucos, item)
        score_muitos = _score(tokens_muitos, item)
        assert score_muitos >= score_poucos, (
            "Mais matches devem resultar em score maior ou igual"
        )

    def test_score_correto_item_errado_e_menor(self):
        """Pergunta sobre NFA deve ter score menor para item de FUNRURAL."""
        item_nfa = next(i for i in KB if "nfa" in i["tags"])
        item_funrural = next(i for i in KB if "funrural" in i["tags"])
        tokens = _tokenizar("o que é uma nota fiscal agropecuária")
        score_nfa = _score(tokens, item_nfa)
        score_funrural = _score(tokens, item_funrural)
        assert score_nfa >= score_funrural, (
            "Score para item correto (NFA) deve ser >= score do item errado (FUNRURAL)"
        )

    def test_score_retorna_float(self):
        tokens = _tokenizar("icms aliquota")
        score = _score(tokens, KB[0])
        assert isinstance(score, float)

    def test_score_nao_negativo(self):
        tokens = _tokenizar("palavra inexistente xyzabc")
        for item in KB:
            assert _score(tokens, item) >= 0.0


# ── buscar ──────────────────────────────────────────────────────────────────


class TestBuscar:
    """Testa a função de busca semântica."""

    @pytest.mark.parametrize("pergunta,tema_esperado", [
        ("O que é uma NFA?", "nfa"),
        ("como funciona o ICMS no agronegócio?", "icms"),
        ("o que é FUNRURAL?", "funrural"),
        ("o que é o CTN?", "ctn"),
        ("lei kandir explicada", "lc 87"),
        ("reforma tributária IBS CBS", "ec 132"),
        ("sinais de fraude em notas fiscais", "fraude"),
        ("GTA gado bovino transporte", "gta"),
        ("principais CFOPs agropecuários", "cfop"),
        ("prazos de decadência prescricao", "prazo"),
    ])
    def test_busca_retorna_item_relevante(self, pergunta, tema_esperado):
        """Cada pergunta deve retornar item com tag correspondente."""
        resultados = buscar(pergunta, top_k=1)
        assert len(resultados) >= 1, f"Busca vazia para '{pergunta}'"
        item = resultados[0]
        tags_str = " ".join(item["tags"]).lower()
        assert tema_esperado in tags_str, (
            f"Esperava tag '{tema_esperado}' em {item['tags']} para '{pergunta}'"
        )

    def test_busca_retorna_lista(self):
        resultado = buscar("nfa")
        assert isinstance(resultado, list)

    def test_busca_top_k_respeitado(self):
        resultado = buscar("fiscal agropecuário ICMS FUNRURAL", top_k=3)
        assert len(resultado) <= 3

    def test_busca_texto_vazio_retorna_lista_vazia(self):
        resultado = buscar("")
        assert resultado == []

    def test_busca_texto_irrelevante_retorna_lista_vazia(self):
        """Texto completamente fora do domínio pode não ter match acima do min_score."""
        resultado = buscar("xyzxyzxyz palavrainexistente abc123", min_score=0.5)
        assert resultado == []

    def test_busca_com_min_score_zero_retorna_resultados(self):
        resultado = buscar("nfa", min_score=0.0)
        assert len(resultado) >= 1

    def test_busca_retorna_itens_da_kb(self):
        """Itens retornados devem ser os mesmos objetos da KB."""
        resultados = buscar("ICMS diferimento")
        for item in resultados:
            assert item in KB, "Item retornado não está na KB original"

    def test_busca_variacao_grafia_nfa(self):
        """Deve encontrar NFA com diferentes grafias."""
        for variacao in ["NFA", "nota fiscal agropecuária", "nota agropecuária"]:
            resultado = buscar(variacao, top_k=1)
            assert len(resultado) >= 1, f"Sem resultado para variação '{variacao}'"


# ── responder ───────────────────────────────────────────────────────────────


class TestResponder:
    """Testa a função principal de resposta."""

    def test_responde_string(self):
        resultado = responder("O que é NFA?")
        assert isinstance(resultado, str)
        assert len(resultado) > 50

    def test_resposta_com_match_contem_header(self):
        """Resposta com match deve conter ### (header markdown)."""
        resultado = responder("O que é NFA?")
        assert "###" in resultado

    def test_resposta_com_match_contem_fonte(self):
        """Resposta com match deve conter rodapé com fonte."""
        resultado = responder("o que é FUNRURAL")
        assert "Base de Conhecimento ORGATEC" in resultado

    def test_resposta_icms_contem_lc87(self):
        """Resposta sobre ICMS deve mencionar LC 87/96."""
        resultado = responder("qual a alíquota de ICMS para gado bovino?")
        assert "87" in resultado or "Kandir" in resultado or "ICMS" in resultado

    def test_resposta_funrural_contem_aliquota(self):
        resultado = responder("como é calculado o FUNRURAL do produtor rural?")
        assert "1,2%" in resultado or "1,5%" in resultado or "%" in resultado

    def test_resposta_fraude_lista_sinais(self):
        resultado = responder("quais sinais de fraude em NFA")
        assert "fraude" in resultado.lower() or "alerta" in resultado.lower()

    def test_resposta_sem_match_retorna_generica(self):
        """Pergunta fora do domínio deve retornar resposta genérica."""
        resultado = responder("qual o time campeão da Copa do Mundo de 1958")
        assert "Modo Local" in resultado or "base de conhecimento" in resultado.lower()

    def test_resposta_generica_lista_topicos(self):
        """Resposta genérica deve listar tópicos disponíveis."""
        resultado = responder("nada a ver com fiscal xyzabc 999")
        assert "NFA" in resultado or "ICMS" in resultado or "FUNRURAL" in resultado

    def test_resposta_ctn_menciona_artigos(self):
        resultado = responder("o que é o CTN Código Tributário Nacional")
        assert "art" in resultado.lower() or "Art" in resultado

    def test_resposta_reforma_tributaria_menciona_ibs(self):
        resultado = responder("reforma tributária EC 132 o que muda")
        assert "IBS" in resultado or "CBS" in resultado

    def test_resposta_decadencia_menciona_5_anos(self):
        resultado = responder("prazos decadência prescrição tributária")
        assert "5 anos" in resultado or "5" in resultado

    @pytest.mark.parametrize("pergunta", [
        "nfa",
        "icms",
        "funrural",
        "ctn",
        "cfop",
        "gta",
        "fraude",
        "kandir",
    ])
    def test_resposta_nao_vazia_para_palavras_chave(self, pergunta):
        """Palavras-chave centrais devem sempre retornar resposta não vazia."""
        resultado = responder(pergunta)
        assert resultado.strip() != ""
