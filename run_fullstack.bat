@echo off
title ORGATEC FULLSTACK COMMANDER
chcp 65001 > nul

echo [SQUAD] Iniciando Orquestração Soberana...

REM 1. Inicia o Backend (Porta 8081)
echo [ALFA] Ativando Backend na porta 8081...
start "ORGATEC_BACKEND" cmd /k "python -m uvicorn api.main:app --host 127.0.0.1 --port 8081 --reload"

REM 2. Inicia o Frontend
echo [BETA] Ativando Frontend (Vite)...
cd frontend
start "ORGATEC_FRONTEND" cmd /k "npm run dev"

echo.
echo [!] AMBIENTE PRONTO:
echo [>] API: http://127.0.0.1:8081
echo [>] APP: Verifique a porta do Vite (geralmente 5173)
echo.
pause
