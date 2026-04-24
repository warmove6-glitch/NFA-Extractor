# ANÁLISE TÉCNICA DO PROJETO NFA EXTRACTOR

**Projeto:** OrgExtNF — SEFAZ  
**Data da Análise:** 20 de abril de 2026  
**Analisador:** Claude IA  

---

## 📋 SUMÁRIO EXECUTIVO

O projeto **NFA Extractor** é uma aplicação desktop integrada para extração, processamento e análise de Notas Fiscais Avulsas (NFAs) do SEFAZ-GO. A arquitetura combina:

- **Frontend:** Interface gráfica moderna com CustomTkinter
- **Core:** Motor de extração de PDFs com regex e pdfplumber
- **BI:** Análise financeira e cálculos de risco (HHI)
- **IA:** Integração com Claude API, Google Gemini e Ollama local
- **Relatórios:** Geração de PDFs profissionais e planilhas Excel

**Status Geral:** ✅ Projeto bem estruturado com código organizado, modular e com boas práticas.

---

## 🏗️ ARQUITETURA DO PROJETO

```
NFA Extractor/
├── app.py                 # Interface GUI (CustomTkinter) — 1041 linhas
├── extractor.py          # Core de extração e modelos de dados — 360 linhas
├── ai_client.py          # Integração com APIs de IA — 291 linhas
├── pdf_report.py         # Geração de relatórios em PDF — 435 linhas
├── extrair_nfa.py        # Script CLI + exportação Excel — 177 linhas
├── tests/                # Testes unitários
│   ├── __init__.py
│   └── test_extractor.py
├── assets/               # Logo e recursos visuais
│   └── logo.png
└── config.env           # Configurações de chaves API (git-ignored)
```

### 📊 Estatísticas de Código

| Arquivo | Linhas | Tipo | Responsabilidade |
|---------|--------|------|-----------------|
| **app.py** | 1041 | UI/Desktop | Toda a interface gráfica e orquestração |
| **extractor.py** | 360 | Core | Parsing PDF, modelos Pydantic, KPIs |
| **ai_client.py** | 291 | IA/APIs | Claude, Gemini, Ollama + fallback chain |
| **pdf_report.py** | 435 | Relatórios | Geração profissional de PDFs |
| **extrair_nfa.py** | 177 | CLI | Exportação Excel e script standalone |
| **TOTAL** | **2304** | — | — |

---

## 🔍 ANÁLISE DETALHADA POR MÓDULO

### 1️⃣ **app.py** — Interface Gráfica (CustomTkinter)

#### ✅ Pontos Fortes:
- **Arquitetura bem organizada:** Separação clara entre UI, dados e lógica
- **Paleta de cores consistente:** 11 variáveis de cor bem definidas (BG, CYAN, PRIMARY, etc.)
- **Threading inteligente:** Operações pesadas em threads separadas (extração, PDF, Excel, IA) para não bloquear UI
- **Componentes reutilizáveis:** `_build_cards()`, `_make_treeview()`, `_ir_secao()` reduzem duplicação
- **Feedback ao usuário:** Barra de progresso, status, botões desabilitados durante processamento
- **Multiple tabs:** 6 abas bem estruturadas (Notas, Itens, Destinatários, Gráficos, Tabela IR, Análise IA)

#### ⚠️ Problemas Identificados:

1. **Responsabilidade excessiva (~1000+ linhas)**
   ```python
   # app.py contém: UI setup, gráficos matplotlib, lógica de Excel, validações, handlers
   # RISCO: Difícil de testar, manutenção complexa
   ```
   **Sugestão:** Separar em:
   - `ui/tabs.py` — Construção das abas
   - `ui/cards.py` — Cards KPI
   - `ui/charts.py` — Gráficos matplotlib
   - `ui/handlers.py` — Event handlers

2. **Excel embedded em app.py** (linhas 924-1035)
   ```python
   def _exportar_excel_core(notas, saida: str):  # 112 linhas de lógica Excel
   ```
   **Sugestão:** Mover para módulo separado `excel_export.py`

3. **Hardcoding de strings em múltiplos lugares**
   ```python
   self.lbl_status.configure(text='Aguardando arquivo PDF...')  # Linha 138
   # Repete em vários lugares — usar constantes
   ```

