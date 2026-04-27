"""
Testes para src/infrastructure/ai_client.py.
Usa mocks para evitar chamadas reais às APIs externas.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.domain.extractor import NFA, Parte, Produto
from src.infrastructure.ai_client import (
    _carregar_env,
    _claude_disponivel,
    _gemini_disponivel,
    _ollama_disponivel,
    _montar_prompt,
    analisar,
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

    def test_config_env_tem_prioridade_sobre_env(self, tmp_path):
        config = tmp_path / 'config.env'
        config.write_text('MINHA_CHAVE=do_arquivo\n', encoding='utf-8')
        with patch('src.infrastructure.ai_client.CONFIG_PATH', config):
            with patch.dict('os.environ', {'MINHA_CHAVE': 'do_ambiente'}):
                resultado = _carregar_env('MINHA_CHAVE')
                assert resultado == 'do_arquivo'


# ─── Testes: disponibilidade de APIs ─────────────────────────────────────────

class TestDisponibilidade:

    def test_claude_disponivel_com_chave_valida(self):
        with patch('src.infrastructure.ai_client._carregar_env', return_value='sk-ant-abc123'):
            assert _claude_disponivel() is True

    def test_claude_indisponivel_com_chave_vazia(self):
        with patch('src.infrastructure.ai_client._carregar_env', return_value=''):
            assert _claude_disponivel() is False

    def test_claude_indisponivel_com_chave_errada(self):
        with patch('src.infrastructure.ai_client._carregar_env', return_value='chave_invalida'):
            assert _claude_disponivel() is False

    def test_gemini_disponivel_com_chave(self):
        """_gemini_disponivel() só checa se a chave existe (não o tamanho)."""
        with patch('src.infrastructure.ai_client._carregar_env', return_value='qualquer-chave'):
            assert _gemini_disponivel() is True

    def test_gemini_indisponivel_com_chave_vazia(self):
        with patch('src.infrastructure.ai_client._carregar_env', return_value=''):
            assert _gemini_disponivel() is False

    def test_ollama_disponivel_quando_servidor_responde(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        with patch('src.infrastructure.ai_client.requests.get', return_value=mock_response):
            assert _ollama_disponivel() is True

    def test_ollama_indisponivel_quando_timeout(self):
        import requests as req
        with patch('src.infrastructure.ai_client.requests.get', side_effect=req.exceptions.ConnectionError):
            assert _ollama_disponivel() is False


# ─── Testes: _montar_prompt() ─────────────────────────────────────────────────

class TestMontarPrompt:

    def test_prompt_e_string(self, notas_simples):
        prompt = _montar_prompt(notas_simples)
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_prompt_contem_natureza(self, notas_simples):
        """_montar_prompt inclui natureza de cada nota."""
        prompt = _montar_prompt(notas_simples)
        assert 'VENDA DE GADO BOVINO' in prompt

    def test_prompt_lista_vazia_nao_lanca_erro(self):
        prompt = _montar_prompt([])
        assert isinstance(prompt, str)


# ─── Testes: analisar() — fallback chain ─────────────────────────────────────
# NOTA: analisar() em modo 'auto' chama _analisar_claude/_gemini/_ollama diretamente.
# Os mocks corretos são nas funções privadas, não nas de disponibilidade.

class TestAnalisar:

    def test_retorna_ollama_quando_claude_e_gemini_falham(self, notas_simples):
        """Quando Claude e Gemini retornam prefixo de erro, cai no Ollama."""
        texto_ollama = 'Análise via Ollama Mock'
        with patch('src.infrastructure.ai_client._analisar_claude', return_value='[Claude Inativo]'), \
             patch('src.infrastructure.ai_client._analisar_gemini', return_value='[Gemini Inativo]'), \
             patch('src.infrastructure.ai_client._analisar_ollama', return_value=texto_ollama) as mock_ollama:
            resultado = analisar(notas_simples)
            mock_ollama.assert_called_once()
            assert resultado == texto_ollama

    def test_usa_swift_quando_disponivel(self, notas_simples):
        """Se Swift responde sem prefixo de erro, é usado como motor primário."""
        texto_swift = 'Análise detalhada via Swift Mock'
        with patch('src.infrastructure.ai_client._swift_disponivel', return_value=True), \
             patch('src.infrastructure.ai_client._analisar_swift', return_value=texto_swift) as mock_swift:
            resultado = analisar(notas_simples)
            mock_swift.assert_called_once()
            assert resultado == texto_swift

    def test_usa_ollama_quando_swift_falha(self, notas_simples):
        """Se Swift falha (prefixo [Swift), cai no Ollama."""
        texto_ollama = 'Análise via Ollama Mock'
        with patch('src.infrastructure.ai_client._swift_disponivel', return_value=True), \
             patch('src.infrastructure.ai_client._analisar_swift', return_value='[Swift Falhou: timeout]'), \
             patch('src.infrastructure.ai_client._ollama_disponivel', return_value=True), \
             patch('src.infrastructure.ai_client._analisar_ollama', return_value=texto_ollama) as mock_ollama:
            resultado = analisar(notas_simples)
            mock_ollama.assert_called_once()
            assert resultado == texto_ollama

    def test_resultado_e_string_nao_vazia(self, notas_simples):
        """Garante que o resultado final é sempre string não-vazia."""
        with patch('src.infrastructure.ai_client._analisar_claude', return_value='[Claude Inativo]'), \
             patch('src.infrastructure.ai_client._analisar_gemini', return_value='[Gemini Inativo]'), \
             patch('src.infrastructure.ai_client._analisar_ollama', return_value='Fallback OK'):
            resultado = analisar(notas_simples)
            assert isinstance(resultado, str)
            assert len(resultado) > 0
