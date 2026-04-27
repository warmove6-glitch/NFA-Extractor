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
    _montar_prompt,
    analisar_producao,
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
