from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List
import uuid
from api.services.auditoria import processar_lote_auditoria, tasks_status
from src.infrastructure.database_v2 import SessionLocal, Cliente

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
    )

    return {
        "task_id": task_id,
        "message": "Auditoria iniciada.",
        "arquivos": {"pdf": n_pdf, "xml": n_xml, "total": len(arquivos_bytes)},
    }

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

