from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException, Depends, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from typing import List
import uuid
from datetime import datetime
from jinja2 import Template
from api.services.auditoria import processar_lote_auditoria, tasks_status
from src.infrastructure.database_v2 import SessionLocal, Cliente, Laudo

router = APIRouter(prefix="/auditoria", tags=["Auditoria"])

# Extensões aceitas para upload
_EXT_PDF = {".pdf"}
_EXT_XML = {".xml"}
_EXT_ACEITAS = _EXT_PDF | _EXT_XML


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/upload/{client_id}")
async def iniciar_auditoria(
    client_id: int,
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    modo_relatorio: str = Query('simples', description="'simples' (rápido) ou 'detalhado'"),
    formato_relatorio: str = Query('pdf', description="'pdf' (ReportLab) ou 'html' (moderno)"),
    db: Session = Depends(get_db),
):
    """
    Inicia auditoria multiagente.
    Aceita PDF e XML (NFSe, NF-e, NFA) no mesmo upload — pode misturar tipos.
    """
    import os

    # Valida cliente
    cliente = db.query(Cliente).filter(Cliente.id == client_id).first()
    if not cliente:
        raise HTTPException(
            status_code=404,
            detail=f"Cliente id={client_id} não encontrado. Cadastre antes de auditar.",
        )

    # Valida extensões dos arquivos
    invalidos = []
    for f in files:
        ext = os.path.splitext(f.filename or "")[1].lower()
        if ext not in _EXT_ACEITAS:
            invalidos.append(f.filename)
    if invalidos:
        raise HTTPException(
            status_code=422,
            detail=f"Formato não suportado: {invalidos}. Aceito: PDF e XML.",
        )

    # Lê o conteúdo de todos os arquivos AGORA, antes de retornar a resposta.
    # UploadFile é vinculado ao ciclo da requisição e pode ser fechado pela
    # framework antes que a background task execute — lendo aqui garantimos
    # que os bytes chegam intactos ao processamento assíncrono.
    arquivos_bytes: list[tuple[str, bytes]] = []
    n_pdf = n_xml = 0
    for f in files:
        conteudo = await f.read()
        nome = f.filename or ""
        arquivos_bytes.append((nome, conteudo))
        if nome.lower().endswith(".pdf"):
            n_pdf += 1
        elif nome.lower().endswith(".xml"):
            n_xml += 1

    task_id = str(uuid.uuid4())
    tasks_status[task_id] = {"status": "iniciado", "progress": 0}

    background_tasks.add_task(
        processar_lote_auditoria,
        task_id,
        arquivos_bytes,   # lista de (nome, bytes) — sem dependência de UploadFile
        cliente.nome,
        cliente.cpf_cnpj,
        modo_relatorio,
        formato_relatorio,
    )

    return {
        "task_id": task_id,
        "message": "Auditoria iniciada.",
        "arquivos": {"pdf": n_pdf, "xml": n_xml, "total": len(arquivos_bytes)},
    }

