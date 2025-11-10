-- =====================================================
-- MIGRACIÓN 036: Crear tablas bancarias en PostgreSQL
-- =====================================================
-- Fecha: 2025-11-09
-- Descripción: Crear bank_statements y bank_transactions en PostgreSQL
--              Reemplaza las tablas SQLite legacy

-- =====================================================
-- 1. TABLA: bank_statements
-- =====================================================

CREATE TABLE IF NOT EXISTS bank_statements (
    id SERIAL PRIMARY KEY,
    account_id INTEGER NOT NULL,
    tenant_id INTEGER NOT NULL,
    company_id INTEGER,

    -- Información del archivo
    file_name VARCHAR(255) NOT NULL,
    file_path TEXT,
    file_size INTEGER,
    file_type VARCHAR(20) NOT NULL,  -- 'pdf', 'xlsx', 'csv'

    -- Período del estado de cuenta
    period_start DATE,
    period_end DATE,

    -- Balances
    opening_balance DECIMAL(15,2) DEFAULT 0.0,
    closing_balance DECIMAL(15,2) DEFAULT 0.0,

    -- Totales
    total_credits DECIMAL(15,2) DEFAULT 0.0,
    total_debits DECIMAL(15,2) DEFAULT 0.0,
    transaction_count INTEGER DEFAULT 0,

    -- Status de procesamiento
    parsing_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    parsing_error TEXT,

    -- Timestamps
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    parsed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Foreign keys
    CONSTRAINT fk_bank_statements_account
        FOREIGN KEY (account_id) REFERENCES payment_accounts(id) ON DELETE CASCADE,
    CONSTRAINT fk_bank_statements_tenant
        FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
    CONSTRAINT fk_bank_statements_company
        FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,

    -- Constraints
    CONSTRAINT check_parsing_status
        CHECK (parsing_status IN ('pending', 'processing', 'completed', 'failed')),
    CONSTRAINT check_file_type
        CHECK (file_type IN ('pdf', 'xlsx', 'xls', 'csv'))
);

-- =====================================================
-- 2. TABLA: bank_transactions
-- =====================================================

CREATE TABLE IF NOT EXISTS bank_transactions (
    id SERIAL PRIMARY KEY,
    statement_id INTEGER NOT NULL,
    account_id INTEGER NOT NULL,
    tenant_id INTEGER NOT NULL,
    company_id INTEGER,

    -- Información de la transacción
    transaction_date DATE NOT NULL,
    description TEXT,
    reference VARCHAR(100),

    -- Montos
    amount DECIMAL(15,2) NOT NULL,
    balance DECIMAL(15,2),

    -- Clasificación
    transaction_type VARCHAR(20) NOT NULL,  -- 'debit', 'credit'
    category VARCHAR(100),

    -- Reconciliación
    reconciled BOOLEAN DEFAULT FALSE,
    reconciled_with_invoice_id INTEGER,
    reconciled_at TIMESTAMP,

    -- MSI Detection
    msi_candidate BOOLEAN DEFAULT FALSE,
    msi_invoice_id INTEGER,
    msi_months INTEGER,  -- 3, 6, 9, 12, 18, 24
    msi_confidence DECIMAL(3,2),  -- 0.00 a 1.00

    -- AI/Enrichment
    ai_model VARCHAR(50),
    confidence DECIMAL(3,2),

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Foreign keys
    CONSTRAINT fk_bank_transactions_statement
        FOREIGN KEY (statement_id) REFERENCES bank_statements(id) ON DELETE CASCADE,
    CONSTRAINT fk_bank_transactions_account
        FOREIGN KEY (account_id) REFERENCES payment_accounts(id) ON DELETE CASCADE,
    CONSTRAINT fk_bank_transactions_tenant
        FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
    CONSTRAINT fk_bank_transactions_company
        FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
    CONSTRAINT fk_bank_transactions_invoice
        FOREIGN KEY (reconciled_with_invoice_id) REFERENCES expense_invoices(id) ON DELETE SET NULL,
    CONSTRAINT fk_bank_transactions_msi_invoice
        FOREIGN KEY (msi_invoice_id) REFERENCES expense_invoices(id) ON DELETE SET NULL,

    -- Constraints
    CONSTRAINT check_transaction_type
        CHECK (transaction_type IN ('debit', 'credit')),
    CONSTRAINT check_msi_months
        CHECK (msi_months IS NULL OR msi_months IN (3, 6, 9, 12, 18, 24))
);

-- =====================================================
-- 3. ÍNDICES PARA PERFORMANCE
-- =====================================================

-- Índices para bank_statements
CREATE INDEX IF NOT EXISTS idx_bank_statements_account_id ON bank_statements(account_id);
CREATE INDEX IF NOT EXISTS idx_bank_statements_tenant_id ON bank_statements(tenant_id);
CREATE INDEX IF NOT EXISTS idx_bank_statements_company_id ON bank_statements(company_id);
CREATE INDEX IF NOT EXISTS idx_bank_statements_period ON bank_statements(period_start, period_end);
CREATE INDEX IF NOT EXISTS idx_bank_statements_status ON bank_statements(parsing_status);
CREATE INDEX IF NOT EXISTS idx_bank_statements_uploaded_at ON bank_statements(uploaded_at DESC);

