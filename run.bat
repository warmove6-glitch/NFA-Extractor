@echo off
chcp 65001 > nul
echo 🏛️ Iniciando Backend ORGATEC (Sovereign Mode)...

REM Verifica se o ambiente virtual existe
if not exist .venv (
    echo [!] Ambiente virtual não encontrado. Criando...
    python -m venv .venv
    call .venv\Scripts\activate
    pip install -r requirements.txt
) else (
    call .venv\Scripts\activate
)

echo [>] Iniciando servidor FastAPI na porta 8081...
python -m uvicorn api.main:app --host 0.0.0.0 --port 8081 --reload
