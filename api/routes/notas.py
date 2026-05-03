"""
ORGATEC — Rotas de Notas e Busca Semântica
GET  /notas/buscar-similar   → busca semântica via pgvector no Supabase
POST /notas/{id}/embedding   → gera e salva embedding de uma nota específica
GET  /notas/                 → lista notas (com paginação simples)
"""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.auth.security import TokenData, get_current_user
from src.infrastructure.database_v2 import NotaModel, ProdutoModel, SessionLocal

router = APIRouter(prefix="/notas", tags=["Notas"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Schemas ───────────────────────────────────────────────────────────────────

class BuscaResponse(BaseModel):
    query: str
    resultados: list[dict[str, Any]]
    total: int


class EmbeddingResponse(BaseModel):
    nota_id: int
    sucesso: bool
    mensagem: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/buscar-similar", response_model=BuscaResponse)
def buscar_similar(
    q: str = Query(..., min_length=3, description="Texto da busca semântica"),
    limite: int = Query(8, ge=1, le=20),
    threshold: float = Query(0.70, ge=0.0, le=1.0),
    _: TokenData = Depends(get_current_user),
):
    """
    Busca notas fiscais semanticamente similares à query.

    Exemplos de query:
    - "soja irrigada Paraná com irregularidade de ICMS"
    - "venda de gado bovino acima de R$ 50.000"
    - "nota de insumos agrícolas com NCM divergente"
    """
    from api.services.embeddings import buscar_notas_similares

    try:
        resultados = buscar_notas_similares(
            query=q,
            match_threshold=threshold,
            limit=limite,
        )
    except RuntimeError as exc:
        # Config ausente (OPENAI_API_KEY, SUPABASE keys)
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro na busca semântica: {exc}")

    return BuscaResponse(
        query=q,
        resultados=resultados,
        total=len(resultados),
    )


@router.post("/{nota_id}/embedding", response_model=EmbeddingResponse)
def gerar_embedding_nota(
    nota_id: int,
    db: Session = Depends(get_db),
    _: TokenData = Depends(get_current_user),
):
    """
    Gera e salva o embedding de uma nota específica.
    Útil para re-indexar notas já auditadas.
    """
    from api.services.embeddings import salvar_embedding

    nota = db.query(NotaModel).filter(NotaModel.id == nota_id).first()
    if not nota:
        raise HTTPException(status_code=404, detail=f"Nota id={nota_id} não encontrada.")

    # Concatena descrição dos produtos para enriquecer o embedding
    produtos = db.query(ProdutoModel).filter(ProdutoModel.nota_id == nota_id).all()
    descricao_produtos = "; ".join(
        p.descricao for p in produtos if p.descricao
    ) if produtos else None

    sucesso = salvar_embedding(
        nota_id=nota.id,
        cliente_id=None,           # NotaModel não tem cliente_id direto
        cliente_nome=None,
        natureza=nota.natureza,
        emissao=nota.emissao,
        numero=nota.numero,
        descricao_produtos=descricao_produtos,
    )

    return EmbeddingResponse(
        nota_id=nota_id,
        sucesso=sucesso,
        mensagem="Embedding salvo com sucesso." if sucesso else "Falha ao gerar embedding (verifique OPENAI_API_KEY).",
    )


@router.get("/")
def listar_notas(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: TokenData = Depends(get_current_user),
):
    """Lista notas com paginação simples."""
    total = db.query(NotaModel).count()
    notas = (
        db.query(NotaModel)
        .order_by(NotaModel.data_auditoria.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": [
            {
                "id": n.id,
                "numero": n.numero,
                "emissao": n.emissao,
                "natureza": n.natureza,
                "data_auditoria": n.data_auditoria.isoformat() if n.data_auditoria else None,
            }
            for n in notas
        ],
    }
