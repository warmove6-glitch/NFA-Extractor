"""Testes para src/application/reports/excel_export.py"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.application.reports.excel_export import exportar_excel
from src.domain.extractor import NFA, Parte, Produto

# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def nota_simples() -> NFA:
    return NFA(
        chave_acesso="1" * 44,
        numero="000001",
        emissao="10/04/2025",
        natureza="VENDA DE GADO BOVINO",
        local_emissao="AGENCIA FAZENDARIA DE TROMBAS",
        destinatario=Parte(
            nome="FRIGORIFICO EXEMPLO LTDA",
            cpf_cnpj="12.345.678/0001-90",
            municipio="GOIANIA",
        ),
        produtos=[
            Produto(
                codigo="1070",
                descricao="GADO BOVINO NELORE",
                quantidade=10.0,
                vlr_unitario=2500.0,
                vlr_total=25000.0,
            )
        ],
    )


@pytest.fixture
def lista_notas(nota_simples: NFA) -> list:
    nota2 = NFA(
        numero="000002",
        emissao="20/04/2025",
        natureza="REMESSA PARA RECRIA",
        destinatario=Parte(nome="FAZENDA BOA VISTA", municipio="FORMOSO"),
        produtos=[Produto(quantidade=5.0, vlr_total=12500.0)],
    )
    return [nota_simples, nota2]


# ── Testes ───────────────────────────────────────────────────────────────────

class TestExportarExcel:
    def test_gera_arquivo_xlsx(self, lista_notas):
        """exportar_excel deve criar um arquivo .xlsx no caminho indicado."""
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            path = tmp.name
        try:
            exportar_excel(lista_notas, path, nome_contribuinte="JOAO DA SILVA")
            assert os.path.exists(path), "Arquivo não foi criado"
            assert os.path.getsize(path) > 0, "Arquivo gerado está vazio"
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_arquivo_e_xlsx_valido(self, lista_notas):
        """Arquivo gerado deve ser um ZIP válido (estrutura XLSX)."""
        import zipfile
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            path = tmp.name
        try:
            exportar_excel(lista_notas, path)
            assert zipfile.is_zipfile(path), "Arquivo não é um ZIP/XLSX válido"
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_lista_vazia_levanta_value_error(self):
        """exportar_excel com lista vazia deve levantar ValueError (validação da função)."""
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            path = tmp.name
        try:
            with pytest.raises(ValueError, match="nota fiscal"):
                exportar_excel([], path, nome_contribuinte="TESTE")
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_nota_sem_produtos(self):
        """NFA sem produtos deve ser processada sem erro."""
        nota = NFA(numero="999", emissao="01/01/2025", natureza="VENDA", produtos=[])
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            path = tmp.name
        try:
            exportar_excel([nota], path)
            assert os.path.exists(path)
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_tamanho_minimo_arquivo(self, lista_notas):
        """Arquivo gerado deve ter pelo menos 5KB (workbook real, não vazio)."""
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            path = tmp.name
        try:
            exportar_excel(lista_notas, path, nome_contribuinte="PRODUTOR RURAL")
            size = os.path.getsize(path)
            assert size >= 5000, f"Arquivo muito pequeno: {size} bytes"
        finally:
            if os.path.exists(path):
                os.remove(path)
