@echo off
chcp 65001 > nul
echo =============================================
echo  Build OrgAudi — Executavel Portatil
echo =============================================

REM Instala PyInstaller se necessario
python -c "import PyInstaller" > nul 2>&1
if errorlevel 1 (
    echo Instalando PyInstaller...
    pip install pyinstaller
)

REM Limpa builds anteriores
if exist dist\OrgAudi rmdir /s /q dist\OrgAudi
if exist build rmdir /s /q build

echo Compilando...
pyinstaller ^
  --onedir ^
  --windowed ^
  --name "OrgAudi" ^
  --add-data "extractor.py;." ^
  --add-data "ai_client.py;." ^
  --add-data "pdf_report.py;." ^
  --hidden-import "customtkinter" ^
  --hidden-import "pdfplumber" ^
  --hidden-import "reportlab" ^
  --hidden-import "openpyxl" ^
  --hidden-import "requests" ^
  --hidden-import "PIL" ^
  --collect-all "customtkinter" ^
  app.py

if errorlevel 1 (
    echo ERRO na compilacao!
    pause
    exit /b 1
)

echo.
echo Executavel gerado em: dist\OrgAudi\OrgAudi.exe
echo.
pause
