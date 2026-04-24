import sys
import os
import io

# Forçar saída em UTF-8 para evitar erros de codificação no terminal Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from extractor import extrair_notas
from IAanalitic import resumo_analitico_comercializacao, resumo_geral_preditivo, auditoria_consolidada

def test_ia_analitic():
    downloads_path = os.path.join(os.path.expanduser("~"), "Downloads")
    pdf_files = [
        os.path.join(downloads_path, "GENIS DEST.pdf"),
        os.path.join(downloads_path, "GENIS REM.pdf")
    ]
    
    print("=== TESTE MÓDULO IAanalitic — AUDITORIA 360º ===")
    
    todas_notas = []
    for pdf_path in pdf_files:
        if not os.path.exists(pdf_path):
            print(f"[!] PDF não encontrado em: {pdf_path}")
            continue
            
        print(f"Lendo: {pdf_path}")
        try:
            notas = extrair_notas(pdf_path)
            print(f"[+] {len(notas)} notas extraídas.")
            todas_notas.extend(notas)
        except Exception as e:
            print(f"[ERRO] Falha ao ler {pdf_path}: {e}")

    if not todas_notas:
        print("[FAIL] Nenhuma nota extraída para análise.")
        return

    print(f"\n[SQUAD] Iniciando análise consolidada de {len(todas_notas)} notas via CLAUDE...")
    
    try:
        def callback(token):
            print(token, end="", flush=True)

        # Chamar a Auditoria Consolidada (Sigma -> Gama -> Auditor)
        auditoria_consolidada(todas_notas, callback=callback)

        print("\n\n[OK] Auditoria consolidada finalizada com sucesso.")
    except Exception as e:
        print(f"\n[ERRO] Falha no teste: {e}")

if __name__ == "__main__":
    test_ia_analitic()