-- Índices para bank_transactions
CREATE INDEX IF NOT EXISTS idx_bank_transactions_statement_id ON bank_transactions(statement_id);
CREATE INDEX IF NOT EXISTS idx_bank_transactions_account_id ON bank_transactions(account_id);
CREATE INDEX IF NOT EXISTS idx_bank_transactions_tenant_id ON bank_transactions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_bank_transactions_company_id ON bank_transactions(company_id);
CREATE INDEX IF NOT EXISTS idx_bank_transactions_date ON bank_transactions(transaction_date);
CREATE INDEX IF NOT EXISTS idx_bank_transactions_reconciled ON bank_transactions(reconciled);
CREATE INDEX IF NOT EXISTS idx_bank_transactions_msi_candidate ON bank_transactions(msi_candidate) WHERE msi_candidate = TRUE;
CREATE INDEX IF NOT EXISTS idx_bank_transactions_msi_invoice ON bank_transactions(msi_invoice_id) WHERE msi_invoice_id IS NOT NULL;

-- =====================================================
-- 4. TRIGGER PARA UPDATED_AT
-- =====================================================

-- Función para actualizar updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger para bank_statements
DROP TRIGGER IF EXISTS update_bank_statements_updated_at ON bank_statements;
CREATE TRIGGER update_bank_statements_updated_at
    BEFORE UPDATE ON bank_statements
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger para bank_transactions
DROP TRIGGER IF EXISTS update_bank_transactions_updated_at ON bank_transactions;
CREATE TRIGGER update_bank_transactions_updated_at
    BEFORE UPDATE ON bank_transactions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- 5. VISTA PARA CONSULTAS
-- =====================================================

CREATE OR REPLACE VIEW bank_statements_summary AS
SELECT
    bs.id,
    bs.account_id,
    bs.tenant_id,
    bs.company_id,
    bs.file_name,
    bs.file_type,
    bs.period_start,
    bs.period_end,
    bs.opening_balance,
    bs.closing_balance,
    bs.total_credits,
    bs.total_debits,
    bs.transaction_count,
    bs.parsing_status,
    bs.uploaded_at,
    bs.parsed_at,

    -- Información de la cuenta
    pa.account_name,
    pa.account_type,
    pa.bank_name,

    -- Estadísticas calculadas de transacciones
    COUNT(bt.id) as parsed_transactions_count,
    SUM(CASE WHEN bt.transaction_type = 'credit' THEN bt.amount ELSE 0 END) as parsed_credits_sum,
    SUM(CASE WHEN bt.transaction_type = 'debit' THEN ABS(bt.amount) ELSE 0 END) as parsed_debits_sum,

    -- Estadísticas MSI
    SUM(CASE WHEN bt.msi_candidate = TRUE THEN 1 ELSE 0 END) as msi_candidates_count,
    SUM(CASE WHEN bt.msi_invoice_id IS NOT NULL THEN 1 ELSE 0 END) as msi_matched_count

FROM bank_statements bs
LEFT JOIN payment_accounts pa ON bs.account_id = pa.id
LEFT JOIN bank_transactions bt ON bs.id = bt.statement_id
GROUP BY
    bs.id, bs.account_id, bs.tenant_id, bs.company_id,
    bs.file_name, bs.file_type, bs.period_start, bs.period_end,
    bs.opening_balance, bs.closing_balance, bs.total_credits, bs.total_debits,
    bs.transaction_count, bs.parsing_status, bs.uploaded_at, bs.parsed_at,
    pa.account_name, pa.account_type, pa.bank_name;

-- =====================================================
-- 6. COMENTARIOS PARA DOCUMENTACIÓN
-- =====================================================

COMMENT ON TABLE bank_statements IS 'Estados de cuenta bancarios subidos por usuarios';
COMMENT ON TABLE bank_transactions IS 'Transacciones extraídas de estados de cuenta';
COMMENT ON VIEW bank_statements_summary IS 'Resumen de estados de cuenta con estadísticas';

COMMENT ON COLUMN bank_statements.parsing_status IS 'Estado del parsing: pending, processing, completed, failed';
COMMENT ON COLUMN bank_statements.file_type IS 'Tipo de archivo: pdf, xlsx, xls, csv';

COMMENT ON COLUMN bank_transactions.transaction_type IS 'Tipo de transacción: debit (cargo), credit (abono)';
COMMENT ON COLUMN bank_transactions.msi_candidate IS 'TRUE si la transacción parece ser un pago MSI';
COMMENT ON COLUMN bank_transactions.msi_invoice_id IS 'ID de la factura asociada si se detectó MSI';
COMMENT ON COLUMN bank_transactions.msi_months IS 'Número de meses MSI detectados (3, 6, 9, 12, 18, 24)';
COMMENT ON COLUMN bank_transactions.msi_confidence IS 'Nivel de confianza de detección MSI (0.00 a 1.00)';

-- =====================================================
-- 7. EJEMPLOS DE USO
-- =====================================================

/*
-- Obtener statements de una cuenta específica:
SELECT * FROM bank_statements_summary
WHERE account_id = 1
ORDER BY uploaded_at DESC;

-- Obtener transacciones de un statement:
SELECT * FROM bank_transactions
WHERE statement_id = 1
ORDER BY transaction_date;

-- Buscar candidatos MSI de alta confianza:
SELECT
    bt.*,
    ei.uuid as invoice_uuid,
    ei.nombre_emisor,
    ei.total as invoice_total
FROM bank_transactions bt
LEFT JOIN expense_invoices ei ON bt.msi_invoice_id = ei.id
WHERE bt.msi_candidate = TRUE
AND bt.msi_confidence > 0.90
ORDER BY bt.msi_confidence DESC;

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
