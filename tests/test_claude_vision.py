"""
Testes para Claude Vision (extração de dados de imagens) e modo produção.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.domain.extractor import NFA, Parte, Produto
from src.infrastructure.ai_client import (
    extrair_com_claude_vision,
    analisar_producao,
    _analisar_claude,
)


@pytest.fixture
def notas_teste() -> list[NFA]:
    return [
        NFA(
            numero='000001',
            emissao='15/01/2025',
            natureza='VENDA DE GADO BOVINO',
            destinatario=Parte(nome='FRIGORIFICO A', cpf_cnpj='12.345.678/0001-90'),
            produtos=[Produto(quantidade=10.0, vlr_total=25000.0)],
        ),
    ]


class TestClaudeVision:
    """Testes para extração com Claude Vision."""

    def test_extrair_com_claude_vision_sem_api_key(self):
        """Quando Claude API key ausente, retorna erro."""
        with patch('src.infrastructure.ai_client._carregar_env', return_value=''):
            resultado = extrair_com_claude_vision('fake_base64')
            assert resultado['status'] == 'erro'
            assert 'Claude Vision inativo' in resultado['mensagem']

    def test_extrair_com_claude_vision_mock(self):
        """Mock de sucesso: retorna dados extraídos."""
        with patch('src.infrastructure.ai_client._carregar_env', return_value='sk-ant-test'), \
             patch('anthropic.Anthropic') as mock_anthropic:

            mock_client = MagicMock()
            mock_anthropic.return_value = mock_client

            # Mock resposta com JSON
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text='{"numero": "001234", "valor": 1240.00}')]
            mock_client.messages.create.return_value = mock_response

            resultado = extrair_com_claude_vision('fake_base64')

            assert resultado['status'] == 'sucesso'
            assert resultado['dados']['numero'] == '001234'

    def test_extrair_com_claude_vision_resposta_raw(self):
        """Quando JSON não está no formato esperado, retorna raw."""
        with patch('src.infrastructure.ai_client._carregar_env', return_value='sk-ant-test'), \
             patch('anthropic.Anthropic') as mock_anthropic:

            mock_client = MagicMock()
            mock_anthropic.return_value = mock_client

            # Mock resposta sem JSON válido
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text='Texto simples, não JSON')]
            mock_client.messages.create.return_value = mock_response

            resultado = extrair_com_claude_vision('fake_base64')

            assert resultado['status'] == 'sucesso'
            assert resultado['raw'] == 'Texto simples, não JSON'


class TestAnalisarProducao:
    """Testes para modo produção (Claude + fallback)."""

    def test_analisar_producao_prioriza_claude(self, notas_teste):
        """Quando Claude disponível, deve ser usado como primário."""
        with patch('src.infrastructure.ai_client._carregar_env') as mock_env, \
             patch('src.infrastructure.ai_client._analisar_claude', return_value='Análise Claude OK') as mock_claude, \
             patch('src.infrastructure.ai_client._swift_disponivel', return_value=True):

            mock_env.side_effect = lambda x: 'sk-ant-test' if x == 'ANTHROPIC_API_KEY' else ''

            resultado = analisar_producao(notas_teste)

            assert 'Análise Claude OK' in resultado
            mock_claude.assert_called_once()

    def test_analisar_producao_fallback_swift(self, notas_teste):
        """Quando Claude falha, fallback para Swift."""
        with patch('src.infrastructure.ai_client._carregar_env', return_value=''), \
             patch('src.infrastructure.ai_client._swift_disponivel', return_value=True), \
             patch('src.infrastructure.ai_client._analisar_swift', return_value='Análise Swift OK') as mock_swift:

            resultado = analisar_producao(notas_teste)

            assert 'Análise Swift OK' in resultado
            mock_swift.assert_called_once()

