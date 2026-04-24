import os
import zipfile
import xml.etree.ElementTree as ET
import anthropic
import google.genai as genai
from google.genai import types

DOCX_FILE = r"C:\Users\Veloso\Downloads\PLANILHA DE GADO PARA IR.docx"

# Prompts das Personas Copiados do ai_client.py
SYSTEM_SIGMA = """Você atua como @Sigma: Data Scientist e Consultor Quantitativo Tributário.
SEU MINDSET: Matemática Bayesiana e Contabilidade Tributária Sistêmica.
Analise os dados financeiros e logísticos do arquivo e simule impostos vigentes (IRPF, ICMS).
Apresente a contabilidade de ganhos e faturamentos com clareza objetiva estruturada em tabelas.
"""

SYSTEM_GAMA = """Você atua como @Gama: Advogado e Consultor Tributário Sênior.
SEU MINDSET: Compliance Fiscal e Prevenção de Passivos (ICMS, ITR, IRPJ).
VOCÊ RECEBERÁ o conteúdo cru retirado de um Documento (Word) do Cliente sobre operações de Gado para o IR.
Emita o PARECER JURÍDICO detalhado sobre esse documento avaliando:
1) Os riscos fiscais inerentes.
2) Previsão de cenários.
3) Probabilidade matemática de autuação na malha fina.
4) Resumo estratégico de mitigação."""

def extract_text_from_docx(docx_path):
    """Extrai texto cru de um .docx usando bibliotecas nativas sem precisar de pip install python-docx."""
    text = []
    try:
        with zipfile.ZipFile(docx_path) as docx:
            xml_content = docx.read('word/document.xml')
            tree = ET.XML(xml_content)
            # Extrai todas as tags de parágrafo/texto
            for elt in tree.iter():
                if elt.tag.endswith('}t') and elt.text:
                    text.append(elt.text)
    except Exception as e:
        return f"Erro ao extrair Word: {e}"
    return '\n'.join(text)

def _carregar_env(chave: str) -> str:
    path = os.path.join(os.path.dirname(__file__), 'config.env')
    try:
        with open(path, 'r') as f:
            for l in f:
                if l.startswith(f'{chave}='):
                    return l.split('=', 1)[1].strip()
    except: ...
    return ''

def main():
    print("==================================================")
    print(f"ETAPA 1: LEITURA E EXTRAÇÃO NATIVA DO .DOCX")
    print("==================================================")
    
    texto_cru = extract_text_from_docx(DOCX_FILE)
    if not texto_cru.strip() or "Erro" in texto_cru:
        print(f"[!] Falha na extração de texto: {texto_cru}")
        return
        
    print(f"[OK] Leitura Completa! {len(texto_cru)} caracteres extraídos.")
    print("Trecho inicial:", repr(texto_cru[:100] + "..."))

    print("\n==================================================")
    print("ETAPA 2: @SIGMA E @GAMA (CADEIA CONSULTIVA CORPORATIVA)")
    print("==================================================")
    
    chave_claude = _carregar_env('ANTHROPIC_API_KEY')
    if not chave_claude:
        print("[!] Erro: ANTHROPIC_API_KEY não localizada no config.env.")
        return
        
    print("[>] Ligando Claude-3.5-Sonnet conectado na mente do @Gama...")
    
    try:
        cliente = anthropic.Anthropic(api_key=chave_claude)
        prompt_final = f"Avalie o seguinte documento contábil de controle de gado para o IR:\n\n{texto_cru}"
        
        with open("relatorio_docx_ir.md", "w", encoding='utf-8') as f:
            pass # Limpa artefato
            
        print(" > Processando...")
        
        with cliente.messages.stream(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4000,
            system=SYSTEM_GAMA,
            messages=[{"role": "user", "content": prompt_final}],
        ) as stream:
            for token in stream.text_stream:
                print(token, end="", flush=True)
                with open("relatorio_docx_ir.md", "a", encoding='utf-8') as f:
                    f.write(token)
                    
        print("\n\n[OK] Consultoria Finalizada! Salvo em: relatorio_docx_ir.md")
        
    except Exception as e:
        print(f"\n[!] Falha ao se comunicar com IAM: {e}")

if __name__ == "__main__":
    main()
