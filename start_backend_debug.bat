@echo off
cd /d "D:\01_Projetos_Ativos\NFA Extractor"
echo Iniciando backend, aguarde...
echo.
.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8081 --reload 2>&1
echo.
echo === Backend encerrado ===
pause
