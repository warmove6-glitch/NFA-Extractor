from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List
import uuid
from api.services.auditoria import processar_lote_auditoria, tasks_status
from src.infrastructure.database_v2 import SessionLocal, Cliente

router = APIRouter(prefix="/auditoria", tags=["Auditoria"])


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
    # Buscar dados reais do cliente no banco
    cliente = db.query(Cliente).filter(Cliente.id == client_id).first()
    if not cliente:
        raise HTTPException(
            status_code=404,
            detail=f"Cliente com id={client_id} não encontrado. Cadastre o cliente antes de iniciar a auditoria.",
        )

    task_id = str(uuid.uuid4())
    tasks_status[task_id] = {"status": "iniciado", "progress": 0}

    background_tasks.add_task(
        processar_lote_auditoria,
        task_id,
        files,
        cliente.nome,
        cliente.cpf_cnpj,
    )

    return {"task_id": task_id, "message": "Auditoria iniciada com sucesso."}

@router.get("/status/{task_id}")
async def consultar_status(task_id: str):
    if task_id not in tasks_status:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
    return tasks_status[task_id]

@router.get("/download/{task_id}")
async def baixar_relatorio(task_id: str):
    import os
    from fastapi.responses import FileResponse
    
    pdf_filename = f"Laudo_{task_id[:8]}.pdf"
    pdf_path = os.path.join("data", "laudos", pdf_filename)
    
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="Relatório PDF não encontrado. Verifique se a auditoria foi concluída.")
    
    return FileResponse(
        path=pdf_path, 
        filename=pdf_filename, 
        media_type='application/pdf'
    )

