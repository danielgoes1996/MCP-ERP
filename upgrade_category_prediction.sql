-- =============================================================================
-- UPGRADE PARA PREDICCIÓN DE CATEGORÍAS (FUNCIONALIDAD #10)
-- Agrega tablas y campos faltantes para mejorar coherencia BD ↔ API ↔ UI
-- =============================================================================

BEGIN TRANSACTION;

-- 1. Agregar campos faltantes a expense_records
ALTER TABLE expense_records ADD COLUMN categoria_sugerida TEXT DEFAULT NULL;
ALTER TABLE expense_records ADD COLUMN confianza REAL DEFAULT NULL;
ALTER TABLE expense_records ADD COLUMN razonamiento TEXT DEFAULT NULL;
ALTER TABLE expense_records ADD COLUMN category_alternatives TEXT DEFAULT NULL; -- JSON
ALTER TABLE expense_records ADD COLUMN prediction_method TEXT DEFAULT NULL;
ALTER TABLE expense_records ADD COLUMN ml_model_version TEXT DEFAULT NULL;
ALTER TABLE expense_records ADD COLUMN predicted_at TIMESTAMP DEFAULT NULL;
ALTER TABLE expense_records ADD COLUMN category_confirmed BOOLEAN DEFAULT FALSE;
ALTER TABLE expense_records ADD COLUMN category_corrected_by INTEGER DEFAULT NULL;

-- 2. Crear tabla para historial de predicciones
CREATE TABLE IF NOT EXISTS category_prediction_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    expense_id INTEGER NOT NULL,
    predicted_category TEXT NOT NULL,
    confidence REAL NOT NULL,
    reasoning TEXT,
    alternatives TEXT, -- JSON array of alternatives
    prediction_method TEXT DEFAULT 'hybrid', -- llm, rules, hybrid
    ml_model_version TEXT DEFAULT '1.0',
    user_feedback TEXT DEFAULT NULL, -- accepted, corrected, rejected
    corrected_category TEXT DEFAULT NULL,
    feedback_date TIMESTAMP DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    tenant_id INTEGER NOT NULL,
    FOREIGN KEY (expense_id) REFERENCES expense_records(id),
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

-- 3. Crear tabla para preferencias de categorías por usuario
CREATE TABLE IF NOT EXISTS user_category_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    category_name TEXT NOT NULL,
    frequency INTEGER DEFAULT 1, -- Cuántas veces ha usado esta categoría
    last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    preference_score REAL DEFAULT 1.0, -- Score de preferencia (0.0 - 1.0)
    keywords TEXT, -- JSON array of keywords that trigger this category
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    tenant_id INTEGER NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

-- 4. Crear tabla para categorías personalizadas
CREATE TABLE IF NOT EXISTS custom_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    category_name TEXT NOT NULL,
    category_description TEXT,
    parent_category TEXT DEFAULT NULL, -- Para jerarquías de categorías
    color_hex TEXT DEFAULT '#6B7280', -- Color para UI
    icon_name TEXT DEFAULT 'folder', -- Icono para UI
    keywords TEXT, -- JSON array of detection keywords
    merchant_patterns TEXT, -- JSON array of merchant patterns
    amount_ranges TEXT, -- JSON array of typical amount ranges
    tax_deductible BOOLEAN DEFAULT TRUE,
    requires_receipt BOOLEAN DEFAULT TRUE,
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_by INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id),
    FOREIGN KEY (created_by) REFERENCES users(id)
);

-- 5. Crear tabla para configuración de predicción de categorías
CREATE TABLE IF NOT EXISTS category_prediction_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    auto_apply_high_confidence BOOLEAN DEFAULT TRUE, -- Auto-aplicar si confianza > threshold
    high_confidence_threshold REAL DEFAULT 0.85,
    medium_confidence_threshold REAL DEFAULT 0.65,
    use_llm BOOLEAN DEFAULT TRUE,
    llm_model TEXT DEFAULT 'gpt-3.5-turbo',
    use_user_history BOOLEAN DEFAULT TRUE,
    history_weight REAL DEFAULT 0.3, -- Peso del historial en la predicción
    categories_config TEXT, -- JSON config for categories
    features_weights TEXT, -- JSON weights for different features
    fallback_category TEXT DEFAULT 'oficina',
    require_manual_review BOOLEAN DEFAULT FALSE, -- Require manual review for low confidence
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