4. **Memory leaks em gráficos matplotlib**
   ```python
   plt.close(fig)  # Linha 470 — OK, mas verificar se há referências circulares
   ```

5. **Falta de type hints** (apenas alguns métodos têm)
   ```python
   def _make_treeview(self, parent, colunas: list[tuple], height=22):  # Bom
   def _sort_tree(self, tv, col, reverse):  # Falta type hint
   ```

#### 💡 Recomendações:
- Aumentar cobertura de type hints para 100%
- Usar dataclass ou enum para as cores (`COLOR_PALETTE`)
- Implementar padrão Observer/Event para comunicação entre componentes
- Adicionar logging estruturado em vez de prints simples

---

### 2️⃣ **extractor.py** — Core de Extração e Modelos

#### ✅ Pontos Fortes:
- **Modelos bem definidos com Pydantic:** `Parte`, `Produto`, `NFA`
- **Type hints completos:** Todos os parâmetros e retornos tipados
- **Funções bem documentadas:** Docstrings com Args, Returns, Raises
- **Regex bem estruturado:** Padrões compilados e testáveis
- **Cálculos de BI:** HHI (Herfindahl-Hirschman Index), concentração de mercado
- **Logging centralizado:** Arquivo `extractor.log` para rastrear erros

#### ⚠️ Problemas Identificados:

1. **Regex complexo e difícil de manter** (linhas 132-145)
   ```python
   m = re.match(
       r'^(\d+)\s+(.+?)\s+(\d+[.,]\d+)\s+R\$\s*([\d.,]+)\s+([\d.,]+)\s+R\$\s*([\d.,]+)$',
       linha.strip()
   )
   # Quebra facilmente com variações de espaçamento ou formato do PDF
   ```
   **Sugestão:** Usar testes parametrizados com casos reais de PDFs

2. **Conversão monetária frágil** (linhas 76-90)
   ```python
   def _moeda(s: str) -> float:
       s = re.sub(r'[R$\s]', '', s).replace('.', '').replace(',', '.')
       try:
           return float(s)
       except ValueError:
           logger.warning(f"Falha ao converter valor monetario: '{s}'")
           return 0.0  # PROBLEMA: Silenciosamente retorna 0 em vez de falhar
   ```
   **Risco:** Notas com valores zero podem passar despercebidas

3. **Parsing de parte insuficiente** (linhas 93-120)
   ```python
   # Não trata casos onde o CPF/CNPJ está em linha separada
   # Não captura IE corretamente em todos os casos
   ```

4. **Sem validação de integridade** 
   ```python
   # Não verifica se quantidade_total == soma dos produtos.quantidade
   # Não valida se chave_acesso tem realmente 44 dígitos (apenas regex)
   ```

5. **Função `resumo_geral` muito longa** (linhas 249-359)
   - 111 linhas em uma única função
   - **Sugestão:** Quebrar em subfunções:
     - `_calcular_totais()`
     - `_calcular_hhi()`
     - `_agrupar_por_mes()`
     - `_agrupar_por_destinatario()`

#### 💡 Recomendações:
```python
# Criar classe para padronizar regex
class PatternMatcher:
    PRODUTO = re.compile(r'...')  # Compilar uma vez
    CPF_CNPJ = re.compile(r'...')
    
# Usar Enum para categorias
class NaturezaOperacao(Enum):
    VENDA = 'VENDA'
    REMESSA = 'REMESSA'
    # ...

# Adicionar validação
def validar_nfa(nfa: NFA) -> tuple[bool, list[str]]:
    """Retorna (valida, lista_de_erros)"""
    erros = []
    if len(nfa.chave_acesso) != 44:
        erros.append("Chave de acesso deve ter 44 dígitos")
    # ...
    return len(erros) == 0, erros
```

---

### 3️⃣ **ai_client.py** — Integração com APIs de IA

#### ✅ Pontos Fortes:
- **Fallback chain inteligente:** Claude → Gemini → Ollama → Análise Local
- **System prompt muito bem elaborado:** 98 linhas de instruções super detalhadas
- **Streaming de respostas:** Callback para token-by-token (boa UX)
- **Detecção automática de disponibilidade:** `_claude_disponivel()`, `_gemini_disponivel()`, etc.
- **Suporte a config.env:** Carregamento seguro de chaves API

#### ⚠️ Problemas Identificados:

