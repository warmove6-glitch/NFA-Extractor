"""
Testes para src/infrastructure/ai_client.py (v7.2).
Usa mocks para evitar chamadas reais. Testa circuit breaker e nova API.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.domain.extractor import NFA, Parte, Produto
from src.infrastructure.ai_client import (
    SYSTEM_AUDITOR,
    SYSTEM_GAMA,
    SYSTEM_SIGMA,
    TOKEN_LIMITS,
    CircuitBreaker,
    _carregar_env,
    _get_role,
    _is_failure,
    _montar_prompt,
    _montar_prompt_compacto,
    analisar,
    analisar_com_resumo,
    get_ai_metrics,
)

# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def notas_simples() -> list[NFA]:
    return [
        NFA(
            numero='000001',
            emissao='15/01/2025',
            natureza='VENDA DE GADO BOVINO',
            destinatario=Parte(nome='FRIGORIFICO A', cpf_cnpj='12.345.678/0001-90'),
            produtos=[Produto(quantidade=10.0, vlr_total=25000.0)],
        ),
        NFA(
            numero='000002',
            emissao='20/02/2025',
            natureza='REMESSA DE BEZERROS',
            destinatario=Parte(nome='FAZENDA B', cpf_cnpj='98.765.432/0001-10'),
            produtos=[Produto(quantidade=8.0, vlr_total=20000.0)],
        ),
    ]


# ─── Testes: _carregar_env() ──────────────────────────────────────────────────

class TestCarregarEnv:

    def test_le_variavel_de_ambiente(self):
        with patch.dict('os.environ', {'MINHA_CHAVE': 'valor123'}):
            with patch('src.infrastructure.ai_client.CONFIG_PATH') as mock_path:
                mock_path.exists.return_value = False
                resultado = _carregar_env('MINHA_CHAVE')
                assert resultado == 'valor123'

    def test_retorna_string_vazia_se_nao_existe(self):
        with patch('src.infrastructure.ai_client.CONFIG_PATH') as mock_path:
            mock_path.exists.return_value = False
            resultado = _carregar_env('CHAVE_INEXISTENTE_XYZ')
            assert resultado == ''


# ─── Testes: _montar_prompt() ─────────────────────────────────────────────────

class TestMontarPrompt:

    def test_prompt_formato_tabular(self, notas_simples):
        prompt = _montar_prompt(notas_simples)
        assert 'NFA|NAT|' in prompt
        assert '000001' in prompt
        assert '000002' in prompt

    def test_prompt_lista_vazia(self):
        prompt = _montar_prompt([])
        assert 'Nenhuma nota' in prompt

    def test_prompt_compacto_json(self):
        resumo = {"total_notas": 5, "valor": 100000.0}
        result = _montar_prompt_compacto(resumo)
        assert '"total_notas":5' in result


# ─── Testes: _is_failure() ────────────────────────────────────────────────────

class TestIsFailure:

    def test_detecta_inativo(self):
        assert _is_failure("[Claude Inativo]") is True

    def test_detecta_falhou(self):
        assert _is_failure("[Gemini Falhou: timeout]") is True

    def test_detecta_erro(self):
        assert _is_failure("[Ollama Erro: connection refused]") is True

    def test_texto_normal_nao_e_falha(self):
        assert _is_failure("Análise completa com sucesso.") is False

    def test_colchete_no_meio_nao_e_falha(self):
        assert _is_failure("Resultado [parcial] ok") is False


# ─── Testes: CircuitBreaker ───────────────────────────────────────────────────

class TestCircuitBreaker:

    def test_disponivel_inicialmente(self):
        cb = CircuitBreaker(max_failures=3, cooldown=60)
        assert cb.is_available("test") is True

    def test_abre_apos_max_falhas(self):
        cb = CircuitBreaker(max_failures=2, cooldown=60)
        cb.failure("test")
        assert cb.is_available("test") is True
        cb.failure("test")
        assert cb.is_available("test") is False

    def test_reseta_apos_sucesso(self):
        cb = CircuitBreaker(max_failures=2, cooldown=60)
        cb.failure("test")
        cb.success("test", 0.5)
        cb.failure("test")
        # Ainda disponível pois o sucesso resetou o contador
        assert cb.is_available("test") is True

    def test_metrics_retorna_dados(self):
        cb = CircuitBreaker()
        cb.success("ollama", 1.0)
        cb.failure("claude")
        m = cb.metrics()
        assert "ollama" in m
        assert "claude" in m
        assert m["ollama"]["calls"] == 1
        assert m["claude"]["failures"] == 1

    def test_half_open_apos_cooldown(self):
        cb = CircuitBreaker(max_failures=1, cooldown=0.0)  # cooldown zero para teste
        cb.failure("test")
        assert cb.is_available("test") is False
        # Com cooldown=0, já deve permitir
        import time
        time.sleep(0.01)
        assert cb.is_available("test") is True


# ─── Testes: Token Limits ────────────────────────────────────────────────────

class TestTokenLimits:

    def test_sigma_tem_limite(self):
        assert TOKEN_LIMITS["sigma"] == 1024

    def test_auditor_tem_maior_limite(self):
        assert TOKEN_LIMITS["auditor"] > TOKEN_LIMITS["sigma"]

    def test_etl_tem_menor_limite(self):
        assert TOKEN_LIMITS["etl"] < TOKEN_LIMITS["sigma"]


# ─── Testes: analisar() — fallback chain ─────────────────────────────────────

class TestAnalisar:

    def test_retorna_ollama_quando_primeiro_provedor(self, notas_simples):
        """Com prioridade local-first, Ollama é o primeiro."""
        texto = 'Análise via Ollama Mock'
        with patch('src.infrastructure.ai_client._ollama_generate', return_value=texto):
            resultado = analisar(notas_simples)
            assert resultado == texto

    def test_fallback_quando_ollama_falha(self, notas_simples):
        """Se Ollama falha, tenta Claude."""
        texto_claude = 'Análise via Claude Mock'
        with patch('src.infrastructure.ai_client._ollama_generate', return_value='[Ollama Erro: timeout]'), \
             patch('src.infrastructure.ai_client._claude_generate', return_value=texto_claude):
            resultado = analisar(notas_simples)
            assert resultado == texto_claude

    def test_todos_falham_retorna_erro(self, notas_simples):
        """Se todos os provedores falham, retorna mensagem de erro."""
        with patch('src.infrastructure.ai_client._ollama_generate', return_value='[Ollama Erro]'), \
             patch('src.infrastructure.ai_client._claude_generate', return_value='[Claude Inativo]'), \
             patch('src.infrastructure.ai_client._gemini_generate', return_value='[Gemini Falhou]'):
            resultado = analisar(notas_simples)
            assert 'ERRO' in resultado

    def test_provedor_especifico(self, notas_simples):
        """Modo provedor=gemini deve chamar apenas Gemini."""
        with patch('src.infrastructure.ai_client._gemini_generate', return_value='Gemini OK'):
            resultado = analisar(notas_simples, provedor='gemini')
            assert resultado == 'Gemini OK'

    def test_resultado_sempre_string(self, notas_simples):
        with patch('src.infrastructure.ai_client._ollama_generate', return_value='OK'):
            resultado = analisar(notas_simples)
            assert isinstance(resultado, str)
            assert len(resultado) > 0


# ─── Testes: analisar_com_resumo() ───────────────────────────────────────────

class TestAnalisarComResumo:

    def test_chama_ollama_com_json_compacto(self):
        resumo = {"total_notas": 10, "valor": 50000}
        with patch('src.infrastructure.ai_client._ollama_generate', return_value='{"ok":true}') as mock:
            resultado = analisar_com_resumo(resumo, SYSTEM_SIGMA)
            assert resultado == '{"ok":true}'
            # Verifica que o prompt é JSON compacto
            call_args = mock.call_args
            prompt = call_args[0][0]
            assert '"total_notas":10' in prompt


# ─── Testes: get_ai_metrics() ────────────────────────────────────────────────

class TestGetAiMetrics:

    def test_retorna_dict(self):
        result = get_ai_metrics()
        assert isinstance(result, dict)
