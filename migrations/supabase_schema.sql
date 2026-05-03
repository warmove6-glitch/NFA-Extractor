-- ============================================================
-- NFA Extractor — Schema Migration for Supabase PostgreSQL
-- Execute no Supabase Dashboard: SQL Editor → New Query
-- ============================================================

-- Extensão para UUIDs (opcional, futuro)
-- CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── Tabela: audit_tasks ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_tasks (
    task_id     VARCHAR(64) PRIMARY KEY,
    status      VARCHAR(50) NOT NULL DEFAULT 'iniciado',
    progress    INTEGER     NOT NULL DEFAULT 0,
    payload_json TEXT       NOT NULL DEFAULT '{}',
    created_at  TIMESTAMP   NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMP   DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_audit_tasks_updated_at ON audit_tasks (updated_at);

-- ── Tabela: users ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id              SERIAL PRIMARY KEY,
    nome            VARCHAR(255) NOT NULL,
    email           VARCHAR(255) NOT NULL UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    role            VARCHAR(50)  DEFAULT 'user',
    is_active       BOOLEAN      DEFAULT TRUE,
    created_at      TIMESTAMP    DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_users_id    ON users (id);
CREATE INDEX IF NOT EXISTS ix_users_email ON users (email);

-- ── Tabela: clientes ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS clientes (
    id           SERIAL PRIMARY KEY,
    nome         VARCHAR(255) NOT NULL,
    cpf_cnpj     VARCHAR(20)  NOT NULL UNIQUE,
    data_cadastro TIMESTAMP   DEFAULT NOW()
);

-- ── Tabela: notas ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS notas (
    id            SERIAL PRIMARY KEY,
    chave_acesso  VARCHAR(44)  NOT NULL UNIQUE,
    numero        VARCHAR,
    emissao       VARCHAR,
    natureza      VARCHAR,
    laudo_ia      TEXT,
    data_auditoria TIMESTAMP   DEFAULT NOW(),
    CONSTRAINT uq_nota_numero_emissao UNIQUE (numero, emissao)
);
CREATE INDEX IF NOT EXISTS ix_notas_id           ON notas (id);
CREATE INDEX IF NOT EXISTS ix_notas_chave_acesso ON notas (chave_acesso);
CREATE INDEX IF NOT EXISTS ix_notas_numero       ON notas (numero);

-- ── Tabela: laudos ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS laudos (
    id             SERIAL PRIMARY KEY,
    cliente_id     INTEGER NOT NULL REFERENCES clientes (id),
    data_auditoria TIMESTAMP DEFAULT NOW(),
    veredito_ia    TEXT,
    qtd_notas      INTEGER,
    valor_total    FLOAT,
    qtd_anomalias  INTEGER,
    pdf_path       VARCHAR(500)
);

-- ── Tabela: produtos ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS produtos (
    id          SERIAL PRIMARY KEY,
    nota_id     INTEGER REFERENCES notas (id) ON DELETE CASCADE,
    codigo      VARCHAR,
    descricao   VARCHAR,
    quantidade  FLOAT,
    vlr_total   FLOAT
);
CREATE INDEX IF NOT EXISTS ix_produtos_id ON produtos (id);

-- ============================================================
-- Verificação: lista tabelas criadas
-- ============================================================
SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;
