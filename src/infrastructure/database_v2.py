from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

Base = declarative_base()

class Cliente(Base):
    __tablename__ = 'clientes'
    id = Column(Integer, primary_key=True)
    nome = Column(String(255), nullable=False)
    cpf_cnpj = Column(String(20), unique=True, nullable=False)
    data_cadastro = Column(DateTime, default=datetime.now)
    
    # Relacionamento com Laudos
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
    pdf_path = Column(String(500)) # Caminho para o arquivo salvo
    
    cliente = relationship("Cliente", back_populates="laudos")

# Configuração Engine (SQLite Local Otimizado)
DATABASE_URL = "sqlite:///./orgatec_sovereign.db"
engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False, "timeout": 30}
)

# Ativação do modo WAL para performance
from sqlalchemy import event
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    init_db()
    print("Base de Dados ORGATEC inicializada com suporte a Laudos.")
