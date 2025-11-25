-- =============================================================================
-- UPGRADE PARA DETECCIÓN DE DUPLICADOS (FUNCIONALIDAD #9)
-- Agrega campos y tablas faltantes para mejorar coherencia BD ↔ API ↔ UI
-- =============================================================================

BEGIN TRANSACTION;

-- 1. Agregar campos faltantes a expense_records
ALTER TABLE expense_records ADD COLUMN similarity_score REAL DEFAULT NULL;
ALTER TABLE expense_records ADD COLUMN risk_level TEXT DEFAULT NULL;
ALTER TABLE expense_records ADD COLUMN is_duplicate BOOLEAN DEFAULT FALSE;
ALTER TABLE expense_records ADD COLUMN duplicate_of INTEGER DEFAULT NULL;
ALTER TABLE expense_records ADD COLUMN duplicate_confidence REAL DEFAULT NULL;
ALTER TABLE expense_records ADD COLUMN ml_features_json TEXT DEFAULT NULL;

-- 2. Crear tabla para detecciones de duplicados persistentes
CREATE TABLE IF NOT EXISTS duplicate_detections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    expense_id INTEGER NOT NULL,
    potential_duplicate_id INTEGER NOT NULL,
    similarity_score REAL NOT NULL,
    risk_level TEXT NOT NULL,
    confidence_level TEXT NOT NULL,
    match_reasons TEXT, -- JSON array of reasons
    detection_method TEXT DEFAULT 'hybrid',
    ml_features_json TEXT, -- JSON ML features
    status TEXT DEFAULT 'pending', -- pending, confirmed, rejected
    reviewed_by INTEGER DEFAULT NULL,
    reviewed_at TIMESTAMP DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    tenant_id INTEGER NOT NULL,
    FOREIGN KEY (expense_id) REFERENCES expense_records(id),
    FOREIGN KEY (potential_duplicate_id) REFERENCES expense_records(id),
    FOREIGN KEY (reviewed_by) REFERENCES users(id),
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

-- 3. Crear tabla para configuración de detección de duplicados
CREATE TABLE IF NOT EXISTS duplicate_detection_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    similarity_threshold_high REAL DEFAULT 0.85,
    similarity_threshold_medium REAL DEFAULT 0.70,
    similarity_threshold_low REAL DEFAULT 0.55,
    time_window_days INTEGER DEFAULT 30,
    auto_block_high_risk BOOLEAN DEFAULT TRUE,
    auto_review_medium_risk BOOLEAN DEFAULT TRUE,
    enabled_methods TEXT DEFAULT 'hybrid', -- comma separated: ml,heuristic,hybrid
    weights_description REAL DEFAULT 0.4,
    weights_amount REAL DEFAULT 0.3,
    weights_provider REAL DEFAULT 0.2,
    weights_date REAL DEFAULT 0.1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

-- 4. Crear tabla para métricas ML (features)
CREATE TABLE IF NOT EXISTS expense_ml_features (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    expense_id INTEGER NOT NULL,
    feature_vector TEXT NOT NULL, -- JSON vector of ML features
    embedding_vector TEXT DEFAULT NULL, -- JSON OpenAI embeddings
    extraction_method TEXT DEFAULT 'rule_based',
    feature_quality_score REAL DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    tenant_id INTEGER NOT NULL,
    FOREIGN KEY (expense_id) REFERENCES expense_records(id),
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

-- 5. Crear índices para performance
CREATE INDEX IF NOT EXISTS idx_duplicate_detections_expense ON duplicate_detections(expense_id);
CREATE INDEX IF NOT EXISTS idx_duplicate_detections_potential ON duplicate_detections(potential_duplicate_id);
CREATE INDEX IF NOT EXISTS idx_duplicate_detections_tenant ON duplicate_detections(tenant_id);
CREATE INDEX IF NOT EXISTS idx_duplicate_detections_status ON duplicate_detections(status);
CREATE INDEX IF NOT EXISTS idx_duplicate_detections_risk ON duplicate_detections(risk_level);
CREATE INDEX IF NOT EXISTS idx_duplicate_detections_score ON duplicate_detections(similarity_score DESC);

CREATE INDEX IF NOT EXISTS idx_duplicate_config_tenant ON duplicate_detection_config(tenant_id);

CREATE INDEX IF NOT EXISTS idx_ml_features_expense ON expense_ml_features(expense_id);
CREATE INDEX IF NOT EXISTS idx_ml_features_tenant ON expense_ml_features(tenant_id);

-- Índices adicionales en expense_records para detección
CREATE INDEX IF NOT EXISTS idx_expense_similarity_score ON expense_records(similarity_score DESC);
CREATE INDEX IF NOT EXISTS idx_expense_risk_level ON expense_records(risk_level);
CREATE INDEX IF NOT EXISTS idx_expense_is_duplicate ON expense_records(is_duplicate);
CREATE INDEX IF NOT EXISTS idx_expense_duplicate_of ON expense_records(duplicate_of);

-- 6. Trigger para actualizar updated_at en configuración
CREATE TRIGGER IF NOT EXISTS duplicate_config_updated_at
    AFTER UPDATE ON duplicate_detection_config
    FOR EACH ROW
    WHEN NEW.updated_at = OLD.updated_at OR NEW.updated_at IS NULL
BEGIN
    UPDATE duplicate_detection_config
    SET updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.id;
END;

-- 7. Trigger para actualizar updated_at en ML features
CREATE TRIGGER IF NOT EXISTS ml_features_updated_at
    AFTER UPDATE ON expense_ml_features
    FOR EACH ROW
    WHEN NEW.updated_at = OLD.updated_at OR NEW.updated_at IS NULL
BEGIN
    UPDATE expense_ml_features
    SET updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.id;
END;

-- 8. Configuración default para tenant 1
INSERT OR IGNORE INTO duplicate_detection_config (tenant_id)
VALUES (1);

-- 9. Foreign key constraint para duplicate_of
CREATE INDEX IF NOT EXISTS idx_expense_duplicate_ref ON expense_records(duplicate_of);

COMMIT;

-- =============================================================================
-- VERIFICACIÓN DE UPGRADE
-- =============================================================================
-- Verificar que las tablas se crearon correctamente
.print "✅ Verificando tablas creadas:"
.print "📊 duplicate_detections:"
SELECT COUNT(*) as count FROM duplicate_detections;
.print "⚙️ duplicate_detection_config:"
SELECT COUNT(*) as count FROM duplicate_detection_config;
.print "🤖 expense_ml_features:"
SELECT COUNT(*) as count FROM expense_ml_features;

-- Verificar campos agregados a expense_records
.print "✅ Verificando campos agregados a expense_records:"
PRAGMA table_info(expense_records);

.print "🎉 Upgrade de detección de duplicados completado exitosamente!"