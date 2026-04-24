@echo off
cd /d "D:\01_Projetos_Ativos\NFA Extractor"

echo [1/4] Removendo lock do git...
del /f ".git\index.lock" 2>nul

echo [2/4] Configurando identidade...
git config user.email "orgatec.cloud@gmail.com"
git config user.name "ORGATEC IA"

echo [3/4] Adicionando arquivos alterados...
git add api/main.py
git add api/routes/auditoria.py
git add api/services/auditoria.py
git add frontend/src/pages/AuditoriaModule.jsx
git add frontend/src/pages/LoginPage.jsx
git add src/application/sovereign_engine.py
git add src/infrastructure/database_v2.py
git add src/infrastructure/ai_client.py
git add src/application/reports/pdf_report.py

echo [4/4] Commitando...
git commit -m "fix: segurança, bugs e limpeza de código (Cowork 2026-04-24)" -m "- CORS: removido allow_origins=*, usa ALLOWED_ORIGINS via env" -m "- Login: credenciais dev protegidas por import.meta.env.DEV" -m "- ai_client: sanitização contra prompt injection + bug fix em perguntar()" -m "- AuditoriaModule: polling com timeout 15 min + estados error/timeout" -m "- auditoria service: task queue thread-safe com threading.Lock" -m "- auditoria routes: busca cliente real no banco (404 se nao existir)" -m "- sovereign_engine: magic numbers extraidos como constantes de classe" -m "- pdf_report: HTML escaping corrigido" -m "- database_v2: UniqueConstraint(numero, emissao) na NotaModel"

echo.
echo [PUSH] Enviando para GitHub...
git push origin demo-gravacao

echo.
echo === CONCLUIDO ===
pause
