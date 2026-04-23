import sys
import os
import io
from pathlib import Path

# Forçar saída em UTF-8 para evitar erros de codificação no terminal Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from extractor import extrair_notas
from agents_engine import rodar_auditoria_completa
from src.infrastructure.database_v2 import SessionLocal, Cliente, Laudo, init_db

def main():
    # Parametrização para permitir qualquer cliente (Genes é a referência atual)
    client_name = sys.argv[1] if len(sys.argv) > 1 else "GENIS CARLOS LUIZ DE OLIVEIRA"
    
    print(f"\n[SQUAD] Iniciando Auditoria Forense Consolidada para: {client_name}")
    print("="*60)

    # Caminhos dos PDFs (Referência de Desenvolvimento)
    search_paths = [
        os.path.join(os.path.expanduser("~"), "Downloads"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Temp")
    ]
    
    pdf_names = ["GENIS DEST.pdf", "GENIS REM.pdf"]
    pdf_files = []
    
    for path in search_paths:
        for name in pdf_names:
            full_path = os.path.join(path, name)
            if os.path.exists(full_path):
                pdf_files.append(full_path)
    
    todas_notas = []
    for pdf_path in pdf_files:
        if not os.path.exists(pdf_path):
            print(f"[!] Aviso: PDF não encontrado em: {pdf_path}")
            continue
            
        print(f"[>] Extraindo dados de: {os.path.basename(pdf_path)}...")
        try:
            notas, _, _ = extrair_notas(pdf_path)
            todas_notas.extend(notas)
        except Exception as e:
            print(f"[!] Erro ao processar {pdf_path}: {e}")

    if not todas_notas:
        print("[FAIL] Nenhuma nota extraída para análise.")
        return

    print(f"\n[SQUAD] Disparando Orquestração Multi-Agente (Sigma -> Gama -> Auditor) para {len(todas_notas)} notas...")
    
    try:
        # Execução via LangGraph (agents_engine)
        resultado = rodar_auditoria_completa(todas_notas, client_name)
        veredito = resultado['veredito_final']
        
        # 1. Salvar Relatório em Markdown
        report_file = f"laudo_forense_{client_name.replace(' ', '_')}.md"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(f"# LAUDO DE AUDITORIA FORENSE - {client_name}\n\n")
            f.write(veredito)
        
        print(f"\n[OK] Relatório gerado: {report_file}")
        
        # 2. Persistência no Banco de Dados V2
        print(f"[>] Persistindo resultado no banco de dados Orgatec Sovereign...")
        init_db()
        with SessionLocal() as db:
            # Busca ou cria o cliente
            cliente = db.query(Cliente).filter_by(nome=client_name).first()
            if not cliente:
                cliente = Cliente(nome=client_name, cpf_cnpj="TESTE-000")
                db.add(cliente)
                db.commit()
                db.refresh(cliente)
            
            # Cria o Laudo
            novo_laudo = Laudo(
                cliente_id=cliente.id,
                veredito_ia=veredito,
                qtd_notas=len(todas_notas),
                valor_total=sum(n.valor_total for n in todas_notas),
                qtd_anomalias=0, # Seria extraído do veredito se houvesse parsing estruturado
                pdf_path=str(Path(report_file).absolute())
            )
            db.add(novo_laudo)
            db.commit()
            print(f"[OK] Laudo persistido no ID: {novo_laudo.id}")

        print("\n" + "="*60)
        print("AUDITORIA CONCLUÍDA COM SUCESSO.")
        print("="*60)

    except Exception as e:
        print(f"\n[ERRO FATAL] Falha na orquestração: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
