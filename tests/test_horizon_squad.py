"""Testes da bridge horizon_squad.

Estratégia: como rodar Claude real custaria tokens e exigiria chave válida,
testamos só os caminhos sem-chave e com-mock. O caminho real é coberto por
teste E2E manual.
"""
from __future__ import annotations

import os
from unittest import mock

import pytest

from src.integrations import horizon_squad


@pytest.fixture(autouse=True)
def reset_cache():
    """Reset do cache de carga entre testes (não vaza estado)."""
    horizon_squad._squad_modulo = None
    horizon_squad._carregado = False
    horizon_squad._erro_carga = None
    yield


class TestStatusSquad:
    def test_sem_anthropic_key_retorna_desabilitado(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        s = horizon_squad.status_squad()
        assert s["habilitado"] is False
        assert s["anthropic_api_key_definida"] is False

    def test_com_anthropic_key_retorna_habilitado(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fake")
        # Sem mockar carregamento real, só checa o flag
        s = horizon_squad.status_squad()
        assert s["habilitado"] is True
        assert s["anthropic_api_key_definida"] is True

    def test_flag_explicitamente_desligada(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fake")
        monkeypatch.setenv("ENABLE_HORIZON_SQUAD", "false")
        s = horizon_squad.status_squad()
        assert s["habilitado"] is False

    def test_modelos_default(self, monkeypatch):
        monkeypatch.delenv("AUDITORIA_MODEL", raising=False)
        monkeypatch.delenv("AUDITORIA_MODEL_SIMPLES", raising=False)
        s = horizon_squad.status_squad()
        assert "claude-sonnet" in s["modelo_principal"]
        assert "haiku" in s["modelo_simples"]

    def test_horizon_path_inexistente(self, monkeypatch, tmp_path):
        path_inexistente = tmp_path / "nao_existe"
        # Forçamos via monkeypatch da constante
        monkeypatch.setattr(horizon_squad, "_HORIZON_PATH", path_inexistente)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fake")
        s = horizon_squad.status_squad()
        assert s["horizon_blue_existe"] is False


class TestExecutarSquad:
    def test_sem_chave_retorna_none(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        resultado = horizon_squad.executar_squad_para_lote([], "Cliente", "12345678901")
        assert resultado is None

    def test_flag_desligada_retorna_none(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fake")
        monkeypatch.setenv("ENABLE_HORIZON_SQUAD", "false")
        resultado = horizon_squad.executar_squad_para_lote([], "Cliente", "12345678901")
        assert resultado is None

    def test_horizon_blue_indisponivel(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fake")
        monkeypatch.setattr(horizon_squad, "_HORIZON_PATH", tmp_path / "fake")
        resultado = horizon_squad.executar_squad_para_lote([], "Cliente", "12345678901")
        assert resultado is None


class TestPromptHelpers:
    def test_resumir_lote_vazio(self):
        prompt = horizon_squad._resumir_lote_para_prompt([], "ADELA", "12345678901")
        assert "ADELA" in prompt
        assert "sem notas" in prompt

    def test_resumir_lote_com_notas(self):
        # NFA-like com atributos mínimos
        from types import SimpleNamespace
        notas = [
            SimpleNamespace(
                numero="123", natureza="VENDA", emissao="01/01/2025",
                valor_total=10000.0, quantidade_total=10,
            ),
            SimpleNamespace(
                numero="124", natureza="VENDA", emissao="02/01/2025",
                valor_total=15000.0, quantidade_total=15,
            ),
        ]
        prompt = horizon_squad._resumir_lote_para_prompt(notas, "ADELA", "12345678901")
        assert "ADELA" in prompt
        assert "TOTAL DE NOTAS: 2" in prompt
        assert "R$ 25,000.00" in prompt
        assert "VENDA: 2" in prompt
