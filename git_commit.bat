@echo off
cd /d "D:\01_Projetos_Ativos\NFA Extractor"
echo ========================================
echo  NFA Extractor - Git Commit (fix CORS + CPF/CNPJ)
echo ========================================
echo.

git add api/services/auditoria.py
git add api/main.py

echo.
echo === STATUS ===
git status

echo.
git commit -m "fix: formatar CPF/CNPJ antes do schema Pydantic + exception handler CORS para erros 500"

echo.
echo === LOG ===
git log --oneline -3

echo.
echo === PUSH ===
git push

echo.
echo === CONCLUIDO ===
pause