-- 6. Crear tabla para métricas de aprendizaje
CREATE TABLE IF NOT EXISTS category_learning_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    user_id INTEGER DEFAULT NULL,
    category_name TEXT NOT NULL,
    total_predictions INTEGER DEFAULT 0,
    correct_predictions INTEGER DEFAULT 0,
    accuracy_rate REAL DEFAULT 0.0,
    avg_confidence REAL DEFAULT 0.0,
    most_common_keywords TEXT, -- JSON array
    most_common_merchants TEXT, -- JSON array
    typical_amount_range TEXT, -- e.g., "100-500"
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 7. Crear índices para performance
CREATE INDEX IF NOT EXISTS idx_category_prediction_expense ON category_prediction_history(expense_id);
CREATE INDEX IF NOT EXISTS idx_category_prediction_tenant ON category_prediction_history(tenant_id);
CREATE INDEX IF NOT EXISTS idx_category_prediction_category ON category_prediction_history(predicted_category);
CREATE INDEX IF NOT EXISTS idx_category_prediction_feedback ON category_prediction_history(user_feedback);
CREATE INDEX IF NOT EXISTS idx_category_prediction_method ON category_prediction_history(prediction_method);
CREATE INDEX IF NOT EXISTS idx_category_prediction_confidence ON category_prediction_history(confidence DESC);

CREATE INDEX IF NOT EXISTS idx_user_preferences_user ON user_category_preferences(user_id);
CREATE INDEX IF NOT EXISTS idx_user_preferences_tenant ON user_category_preferences(tenant_id);
CREATE INDEX IF NOT EXISTS idx_user_preferences_category ON user_category_preferences(category_name);
CREATE INDEX IF NOT EXISTS idx_user_preferences_frequency ON user_category_preferences(frequency DESC);
CREATE INDEX IF NOT EXISTS idx_user_preferences_active ON user_category_preferences(active);

CREATE INDEX IF NOT EXISTS idx_custom_categories_tenant ON custom_categories(tenant_id);
CREATE INDEX IF NOT EXISTS idx_custom_categories_name ON custom_categories(category_name);
CREATE INDEX IF NOT EXISTS idx_custom_categories_active ON custom_categories(is_active);
CREATE INDEX IF NOT EXISTS idx_custom_categories_sort ON custom_categories(sort_order);

CREATE INDEX IF NOT EXISTS idx_category_config_tenant ON category_prediction_config(tenant_id);

CREATE INDEX IF NOT EXISTS idx_learning_metrics_tenant ON category_learning_metrics(tenant_id);
CREATE INDEX IF NOT EXISTS idx_learning_metrics_user ON category_learning_metrics(user_id);
CREATE INDEX IF NOT EXISTS idx_learning_metrics_category ON category_learning_metrics(category_name);

-- Índices adicionales en expense_records para predicción
CREATE INDEX IF NOT EXISTS idx_expense_categoria_sugerida ON expense_records(categoria_sugerida);
CREATE INDEX IF NOT EXISTS idx_expense_confianza ON expense_records(confianza DESC);
CREATE INDEX IF NOT EXISTS idx_expense_prediction_method ON expense_records(prediction_method);
CREATE INDEX IF NOT EXISTS idx_expense_category_confirmed ON expense_records(category_confirmed);
CREATE INDEX IF NOT EXISTS idx_expense_predicted_at ON expense_records(predicted_at DESC);

-- 8. Triggers para actualizar updated_at
CREATE TRIGGER IF NOT EXISTS user_preferences_updated_at
    AFTER UPDATE ON user_category_preferences
    FOR EACH ROW
    WHEN NEW.updated_at = OLD.updated_at OR NEW.updated_at IS NULL
BEGIN
    UPDATE user_category_preferences
    SET updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS custom_categories_updated_at
    AFTER UPDATE ON custom_categories
    FOR EACH ROW
    WHEN NEW.updated_at = OLD.updated_at OR NEW.updated_at IS NULL
