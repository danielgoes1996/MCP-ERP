-- Migración 019: Crear tabla de estados de cuenta bancarios
-- Fecha: 2025-09-27
-- Descripción: Tabla para trackear archivos de estados de cuenta subidos

-- =====================================================
-- PASO 1: CREAR TABLA DE ESTADOS DE CUENTA
-- =====================================================

CREATE TABLE IF NOT EXISTS bank_statements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    tenant_id INTEGER NOT NULL,
    file_name TEXT NOT NULL,
    file_path TEXT,
    file_size INTEGER,
    file_type TEXT NOT NULL, -- 'pdf', 'excel', 'csv'
    period_start DATE,
    period_end DATE,
    opening_balance REAL DEFAULT 0.0,
    closing_balance REAL DEFAULT 0.0,
    total_credits REAL DEFAULT 0.0,
    total_debits REAL DEFAULT 0.0,
    transaction_count INTEGER DEFAULT 0,
    parsing_status TEXT NOT NULL DEFAULT 'pending', -- 'pending', 'processing', 'completed', 'failed'
    parsing_error TEXT,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    parsed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (account_id) REFERENCES user_payment_accounts(id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (tenant_id) REFERENCES tenants(id),

    CHECK (parsing_status IN ('pending', 'processing', 'completed', 'failed')),
    CHECK (file_type IN ('pdf', 'excel', 'csv', 'xlsx', 'xls'))
);

-- =====================================================
-- PASO 2: AÑADIR CAMPO STATEMENT_ID A BANK_MOVEMENTS
-- =====================================================

-- Agregar referencia al statement en bank_movements
ALTER TABLE bank_movements ADD COLUMN statement_id INTEGER;

-- Crear foreign key constraint (nota: SQLite no soporta ADD CONSTRAINT, recreamos en el futuro si necesario)

-- =====================================================
-- PASO 3: CREAR ÍNDICES PARA PERFORMANCE
-- =====================================================

-- Índices para bank_statements
CREATE INDEX idx_bank_statements_account_id ON bank_statements(account_id);
CREATE INDEX idx_bank_statements_user_tenant ON bank_statements(user_id, tenant_id);
CREATE INDEX idx_bank_statements_period ON bank_statements(period_start, period_end);
CREATE INDEX idx_bank_statements_status ON bank_statements(parsing_status);
CREATE INDEX idx_bank_statements_uploaded_at ON bank_statements(uploaded_at DESC);

-- Índice para bank_movements statement_id
CREATE INDEX idx_bank_movements_statement_id ON bank_movements(statement_id);

-- =====================================================
-- PASO 4: CREAR TRIGGER PARA UPDATED_AT
-- =====================================================

CREATE TRIGGER update_bank_statements_timestamp
    AFTER UPDATE ON bank_statements
    FOR EACH ROW
BEGIN
    UPDATE bank_statements
    SET updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.id;
END;

-- =====================================================
-- PASO 5: CREAR VISTA PARA CONSULTAS COMPLEJAS
-- =====================================================

CREATE VIEW IF NOT EXISTS bank_statements_summary AS
SELECT
    bs.*,
    upa.nombre as account_name,
    upa.tipo as account_type,
    upa.banco_nombre,
    u.name as user_name,
    u.email as user_email,
    COUNT(bm.id) as parsed_transactions,
    SUM(CASE WHEN bm.amount > 0 THEN bm.amount ELSE 0 END) as parsed_credits,
    SUM(CASE WHEN bm.amount < 0 THEN ABS(bm.amount) ELSE 0 END) as parsed_debits
FROM bank_statements bs
LEFT JOIN user_payment_accounts upa ON bs.account_id = upa.id
LEFT JOIN users u ON bs.user_id = u.id
LEFT JOIN bank_movements bm ON bs.id = bm.statement_id
GROUP BY bs.id, upa.nombre, upa.tipo, upa.banco_nombre, u.name, u.email;

-- =====================================================
-- REGISTRAR MIGRACIÓN
-- =====================================================

INSERT OR IGNORE INTO schema_migrations (version, description, applied_at)
VALUES ('019', 'Add bank statements table for file upload tracking', CURRENT_TIMESTAMP);

-- =====================================================
-- EJEMPLOS DE CONSULTAS
-- =====================================================

/*
-- Obtener statements de una cuenta específica:
SELECT * FROM bank_statements_summary
WHERE account_id = 1
ORDER BY uploaded_at DESC;

-- Obtener transactions de un statement:
SELECT bm.*, bs.file_name
FROM bank_movements bm
JOIN bank_statements bs ON bm.statement_id = bs.id
WHERE bs.id = 1;

-- Estadísticas de procesamiento:
SELECT
    parsing_status,
    COUNT(*) as count,
    AVG(transaction_count) as avg_transactions,
    SUM(total_credits) as total_credits,
    SUM(total_debits) as total_debits
FROM bank_statements
GROUP BY parsing_status;
*/