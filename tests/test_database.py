"""Testes de Unidade para a Persistência de Banco de Dados."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.infrastructure.database_v2 import (
    Base, NotaModel, Cliente, ProdutoModel,
    _get_or_create_cliente, salvar_notas_bd,
)
from src.domain.extractor import NFA, Parte, Produto
from src.infrastructure import database_v2 as database

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
 