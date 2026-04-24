@echo off
cd /d "D:\01_Projetos_Ativos\NFA Extractor"
echo Verificando status...
git log --oneline -3
echo.
echo Enviando para GitHub (branch: demo-gravacao)...
git push origin demo-gravacao
echo.
echo === RESULTADO ACIMA ===
pause
