"""Testes de Unidade para a Persistência de Banco de Dados."""

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from src.domain.extractor import NFA, Parte, Produto
from src.infrastructure import database_v2 as database
from src.infrastructure.database_v2 import (
    Base,
    Cliente,
    NotaModel,
    ProdutoModel,
    _get_or_create_cliente,
    _migrar_users_created_at,
    salvar_notas_bd,
)

# SQLite em memória para isolamento total dos testes
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


class TestDatabasePersistence:

    def test_get_or_create_cliente_cria_novo(self):
        """_get_or_create_cliente deve criar um Cliente na primeira chamada."""
        with TestingSessionLocal() as db:
            cliente = _get_or_create_cliente(db, "JOÃO DA SILVA", "111.111.111-11")
            assert cliente is not None
            assert cliente.nome == "JOÃO DA SILVA"
            assert cliente.cpf_cnpj == "111.111.111-11"
            assert cliente.id is not None

    def test_get_or_create_cliente_reutiliza_existente(self):
        """Segunda chamada com mesmo CPF deve retornar o mesmo registro."""
        with TestingSessionLocal() as db:
            c1 = _get_or_create_cliente(db, "JOÃO DA SILVA", "111.111.111-11")
            c2 = _get_or_create_cliente(db, "JOÃO DA SILVA", "111.111.111-11")
            assert c1.id == c2.id

    def test_salvar_notas_bd_salva_com_sucesso(self):
        """Nota válida com chave deve ser persistida."""
        notas = [
            NFA(
                chave_acesso="12345678901234567890123456789012345678901234",
                numero="1000",
                emissao="01/01/2026",
                natureza="VENDA",
                produtos=[
                    Produto(codigo="1070", descricao="GADO", quantidade=10.0, vlr_total=25000.0)
                ],
            )
        ]
        salvas, ignoradas = salvar_notas_bd(notas)
        assert salvas == 1
        assert ignoradas == 0

    def test_salvar_notas_bd_idempotencia(self):
        """Segunda inserção da mesma nota deve ser ignorada (sem duplicata)."""
        notas = [
            NFA(
                chave_acesso="12345678901234567890123456789012345678901234",
                numero="1000",
                emissao="01/01/2026",
                natureza="VENDA",
                produtos=[Produto(descricao="GADO", quantidade=10.0, vlr_total=25000.0)],
            )
        ]
        salvar_notas_bd(notas)
        salvas2, ignoradas2 = salvar_notas_bd(notas)
        assert salvas2 == 0
        assert ignoradas2 == 1

    def test_salvar_notas_bd_persiste_produtos(self):
        """Produtos da NFA devem aparecer no banco em cascata."""
        notas = [
            NFA(
                chave_acesso="12345678901234567890123456789012345678901234",
                numero="1000",
                emissao="01/01/2026",
                natureza="VENDA",
                produtos=[Produto(codigo="1070", descricao="GADO", quantidade=10.0, vlr_total=25000.0)],
            )
        ]
        salvar_notas_bd(notas)
        with TestingSessionLocal() as db:
            nota_db = db.query(NotaModel).first()
            assert nota_db is not None
            assert len(nota_db.produtos) == 1
            assert nota_db.produtos[0].codigo == "1070"
            assert nota_db.produtos[0].descricao == "GADO"
            assert nota_db.produtos[0].quantidade == 10.0
            assert nota_db.produtos[0].vlr_total == 25000.0


class TestMigracaoUsersLegada:
    """Migração defensiva: users.data_cadastro → users.created_at."""

    def test_renomeia_data_cadastro_para_created_at(self):
        """Tabela legada com data_cadastro deve ser renomeada idempotentemente."""
        # Engine isolado: simula DB legado sem `created_at`
        legacy_engine = create_engine("sqlite:///:memory:", echo=False)
        with legacy_engine.begin() as conn:
            conn.execute(text(
                "CREATE TABLE users ("
                "id INTEGER PRIMARY KEY, "
                "nome VARCHAR(255), "
                "email VARCHAR(255), "
                "hashed_password VARCHAR(255), "
                "role VARCHAR(50), "
                "is_active BOOLEAN, "
                "data_cadastro TIMESTAMP)"
            ))
            conn.execute(text(
                "INSERT INTO users (nome, email, hashed_password, role, is_active, data_cadastro) "
                "VALUES ('Admin', 'admin@x.com', 'hash', 'admin', 1, '2024-01-01')"
            ))

        # Substitui engine global temporariamente
        database.engine = legacy_engine
        try:
            _migrar_users_created_at()
            cols = {c["name"] for c in inspect(legacy_engine).get_columns("users")}
            assert "created_at" in cols
            assert "data_cadastro" not in cols
            # Dados preservados
            with legacy_engine.connect() as conn:
                row = conn.execute(text("SELECT email, created_at FROM users")).fetchone()
                assert row[0] == "admin@x.com"
                assert row[1] is not None
        finally:
            database.engine = engine  # restaura

    def test_idempotente_em_db_ja_migrado(self):
        """Rodar 2x não deve falhar nem alterar nada."""
        legacy_engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(bind=legacy_engine)

        database.engine = legacy_engine
        try:
            _migrar_users_created_at()  # primeira chamada (no-op, tabela já tem created_at)
            _migrar_users_created_at()  # segunda chamada
            cols = {c["name"] for c in inspect(legacy_engine).get_columns("users")}
            assert "created_at" in cols
        finally:
            database.engine = engine

    def test_sem_users_nao_falha(self):
        """Migração em DB sem tabela users deve sair silenciosamente."""
        empty_engine = create_engine("sqlite:///:memory:", echo=False)
        database.engine = empty_engine
        try:
            _migrar_users_created_at()  # não deve levantar
        finally:
            database.engine = engine
