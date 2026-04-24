import os
from pathlib import Path
from sqlalchemy import (
    create_engine, Column, Integer, String, Float,
    DateTime, ForeignKey, Text, Boolean, event, UniqueConstraint,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Base = declarative_base()


# ── Modelos ──────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"
    id              = Column(Integer, primary_key=True, index=True)
    nome            = Column(String(255), nullable=False)
    email           = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role            = Column(String(50), default="user")          # "user" | "admin"
    is_active       = Column(Boolean, default=True)
    created_at      = Column(DateTime, default=datetime.now)


class Cliente(Base):
    __tablename__ = "clientes"
    id            = Column(Integer, primary_key=True)
    nome          = Column(String(255), nullable=False)
    cpf_cnpj      = Column(String(20), unique=True, nullable=False)
    data_cadastro = Column(DateTime, default=datetime.now)
    laudos        = relationship("Laudo", back_populates="cliente", cascade="all, delete-orphan")


class NotaModel(Base):
    __tablename__ = "notas"
    id             = Column(Integer, primary_key=True, index=True)
    chave_acesso   = Column(String(44), unique=True, index=True, nullable=False)
    numero         = Column(String, index=True)
    emissao        = Column(String)
    natureza       = Column(String)
    laudo_ia       = Column(Text)
    data_auditoria = Column(DateTime, default=datetime.now)
    produtos       = relationship("ProdutoModel", back_populates="nota", cascade="all, delete-orphan")
    __table_args__ = (UniqueConstraint("numero", "emissao", name="uq_nota_numero_emissao"),)


class ProdutoModel(Base):
    __tablename__ = "produtos"
    id        = Column(Integer, primary_key=True, index=True)
    nota_id   = Column(Integer, ForeignKey("notas.id", ondelete="CASCADE"))
    codigo    = Column(String)
    descricao = Column(String)
    quantidade = Column(Float)
    vlr_total = Column(Float)
    nota      = relationship("NotaModel", back_populates="produtos")


class Laudo(Base):
    __tablename__ = "laudos"
    id             = Column(Integer, primary_key=True)
    cliente_id     = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    data_auditoria = Column(DateTime, default=datetime.now)
    veredito_ia    = Column(Text)
    qtd_notas      = Column(Integer)
    valor_total    = Column(Float)
    qtd_anomalias  = Column(Integer)
    pdf_path       = Column(String(500))
    cliente        = relationship("Cliente", back_populates="laudos")


# ── Conexão resiliente ───────────────────────────────────────────────────────

def get_engine():
    db_url = os.getenv("DATABASE_URL", "")

    # Fallback: lê config.env se existir (sem expor credenciais no repo)
    if not db_url:
        env_path = Path(__file__).parent.parent.parent / "config.env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("DATABASE_URL="):
                    db_url = line.split("=", 1)[1].strip()
                    break

    if not db_url:
        db_url = "sqlite:///./orgatec_sovereign.db"

    try:
        if "postgresql" in db_url:
            eng = create_engine(db_url, connect_args={"connect_timeout": 5})
            eng.connect()
            logger.info("DB: PostgreSQL conectado.")
            return eng
    except Exception as exc:
        logger.warning(f"Postgres indisponível ({exc}). Usando SQLite.")

    sqlite_url = "sqlite:///./orgatec_sovereign.db"
    eng = create_engine(sqlite_url, connect_args={"check_same_thread": False})

    @event.listens_for(eng, "connect")
    def set_sqlite_pragma(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.close()

    logger.info("DB: SQLite WAL conectado.")
    return eng


engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    Base.metadata.create_all(bind=engine)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_or_create_cliente(session, nome: str, cpf_cnpj: str) -> Cliente:
    cliente = session.query(Cliente).filter_by(cpf_cnpj=cpf_cnpj).first()
    if cliente:
        return cliente
    novo = Cliente(nome=nome, cpf_cnpj=cpf_cnpj)
    session.add(novo)
    session.flush()
    return novo


def salvar_notas_bd(notas, laudo_texto: str = None) -> tuple[int, int]:
    salvas, ignoradas = 0, 0
    with SessionLocal() as db:
        for nfa in notas:
            chv = nfa.chave_acesso or nfa.numero
            if not chv:
                continue
            if db.query(NotaModel).filter_by(chave_acesso=chv).first():
                ignoradas += 1
                continue
            try:
                nova = NotaModel(
                    chave_acesso=chv,
                    numero=nfa.numero,
                    emissao=nfa.emissao,
                    natureza=nfa.natureza,
                    laudo_ia=laudo_texto,
                )
                nova.produtos = [
                    ProdutoModel(
                        codigo=p.codigo,
                        descricao=p.descricao,
                        quantidade=p.quantidade,
                        vlr_total=p.vlr_total,
                    )
                    for p in nfa.produtos
                ]
                db.add(nova)
                db.commit()
                salvas += 1
            except Exception as exc:
                db.rollback()
                logger.error(f"Erro ao salvar nota {chv}: {exc}")
    return salvas, ignoradas
