"""Testes do repositório de status de tasks de auditoria (AuditTask).

Estratégia (mesma de tests/test_database.py): SQLite em memória, fixture
substitui `engine` e `SessionLocal` no módulo `database_v2` durante cada teste.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.infrastructure import database_v2 as database
from src.infrastructure.audit_task_repo import (
    cleanup_old_tasks,
    get_task,
    task_exists,
    upsert_task,
)
from src.infrastructure.database_v2 import AuditTask, Base

# Engine isolado por suíte (in-memory)
engine = create_engine("sqlite:///:memory:", echo=False)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function", autouse=True)
def override_db():
    """Substitui engine global pelo SQLite em memória durante cada teste."""
    database.engine = engine
    database.SessionLocal = TestingSessionLocal
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


class TestAuditTaskRepo:

    def test_upsert_cria_task_nova(self):
        """upsert_task em chave nova insere row com payload serializado."""
        upsert_task(
            "abc-123",
            {"status": "extraindo", "progress": 10},
        )
        with TestingSessionLocal() as db:
            task = db.get(AuditTask, "abc-123")
            assert task is not None
            assert task.status == "extraindo"
            assert task.progress == 10
            payload = json.loads(task.payload_json)
            assert payload["status"] == "extraindo"

    def test_upsert_atualiza_task_existente(self):
        """Segundo upsert no mesmo task_id atualiza em vez de duplicar."""
        upsert_task("xyz-999", {"status": "iniciado", "progress": 0})
        upsert_task(
            "xyz-999",
            {"status": "concluido", "progress": 100, "resultado": "OK", "total_notas": 5},
        )
        data = get_task("xyz-999")
        assert data["status"] == "concluido"
        assert data["progress"] == 100
        assert data["resultado"] == "OK"
        assert data["total_notas"] == 5

        # Confirma que continua sendo apenas 1 row
        with TestingSessionLocal() as db:
            assert db.query(AuditTask).count() == 1

    def test_get_task_inexistente_retorna_none(self):
        assert get_task("nao-existe") is None

    def test_task_exists(self):
        assert task_exists("k1") is False
        upsert_task("k1", {"status": "iniciado", "progress": 0})
        assert task_exists("k1") is True

    def test_cleanup_remove_apenas_antigas(self):
        """cleanup_old_tasks deve remover só rows com updated_at < cutoff."""
        # cria 2 tasks: uma "velha" (forçando updated_at no passado) e uma nova
        upsert_task("velha", {"status": "concluido", "progress": 100})
        upsert_task("nova", {"status": "extraindo", "progress": 10})

        # força updated_at da "velha" para 2 horas atrás
        with TestingSessionLocal() as db:
            t = db.get(AuditTask, "velha")
            t.updated_at = datetime.now() - timedelta(hours=2)
            db.commit()

        # TTL de 1h: só a "velha" deve sair
        deletados = cleanup_old_tasks(ttl_seconds=3600)
        assert deletados == 1
        assert get_task("velha") is None
        assert get_task("nova") is not None

    def test_get_task_payload_corrompido_devolve_fallback(self):
        """Se payload_json estiver corrompido, devolve dict mínimo das colunas."""
        upsert_task("corrupt", {"status": "extraindo", "progress": 42})
        with TestingSessionLocal() as db:
            t = db.get(AuditTask, "corrupt")
            t.payload_json = "}{ isso nao eh json valido"
            db.commit()
        data = get_task("corrupt")
        assert data == {"status": "extraindo", "progress": 42}
