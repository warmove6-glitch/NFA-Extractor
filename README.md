# 🏛️ OrgAudi — Auditoria Inteligente & BI para NFAs

![Banner](https://img.shields.io/badge/Status-Operational-success?style=for-the-badge&logo=ai&color=059669)
![Architecture](https://img.shields.io/badge/Architecture-Clean_DDD-blue?style=for-the-badge)
![Squad](https://img.shields.io/badge/Squad-Antigravity-orange?style=for-the-badge)

**OrgAudi** é o centro de comando para auditoria de Notas Fiscais Avulsas (NFAs). Transformamos o caos de dados tributários em **Inteligência de Negócios** e **Compliance Fiscal** de alta fidelidade, utilizando o estado da arte em IA Generativa.

---

## 💎 Diferenciais Estratégicos

### 🧠 Tríplice Aliança de IA (Orquestração 2026)
Nosso núcleo de inteligência (`ai_client.py`) opera em uma hierarquia de alta resiliência:
*   **Claude Sonnet 4 (Top-tier):** O "Auditor Sênior". Redação jurídica impecável e análise profunda de anomalias.
*   **Google Gemini (Volume):** Janela de contexto massiva para auditoria de lotes com centenas de notas simultâneas.
*   **Ollama (Privacidade):** Motor local para processamento 100% offline, garantindo sigilo absoluto dos dados da fazenda.

### 📊 Business Intelligence Nativo
- **Análise de Risco HHI:** Cálculo automático do Índice Herfindahl-Hirschman para medir a dependência de compradores.
- **Detecção de Anomalias:** Algoritmos que sinalizam variações de preço e volume acima dos desvios padrão regionais.
- **Gráficos Executivos:** Visualização premium em Donut e Séries Temporais com estética Dark Mode.

### 🗄️ Persistência PostgreSQL
Integração via SQLAlchemy que armazena não apenas os dados das notas, mas o **histórico completo de laudos técnicos**, permitindo auditorias retroativas e monitoramento de tendências ao longo dos anos.

---

## 🛠️ Stack Tecnológica

| Camada | Tecnologia |
| :--- | :--- |
| **Interface** | CustomTkinter (Enterprise Dark Mode) |
| **Inteligência** | Anthropic Claude API / Google GenAI / Ollama |
| **Banco de Dados** | PostgreSQL + SQLAlchemy Core |
| **Relatórios** | ReportLab (PDF c/ Markdown) + OpenPyXL |
| **Segurança** | Pydantic V2 (Data Validation) |

---

## ⚙️ Configuração Rápida

1.  **Ambiente Virtual:**
    ```powershell
    python -m venv .venv
    .\.venv\Scripts\activate
    pip install -r requirements.txt
    ```

2.  **Variáveis de Ambiente (`config.env`):**
    ```env
    ANTHROPIC_API_KEY=sk-ant-...
    GOOGLE_API_KEY=AIza...
    DATABASE_URL=postgresql://postgres:nfa_password@localhost:5432/nfa_extractor
    ```

3.  **Infraestrutura (Docker):**
    ```powershell
    docker-compose up -d
    ```

---

## 📖 Como Operar

### Dashboard Gráfico
Para a experiência completa de auditoria:
```powershell
python app.py
```

### Motor de Laudos (CLI)
Para gerar um relatório consultivo completo instantaneamente:
```powershell
python gerar_laudo.py
```

---

## 🛡️ SRE & Auditoria do Código
Qualidade garantida via `pytest`. Nenhuma alteração no parser chega à produção sem passar pela suíte de validação:
```powershell
pytest tests/ -v
```

---

> [!NOTE]
> *"Transformando dados fiscais em vantagem competitiva no agronegócio."*  
> **Gerenciado pela Squad Antigravity (Alfa, Beta, Sigma, Gama, Delta).**
