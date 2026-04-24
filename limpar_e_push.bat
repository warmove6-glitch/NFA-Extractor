@echo off
chcp 65001 >nul
echo === Limpando locks e arquivo acidental ===

:: Remove lock do git se existir
if exist ".git\HEAD.lock" del /f ".git\HEAD.lock"
if exist ".git\index.lock" del /f ".git\index.lock"

:: Remove arquivo acidental
if exist "frontend\]" (
    del /f "frontend\]"
    echo Arquivo "frontend\]" removido.
) else (
    echo Arquivo "frontend\]" nao encontrado.
)

:: Commit da remocao
git add -A
git commit -m "chore: remover arquivo acidental frontend/]"
git push origin demo-gravacao

echo.
echo === Concluido! ===
pause
