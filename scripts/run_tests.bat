@echo off
chcp 65001 > nul
title NFA Extractor — Testes

cd /d "D:\01_Projetos_Ativos\NFA Extractor"
echo.
echo ========================================
echo  NFA Extractor — Rodando Testes
echo ========================================
echo.

REM Verificar venv
if not exist ".venv\Scripts\python.exe" (
    echo [ERRO] venv nao encontrado. Rode: python -m venv .venv
    pause
    exit /b 1
)

echo [1/3] Verificando imports principais...
.venv\Scripts\python.exe -c "import fastapi, pydantic, sqlalchemy, bcrypt; print('  OK: fastapi, pydantic, sqlalchemy, bcrypt')"
if errorlevel 1 (
    echo [ERRO] Dependencias faltando. Rode: .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

echo.
echo [2/3] Verificando sintaxe dos arquivos principais...
.venv\Scripts\python.exe -m py_compile api\main.py api\routes\auth.py api\routes\auditoria.py api\auth\security.py api\services\auditoria.py && echo   OK: api/
.venv\Scripts\python.exe -m py_compile src\infrastructure\ai_client.py src\infrastructure\database_v2.py src\application\sovereign_engine.py && echo   OK: src/

echo.
echo [3/3] Rodando suite de testes pytest...
echo ----------------------------------------
.venv\Scripts\python.exe -m pytest tests\ -v --tb=short -q 2>&1
echo ----------------------------------------
echo.

echo Pressione qualquer tecla para fechar...
pause > nul
