-- UPGRADE BANK RECONCILIATION SCHEMA
-- Mejora la conciliación bancaria completando coherencia API ↔ BD
-- Funcionalidad #7: Conciliación Bancaria

-- 1. Agregar campos faltantes a bank_movements
ALTER TABLE bank_movements ADD COLUMN decision TEXT;
ALTER TABLE bank_movements ADD COLUMN bank_metadata TEXT; -- JSON con datos bancarios
ALTER TABLE bank_movements ADD COLUMN confidence REAL DEFAULT 0.0;
ALTER TABLE bank_movements ADD COLUMN movement_id TEXT; -- ID único del banco
ALTER TABLE bank_movements ADD COLUMN transaction_type TEXT; -- debit, credit, transfer
ALTER TABLE bank_movements ADD COLUMN reference TEXT; -- Referencia bancaria
ALTER TABLE bank_movements ADD COLUMN balance_after REAL; -- Balance después del movimiento
ALTER TABLE bank_movements ADD COLUMN raw_data TEXT; -- Datos raw del banco
ALTER TABLE bank_movements ADD COLUMN processing_status TEXT DEFAULT 'pending';
ALTER TABLE bank_movements ADD COLUMN matched_at TIMESTAMP;
ALTER TABLE bank_movements ADD COLUMN matched_by INTEGER;
ALTER TABLE bank_movements ADD COLUMN auto_matched BOOLEAN DEFAULT FALSE;
ALTER TABLE bank_movements ADD COLUMN reconciliation_notes TEXT;
ALTER TABLE bank_movements ADD COLUMN bank_account_id TEXT;
ALTER TABLE bank_movements ADD COLUMN category TEXT;

-- 2. Crear tabla para feedback de matching
CREATE TABLE IF NOT EXISTS bank_reconciliation_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    movement_id INTEGER NOT NULL,
    expense_id INTEGER,
    feedback_type TEXT NOT NULL, -- 'accepted', 'rejected', 'manual_review'
    confidence REAL DEFAULT 0.0,
    match_criteria TEXT, -- JSON con criterios usados
    user_decision TEXT,
    feedback_notes TEXT,
    created_by INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    tenant_id INTEGER NOT NULL,
    FOREIGN KEY (movement_id) REFERENCES bank_movements(id) ON DELETE CASCADE,
    FOREIGN KEY (expense_id) REFERENCES expense_records(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES users(id),
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

-- 3. Crear tabla para reglas de matching automático
CREATE TABLE IF NOT EXISTS bank_matching_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_name TEXT NOT NULL,
    rule_type TEXT NOT NULL, -- 'amount', 'description', 'date', 'reference'
    pattern TEXT, -- Regex o patrón de matching
    confidence_weight REAL DEFAULT 1.0,
    priority INTEGER DEFAULT 100,
    active BOOLEAN DEFAULT TRUE,
    tenant_id INTEGER NOT NULL,
    created_by INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id),
    FOREIGN KEY (created_by) REFERENCES users(id)
);

-- 4. Crear tabla para configuración ML
CREATE TABLE IF NOT EXISTS bank_ml_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_type TEXT NOT NULL, -- 'matching_threshold', 'features', 'model_params'
    config_data TEXT NOT NULL, -- JSON con configuración
    version TEXT DEFAULT '1.0',
    active BOOLEAN DEFAULT TRUE,
    tenant_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

-- 5. Crear índices para performance
CREATE INDEX IF NOT EXISTS idx_bank_movements_decision ON bank_movements(decision);
CREATE INDEX IF NOT EXISTS idx_bank_movements_confidence ON bank_movements(confidence);
CREATE INDEX IF NOT EXISTS idx_bank_movements_movement_id ON bank_movements(movement_id);
CREATE INDEX IF NOT EXISTS idx_bank_movements_type ON bank_movements(transaction_type);
CREATE INDEX IF NOT EXISTS idx_bank_movements_status ON bank_movements(processing_status);
CREATE INDEX IF NOT EXISTS idx_bank_movements_account ON bank_movements(bank_account_id);
CREATE INDEX IF NOT EXISTS idx_bank_movements_date ON bank_movements(date DESC);
CREATE INDEX IF NOT EXISTS idx_bank_movements_amount ON bank_movements(amount);
CREATE INDEX IF NOT EXISTS idx_bank_movements_matched ON bank_movements(matched_expense_id);
CREATE INDEX IF NOT EXISTS idx_bank_movements_tenant_status ON bank_movements(tenant_id, processing_status);

