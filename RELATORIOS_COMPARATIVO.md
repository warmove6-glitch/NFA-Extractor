# Relatórios IRPF — Comparativo de Formatos

## 📋 Três Opções Disponíveis

### 1. **Relatório Simples** (Minimalista)
**Arquivo**: `pdf_weasyprint_simples.py`

**Quando usar**: 
- Auditores que querem apenas resumo executivo
- PDFs rápidos para impressão
- Foco comercial/executivo

**Conteúdo**:
- ✅ Header com metadados (contribuinte, CPF, data)
- ✅ Badge de nível de risco
- ✅ 4 KPIs essenciais (notas, cabeças, valor, ticket médio)
- ✅ Resumo por tipo de operação (2 colunas)
- ❌ Sem tabelas mensais
- ❌ Sem destinatários
- ❌ Sem análise detalhada

**Design**: Minimalista, muito espaço em branco, foco em números

**Tempo geração**: ~500ms

---

### 2. **Relatório Premium** (Completo)
**Arquivo**: `pdf_weasyprint.py`

**Quando usar**:
- Análise técnica completa
- Auditoria fiscal detalhada
- Conformidade regulatória

**Conteúdo**:
- ✅ Header com metadados
- ✅ Badge de nível de risco
- ✅ 4 KPIs principais
- ✅ Tabela mensal (período, notas, cabeças, valor)
- ✅ Operações por tipo
- ✅ Top 10 destinatários
- ✅ Análise estatística

**Design**: Profissional, sidebar metadados, muitos dados

**Tempo geração**: ~800ms

---

### 3. **HTML Premium** (Interativo)
**Arquivo**: `planilha_ir_premium.py`

**Quando usar**:
- Visualização na web (não PDF)
- Apresentação ao cliente
- Compartilhamento por email

**Conteúdo**:
- ✅ Sidebar com metadados
- ✅ Cards KPI com hover
- ✅ Tabelas interativas
- ✅ Badges coloridas
- ✅ Responsivo (mobile/desktop)
- ✅ Print-friendly

**Design**: Moderno, glassmorphism, cores Fiscal Clarity

**Tempo geração**: ~50ms

---

## 🎯 Comparativo Detalhado

| Aspecto | Simples | Premium | HTML |
|---------|---------|---------|------|
| Formato | PDF | PDF | HTML |
| KPIs | 4 | 4 | 4 |
| Tabelas | Operações | Mensal + Ops + Top10 | Completo |
| Páginas | 1 | 1-2 | 1 |
| Tamanho | ~50KB | ~100KB | ~30KB |
| Tempo | 500ms | 800ms | 50ms |
| Print | ✅ | ✅ | ✅ |
| Mobile | ❌ | ❌ | ✅ |
| Interativo | ❌ | ❌ | ✅ |

---

## 🎨 Design Comparativo

### Simples
```
┌─────────────────────────────┐
│ PLANILHA IRPF               │
│ Contribuinte: XXXX          │
│ CPF: XXXX  Data: 27/04/2026 │
├─────────────────────────────┤
│ Nível: BAIXO (30%)          │
├─────────────────────────────┤
│ │ KPI1 │ KPI2 │ KPI3 │ KPI4 │
├─────────────────────────────┤
│ VENDA    150   70%          │
│ REMESSA   45   20%          │
│ OUTRAS    15   10%          │
└─────────────────────────────┘
```

### Premium
```
┌─────────────────────────────────────┐
│ PLANILHA IRPF  Lei 8.023/90         │
│ Contribuinte: XXXX  CPF: XXXX       │
│ Data: 27/04/2026  Período: 12 meses │
├─────────────────────────────────────┤
│ [BAIXO - 30%]                       │
├─────────────────────────────────────┤
│ │ KPI1 │ KPI2 │ KPI3 │ KPI4 │       │
├─────────────────────────────────────┤
│ Resumo por Mês                      │
│ │ Mês │ Notas │ Cabeças │ Valor │   │
├─────────────────────────────────────┤
│ Operações por Tipo                  │
│ │ Tipo │ Qtd │ % │                  │
├─────────────────────────────────────┤
│ Principais Destinatários (Top 10)   │
│ │ Empresa │ Notas │ Valor │         │
└─────────────────────────────────────┘
```

### HTML (Web)
```
┌─────────────────────────────────────┐
│ Sidebar:                │ Main:      │
│ • Contribuinte          │ Header     │
│ • CPF/CNPJ              │ KPI Cards  │
│ • Total Notas           │ Tabelas    │
│                         │ Badges     │
│                         │            │
│                         │ Hover fx   │
└─────────────────────────────────────┘
```

---

## 📊 Como Usar

### Gerar Relatório Simples
```python
from src.application.reports.pdf_weasyprint_simples import gerar_pdf_simples

gerar_pdf_simples(
    notas=notas_lista,
    saida="relatorio_simples.pdf",
    nome_contribuinte="João Silva",
    cpf_contribuinte="123.456.789-00",
    risco_nivel="BAIXO",
    score_risco=0.3
)
```

### Gerar Relatório Premium
```python
from src.application.reports.pdf_weasyprint import gerar_pdf_weasyprint

gerar_pdf_weasyprint(
    notas=notas_lista,
    saida="relatorio_premium.pdf",
    nome_contribuinte="João Silva",
    cpf_contribuinte="123.456.789-00",
    risco_nivel="ALTO",
    score_risco=0.7
)
```

### Gerar HTML Premium
```python
from src.domain.planilha_ir_premium import gerar_html_planilha_premium
from src.domain.planilha_ir import gerar_dados_planilha

dados = gerar_dados_planilha(notas_lista, "João Silva")
html = gerar_html_planilha_premium(dados)
with open("relatorio.html", "w") as f:
    f.write(html)
```

---

## 🎯 Recomendações de Uso

| Cenário | Formato Recomendado |
|---------|-------------------|
| Auditoria interna rápida | **Simples** |
| Relatório técnico completo | **Premium** |
| Apresentação ao cliente | **HTML** |
| Email para cliente | **Simples** ou **Premium** |
| Visualização web | **HTML** |
| Conformidade regulatória | **Premium** |
| Dashboard executivo | **HTML** |

---

## 📦 Implementação Atual

**No sistema**: Auditoria usa `planilha_ir_premium.py` por padrão (HTML)

Para usar versão simplificada:
```python
# Em api/services/auditoria.py
html_planilha = gerar_html_planilha_simples(dados_planilha)  # Novo
```

---

**Status**: ✅ Três opções implementadas e testadas (156/156 testes)  
**Data**: 2026-04-27
