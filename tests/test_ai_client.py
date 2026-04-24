"""
Testes para o módulo ai_client.py.
Usa mocks para evitar chamadas reais às APIs externas.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from extractor import NFA, Parte, Produto
from ai_client import (
    _carregar_env,
    _claude_disponivel,
    _gemini_disponivel,
    _ollama_disponivel,
    _montar_prompt,
    _analise_local,
    analisar,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def notas_simples() -> list[NFA]:
    """Lista mínima de notas para testar o cliente IA."""
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
    """Valida leitura de variáveis de ambiente e config.env."""

    def test_retorna_string_vazia_se_nao_existe(self):
        with patch('ai_client._carregar_env', return_value=''):
            assert _carregar_env('CHAVE_INEXISTENTE') == ''

    def test_le_variavel_de_ambiente(self):
        with patch.dict('os.environ', {'MINHA_CHAVE': 'valor123'}):
            # Simula ausência do config.env
            with patch('ai_client.CONFIG_PATH') as mock_path:
                mock_path.exists.return_value = False
                resultado = _carregar_env('MINHA_CHAVE')
                assert resultado == 'valor123'

    def test_config_env_tem_prioridade_sobre_env(self, tmp_path):
        """Chave no config.env deve sobrescrever variável de ambiente."""
        config = tmp_path / 'config.env'
        config.write_text('MINHA_CHAVE=do_arquivo\n', encoding='utf-8')
        with patch('ai_client.CONFIG_PATH', config):
            with patch.dict('os.environ', {'MINHA_CHAVE': 'do_ambiente'}):
                resultado = _carregar_env('MINHA_CHAVE')
                assert resultado == 'do_arquivo'


# ─── Testes: verificação de disponibilidade de APIs ──────────────────────────

class TestDisponibilidade:
    """Valida lógica de detecção de disponibilidade de cada API."""

    def test_claude_disponivel_com_chave_valida(self):
        with patch('ai_client._carregar_env', return_value='sk-ant-abc123'):
            assert _claude_disponivel() is True

    def test_claude_indisponivel_com_chave_vazia(self):
        with patch('ai_client._carregar_env', return_value=''):
            assert _claude_disponivel() is False

    def test_claude_indisponivel_com_chave_errada(self):
        with patch('ai_client._carregar_env', return_value='chave_invalida'):
            assert _claude_disponivel() is False

    def test_claude_indisponivel_com_espaco(self):
        """Chave com espaço à esquerda não deve ser reconhecida (sem strip)."""
        with patch('ai_client._carregar_env', return_value=' sk-ant-abc123'):
            # O código atual não faz strip — este teste documenta o comportamento
            assert _claude_disponivel() is False

    def test_gemini_disponivel_com_chave_longa(self):
        chave = 'AIzaSy' + 'x' * 30  # > 10 chars
        with patch('ai_client._carregar_env', return_value=chave):
            assert _gemini_disponivel() is True

    def test_gemini_indisponivel_com_chave_curta(self):
        with patch('ai_client._carregar_env', return_value='abc'):
            assert _gemini_disponivel() is False

    def test_gemini_indisponivel_com_chave_vazia(self):
        with patch('ai_client._carregar_env', return_value=''):
            assert _gemini_disponivel() is False

    def test_ollama_disponivel_quando_servidor_responde(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        with patch('ai_client.requests.get', return_value=mock_response):
            assert _ollama_disponivel() is True

    def test_ollama_indisponivel_quando_servidor_retorna_erro(self):
        mock_response = MagicMock()
        mock_response.status_code = 500
        with patch('ai_client.requests.get', return_value=mock_response):
            assert _ollama_disponivel() is False

    def test_ollama_indisponivel_quando_timeout(self):
        import requests as req
        with patch('ai_client.requests.get', side_effect=req.exceptions.ConnectionError):
            assert _ollama_disponivel() is False


# ─── Testes: _montar_prompt() ─────────────────────────────────────────────────

class TestMontarPrompt:
    """Valida que o prompt contém as informações essenciais das notas."""

    def test_prompt_contem_total_notas(self, notas_simples):
        prompt = _montar_prompt(notas_simples)
        assert 'Total de Notas: 2' in prompt

    def test_prompt_contem_faturamento(self, notas_simples):
        """Verifica que o valor total (R$ 45000) aparece no prompt (formato US: 45,000.00)."""
        prompt = _montar_prompt(notas_simples)
        assert 'R$' in prompt
        # Python usa locale padrão US: 45,000.00 (não formato BR 45.000,00)
        assert '45,000.00' in prompt  # 25000 + 20000

    def test_prompt_contem_hhi(self, notas_simples):
        prompt = _montar_prompt(notas_simples)
        assert 'HHI' in prompt.upper()

    def test_prompt_contem_destinatario(self, notas_simples):
        prompt = _montar_prompt(notas_simples)
        assert 'FRIGORIFICO A' in prompt

    def test_prompt_nao_vazio_para_lista_vazia(self):
        """Lista vazia deve gerar prompt sem erro (com zeros)."""
        prompt = _montar_prompt([])
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_prompt_contem_tipos_animais(self, notas_simples):
        """Se há produtos com descrição, devem aparecer no prompt."""
        notas = [NFA(
            numero='001',
            natureza='VENDA',
            destinatario=Parte(nome='COMP A'),
            produtos=[Produto(descricao='NELORE MACHO ATE 12M', quantidade=5.0, vlr_total=10000.0)],
        )]
        prompt = _montar_prompt(notas)
        assert 'NELORE' in prompt


# ─── Testes: _analise_local() ─────────────────────────────────────────────────

class TestAnaliseLocal:
    """Valida o fallback de análise estatística local (sem API)."""

    def test_retorna_string(self, notas_simples):
        resultado = _analise_local(notas_simples)
        assert isinstance(resultado, str)
        assert len(resultado) > 0

    def test_contem_totais(self, notas_simples):
        """_analise_local usa formato US (45,000.00) — locale padrão do Python."""
        resultado = _analise_local(notas_simples)
        assert '2' in resultado  # total_notas
        # Formato US (padrão Python sem locale): 45,000.00
        assert '45,000.00' in resultado

    def test_contem_compradores(self, notas_simples):
        resultado = _analise_local(notas_simples)
        assert 'FRIGORIFICO A' in resultado

    def test_lista_vazia_nao_lanca_erro(self):
        resultado = _analise_local([])
        assert isinstance(resultado, str)

    def test_contem_evolucao_mensal(self, notas_simples):
        resultado = _analise_local(notas_simples)
        assert '01/2025' in resultado or '02/2025' in resultado


# ─── Testes: analisar() — fallback chain ─────────────────────────────────────

class TestAnalisar:
    """Testa a orquestração da cadeia de fallback (Claude → Gemini → Ollama → Local)."""

    def test_usa_analise_local_quando_nenhuma_api_disponivel(self, notas_simples):
        with patch('ai_client._claude_disponivel', return_value=False), \
             patch('ai_client._gemini_disponivel', return_value=False), \
             patch('ai_client._ollama_disponivel', return_value=False):
            resultado = analisar(notas_simples)
            assert isinstance(resultado, str)
            assert len(resultado) > 0

    def test_usa_gemini_quando_claude_indisponivel(self, notas_simples):
        texto_gemini = 'Análise via Gemini Mock'
        with patch('ai_client._claude_disponivel', return_value=False), \
             patch('ai_client._gemini_disponivel', return_value=True), \
             patch('ai_client._analisar_gemini', return_value=texto_gemini) as mock_gemini:
            resultado = analisar(notas_simples)
            mock_gemini.assert_called_once()
            assert resultado == texto_gemini

    def test_usa_ollama_quando_claude_e_gemini_indisponiveis(self, notas_simples):
        texto_ollama = 'Análise via Ollama Mock'
        with patch('ai_client._claude_disponivel', return_value=False), \
             patch('ai_client._gemini_disponivel', return_value=False), \
             patch('ai_client._ollama_disponivel', return_value=True), \
             patch('ai_client._analisar_ollama', return_value=texto_ollama) as mock_ollama:
            resultado = analisar(notas_simples)
            mock_ollama.assert_called_once()
            assert resultado == texto_ollama

    def test_callback_chamado_na_analise_local(self, notas_simples):
        """Ao usar fallback local, o callback não deve ser chamado (sem streaming)."""
        tokens_recebidos = []
        with patch('ai_client._claude_disponivel', return_value=False), \
             patch('ai_client._gemini_disponivel', return_value=False), \
             patch('ai_client._ollama_disponivel', return_value=False):
            resultado = analisar(notas_simples, callback=tokens_recebidos.append)
            assert isinstance(resultado, str)
            # Análise local não chama callback (retorno direto)
            assert len(tokens_recebidos) == 0

    def test_fallback_interno_do_claude_para_analise_local(self, notas_simples):
        """_analisar_claude captura sua própria exceção e chama _analise_local internamente.

        Pula se o pacote anthropic não estiver instalado no ambiente de teste.
        """
        anthropic = pytest.importorskip(
            'anthropic',
            reason='pacote anthropic não instalado — instale com: pip install anthropic',
        )
        with patch('ai_client._claude_disponivel', return_value=True), \
             patch('ai_client._gemini_disponivel', return_value=False), \
             patch('ai_client._ollama_disponivel', return_value=False):
            # Simula falha do cliente anthropic dentro de _analisar_claude
            mock_client = MagicMock()
            mock_client.messages.stream.side_effect = Exception('API Error')
            with patch.object(anthropic, 'Anthropic', return_value=mock_client):
                resultado = analisar(notas_simples)
                assert isinstance(resultado, str)
                assert len(resultado) > 0
