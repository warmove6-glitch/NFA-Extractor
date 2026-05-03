import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from api.schemas.auditoria import UploadAuditoriaParams, validar_arquivos
from api.schemas.laudos import TaskStatusResponse, UploadResponse
from api.services.auditoria import processar_lote_auditoria, tasks_status
from src.infrastructure.database_v2 import Cliente, Laudo, SessionLocal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auditoria", tags=["Auditoria"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/upload/{client_id}", response_model=UploadResponse)
async def iniciar_auditoria(
    client_id: int,
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    modo_relatorio: Annotated[str, Query(description="'simples' (rápido) ou 'detalhado'")] = "simples",
    formato_relatorio: Annotated[str, Query(description="'html' (padrão) ou 'pdf' (ReportLab)")] = "html",
    db: Session = Depends(get_db),
):
    """
    Inicia auditoria multiagente.
    Aceita PDF e XML (NFSe, NF-e, NFA) no mesmo upload — pode misturar tipos.
    """
    # Valida parâmetros de query via Pydantic
    try:
        params = UploadAuditoriaParams(
            modo_relatorio=modo_relatorio,
            formato_relatorio=formato_relatorio,
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # Valida cliente
    cliente = db.query(Cliente).filter(Cliente.id == client_id).first()
    if not cliente:
        raise HTTPException(
            status_code=404,
            detail=f"Cliente id={client_id} não encontrado. Cadastre antes de auditar.",
        )

    # Validação de arquivos com schema Pydantic
    erros = validar_arquivos(files)
    if erros:
        raise HTTPException(status_code=422, detail="; ".join(erros))

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
        arquivos_bytes,
        cliente.nome,
        cliente.cpf_cnpj,
        params.modo_relatorio,
        params.formato_relatorio,
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
    """Retorna a planilha IRPF HTML armazenada no laudo."""
    from pathlib import Path

    laudo = db.query(Laudo).filter(Laudo.id == laudo_id).first()
    if not laudo:
        raise HTTPException(status_code=404, detail=f"Laudo {laudo_id} não encontrado")

    # Ler diretamente o arquivo HTML da planilha armazenado em pdf_path
    if laudo.pdf_path:
        try:
            pdf_path = Path(laudo.pdf_path)
            if pdf_path.exists():
                with open(pdf_path, encoding="utf-8") as f:
                    return f.read()
        except Exception as e:
            logger.error(f"Erro ao ler planilha do laudo {laudo_id}: {e}")

    # Fallback: HTML vazio se arquivo não encontrado
    return """<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Laudo {}</title></head>
<body>
<h1>Planilha IRPF - Laudo #{}</h1>
<p>Arquivo da planilha não encontrado. Caminho: {}</p>
</body>
</html>""".format(laudo_id, laudo_id, laudo.pdf_path or "N/A")


@router.get("/status/{task_id}", response_model=TaskStatusResponse)
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


@router.get("/planilha/{task_id}", response_class=HTMLResponse)
async def visualizar_planilha(task_id: str):
    """Retorna a planilha IRPF em HTML para visualização direta no navegador."""
    from pathlib import Path

    project_root = Path(__file__).resolve().parent.parent.parent
    html_filename = f"Relatorio_IRPF_{task_id[:8]}.html"
    html_path = project_root / "data" / "laudos" / html_filename

    if not html_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Planilha IRPF não encontrada para task_id: {task_id[:8]}"
        )

    try:
        with open(html_path, encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao ler planilha: {str(e)}")


@router.get("/download/{task_id}")
async def baixar_relatorio(task_id: str):
    """Download do laudo PDF.

    Ordem de busca:
    1. Supabase Storage (se configurado)
    2. Filesystem local data/laudos/ (fallback)
    """
    from pathlib import Path

    from fastapi.responses import FileResponse, RedirectResponse

    from src.infrastructure.supabase_client import supabase_configurado, url_assinada

    pdf_filename = f"Laudo_{task_id[:8]}.pdf"
    html_filename = f"Relatorio_IRPF_{task_id[:8]}.html"

    # 1. Tentar Supabase Storage
    if supabase_configurado():
        url = url_assinada(pdf_filename) or url_assinada(html_filename)
        if url:
            return RedirectResponse(url=url)

    # 2. Fallback: filesystem local
    project_root = Path(__file__).resolve().parent.parent.parent
    laudos_dir = project_root / "data" / "laudos"
    pdf_path = laudos_dir / pdf_filename
    html_path = laudos_dir / html_filename

    if pdf_path.exists():
        return FileResponse(path=str(pdf_path), filename=pdf_filename, media_type="application/pdf")
    if html_path.exists():
        return FileResponse(path=str(html_path), filename=html_filename, media_type="text/html")

    raise HTTPException(
        status_code=404,
        detail=f"Relatório não encontrado para task_id: {task_id[:8]}",
    )


