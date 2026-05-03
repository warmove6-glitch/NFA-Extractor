"""Repositório de status de tasks de auditoria (persistência via PostgreSQL/SQLite).

Substitui o antigo `_tasks_store` em memória. Vantagens:
- Sobrevive a reinicializações do backend
- Suporta múltiplos workers Uvicorn (`--workers N`)
- Cleanup por idade via SQL (delete por `updated_at < cutoff`)

Mantém o estado completo da task como JSON em `payload_json` para preservar
todos os campos dinâmicos que `processar_lote_auditoria` escreve (resultado,
total_notas, erro, etc.) sem exigir migração de schema toda vez que um campo
novo aparecer.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any

from src.infrastructure import database_v2 as _database_module

logger = logging.getLogger(__name__)


def _session():
    """Retorna uma session do SessionLocal *atual* do módulo database_v2.

    Importante: lemos `database_v2.SessionLocal` em runtime (e não via import direto)
    para que a fixture `override_db` dos testes (que substitui o atributo no módulo)
    seja respeitada.
    """
    return _database_module.SessionLocal()


def upsert_task(task_id: str, payload: dict[str, Any]) -> None:
    """Cria ou atualiza task. Estado completo serializado em `payload_json`."""
    status = str(payload.get("status", "iniciado"))
    progress_raw = payload.get("progress", 0)
    try:
        progress = int(progress_raw)
    except (TypeError, ValueError):
        progress = 0
    payload_json = json.dumps(payload, ensure_ascii=False, default=str)

    AuditTask = _database_module.AuditTask
    with _session() as db:
        task = db.get(AuditTask, task_id)
        if task is None:
            task = AuditTask(
                task_id=task_id,
                status=status,
                progress=progress,
                payload_json=payload_json,
            )
            db.add(task)
        else:
            task.status = status
            task.progress = progress
            task.payload_json = payload_json
        db.commit()


def get_task(task_id: str) -> dict[str, Any] | None:
    """Retorna o payload completo da task, ou None se não existe."""
    AuditTask = _database_module.AuditTask
    with _session() as db:
        task = db.get(AuditTask, task_id)
        if task is None:
            return None
        try:
            data = json.loads(task.payload_json or "{}")
            if not isinstance(data, dict):
                # JSON válido mas não é objeto — usa fallback consistente
                return {"status": task.status, "progress": task.progress}
            return data
        except json.JSONDecodeError:
            # payload corrompido: devolve o mínimo a partir das colunas
            return {"status": task.status, "progress": task.progress}


def task_exists(task_id: str) -> bool:
    AuditTask = _database_module.AuditTask
    with _session() as db:
        return db.get(AuditTask, task_id) is not None


def cleanup_old_tasks(ttl_seconds: int = 3600) -> int:
    """Remove tasks com `updated_at` mais antigas que o TTL. Retorna total deletado.

    `ttl_seconds=0` força limpeza imediata (útil em testes e para forçar drop).
    """
    AuditTask = _database_module.AuditTask
    cutoff = datetime.now() - timedelta(seconds=ttl_seconds)
    with _session() as db:
        deletados = (
            db.query(AuditTask)
            .filter(AuditTask.updated_at < cutoff)
            .delete(synchronize_session=False)
        )
        db.commit()
        return int(deletados or 0)