@router.get("/relatorio/{laudo_id}", response_class=HTMLResponse)
async def visualizar_relatorio_html(
    laudo_id: int,
    db: Session = Depends(get_db),
):
    """Gera e retorna relatório moderno em HTML baseado no laudo."""
    laudo = db.query(Laudo).filter(Laudo.id == laudo_id).first()
    if not laudo:
        raise HTTPException(status_code=404, detail=f"Laudo {laudo_id} não encontrado")

    cliente = db.query(Cliente).filter(Cliente.id == laudo.cliente_id).first()

    conformidade = 100 - (laudo.qtd_anomalias / max(laudo.qtd_notas, 1) * 100)
    nivel_risco = "ALTO" if laudo.qtd_anomalias > 5 else "MÉDIO" if laudo.qtd_anomalias > 2 else "BAIXO"
    score_risco = round((laudo.qtd_anomalias / max(laudo.qtd_notas, 1) * 10), 1)

    data_formatada = laudo.data_auditoria.strftime("%d de %B, %Y") if laudo.data_auditoria else "N/A"
    hora_formatada = laudo.data_auditoria.strftime("%H:%M:%S") if laudo.data_auditoria else "N/A"

    veredito_completo = laudo.veredito_ia or "Análise não disponível"

    html_template = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Relatório de Auditoria NFA - Laudo #{{ laudo_id }}</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Inter', sans-serif; background-color: #f5f7fa; color: #333; }
        .container { display: flex; min-height: 100vh; }
        .sidebar { width: 280px; background-color: #2d3436; color: #ecf0f1; padding: 40px 30px; box-shadow: 2px 0 8px rgba(0,0,0,0.1); }
        .sidebar-title { font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: #95a5a6; margin-bottom: 20px; margin-top: 30px; }
        .sidebar-title:first-child { margin-top: 0; }
        .metadata-item { margin-bottom: 16px; }
        .metadata-label { font-size: 11px; color: #bdc3c7; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px; }
        .metadata-value { font-size: 14px; color: #ecf0f1; font-weight: 500; word-break: break-word; }
        .metadata-badge { display: inline-block; background-color: #27ae60; color: white; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; margin-top: 4px; }
        .metadata-badge.warning { background-color: #f39c12; }
        .metadata-badge.danger { background-color: #e74c3c; }
        .main { flex: 1; padding: 40px; overflow-y: auto; }
        .header { margin-bottom: 40px; }
        .header-title { font-size: 32px; font-weight: 700; color: #2d3436; margin-bottom: 8px; }
        .header-subtitle { font-size: 14px; color: #7f8c8d; font-weight: 400; }
        .card { background-color: white; border-radius: 12px; padding: 24px; margin-bottom: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
        .card-title { font-size: 18px; font-weight: 600; color: #2d3436; margin-bottom: 16px; border-bottom: 2px solid #ecf0f1; padding-bottom: 12px; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 16px; margin-bottom: 24px; }
        .stat-box { background: linear-gradient(135deg, #f5f7fa 0%, #ecf0f1 100%); padding: 16px; border-radius: 8px; text-align: center; }
        .stat-label { font-size: 12px; color: #7f8c8d; font-weight: 600; text-transform: uppercase; margin-bottom: 8px; }
        .stat-value { font-size: 24px; font-weight: 700; color: #2d3436; }
        .analysis-section { background: linear-gradient(135deg, #f5f7fa 0%, #ecf0f1 100%); border-left: 4px solid #2980b9; padding: 16px; border-radius: 8px; margin-top: 12px; font-size: 13px; line-height: 1.6; color: #555; white-space: pre-wrap; word-wrap: break-word; }
        .footer { text-align: center; padding: 20px 0; border-top: 1px solid #ecf0f1; margin-top: 20px; font-size: 12px; color: #95a5a6; }
        @media (max-width: 768px) { .container { flex-direction: column; } .sidebar { width: 100%; padding: 30px 20px; } .main { padding: 30px 20px; } }
    </style>
</head>
<body>
    <div class="container">
        <aside class="sidebar">
            <div class="sidebar-title">Status</div>
            <div class="metadata-item"><div class="metadata-label">Situação</div><div class="metadata-value"><span class="metadata-badge">Concluído</span></div></div>
            <div class="sidebar-title">Documento</div>
            <div class="metadata-item"><div class="metadata-label">ID da Auditoria</div><div class="metadata-value">AUD-{{ laudo_id }}</div></div>
            <div class="metadata-item"><div class="metadata-label">Data de Emissão</div><div class="metadata-value">{{ data_formatada }}</div></div>
            <div class="sidebar-title">Contribuinte</div>
            <div class="metadata-item"><div class="metadata-label">Nome</div><div class="metadata-value">{{ cliente.nome if cliente else 'N/A' }}</div></div>
            <div class="metadata-item"><div class="metadata-label">CNPJ/CPF</div><div class="metadata-value">{{ cliente.cpf_cnpj if cliente else 'N/A' }}</div></div>
            <div class="sidebar-title">Risco</div>
            <div class="metadata-item"><div class="metadata-label">Nível</div><div class="metadata-value"><span class="metadata-badge {% if nivel_risco == 'ALTO' %}danger{% elif nivel_risco == 'MÉDIO' %}warning{% endif %}">{{ nivel_risco }}</span></div></div>
            <div class="metadata-item"><div class="metadata-label">Score</div><div class="metadata-value">{{ score_risco }} / 10</div></div>
        </aside>
        <main class="main">
            <div class="header">
                <h1 class="header-title">Relatório de Auditoria NFA</h1>
                <p class="header-subtitle">Análise automatizada de Notas Fiscais Agropecuárias com IA</p>
            </div>
            <div class="card">
                <h2 class="card-title">Resumo Executivo</h2>
                <div class="stats-grid">
                    <div class="stat-box"><div class="stat-label">Notas Processadas</div><div class="stat-value">{{ qtd_notas }}</div></div>
                    <div class="stat-box"><div class="stat-label">Valor Total</div><div class="stat-value">R$ {{ valor_total_formatado }}</div></div>
                    <div class="stat-box"><div class="stat-label">Anomalias</div><div class="stat-value">{{ qtd_anomalias }}</div></div>
                    <div class="stat-box"><div class="stat-label">Conformidade</div><div class="stat-value">{{ conformidade_pct }}</div></div>
                </div>
            </div>
            <div class="card">
                <h2 class="card-title">Análise Técnica</h2>
                <p style="font-size: 12px; color: #7f8c8d; margin-bottom: 12px; text-transform: uppercase; font-weight: 600;">Veredito do Auditor Fiscal</p>
                <div class="analysis-section">{{ veredito_completo }}</div>
            </div>
            <footer class="footer"><p>© 2026 ORGATEC IA. Todos os direitos reservados. | Laudo #{{ laudo_id }}</p></footer>
        </main>
    </div>
</body>
</html>"""

    template = Template(html_template)
    html_content = template.render(
        laudo_id=laudo_id,
        qtd_notas=laudo.qtd_notas,
        valor_total_formatado=f"{laudo.valor_total:,.2f}",
        qtd_anomalias=laudo.qtd_anomalias,
        conformidade_pct=f"{conformidade:.1f}%",
        data_formatada=data_formatada,
        hora_formatada=hora_formatada,
        cliente=cliente,
        nivel_risco=nivel_risco,
        score_risco=score_risco,
        veredito_completo=veredito_completo,
    )

    return html_content


@router.get("/status/{task_id}")
async def consultar_status(task_id: str):
    if task_id not in tasks_status:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
    return tasks_status[task_id]

@router.get("/laudos")
async def listar_laudos(
    db: Session = Depends(get_db),
    limit: int = 50,
):
    """Retorna histórico de laudos gerados (mais recentes primeiro)."""
    from src.infrastructure.database_v2 import Laudo
    laudos = (
        db.query(Laudo)
        .order_by(Laudo.data_auditoria.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": l.id,
            "cliente_id": l.cliente_id,
            "data_auditoria": l.data_auditoria.isoformat() if l.data_auditoria else None,
            "qtd_notas": l.qtd_notas,
            "valor_total": l.valor_total,
            "qtd_anomalias": l.qtd_anomalias,
            "pdf_path": l.pdf_path,
            "veredito_resumo": (l.veredito_ia or "")[:300],
        }
        for l in laudos
    ]


@router.get("/download/{task_id}")
async def baixar_relatorio(task_id: str):
    import os
    from pathlib import Path
    from fastapi.responses import FileResponse

    pdf_filename = f"Laudo_{task_id[:8]}.pdf"
    # Caminho absoluto baseado no diretório raiz do projeto
    project_root = Path(__file__).resolve().parent.parent.parent
    pdf_path = project_root / "data" / "laudos" / pdf_filename

    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail=f"Relatório PDF não encontrado: {pdf_filename}")

    return FileResponse(
        path=str(pdf_path),
        filename=pdf_filename,
        media_type='application/pdf'
    )


