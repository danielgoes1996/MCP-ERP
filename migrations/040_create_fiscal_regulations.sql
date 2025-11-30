-- Migration: Create fiscal_regulations table for RAG-based depreciation rates
-- Author: System
-- Date: 2025-11-28
-- Description: Stores Mexican fiscal law articles (LISR, CFF, RLISR) with embeddings
--              for semantic search of depreciation rates and tax regulations

-- Enable pgvector extension if not already enabled
CREATE EXTENSION IF NOT EXISTS vector;

-- Main table for fiscal regulations
CREATE TABLE IF NOT EXISTS fiscal_regulations (
    id SERIAL PRIMARY KEY,

    -- Legal identification
    law_code VARCHAR(50) NOT NULL,              -- "LISR", "CFF", "RLISR", "LIVA"
    article_number VARCHAR(50) NOT NULL,        -- "34", "34-V", "36"
    section VARCHAR(100),                       -- "Fracción V", "Inciso a)", "Párrafo 2"
    title TEXT NOT NULL,                        -- "Tasas de depreciación de activos fijos"

    -- Content
    content TEXT NOT NULL,                      -- Full article text
    content_normalized TEXT NOT NULL,           -- Lowercase, no accents, for search

    -- Embeddings for semantic search (using sentence-transformers paraphrase-multilingual-MiniLM-L12-v2: 384 dimensions)
    content_embedding vector(384),

    -- Metadata for filtering
    regulation_type VARCHAR(50) NOT NULL,       -- "depreciation", "deductions", "tax_rates", "vat", "retention"
    asset_categories TEXT[],                    -- {"equipo_computo", "vehiculos", "mobiliario"}
    keywords TEXT[],                            -- {"depreciación", "tasa", "porciento", "laptop"}

    -- Structured data extracted from article (for quick access without LLM)
    structured_data JSONB,                      -- Rates, rules, examples parsed

    -- Legal metadata
    effective_date DATE NOT NULL,               -- When this regulation became effective
    superseded_date DATE,                       -- If replaced by another regulation
    status VARCHAR(20) DEFAULT 'active',        -- "active", "superseded", "repealed"

    -- Source and audit
    source_url TEXT,                            -- Official URL (DOF, diputados.gob.mx)
    dof_publication_date DATE,                  -- Diario Oficial de la Federación date
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Ensure uniqueness per law/article/date
    UNIQUE(law_code, article_number, effective_date)
);

-- Indices for performance

-- Vector similarity search (IVFFlat index for approximate nearest neighbor)
CREATE INDEX IF NOT EXISTS idx_fiscal_regulations_embedding
ON fiscal_regulations
USING ivfflat (content_embedding vector_cosine_ops)
WITH (lists = 100);

-- Traditional indices
CREATE INDEX IF NOT EXISTS idx_fiscal_regulations_type
ON fiscal_regulations(regulation_type);

CREATE INDEX IF NOT EXISTS idx_fiscal_regulations_status
ON fiscal_regulations(status);

CREATE INDEX IF NOT EXISTS idx_fiscal_regulations_law_article
ON fiscal_regulations(law_code, article_number);

CREATE INDEX IF NOT EXISTS idx_fiscal_regulations_categories
ON fiscal_regulations USING GIN(asset_categories);

CREATE INDEX IF NOT EXISTS idx_fiscal_regulations_keywords
ON fiscal_regulations USING GIN(keywords);

CREATE INDEX IF NOT EXISTS idx_fiscal_regulations_effective_date
ON fiscal_regulations(effective_date DESC);

-- Full-text search index on content
CREATE INDEX IF NOT EXISTS idx_fiscal_regulations_content_search
ON fiscal_regulations USING GIN(to_tsvector('spanish', content));

-- Comments for documentation
COMMENT ON TABLE fiscal_regulations IS 'Stores Mexican fiscal law articles with vector embeddings for RAG-based retrieval of depreciation rates and tax regulations';
COMMENT ON COLUMN fiscal_regulations.content_embedding IS 'Vector embedding (384d) using sentence-transformers paraphrase-multilingual-MiniLM-L12-v2';
COMMENT ON COLUMN fiscal_regulations.structured_data IS 'JSONB with parsed rates, e.g., {"depreciation_rate_annual": 30.0, "depreciation_years": 3.33, "asset_type": "equipo_computo"}';
COMMENT ON COLUMN fiscal_regulations.regulation_type IS 'Category: depreciation, deductions, tax_rates, vat, retention';
COMMENT ON COLUMN fiscal_regulations.status IS 'active = currently in force, superseded = replaced, repealed = no longer valid';

-- Trigger to update updated_at
CREATE OR REPLACE FUNCTION update_fiscal_regulations_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER fiscal_regulations_updated_at
    BEFORE UPDATE ON fiscal_regulations
    FOR EACH ROW
    EXECUTE FUNCTION update_fiscal_regulations_updated_at();
