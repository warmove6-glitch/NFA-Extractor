from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException
from typing import List
import uuid
from api.services.auditoria import processar_lote_auditoria, tasks_status

router = APIRouter(prefix="/auditoria", tags=["Auditoria"])

@router.post("/upload/{client_id}")
async def iniciar_auditoria(
    client_id: int, 
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...)
):
    task_id = str(uuid.uuid4())
    tasks_status[task_id] = {"status": "iniciado", "progress": 0}
    
    # Em produção, buscar dados do cliente no DB pelo client_id
    client_name = "Cliente Mock" 
    client_cpf = "000.000.000-00"
    
    background_tasks.add_task(processar_lote_auditoria, task_id, files, client_name, client_cpf)
    
    return {"task_id": task_id, "message": "Auditoria iniciada com sucesso."}

@router.get("/status/{task_id}")
async def consultar_status(task_id: str):
    if task_id not in tasks_status:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
    return tasks_status[task_id]
