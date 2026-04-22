# NFA Extractor — SEFAZ (Orgatec / Sentinela)

**NFA Extractor** é uma aplicação completa (Desktop App & Backend CLI) desenvolvida para auditar, extrair e projetar inteligência de negócios a partir de Notas Fiscais Avulsas (NFAs) de Produtores Rurais do Estado de Goiás.

## 🎯 Arquitetura de Inteligência Múltipla ("Tríplice Aliança")
O projeto inclui um `ai_client.py` rodando um prompt mestre de **Consultoria Sênior de Agronegócio** operando através de uma cadeia resiliente (Fallback Chain):
1. **Claude 3.5 Sonnet (API)**: O cérebro principal. Especialista em redação técnica, compliance tributário e auditoria.
2. **Google Gemini 1.5 Pro (API)**: A segunda linha de defesa. Ativado caso o Claude fique indisponível, oferecendo janelas de contexto gigantes.
3. **Ollama Llama 3.1 (Local)**: A garantia de privacidade absoluta. Atuando offline sem enviar dados da fazenda para a nuvem caso selecionado.

## 📈 Inteligência de Negócios (Business Intelligence)
O parser (`extractor.py`) não apenas lê texto. Ele conta com validação estrita (Pydantic V2) e implementa Matemática de Mercado:
- **Índice HHI**: Calcula ativamente o *Herfindahl-Hirschman Index* sobre faturamento bruto (apenas Vendas, ignorando remessas) para classificar na hora o seu Risco de Dependência de Mercado.
- **Preço Médio Unitário**: Extrai a média R$/Cabeça para a IA confrontar o preço das notas automaticamente com o índice regional de arrobas do CEPEA/SENAR-GO.

## 🛠️ Como Instalar e Rodar

1. **Pré-requisitos**:
   Instale o Python 3.12+ no Windows.

2. **Clone e Dependências**:
   ```powershell
   git clone <este-repositorio>
   cd "NFA Extractor"
   pip install -r requirements.txt
   ```

3. **Configuração de IAs (Chaves de API)**:
   Crie um arquivo chamado `config.env` na raiz do projeto (mesma pasta de `app.py`) e coloque dentro dele:
   ```env
   ANTHROPIC_API_KEY=sk-ant-SuaChaveAqui
   GOOGLE_API_KEY=AIzaSuaChaveAqui
   ```
   *(Proteja este arquivo e nunca suba ele no Git)*.

4. **Rodando a Interface de Usuário Gráfica (App)**:
   ```powershell
   python app.py
   ```

5. **Rodando o Extrator Rápido no Terminal**:
   ```powershell
   python extrair_nfa.py "caminho/do/seu/arquivo.pdf" "meus_dados.xlsx"
   ```

## 🧪 Suíte de Testes e SRE
A qualidade do parser é garantida por uma suíte rigorosa automatizada usando `pytest`. 
Para testar, basta rodar:
```powershell
pytest tests/ -v
```

---
*Gerenciado pela Squad Orgatec/Sentinela: @Alfa (Arquiteto), @Beta (Frontend), @Delta (QA e SRE).*
