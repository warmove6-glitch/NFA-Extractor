@echo off
chcp 65001 > nul
echo Iniciando OrgAudi...

REM Verifica se Python esta instalado
python --version > nul 2>&1
if errorlevel 1 (
    echo ERRO: Python nao encontrado. Instale Python 3.10+ de https://python.org
    pause
    exit /b 1
)

REM Instala dependencias se necessario
python -c "import customtkinter" > nul 2>&1
if errorlevel 1 (
    echo Instalando dependencias...
    pip install -r requirements.txt
)

REM Inicia o app
python app.py
