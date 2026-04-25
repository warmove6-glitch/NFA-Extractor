"""Testes para src/application/reports/ir_report.py"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.application.reports.ir_report import gerar_pdf_ir
from src.domain.extractor import NFA, Parte, Produto


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def notas_ir() -> list:
    """Lote de NFAs representando operações de um ano fiscal."""
    notas = []
    for i in range(3):
        notas.append(NFA(
            chave_acesso=str(i + 1) * 44,
            numero=f"00{i+1}",
            emissao=f"{(i+1)*3:02d}/04/2025",
            natureza="VENDA DE GADO BOVINO",
            destinatario=Parte(
                nome=f"FRIGORIFICO {i+1} LTDA",
                cpf_cnpj="12.345.678/0001-90",
                municipio="GOIANIA",
            ),
            produtos=[
                Produto(
                    descricao="BOVINA NELORE",
                    quantidade=float(10 + i * 5),
                    vlr_unitario=3000.0,
                    vlr_total=float((10 + i * 5) * 3000),
                )
            ],
        ))
    return notas


# ── Testes ───────────────────────────────────────────────────────────────────

class TestGerarPdfIr:
    def test_gera_arquivo_pdf(self, notas_ir):
        """gerar_pdf_ir deve criar um arquivo PDF no caminho indicado."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            path = tmp.name
        try:
            gerar_pdf_ir(notas_ir, path)
            assert os.path.exists(path), "PDF não foi criado"
            assert os.path.getsize(path) > 0, "PDF gerado está vazio"
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_pdf_começa_com_header_correto(self, notas_ir):
        """PDF gerado deve começar com o magic bytes '%PDF-'."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            path = tmp.name
        try:
            gerar_pdf_ir(notas_ir, path)
            with open(path, "rb") as f:
                header = f.read(5)
            assert header == b"%PDF-", f"Header inválido: {header}"
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_lista_vazia_levanta_value_error(self):
        """gerar_pdf_ir com lista vazia deve levantar ValueError (validação da função)."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            path = tmp.name
        try:
            with pytest.raises(ValueError, match="nota fiscal"):
                gerar_pdf_ir([], path)
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_tamanho_minimo_pdf(self, notas_ir):
        """PDF gerado deve ter pelo menos 3KB."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            path = tmp.name
        try:
            gerar_pdf_ir(notas_ir, path)
            size = os.path.getsize(path)
            assert size >= 3000, f"PDF muito pequeno: {size} bytes"
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_ano_padrao_aceito(self, notas_ir):
        """gerar_pdf_ir deve aceitar ano como string via saida path."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            path = tmp.name
        try:
            gerar_pdf_ir(notas_ir, saida=path)
            assert os.path.exists(path)
        finally:
            if os.path.exists(path):
                os.remove(path)
