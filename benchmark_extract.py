#!/usr/bin/env python
"""Benchmark de extração de PDF."""
import time
import sys
import os
from pathlib import Path

# Adicionar src ao path
sys.path.insert(0, str(Path(__file__).parent))

# Medir disponibilidade de PyMuPDF
t_import_start = time.time()
try:
    import fitz
    t_fitz = time.time() - t_import_start
    print(f"✓ PyMuPDF importado em {t_fitz:.3f}s")
    has_fitz = True
except ImportError:
    print("✗ PyMuPDF NÃO DISPONÍVEL - usando pdfplumber fallback (LENTO)")
    has_fitz = False

from src.domain.extractor import extrair_notas

# Encontrar um PDF de teste
pdf_dir = Path("tests")
pdfs = list(pdf_dir.glob("*.pdf"))

if not pdfs:
    print("Nenhum PDF encontrado em tests/")
    sys.exit(1)

pdf_path = str(pdfs[0])
print(f"\nTestando com: {Path(pdf_path).name}")

# Benchmark
print("\n[BENCHMARK] Extração de PDF")
print("-" * 60)

t_start = time.time()
notas, nome_prod, cpf_prod = extrair_notas(pdf_path)
t_elapsed = time.time() - t_start

print(f"Tempo total: {t_elapsed:.2f}s")
print(f"Notas extraídas: {len(notas)}")
print(f"PyMuPDF ativo: {'✓ SIM' if has_fitz else '✗ NÃO (FALLBACK pdfplumber)'}")
print("-" * 60)

if t_elapsed > 5:
    print("⚠️  LENTO! Esperado <1s com PyMuPDF, ~10-15s com pdfplumber")
else:
    print("✓ Rápido!")
