@echo off
cd /d "D:\01_Projetos_Ativos\NFA Extractor"

echo Liberando porta 8081...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8081 " ^| findstr "LISTENING"') do (
    taskkill /PID %%a /F >nul 2>&1
)
timeout /t 2 /nobreak >nul

echo Iniciando backend NFA Extractor...
echo   API:  http://127.0.0.1:8081
echo   Docs: http://127.0.0.1:8081/docs
echo.
.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8081 --reload 2>&1
echo.
echo === Backend encerrado ===
pause
