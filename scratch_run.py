import json
import sys
from extractor import extrair_notas
from database import salvar_notas_bd, criar_tabelas
from ai_client import analisar

pdfs = [
    r"C:\Users\Veloso\Downloads\GENIS DEST.pdf",
    r"C:\Users\Veloso\Downloads\GENIS REM.pdf"
]

def main():
    todas_notas = []
    
    print("\n" + "="*50)
    print("ETAPA 1: EXTRAÇÃO & PARSING (Local CPU)")
    print("="*50)
    
    for pdf in pdfs:
        print(f"[>] Extraindo de: {pdf}")
        try:
            notas = extrair_notas(pdf)
            todas_notas.extend(notas)
            print(f"    [+] {len(notas)} notas contabilizadas.")
        except Exception as e:
            print(f"    [!] Erro na leitura: {e}")

    if not todas_notas:
        print("Nenhuma nota extraída.")
        return

    print("\n" + "="*50)
    print(f"ETAPA 2: PERSISTÊNCIA NO BANCO (PostgreSQL Local)")
    print("="*50)
    try:
        criar_tabelas()
        salvas, ignoradas = salvar_notas_bd(todas_notas)
        print(f"[OK] Banco salvo! Novas: {salvas} | Ignoradas: {ignoradas}")
    except Exception as e:
        print(f"[FAIL] Banco indisponível/Erro: {e}")

    print("\n" + "="*50)
    print("ETAPA 3: IA & CONSULTORIA CORPORATIVA (Sigma & Gama)")
    print("="*50)
    
    modo = 'claude' # Tenta estressar usando a pipeline completa, ou falha caindo pro ollama nativo
    print(f"[>] Disparando pipeline para modo: {modo}...")
    
    try:
        relatorio = analisar(todas_notas, provedor=modo)
        
        # Salvando o log consultivo localmente num artefato para leitura
        with open('relatorio_consultivo_final.md', 'w', encoding='utf-8') as f:
            f.write(relatorio)
            
        print("[OK] Pipeline IA disparada com sucesso!")
        print("==> Amostra Inicial do Laudo:")
        print(relatorio[:800] + "...\n(Veja o arquivo relatorio_consultivo_final.md na raiz para o laudo completo)")
        
    except Exception as e:
        print(f"[!] Erro ao conectar as mentes artificiais: {e}")

if __name__ == "__main__":
    main()
