@echo off
cd /d "D:\01_Projetos_Ativos\NFA Extractor"
echo ========================================
echo  NFA Extractor - Rodando testes pytest
echo ========================================
echo.
.venv\Scripts\python.exe -m pytest tests/ -v --tb=short 2>&1 > test_output.txt
echo.
echo === RESULTADO ===
type test_output.txt
echo.
echo === FIM DOS TESTES ===
echo Resultado salvo em: test_output.txt
pause