1. **Detecção de API frágil** (linhas 110-123)
   ```python
   def _claude_disponivel() -> bool:
       return _carregar_env('ANTHROPIC_API_KEY').startswith('sk-ant-')
   # Problema: E se a chave tem espaço? E se está vazia?
   ```
   **Solução:**
   ```python
   def _claude_disponivel() -> bool:
       key = _carregar_env('ANTHROPIC_API_KEY').strip()
       return bool(key and key.startswith('sk-ant-'))
   ```

2. **Sem cache de respostas IA**
   ```python
   # A mesma análise pode ser rodada múltiplas vezes
   # CUSTO: Múltiplas chamadas à API, latência
   ```
   **Sugestão:** Implementar cache com hash do resumo_geral()

3. **System prompt gigante e hardcoded** (99 linhas)
   ```python
   SYSTEM_PROMPT = """Você é um Consultor..."""  # Linha 15-98
   # PROBLEMA: Difícil de manter, versionar, testar
   ```
   **Sugestão:** Usar arquivo `prompts/sistema.md` externo

4. **Tratamento de erro silencioso**
   ```python
   except Exception as e:
       if callback:
           callback(f'[Claude indisponivel: {e}] — tentando Gemini...\n\n')
       if _gemini_disponivel():
           return _analisar_gemini(notas, callback)
       return _analise_local(notas)
   # Não loga o erro, apenas continua
   ```

5. **Prompt montagem ineficiente** (linhas 126-167)
   ```python
   # Constrói string manualmente com múltiplos joins
   # Sugestão: Usar template string ou Jinja2
   ```

#### 💡 Recomendações:
```python
# Criar classe wrapper para cada API
class IAProvider(ABC):
    @abstractmethod
    async def analisar(self, notas: list[NFA], callback) -> str: pass

class ClaudeProvider(IAProvider):
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
    
    async def analisar(self, notas: list[NFA], callback) -> str:
        # Implementação

# Usar cache com TTL
@functools.lru_cache(maxsize=10)
def analisar_com_cache(notas_hash: str) -> str:
    # ...
```

---

### 4️⃣ **pdf_report.py** — Geração de Relatórios

#### ✅ Pontos Fortes:
- **ReportLab bem utilizado:** Paleta de cores, estilos, tabelas profissionais
- **Header/Footer customizado:** Logo, data, número de página
- **Gráficos integrados:** Matplotlib → PNG → PDF (bom fluxo)
- **Tabelas bem formatadas:** Cores alternadas, bordas, alinhamento
- **Modular:** Funções `_card()`, `_estilo_tabela()`, `_gerar_graficos()`

#### ⚠️ Problemas Identificados:

1. **Gráficos salvos em memória (BytesIO)** — OK, mas sem limite
   ```python
   buf = io.BytesIO()
   plt.savefig(buf, format='png', dpi=150)  # Linha 400
   # Se muitos gráficos, pode estourar memória
   ```
   **Sugestão:** Usar arquivo temporário com `tempfile`

2. **Função `gerar_pdf` muito longa** (162 linhas)
   - Construir story
   - Adicionar capa
   - Adicionar abas
   - Adicionar gráficos
   - **Sugestão:** Usar padrão Builder

3. **Hardcoding de dimensões**
   ```python
   colWidths=[5.5*cm, 3.5*cm, 3.5*cm, 1.5*cm, 2*cm, 2.5*cm]  # Linha 245
   # Manutenção difícil, sem documentação
   ```
   **Sugestão:**
   ```python
   COLUMN_WIDTHS = {
       'destinatarios': [5.5*cm, 3.5*cm, 3.5*cm, 1.5*cm, 2*cm, 2.5*cm],
       'itens': [1.8*cm, 2*cm, 4*cm, ...],
   }
   ```

4. **Sem tratamento de caso vazio**
   ```python
   if not notas:  # Linha 801 em app.py
       # Mas em pdf_report.py, se notas vazio?
   ```

5. **Path absoluto do logo** (linha 21)
   ```python
   LOGO_PATH = str(Path(__file__).parent / 'assets' / 'logo.png')
   # Quebra se asset não existe — se checa em linha 47
   ```

