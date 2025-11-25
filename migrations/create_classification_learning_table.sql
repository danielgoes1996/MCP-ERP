-- Tabla para histórico de clasificaciones validadas
-- Permite al sistema aprender de correcciones humanas

CREATE TABLE IF NOT EXISTS classification_learning_history (
    id SERIAL PRIMARY KEY,

    -- Identificación de la factura
    company_id INTEGER NOT NULL,
    tenant_id INTEGER NOT NULL,
    session_id VARCHAR(100),

    -- Datos del proveedor y concepto
    rfc_emisor VARCHAR(13),
    nombre_emisor VARCHAR(500),
    concepto TEXT,
    total NUMERIC(15, 2),
    uso_cfdi VARCHAR(10),

    -- Embedding del par (emisor + concepto) - opcional para futuro
    -- embedding vector(384),  -- Deshabilitado hasta instalar pgvector

    -- Clasificación
    sat_account_code VARCHAR(20) NOT NULL,
    sat_account_name VARCHAR(500),
    family_code VARCHAR(10),

    -- Metadatos de la validación
    validation_type VARCHAR(20) NOT NULL, -- 'human', 'auto', 'corrected'
    validated_by VARCHAR(100),
    validated_at TIMESTAMP DEFAULT NOW(),

    -- Confianza original del LLM (si aplica)
    original_llm_prediction VARCHAR(20),
    original_llm_confidence NUMERIC(3, 2),

    -- Índices
    created_at TIMESTAMP DEFAULT NOW()
);

-- Índice para búsqueda rápida por emisor
CREATE INDEX IF NOT EXISTS idx_learning_emisor ON classification_learning_history (rfc_emisor, nombre_emisor);

-- Índice para búsqueda vectorial (cosine similarity) - deshabilitado hasta pgvector
-- CREATE INDEX IF NOT EXISTS idx_learning_embedding ON classification_learning_history
--     USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Índice para filtrar por company
CREATE INDEX IF NOT EXISTS idx_learning_company ON classification_learning_history (company_id, tenant_id);

-- Índice para búsqueda de texto completo en concepto
CREATE INDEX IF NOT EXISTS idx_learning_concepto ON classification_learning_history USING gin (to_tsvector('spanish', concepto));

COMMENT ON TABLE classification_learning_history IS 'Histórico de clasificaciones validadas para aprendizaje continuo del sistema';
-- COMMENT ON COLUMN classification_learning_history.embedding IS 'Vector semántico de emisor + concepto para búsqueda por similitud';
COMMENT ON COLUMN classification_learning_history.validation_type IS 'human=corregido por usuario, auto=validado automáticamente, corrected=LLM corregido';
