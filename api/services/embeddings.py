"""
ORGATEC — Serviço de Embeddings Semânticos
Provedor : Voyage AI — voyage-finance-2  (1024 dims)
           Parceiro oficial da Anthropic para embeddings.
           Treinado especificamente para documentos financeiros/fiscais.
Armazenamento : Supabase via REST API (sem conexão direta ao DB)

Configurar no .env:
    VOYAGE_API_KEY=pa-...
"""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "voyage-finance-2"
EMBEDDING_DIMS  = 1024


def _voyage_client():
    """Instância lazy do cliente Voyage AI."""
    try:
        import voyageai
        key = os.getenv("VOYAGE_API_KEY", "")
        if not key:
            raise RuntimeError(
                "VOYAGE_API_KEY não definida. "
                "Obtenha em https://dash.voyageai.com e adicione ao .env"
            )
        return voyageai.Client(api_key=key)
    except ImportError:
        raise RuntimeError(
            "Pacote 'voyageai' não instalado. "
            "Execute: pip install voyageai"
        )


def _supabase_client():
    """Instância lazy do cliente Supabase."""
    from supabase import create_client
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL ou SUPABASE_SERVICE_KEY não definidos")
    return create_client(url, key)


# ── Geração de embedding ──────────────────────────────────────────────────────

def gerar_embedding(texto: str) -> list[float]:
    """
    Gera embedding via Voyage AI voyage-finance-2.
    Retorna lista de 1024 floats.

    voyage-finance-2 é otimizado para:
    - Documentos fiscais e contábeis
    - Textos em português do Brasil
    - NF-e, SPED, eSocial, CT-e
    """
    texto = texto.strip()
    if not texto:
        raise ValueError("Texto vazio não pode ser embeddado.")

    client = _voyage_client()
    resultado = client.embed(
        texts=[texto],
        model=EMBEDDING_MODEL,
        input_type="document",   # "document" para indexação, "query" para busca
    )
    return resultado.embeddings[0]


def gerar_embedding_query(query: str) -> list[float]:
    """Embedding otimizado para queries de busca (input_type='query')."""
    query = query.strip()
    if not query:
        raise ValueError("Query vazia.")

    client = _voyage_client()
    resultado = client.embed(
        texts=[query],
        model=EMBEDDING_MODEL,
        input_type="query",
    )
    return resultado.embeddings[0]


def _montar_texto_nota(
    natureza: str | None,
    descricao_produtos: str | None,
    cliente_nome: str | None,
    numero: str | None,
) -> str:
    """Concatena campos relevantes da nota para gerar embedding representativo."""
    partes = []
    if natureza:
        partes.append(f"Natureza: {natureza}")
    if descricao_produtos:
        partes.append(f"Produtos: {descricao_produtos}")
    if cliente_nome:
        partes.append(f"Cliente: {cliente_nome}")
    if numero:
        partes.append(f"NF nº {numero}")
    return " | ".join(partes) or "Nota fiscal sem descrição"


# ── Persistência no Supabase ──────────────────────────────────────────────────

def salvar_embedding(
    nota_id: int,
    cliente_id: int | None,
    cliente_nome: str | None,
    natureza: str | None,
    emissao: str | None,
    numero: str | None,
    descricao_produtos: str | None,
) -> bool:
    """
    Gera e salva o embedding de uma nota na tabela notas_embeddings do Supabase.
    Usa upsert por nota_id — re-indexar é seguro.
    Retorna True em sucesso, False em falha (sem levantar exceção, não bloqueia auditoria).
    """
    try:
        texto = _montar_texto_nota(natureza, descricao_produtos, cliente_nome, numero)
        vetor = gerar_embedding(texto)

        sb = _supabase_client()
        sb.table("notas_embeddings").upsert(
            {
                "nota_id":      nota_id,
                "cliente_id":   cliente_id,
                "cliente_nome": cliente_nome,
                "natureza":     natureza,
                "emissao":      emissao,
                "numero":       numero,
                "descricao":    texto,
                "embedding":    vetor,
            },
            on_conflict="nota_id",
        ).execute()

        logger.info(f"Embedding salvo: nota_id={nota_id}")
        return True

    except Exception as exc:
        logger.warning(f"Falha ao salvar embedding nota_id={nota_id}: {exc}")
        return False


# ── Busca semântica ───────────────────────────────────────────────────────────

def buscar_notas_similares(
    query: str,
    match_threshold: float = 0.70,
    limit: int = 8,
) -> list[dict[str, Any]]:
    """
    Busca notas fiscais semanticamente similares à query.
    Usa input_type='query' para otimizar a busca (assimétrica: query × documento).
    """
    if not query.strip():
        return []

    vetor = gerar_embedding_query(query)

    sb = _supabase_client()
    resultado = sb.rpc(
        "match_notas",
        {
            "query_embedding": vetor,
            "match_threshold": match_threshold,
            "match_count":     limit,
        },
    ).execute()

    return resultado.data or []