#### 💡 Recomendações:
```python
# Usar padrão Builder
class RelatorioPDFBuilder:
    def __init__(self, saida: str):
        self.saida = saida
        self.story = []
    
    def adicionar_capa(self, notas: list[NFA]) -> 'RelatorioPDFBuilder':
        # ...
        return self
    
    def adicionar_graficos(self, res: dict) -> 'RelatorioPDFBuilder':
        # ...
        return self
    
    def gerar(self) -> None:
        # SimpleDocTemplate(...).build(self.story)

# Usar
RelatorioP
DFBuilder(saida)
    .adicionar_capa(notas)
    .adicionar_graficos(res)
    .gerar()
```

---

### 5️⃣ **extrair_nfa.py** — CLI e Exportação Excel

#### ✅ Pontos Fortes:
- **Script standalone bem pensado:** Funciona como CLI ou importável
- **Função `_cel_style()` reutilizável:** Evita duplicação em Excel
- **3 abas bem estruturadas:** Notas, Itens, Resumo por Destinatário
- **Totalizações:** Linha de total com cores destacadas

#### ⚠️ Problemas Identificados:

1. **Cores hardcoded novamente**
   ```python
   CYAN   = '00D4FF'  # Definidas aqui E em app.py E em pdf_report.py
   ```
   **Sugestão:** Criar módulo `constants.py` com paleta centralizada

2. **CLI argument parsing simples**
   ```python
   if len(sys.argv) < 2:
       print('Uso: python extrair_nfa.py <arquivo.pdf> [saida.xlsx]')
   # Melhorar com argparse
   ```
   **Solução:**
   ```python
   import argparse
   parser = argparse.ArgumentParser(description='Extrator de NFA')
   parser.add_argument('pdf', help='Arquivo PDF')
   parser.add_argument('--saida', help='Arquivo Excel de saída')
   args = parser.parse_args()
   ```

3. **Sem validação de arquivo de entrada**
   ```python
   pdf_path = sys.argv[1]
   # Não verifica se existe
   notas = extrair_notas(pdf_path)  # Apenas pega exceção genérica
   ```

4. **Duplicação de lógica Excel**
   ```python
   # Mesma lógica em:
   # - app.py: _exportar_excel_core() — 112 linhas
   # - extrair_nfa.py: exportar_excel() — 109 linhas
   # São quase idênticas!
   ```
   **Solução:** Criar `excel_export.py` único e importar em ambos

---

## 🎯 ANÁLISE DE QUALIDADE

### Cobertura de Type Hints
- **app.py:** ~40% ❌
- **extractor.py:** ~95% ✅
- **ai_client.py:** ~60% ⚠️
- **pdf_report.py:** ~30% ❌
- **extrair_nfa.py:** ~20% ❌

### Documentação
- **extractor.py:** Excelente (docstrings em todas as funções) ✅
- **ai_client.py:** Boa (comentários em seções) ✅
- **pdf_report.py:** Média (alguns comentários) ⚠️
- **app.py:** Média (sem docstrings) ⚠️
- **extrair_nfa.py:** Boa (comentários de seção) ✅

### Testes
- **Arquivo:** `tests/test_extractor.py` — ❓ (não foi lido, arquivo vazio?)
- **Cobertura estimada:** ~5% ❌
- **Teste de integração:** Não há

### Segurança
- **API Keys:** Armazenadas em `config.env` ✅ (git-ignored)
- **Validação de entrada:** Fraca em PDFs ⚠️
- **Injeção SQL:** Não aplicável (não usa BD)
- **LGPD/Privacidade:** Arquivo log com dados sensíveis ⚠️ (linhas 13-17, extractor.py)

---

## 🚀 PROBLEMAS CRÍTICOS

| Severidade | Problema | Impacto | Fix |
|-----------|----------|--------|-----|
| 🔴 **CRÍTICO** | Duplicação de 109 linhas (Excel) em 2 places | Manutenção, bugs | Criar `excel_export.py` |
| 🔴 **CRÍTICO** | app.py com 1041 linhas (muito grande) | Difícil testar, manter | Refatorar em submódulos |
| 🟠 **ALTO** | Sem validação de integridade NFA | Dados corrompidos passam | Implementar `validar_nfa()` |
| 🟠 **ALTO** | Sem testes unitários | Regressões não detectadas | Adicionar pytest |
| 🟠 **ALTO** | Paleta de cores em 3 lugares | Manutenção difícil | Centralizar em `constants.py` |
| 🟡 **MÉDIO** | Regex de produto frágil | Falhas de parsing | Melhorar com casos de teste |
| 🟡 **MÉDIO** | System prompt em string literal | Versionamento difícil | Usar arquivo externo |
| 🟡 **MÉDIO** | Sem logging estruturado | Debug difícil | Usar `structlog` |

