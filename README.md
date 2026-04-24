# 🏛️ ORGATEC — Auditoria Fiscal Soberana & BI

![Banner](https://img.shields.io/badge/Status-Operational-success?style=for-the-badge&logo=ai&color=0ea5e9)
![Architecture](https://img.shields.io/badge/Architecture-Clean_Architecture-0ea5e9?style=for-the-badge)
![Framework](https://img.shields.io/badge/Stack-React_19_|_FastAPI-6366f1?style=for-the-badge)
![Squad](https://img.shields.io/badge/Squad-Antigravity-00D4FF?style=for-the-badge)

**ORGATEC** é uma plataforma de auditoria forense e inteligência tributária projetada para transformar Notas Fiscais Avulsas (NFAs) em laudos técnicos de alta precisão. Utilizando a **Squad Antigravity**, o sistema automatiza a detecção de fraudes e anomalias com rigor matemático e jurídico.

---

## 💎 Diferenciais Soberanos

### 🧠 Orquestração Multi-Agente (LangGraph)
Diferente de extratores simples, o ORGATEC utiliza uma squad de agentes especializados:
*   **@Alfa (Arquitetura):** Mantém a integridade sistêmica e Clean Architecture.
*   **@Sigma (Dados):** Motor quantitativo que roda modelos Bayesianos de risco.
*   **@Gama (Compliance):** Consultor sênior que emite pareceres baseados na legislação.
*   **@Delta (QA/SRE):** Garante que nenhum dado saia sem validação tripla (Linter, Security, Type).

### 🎨 Interface "Centro de Comando"
O frontend foi reconstruído em **React 19** com uma estética premium:
- **Matrix Background:** Imersão visual em operações táticas.
- **Glassmorphism:** UI moderna com transparências e desfoques.
- **Dashboard Dinâmico:** Métricas em tempo real extraídas diretamente do banco de dados.

---

## 🛠️ Stack Tecnológica

| Camada | Tecnologia |
| :--- | :--- |
| **Frontend** | React 19, Vite, Tailwind CSS 4, Framer Motion |
| **Backend** | FastAPI, Python 3.12, Pydantic V2 |
| **Inteligência** | Pydantic AI, LangGraph, Claude 3.5, Gemini 1.5 |
| **Dados** | SQLAlchemy (Postgres / Fallback SQLite) |
| **Arquitetura** | Clean Architecture (Domain, Application, Infrastructure) |

---

## ⚙️ Estrutura do Projeto

O projeto segue rigorosamente os padrões de **Clean Architecture**:

- `api/`: Controladores e rotas FastAPI.
- `src/domain/`: Regras de negócio, modelos Pydantic e lógica de extração.
- `src/application/`: Serviços de auditoria, analytics e geradores de relatórios.
- `src/infrastructure/`: Persistência de dados e clientes de IA.
- `data/`: Data Lake centralizado contendo bancos de dados, logs e laudos.
- `frontend/`: Aplicação web moderna em React.

---

## 🚀 Operação Técnica

### 1. Preparação
Certifique-se de que o PostgreSQL está rodando via Docker:
```powershell
docker-compose up -d
```

### 2. Ativação Fullstack
Para iniciar simultaneamente o backend e o frontend em modo de desenvolvimento:
```powershell
./run_fullstack.bat
```
*   **API:** `http://localhost:8081`
*   **APP:** `http://localhost:5173` (ou porta informada pelo Vite)

### 3. Trilha de Auditoria
O sistema gera logs imutáveis com hashes de integridade em `data/logs/`, garantindo conformidade total com protocolos de segurança.

---

## 🛡️ Qualidade & SRE
A suíte de testes valida a integridade do parser e da conexão com o banco:
```powershell
pytest tests/ -v
```

---

> [!IMPORTANT]
> **