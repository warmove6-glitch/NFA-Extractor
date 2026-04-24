import os
from pathlib import Path
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Text, event
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

if __name__ == "__main__":
    init_db()
    print("Base de Dados ORGATEC inicializada com suporte a Laudos.")

