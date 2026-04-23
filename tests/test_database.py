"""Testes de Unidade para a Persistência de Banco de Dados (@Delta)."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base, NotaModel, ParteModel, ProdutoModel, _get_or_create_parte, salvar_notas_bd
from extractor import NFA, Parte, Produto

# Mudar o "binding" global do database.py para usar um SQLite na memória durante os testes
import database

# Inicializa banco SQLite na memória local
engine = create_engine("sqlite:///:memory:", echo=False)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function", autouse=True)
def override_db():
    # Sobrescreve engine e sessionmaker para os testes usarem o SQLite InMemory
    database.engine = engine
    database.SessionLocal = TestingSessionLocal
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

class TestDatabasePersistence:
    
    def test_get_or_create_parte(self):
        with TestingSessionLocal() as db:
            p = Parte(nome="JOÃO DA SILVA", cpf_cnpj="111.111.111-11", municipio="GOIANIA")
            
            # 1. Cria a primeira vez
            parte1 = _get_or_create_parte(db, p)
            assert parte1 is not None
            assert parte1.nome == "JOÃO DA SILVA"
            assert parte1.id is not None
            
            # 2. Busca e reutiliza
            parte2 = _get_or_create_parte(db, p)
            assert parte1.id == parte2.id

    def test_salvar_notas_bd(self):
        notas = [
            NFA(
                chave_acesso="12345678901234567890123456789012345678901234",
                numero="1000",
                emissao="01/01/2026",
                natureza="VENDA",
                destinatario=Parte(nome="FRIGORIFICO A", cpf_cnpj="11.111.111/0001-11"),
                produtos=[
                    Produto(codigo="1070", descricao="GADO", quantidade=10.0, vlr_total=25000.0)
                ]
            )
        ]
        
        salvas, ignoradas = salvar_notas_bd(notas)
        assert salvas == 1
        assert ignoradas == 0
        
        # Teste de Idempotência (ON CONFLICT DO NOTHING manual)
        salvas2, ignoradas2 = salvar_notas_bd(notas)
        assert salvas2 == 0
        assert ignoradas2 == 1
        
        # Verifica a estrutura no banco de dados final
        with TestingSessionLocal() as db:
            nota_db = db.query(NotaModel).first()
            assert nota_db is not None
            assert nota_db.chave_acesso == "12345678901234567890123456789012345678901234"
            assert nota_db.natureza == "VENDA"
            
            # Relacionamentos
            assert nota_db.destinatario is not None
            assert nota_db.destinatario.nome == "FRIGORIFICO A"
            
            # Filhos em cascata
            assert len(nota_db.produtos) == 1
            assert nota_db.produtos[0].descricao == "GADO"
            assert nota_db.produtos[0].vlr_total == 25000.0

    def test_salvar_notas_bd_ignora_nota_sem_chave(self):
        notas = [
            NFA(
                chave_acesso="", # Uma nota sem numeração nenhuma não pode subir pro BI
                numero="",
                natureza="VENDA",
                produtos=[]
            )
        ]
        salvas, ignoradas = salvar_notas_bd(notas)
        assert salvas == 0
        assert ignoradas == 0
        
        with TestingSessionLocal() as db:
            assert db.query(NotaModel).count() == 0
