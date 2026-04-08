-- Enable pgvector extension for semantic search
CREATE EXTENSION IF NOT EXISTS vector;

-- Product embeddings table: stores vector embeddings for each product (anaart)
CREATE TABLE IF NOT EXISTS product_embeddings (
    cod_art VARCHAR(20) PRIMARY KEY REFERENCES anaart(cod_art) ON DELETE CASCADE,
    embedding vector(1536) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for fast cosine similarity search using IVFFlat
CREATE INDEX IF NOT EXISTS idx_product_embeddings_cosine
    ON product_embeddings USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