-- Índices para feedback
CREATE INDEX IF NOT EXISTS idx_feedback_movement ON bank_reconciliation_feedback(movement_id);
CREATE INDEX IF NOT EXISTS idx_feedback_expense ON bank_reconciliation_feedback(expense_id);
CREATE INDEX IF NOT EXISTS idx_feedback_tenant ON bank_reconciliation_feedback(tenant_id);
CREATE INDEX IF NOT EXISTS idx_feedback_type ON bank_reconciliation_feedback(feedback_type);
CREATE INDEX IF NOT EXISTS idx_feedback_date ON bank_reconciliation_feedback(created_at DESC);

-- Índices para reglas
CREATE INDEX IF NOT EXISTS idx_rules_tenant ON bank_matching_rules(tenant_id, active);
CREATE INDEX IF NOT EXISTS idx_rules_type ON bank_matching_rules(rule_type);
CREATE INDEX IF NOT EXISTS idx_rules_priority ON bank_matching_rules(priority);

-- 6. Insertar reglas de matching por defecto
INSERT OR IGNORE INTO bank_matching_rules (rule_name, rule_type, pattern, confidence_weight, priority, tenant_id, created_by)
VALUES
('Exact Amount Match', 'amount', 'exact', 2.0, 10, 1, 1),
('Similar Amount (±1%)', 'amount', 'similar_1pct', 1.8, 20, 1, 1),
('Similar Amount (±5%)', 'amount', 'similar_5pct', 1.5, 30, 1, 1),
('Description Keywords', 'description', 'keywords', 1.2, 40, 1, 1),
('Same Day', 'date', 'same_day', 1.5, 25, 1, 1),
('Same Week', 'date', 'same_week', 1.0, 50, 1, 1),
('Reference Match', 'reference', 'contains', 2.5, 5, 1, 1);

-- 7. Insertar configuración ML por defecto
INSERT OR IGNORE INTO bank_ml_config (config_type, config_data, tenant_id)
VALUES
('matching_threshold', '{"auto_match": 0.85, "suggest": 0.65, "manual": 0.4}', 1),
('features', '{"amount_weight": 0.3, "date_weight": 0.2, "description_weight": 0.25, "reference_weight": 0.25}', 1),
('model_params', '{"algorithm": "weighted_similarity", "normalize": true, "fuzzy_match": true}', 1);

-- 8. Actualizar registros existentes
UPDATE bank_movements SET
    processing_status = 'processed',
    confidence = 1.0,
    decision = CASE
        WHEN matched_expense_id IS NOT NULL THEN 'accepted'
        ELSE 'pending'
    END,
    auto_matched = FALSE
WHERE processing_status IS NULL;

-- 9. Vista para conciliación enriquecida
CREATE VIEW IF NOT EXISTS bank_reconciliation_view AS
SELECT
    bm.*,
    e.description as expense_description,
    e.amount as expense_amount,
    e.category as expense_category,
    e.merchant_name,
    u.name as user_name,
    u.email as user_email,
    ABS(COALESCE(bm.amount, 0) - COALESCE(e.amount, 0)) as amount_difference,
    CASE
        WHEN bm.amount IS NOT NULL AND e.amount IS NOT NULL THEN
            CASE
                WHEN ABS(bm.amount - e.amount) < 0.01 THEN 'exact'
                WHEN ABS(bm.amount - e.amount) < bm.amount * 0.05 THEN 'close'
                ELSE 'different'
            END
        ELSE 'unknown'
    END as amount_match_quality,
    CASE
        WHEN bm.matched_expense_id IS NOT NULL THEN 'matched'
        WHEN bm.decision = 'rejected' THEN 'rejected'
        WHEN bm.confidence >= 0.85 THEN 'high_confidence'
        WHEN bm.confidence >= 0.65 THEN 'medium_confidence'
        ELSE 'low_confidence'
    END as reconciliation_status
FROM bank_movements bm
LEFT JOIN expense_records e ON bm.matched_expense_id = e.id
LEFT JOIN users u ON e.user_id = u.id;

-- 10. Trigger para actualizar matched_at automáticamente
CREATE TRIGGER IF NOT EXISTS bank_movements_matched_at
    AFTER UPDATE ON bank_movements
    FOR EACH ROW
    WHEN NEW.matched_expense_id != OLD.matched_expense_id AND NEW.matched_expense_id IS NOT NULL
BEGIN
    UPDATE bank_movements
    SET matched_at = CURRENT_TIMESTAMP
    WHERE id = NEW.id;
END;

-- 11. Actualizar metadatos de schema
INSERT OR IGNORE INTO schema_versions (version, description)
VALUES ('2.2.0', 'Enhanced Bank Reconciliation - Complete API-BD Coherence + ML Engine');

PRAGMA foreign_keys = ON;