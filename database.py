"""Módulo de Persistência — SQLAlchemy Postgres para NFA Extractor."""

import logging
from pathlib import Path
import os
import re

from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

from extractor import NFA, Parte, Produto

logger = logging.getLogger('NFA_Database')
logger.setLevel(logging.INFO)

CONFIG_PATH = Path(__file__).parent / 'config.env'

def _carregar_env(chave: str) -> str:
    if CONFIG_PATH.exists():
        for linha in CONFIG_PATH.read_text(encoding='utf-8').splitlines():
            if linha.startswith(f'{chave}='):
                return linha.split('=', 1)[1].strip()
    return os.getenv(chave, '')

# URL default segura fallbacks para localhost se não houver config
DATABASE_URL = _carregar_env('DATABASE_URL') or "postgresql://postgres:nfa_password@localhost:5432/nfa_extractor"

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class ParteModel(Base):
    __tablename__ = 'partes'
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, index=True, nullable=False)
    ie = Column(String)
    cpf_cnpj = Column(String, index=True)
    municipio = Column(String)

    # Prevenção de duplicação exata caso a mesma empresa apareça várias vezes (nome + cpf/cnpj)
    __table_args__ = (UniqueConstraint('nome', 'cpf_cnpj', name='_nome_cpf_uc'),)


class NotaModel(Base):
    __tablename__ = 'notas'
    id = Column(Integer, primary_key=True, index=True)
    chave_acesso = Column(String(44), unique=True, index=True, nullable=False)
    numero = Column(String, index=True)
    emissao = Column(String)
    natureza = Column(String)
    local_emissao = Column(String)

    remetente_id = Column(Integer, ForeignKey('partes.id'), nullable=True)
    destinatario_id = Column(Integer, ForeignKey('partes.id'), nullable=True)
    transportador_id = Column(Integer, ForeignKey('partes.id'), nullable=True)

    remetente = relationship("ParteModel", foreign_keys=[remetente_id])
    destinatario = relationship("ParteModel", foreign_keys=[destinatario_id])
    transportador = relationship("ParteModel", foreign_keys=[transportador_id])

    produtos = relationship("ProdutoModel", back_populates="nota", cascade="all, delete-orphan")


class ProdutoModel(Base):
    __tablename__ = 'produtos'
    id = Column(Integer, primary_key=True, index=True)
    nota_id = Column(Integer, ForeignKey('notas.id', ondelete="CASCADE"))
    codigo = Column(String)
    descricao = Column(String)
    quantidade = Column(Float)
    vlr_icms = Column(Float)
    vlr_unitario = Column(Float)
    vlr_total = Column(Float)

    nota = relationship("NotaModel", back_populates="produtos")


def criar_tabelas():
    """Inicializa as tabelas no banco de dados, ignorando se já existerem."""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Tabelas PostgreSQL verificadas/criadas com sucesso.")
    except Exception as e:
        logger.error(f"Falha ao conectar no banco PostgreSQL para criação: {e}")
        raise ValueError(f"PostgreSQL não está rodando ou credenciais inválidas. Erro: {e}")

def _get_or_create_parte(session, p_data: Parte) -> ParteModel | None:
    if not p_data.nome.strip():
        return None
    # Busca por cpf_cnpj ou (se não tiver) por nome exato
    parte_db = None
    if p_data.cpf_cnpj:
        parte_db = session.query(ParteModel).filter_by(cpf_cnpj=p_data.cpf_cnpj).first()
    else:
        parte_db = session.query(ParteModel).filter_by(nome=p_data.nome).first()

    if parte_db:
        return parte_db
    
    nova_parte = ParteModel(
        nome=p_data.nome,
        ie=p_data.ie,
        cpf_cnpj=p_data.cpf_cnpj,
        municipio=p_data.municipio
    )
    session.add(nova_parte)
    session.flush() # obtem o ID
    return nova_parte


def salvar_notas_bd(notas: list[NFA]) -> tuple[int, int]:
    """Salva a lista gerada de Pydantic Models no Banco PostgreSQL.
    
    Faz um ON CONFLICT DO NOTHING manual pela chave_acesso.
    
    Returns:
        tuple[int, int]: (quantidade_salvas_com_sucesso, quantidade_ja_existente_ignorada)
    """
    salvas = 0
    ignoradas = 0

    with SessionLocal() as db:
        for nfa in notas:
            # Pula notas sem chave, pois são irratreáveis globalmente
            chv = nfa.chave_acesso or nfa.numero
            if not chv:
                continue
                
            existente = db.query(NotaModel).filter_by(chave_acesso=chv).first()
            if existente:
                ignoradas += 1
                continue

            try:
                rem = _get_or_create_parte(db, nfa.remetente)
                dst = _get_or_create_parte(db, nfa.destinatario)
                trp = _get_or_create_parte(db, nfa.transportador)

                nova_nota = NotaModel(
                    chave_acesso=chv,
                    numero=nfa.numero,
                    emissao=nfa.emissao,
                    natureza=nfa.natureza,
                    local_emissao=nfa.local_emissao,
                    remetente_id=rem.id if rem else None,
                    destinatario_id=dst.id if dst else None,
                    transportador_id=trp.id if trp else None
                )

                produtos_db = []
                for p in nfa.produtos:
                    produtos_db.append(ProdutoModel(
                        codigo=p.codigo,
                        descricao=p.descricao,
                        quantidade=p.quantidade,
                        vlr_icms=p.vlr_icms,
                        vlr_unitario=p.vlr_unitario,
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