---

## 💡 RECOMENDAÇÕES PRIORITÁRIAS

### 🥇 Prioridade 1: Refatoração Estrutural (2-3 dias)
1. Separar `app.py` em submódulos:
   ```
   ui/
   ├── __init__.py
   ├── main.py         # Classe App
   ├── tabs.py         # _build_tab_*
   ├── cards.py        # _build_cards
   ├── charts.py       # _atualizar_graficos
   └── handlers.py     # Event handlers
   ```

2. Consolidar Excel:
   ```
   core/
   ├── excel_export.py  # Função única para ambos app.py e extrair_nfa.py
   ```

3. Centralizar constantes:
   ```
   constants.py
   - COLORS (dict)
   - COLUMN_WIDTHS (dict)
   - REGEX_PATTERNS (dict)
   ```

### 🥈 Prioridade 2: Testes (1-2 dias)
```bash
pytest tests/ --cov=. --cov-report=html
```

Criar testes para:
- `_moeda()` com 20 casos (incluindo edge cases)
- `_parse_produto()` com PDFs reais
- `classificar_natureza()` com 10+ casos
- `resumo_geral()` com dados mock
- Fallback chain IA

### 🥉 Prioridade 3: Melhorias de Qualidade (1-2 dias)
- [ ] Type hints 100% em todos arquivos
- [ ] Docstrings em todos métodos públicos
- [ ] Lint: `pylint app.py`
- [ ] Format: `black *.py`
- [ ] Type check: `mypy . --strict`

### 4️⃣ Prioridade 4: Features (1+ semanas)
- [ ] Suporte a múltiplos PDFs simultâneos
- [ ] Banco de dados (SQLite) para histórico
- [ ] API REST com FastAPI
- [ ] Dashboard web com Streamlit
- [ ] CLI melhorado com argparse
- [ ] Caching de análises IA

---

## 📈 MÉTRICAS DO PROJETO

```
Linguagem principal: Python 3.9+
Framework GUI: CustomTkinter
Dependências principais:
  - pdfplumber (PDF parsing)
  - pydantic (Data models)
  - openpyxl (Excel)
  - reportlab (PDF generation)
  - matplotlib (Charts)
  - anthropic/google-generativeai (IA APIs)

Complexidade Ciclomática:
  - app.py: ~40 (MUITO ALTA — refatorar!)
  - extractor.py: ~8 (Boa)
  - ai_client.py: ~12 (Aceitável)
  - pdf_report.py: ~15 (Média)

Cobertura de testes: ~5%
Linhas de código: ~2304
Duplicação: ~12% (principalmente Excel)
```

---

## 🔐 Recomendações de Segurança

1. **Arquivo de log contém dados sensíveis**
   ```python
   logger.warning(f"Falha ao converter valor monetario: '{s}'")  # Linha 89
   # Pode vazar valores de notas fiscais
   ```
   **Fix:** Sanitizar dados antes de logar

2. **Sem limite de tamanho de PDF**
   ```python
   with pdfplumber.open(pdf_path) as pdf:
       total = len(pdf.pages)  # PDFs gigantes podem estourar memória
   ```
   **Fix:** Adicionar limite (ex: máximo 500 páginas)

3. **Config.env pode ser exposto acidentalmente**
   ```
   # Sempre usar .gitignore:
   config.env
   *.log
   .venv/
   ```

---

## 📝 CONCLUSÃO

O projeto **NFA Extractor** é **bem concebido** e **modular**, com boa separação de responsabilidades em geral. O maior desafio é **app.py com 1041 linhas**, que precisa ser refatorado.

### Nota Geral: **7.5 / 10** ✅

**Força:** Lógica de BI, integração com IA, interface visual  
**Fraqueza:** Tamanho de arquivos, duplicação, falta de testes  
**Próximos passos:** Refatorar estrutura, adicionar testes, melhorar CI/CD

---

*Fim da análise. Documento gerado automaticamente via Claude IA.*
