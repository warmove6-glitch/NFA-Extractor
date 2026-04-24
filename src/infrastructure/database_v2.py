import os
from pathlib import Path
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Text, event, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import logging

# Configuração de Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Base = declarative_base()

class Cliente(Base):
    __tablename__ = 'clientes'
    id = Column(Integer, primary_key=True)
    nome = Column(String(255), nullable=False)
    cpf_cnpj = Column(String(20), unique=True, nullable=False)
    data_cadastro = Column(DateTime, default=datetime.now)
    laudos = relationship("Laudo", back_populates="cliente", cascade="all, delete-orphan")

class NotaModel(Base):
    __tablename__ = 'notas'
    id           = Column(Integer, primary_key=True, index=True)
    chave_acesso = Column(String(44), unique=True, index=True, nullable=False)
    numero       = Column(String, index=True)
    emissao      = Column(String)
    natureza     = Column(String)
    laudo_ia     = Column(Text)
    data_auditoria = Column(DateTime, default=datetime.now)
    produtos     = relationship("ProdutoModel", back_populates="nota", cascade="all, delete-orphan")

    # Garante que não haja duplicatas de número+data mesmo que a chave de acesso mude
    __table_args__ = (
        UniqueConstraint('numero', 'emissao', name='uq_nota_numero_emissao'),
    )

class ProdutoModel(Base):
    __tablename__ = 'produtos'
    id = Column(Integer, primary_key=True, index=True)
    nota_id = Column(Integer, ForeignKey('notas.id', ondelete="CASCADE"))
    codigo = Column(String)
    descricao = Column(String)
    quantidade = Column(Float)
    vlr_total = Column(Float)
    nota = relationship("NotaModel", back_populates="produtos")

class Laudo(Base):
    __tablename__ = 'laudos'
    id = Column(Integer, primary_key=True)
    cliente_id = Column(Integer, ForeignKey('clientes.id'), nullable=False)
    data_auditoria = Column(DateTime, default=datetime.now)
    veredito_ia = Column(Text)
    qtd_notas = Column(Integer)
    valor_total = Column(Float)
    qtd_anomalias = Column(Integer)
    pdf_path = Column(String(500))
    cliente = relationship("Cliente", back_populates="laudos")

# --- LÓGICA DE CONEXÃO RESILIENTE (SQUAD ALFA) ---
def get_engine():
    # Tenta carregar do config.env na raiz
    env_path = Path(__file__).parent.parent.parent / 'config.env'
    db_url = "sqlite:///./orgatec_sovereign.db" # Default Fallback

    if env_path.exists():
        with open(env_path, 'r') as f:
            for line in f:
                if line.startswith('DATABASE_URL='):
                    db_url = line.split('=', 1)[1].strip()
                    break
    
    try:
        # Se for Postgres, tenta conectar com timeout curto para falhar rápido
        if "postgresql" in db_url:
            engine = create_engine(db_url, connect_args={'connect_timeout': 5})
            engine.connect()
            logger.info(f"Conexão SOBERANA estabelecida: PostgreSQL")
            return engine
    except Exception as e:
        logger.warning(f"Falha ao conectar no Postgres ({e}). Ativando fallback SQLite.")
    
    # Fallback para SQLite
    sqlite_url = "sqlite:///./orgatec_sovereign.db"
    engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})
    
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()
    
    logger.info("Conexão SOBERANA estabelecida: SQLite Local")
    return engine

engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

def _get_or_create_parte(session, p_data) -> Cliente | None:
    if not p_data.nome.strip():
        return None
    # No novo schema, usamos Cliente para todas as partes se simplificado, ou mantemos a lógica anterior.
    # Como o schema v2 simplificou para 'Cliente', vou buscar por cpf_cnpj no Cliente.
    parte_db = session.query(Cliente).filter_by(cpf_cnpj=p_data.cpf_cnpj).first()
    if parte_db:
        return parte_db
    
    nova_parte = Cliente(
        nome=p_data.nome,
        cpf_cnpj=p_data.cpf_cnpj
    )
    session.add(nova_parte)
    session.flush()
    return nova_parte

def salvar_notas_bd(notas, laudo_texto: str = None) -> tuple[int, int]:
    salvas = 0
    ignoradas = 0
    with SessionLocal() as db:
        for nfa in notas:
            chv = nfa.chave_acesso or nfa.numero
            if not chv: continue
            
            existente = db.query(NotaModel).filter_by(chave_acesso=chv).first()
            if existente:
                ignoradas += 1
                continue

            try:
                # No v2, associamos ao cliente principal (simplificado)
                nova_nota = NotaModel(
                    chave_acesso=chv,
                    numero=nfa.numero,
                    emissao=nfa.emissao,
                    natureza=nfa.natureza,
                    laudo_ia=laudo_texto
                )
                
                produtos_db = []
                for p in nfa.produtos:
                    produtos_db.append(ProdutoModel(
                        codigo=p.codigo,
                        descricao=p.descricao,
                        quantidade=p.quantidade,
                        vlr_total=p.vlr_total
                    ))
                nova_nota.produtos = produtos_db
                
                db.add(nova_nota)
                db.commit()
                salvas += 1
            except Exception as e:
                db.rollback()
                logger.error(f"Falha ao salvar nota {nfa.chave_acesso}: {e}")
                
    return salvas, ignoradas

if __name__ == "__main__":
    init_db()
    print("Base de Dados ORGATEC inicializada com suporte a Laudos.")

