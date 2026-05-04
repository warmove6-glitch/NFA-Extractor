"""ORGATEC – Rotas de Auditoria (protegidas por JWT)."""

from __future__ import annotations

import os
import secrets
import uuid
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from api.auth.security import TokenData, get_current_user
from api.dependencies import get_db
from api.schemas.auditoria import EXTENSOES_ACEITAS, TAMANHO_MAX, TAMANHO_MAX_MB
from api.services.auditoria import processar_lote_auditoria, tasks_status
from src.infrastructure.database_v2 import Cliente

router = APIRouter(prefix="/auditoria", tags=["Auditoria"])


def _validar_arquivo(file: UploadFile) -> None:
    """Valida extensão e tamanho do arquivo."""
    nome = file.filename or ""
    ext = os.path.splitext(nome)[1].lower()
    if ext not in EXTENSOES_ACEITAS:
        raise HTTPException(
            status_code=400,
            detail=f"Extensão '{ext}' não suportada. Aceito: {sorted(EXTENSOES_ACEITAS)}",
        )
    if file.size is not None and file.size > TAMANHO_MAX:
        raise HTTPException(
            status_code=400,
            detail=f"Arquivo excede {TAMANHO_MAX_MB} MB.",
        )


@router.post("/upload/{client_id}")
async def iniciar_auditoria(
    client_id: int,
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """Inicia auditoria — exige JWT válido."""
    cliente = db.query(Cliente).filter(Cliente.id == client_id).first()
    if not cliente:
        raise HTTPException(
            status_code=404,
            detail=f"Cliente com id={client_id} não encontrado.",
        )

    for f in files:
        _validar_arquivo(f)

    task_id = str(uuid.uuid4())
    tasks_status[task_id] = {
        "status": "iniciado",
        "progress": 0,
        "owner_sub": current_user.sub,  # ownership para checar nos GETs
    }

    background_tasks.add_task(
        processar_lote_auditoria,
        task_id,
        files,
        cliente.nome,
        cliente.cpf_cnpj,
    )

    return {"task_id": task_id, "message": "Auditoria iniciada com sucesso."}


def _check_task_owner(task_id: str, user: TokenData) -> dict:
    """Retorna a task se o usuário for dono ou admin. 404 caso contrário."""
    task = tasks_status.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
    owner = task.get("owner_sub")
    if user.role != "admin" and owner and owner != user.sub:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
    return task


@router.get("/status/{task_id}")
async def consultar_status(
    task_id: str,
    current_user: TokenData = Depends(get_current_user),
):
    """Consulta status — exige JWT e ownership."""
    return _check_task_owner(task_id, current_user)


# Path de laudos: protege contra task_id maliciosos via path traversal
_LAUDOS_DIR = os.path.realpath(os.path.join("data", "laudos"))


@router.get("/download/{task_id}")
async def baixar_relatorio(
    task_id: str,
    current_user: TokenData = Depends(get_current_user),
):
    """Download do laudo PDF — exige JWT, ownership, e validação de path."""
    _check_task_owner(task_id, current_user)

    # Sanitiza task_id contra path traversal (só hex/UUID — sem ../ ou /)
    if not task_id.replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="task_id inválido")

    pdf_filename = f"Laudo_{task_id[:8]}.pdf"
    pdf_path = os.path.realpath(os.path.join(_LAUDOS_DIR, pdf_filename))

    # Garante que o path resolvido continua dentro de _LAUDOS_DIR
    if not pdf_path.startswith(_LAUDOS_DIR + os.sep):
        raise HTTPException(status_code=400, detail="Path inválido")

    if not os.path.exists(pdf_path):
        raise HTTPException(
            status_code=404,
            detail="Relatório PDF não encontrado.",
        )

    return FileResponse(
        path=pdf_path,
        filename=pdf_filename,
        media_type="application/pdf",
    )
