"""Testes da fachada _DbTasksProxy (interface dict-like usada por processar_lote).

Garante que `tasks_status[task_id] = ...`, `tasks_status[task_id]`,
`task_id in tasks_status` e `tasks_status.get(...)` continuam funcionando
após a migração de dict em memória → tabela `audit_tasks`.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.infrastructure import database_v2 as database
from src.infrastructure.database_v2 import Base

engine = create_engine("sqlite:///:memory:", echo=False)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function", autouse=True)
def override_db():
    database.engine = engine
    database.SessionLocal = TestingSessionLocal
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def proxy():
    """Instância fresh do proxy por teste (cleanup_interval baixo para os testes)."""
    # Importa aqui dentro para garantir que pega a versão pós-fixture do SessionLocal
    from api.services.auditoria import _DbTasksProxy
    return _DbTasksProxy(ttl_seconds=3600, cleanup_interval=0.0)


class TestDbTasksProxy:

    def test_proxy_persiste_via_db(self, proxy):
        """Setitem grava na tabela; getitem traz de volta o payload completo."""
        proxy["task-A"] = {"status": "extraindo", "progress": 10}
        data = proxy["task-A"]
        assert data["status"] == "extraindo"
        assert data["progress"] == 10

        # estado terminal com campos extras (resultado, total_notas)
        proxy["task-A"] = {
            "status": "concluido",
            "progress": 100,
            "resultado": "ANÁLISE OK",
            "total_notas": 7,
        }
        data2 = proxy["task-A"]
        assert data2["status"] == "concluido"
        assert data2["resultado"] == "ANÁLISE OK"
        assert data2["total_notas"] == 7

    def test_proxy_keyerror_em_chave_inexistente(self, proxy):
        with pytest.raises(KeyError):
            _ = proxy["nao-existe"]

    def test_proxy_get_com_default(self, proxy):
        # ausente → default
        assert proxy.get("ausente") is None
        assert proxy.get("ausente", {"x": 1}) == {"x": 1}
        # presente → payload
        proxy["k"] = {"status": "iniciado", "progress": 0}
        assert proxy.get("k")["status"] == "iniciado"

    def test_proxy_contains(self, proxy):
        assert "x" not in proxy
        proxy["x"] = {"status": "iniciado", "progress": 0}
        assert "x" in proxy
