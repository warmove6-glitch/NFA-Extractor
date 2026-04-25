@echo off
REM ================================================================================
REM NFA Extractor - Inicializador único de desenvolvimento (Windows)
REM Substitui: start_system.bat, run.bat, run_fullstack.bat,
REM            start_backend.bat, start_frontend.bat
REM ================================================================================
chcp 65001 > nul
title ORGATEC NFA Extractor - DEV

cd /d "%~dp0\.."

REM ── Validações ──────────────────────────────────────────────────────────────
if not exist ".venv\Scripts\python.exe" (
    echo [ERRO] .venv nao encontrado. Rode: python -m venv .venv ^&^& make install
    pause
    exit /b 1
)
if not exist "config.env" (
    echo [AVISO] config.env nao encontrado. Copie config.env.template e ajuste.
)

REM ── Backend ─────────────────────────────────────────────────────────────────
echo [1/2] Iniciando Backend (FastAPI :8081)...
start "ORGATEC Backend" /d "%~dp0\.." cmd /k ".venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8081 --reload"

timeout /t 3 /nobreak > nul

REM ── Frontend ────────────────────────────────────────────────────────────────
echo [2/2] Iniciando Frontend (Vite :5173)...
start "ORGATEC Frontend" /d "%~dp0\..\frontend" cmd /k "npm run dev"

echo.
echo ================================================================
echo  Backend  : http://127.0.0.1:8081
echo  Frontend : http://localhost:5173
echo  API Docs : http://127.0.0.1:8081/docs
echo ================================================================
echo.
echo Aguarde alguns segundos para os servicos iniciarem.
exit /b 0
