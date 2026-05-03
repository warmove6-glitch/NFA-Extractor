import logging
import os
from datetime import datetime
from pathlib import Path

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
    inspect,
    text,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Base = declarative_base()


# ── Modelos ──────────────────────────────────────────────────────────────────


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), default="user")  # "user" | "admin"
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)


class Cliente(Base):
    __tablename__ = "clientes"
    id = Column(Integer, primary_key=True)
    nome = Column(String(255), nullable=False)
    cpf_cnpj = Column(String(20), unique=True, nullable=False)
    data_cadastro = Column(DateTime, default=datetime.now)
    laudos = relationship("Laudo", back_populates="cliente", cascade="all, delete-orphan")


class NotaModel(Base):
    __tablename__ = "notas"
    id = Column(Integer, primary_key=True, index=True)
    chave_acesso = Column(String(44), unique=True, index=True, nullable=False)
    numero = Column(String, index=True)
    emissao = Column(String)
    natureza = Column(String)
    laudo_ia = Column(Text)
    data_auditoria = Column(DateTime, default=datetime.now)
    produtos = relationship("ProdutoModel", back_populates="nota", cascade="all, delete-orphan")
    __table_args__ = (UniqueConstraint("numero", "emissao", name="uq_nota_numero_emissao"),)


class ProdutoModel(Base):
    __tablename__ = "produtos"
    id = Column(Integer, primary_key=True, index=True)
    nota_id = Column(Integer, ForeignKey("notas.id", ondelete="CASCADE"))
    codigo = Column(String)
    descricao = Column(String)
    quantidade = Column(Float)
    vlr_total = Column(Float)
    nota = relationship("NotaModel", back_populates="produtos")


class Laudo(Base):
    __tablename__ = "laudos"
    id = Column(Integer, primary_key=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    data_auditoria = Column(DateTime, default=datetime.now)
    veredito_ia = Column(Text)
    qtd_notas = Column(Integer)
    valor_total = Column(Float)
    qtd_anomalias = Column(Integer)
    pdf_path = Column(String(500))
    cliente = relationship("Cliente", back_populates="laudos")


class AuditTask(Base):
    __tablename__ = "audit_tasks"
    task_id = Column(String(64), primary_key=True, index=True)
    status = Column(String(50), nullable=False, default="iniciado")
    progress = Column(Integer, nullable=False, default=0)
    payload_json = Column(Text, nullable=False, default="{}")
    # created_at: marca o nascimento da task (não muda)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    # updated_at: atualizado em todo upsert; indexado para suportar cleanup por idade
    updated_at = Column(
        DateTime, default=datetime.now, onupdate=datetime.now, index=True
    )


# ── Conexão resiliente ───────────────────────────────────────────────────────


def get_engine():
    db_url = os.getenv("DATABASE_URL", "")

    # Fallback: lê config.env se existir (sem expor credenciais no repo)
    if not db_url:
        env_path = Path(__file__).parent.parent.parent / "config.env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
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
    _migrar_audit_tasks()
    _migrar_users_created_at()


def _migrar_audit_tasks() -> None:
    """Migração defensiva: adiciona `created_at` em tabelas `audit_tasks` legadas.

    Em DB novo, `create_all` já cria a coluna. Em DB existente (anterior à
    introdução de `created_at`), aplica `ALTER TABLE ADD COLUMN` se faltar.
    Idempotente. Não precisa de Alembic — segue o padrão `create_all` do projeto.
    """
    try:
        inspector = inspect(engine)
        if not inspector.has_table("audit_tasks"):
            return
        cols = {c["name"] for c in inspector.get_columns("audit_tasks")}
        if "created_at" in cols:
            return
        with engine.begin() as conn:
            # SQLite e PostgreSQL aceitam essa sintaxe sem default explícito;
            # rows existentes ficam com NULL — aceitável para tasks legadas.
            conn.execute(text("ALTER TABLE audit_tasks ADD COLUMN created_at TIMESTAMP"))
        logger.info("DB: coluna audit_tasks.created_at adicionada via migração defensiva.")
    except Exception as exc:
        logger.warning(f"Migração defensiva audit_tasks ignorada: {exc}")


def _migrar_users_created_at() -> None:
    """Migração defensiva: renomeia `users.data_cadastro` → `users.created_at`.

    Tabela legada tinha `data_cadastro`; modelo atual usa `created_at`.
    Se já existe `created_at`, não faz nada. Se só existe `data_cadastro`,
    renomeia preservando os dados. Se nenhuma das duas existir (tabela nova),
    `create_all` já cuidou. Idempotente. SQLite >=3.25 e PostgreSQL >=9.2.
    """
    try:
        inspector = inspect(engine)
        if not inspector.has_table("users"):
            return
        cols = {c["name"] for c in inspector.get_columns("users")}
        if "created_at" in cols:
            return
        if "data_cadastro" not in cols:
            return  # tabela nova ou em estado inesperado — sem ação
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE users RENAME COLUMN data_cadastro TO created_at"))
        logger.info("DB: users.data_cadastro renomeada para created_at via migração defensiva.")
    except Exception as exc:
        logger.warning(f"Migração defensiva users ignorada: {exc}")


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
    if not notas:
        return 0, 0

    with SessionLocal() as db:
        # Otimização: Bulk select para evitar N+1 queries no banco
        chaves_entrada = {n.chave_acesso or n.numero for n in notas if n.chave_acesso or n.numero}
        existentes = db.query(NotaModel.chave_acesso).filter(NotaModel.chave_acesso.in_(chaves_entrada)).all()
        set_existentes = {e[0] for e in existentes}

        for nfa in notas:
            chv = nfa.chave_acesso or nfa.numero
            if not chv:
                continue
            if chv in set_existentes:
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
                salvas += 1
            except Exception as exc:
                logger.error(f"Erro ao salvar nota {chv}: {exc}")

        if salvas > 0:
            try:
                db.commit()  # Commit único em lote (muito mais rápido e seguro)
            except Exception as exc:
                db.rollback()
                logger.error(f"Erro no bulk commit das notas: {exc}")
                salvas = 0

    return salvas, ignoradas