BEGIN
    UPDATE custom_categories
    SET updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS category_config_updated_at
    AFTER UPDATE ON category_prediction_config
    FOR EACH ROW
    WHEN NEW.updated_at = OLD.updated_at OR NEW.updated_at IS NULL
BEGIN
    UPDATE category_prediction_config
    SET updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.id;
END;

-- 9. Insertar configuración default para tenant 1
INSERT OR IGNORE INTO category_prediction_config (tenant_id)
VALUES (1);

-- 10. Insertar categorías por defecto
INSERT OR IGNORE INTO custom_categories (
    tenant_id, category_name, category_description, keywords, merchant_patterns,
    color_hex, icon_name, created_by, sort_order
) VALUES
(1, 'combustible', 'Gastos de combustible y lubricantes',
 '["gasolina", "combustible", "pemex", "shell", "bp", "diesel"]',
 '["pemex", "shell", "bp", "total", "gas"]',
 '#EF4444', 'fuel', 1, 1),

(1, 'alimentos', 'Gastos en alimentos y bebidas',
 '["restaurante", "comida", "almuerzo", "desayuno", "café", "lunch"]',
 '["mcdonalds", "subway", "starbucks", "dominos"]',
 '#F59E0B', 'utensils', 1, 2),

(1, 'transporte', 'Gastos de transporte y viajes',
 '["uber", "taxi", "transporte", "viaje", "avion", "autobus"]',
 '["uber", "cabify", "aeromexico", "volaris", "ado"]',
 '#3B82F6', 'car', 1, 3),

(1, 'hospedaje', 'Gastos de hospedaje en viajes',
 '["hotel", "hospedaje", "alojamiento", "booking"]',
 '["marriott", "hilton", "city express", "booking", "airbnb"]',
 '#8B5CF6', 'bed', 1, 4),

(1, 'oficina', 'Suministros y materiales de oficina',
 '["papeleria", "oficina", "suministros", "materiales", "papel"]',
 '["office depot", "walmart", "costco", "staples"]',
 '#6B7280', 'briefcase', 1, 5),

(1, 'tecnologia', 'Software, licencias y servicios tecnológicos',
 '["software", "licencia", "microsoft", "adobe", "google"]',
 '["microsoft", "adobe", "google", "zoom", "slack", "aws"]',
 '#10B981', 'laptop', 1, 6),

(1, 'servicios', 'Servicios básicos y comunicaciones',
 '["internet", "telefono", "luz", "agua", "electricidad"]',
 '["telmex", "telcel", "cfe", "izzi", "totalplay"]',
 '#F97316', 'phone', 1, 7),

(1, 'marketing', 'Gastos de marketing y publicidad',
 '["publicidad", "marketing", "promocion", "facebook", "google ads"]',
 '["facebook", "google", "instagram", "linkedin"]',
 '#EC4899', 'megaphone', 1, 8);

-- 11. Foreign key constraints adicionales
CREATE INDEX IF NOT EXISTS idx_expense_category_corrected_by ON expense_records(category_corrected_by);

COMMIT;

-- =============================================================================
-- VERIFICACIÓN DE UPGRADE
-- =============================================================================
-- Verificar que las tablas se crearon correctamente
.print "✅ Verificando tablas creadas:"
.print "📈 category_prediction_history:"
SELECT COUNT(*) as count FROM category_prediction_history;
.print "👤 user_category_preferences:"
SELECT COUNT(*) as count FROM user_category_preferences;
.print "📂 custom_categories:"
SELECT COUNT(*) as count FROM custom_categories;
.print "⚙️ category_prediction_config:"
SELECT COUNT(*) as count FROM category_prediction_config;
.print "🧠 category_learning_metrics:"
SELECT COUNT(*) as count FROM category_learning_metrics;

-- Verificar campos agregados a expense_records
.print "✅ Verificando campos agregados a expense_records:"
PRAGMA table_info(expense_records);

.print "🎉 Upgrade de predicción de categorías completado exitosamente!"