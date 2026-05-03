-- ============================================================
-- ORGATEC — pgvector no Supabase
-- Provedor de embeddings: Voyage AI (voyage-finance-2, 1024 dims)
-- Rodar no SQL Editor: https://supabase.com/dashboard/project/ufwvdibacfxfpgududqi/sql
-- ============================================================

-- 1. Extensão pgvector (disponível por padrão no Supabase)
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Tabela de embeddings (independente do schema local Docker)
--    nota_id   → referencia a nota no Postgres local (sem FK para não acoplar)
--    embedding → vetor de 1024 dims (voyage-finance-2)
CREATE TABLE IF NOT EXISTS notas_embeddings (
    id           bigserial PRIMARY KEY,
    nota_id      integer NOT NULL,
    cliente_id   integer,
    cliente_nome text,
    natureza     text,
    emissao      text,
    numero       text,
    descricao    text,
    embedding    vector(1024),
    created_at   timestamptz DEFAULT now(),
    UNIQUE (nota_id)
);

-- 3. Índice IVFFlat para busca de cosseno eficiente
CREATE INDEX IF NOT EXISTS notas_embeddings_cosine_idx
    ON notas_embeddings
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- 4. Função RPC — busca por similaridade semântica
CREATE OR REPLACE FUNCTION match_notas(
    query_embedding vector(1024),
    match_threshold float  DEFAULT 0.70,
    match_count     int    DEFAULT 8
)
RETURNS TABLE (
    nota_id      integer,
    cliente_id   integer,
    cliente_nome text,
    natureza     text,
    emissao      text,
    numero       text,
    descricao    text,
    similarity   float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        ne.nota_id,
        ne.cliente_id,
        ne.cliente_nome,
        ne.natureza,
        ne.emissao,
        ne.numero,
        ne.descricao,
        (1 - (ne.embedding <=> query_embedding))::float AS similarity
    FROM notas_embeddings ne
    WHERE ne.embedding IS NOT NULL
      AND 1 - (ne.embedding <=> query_embedding) > match_threshold
    ORDER BY ne.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- 5. RLS
ALTER TABLE notas_embeddings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service pode tudo"
    ON notas_embeddings FOR ALL
    TO service_role
    USING (true) WITH CHECK (true);

CREATE POLICY "leitura autenticada"
    ON notas_embeddings FOR SELECT
    TO authenticated
    USING (true);
