-- Create base bank_movements table for reconciliation
-- Funcionalidad #7: Conciliación Bancaria

CREATE TABLE IF NOT EXISTS bank_movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    amount REAL NOT NULL,
    description TEXT,
    reference TEXT,
    movement_type TEXT, -- 'debit', 'credit', 'transfer'
    bank_account TEXT,
    matched_expense_id INTEGER,
    tenant_id INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Enhanced reconciliation fields
    decision TEXT,
    bank_metadata TEXT,
    confidence REAL DEFAULT 0.0,
    movement_id TEXT,
    transaction_type TEXT,
    balance_after REAL,
    raw_data TEXT,
    processing_status TEXT DEFAULT 'pending',
    matched_at TIMESTAMP,
    matched_by INTEGER,
    auto_matched BOOLEAN DEFAULT FALSE,
    reconciliation_notes TEXT,
    bank_account_id TEXT,
    category TEXT,

    FOREIGN KEY (matched_expense_id) REFERENCES expense_records(id),
    FOREIGN KEY (tenant_id) REFERENCES tenants(id),
    FOREIGN KEY (matched_by) REFERENCES users(id)
);

-- Create indexes
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

-- Recreate the view now that the table exists
DROP VIEW IF EXISTS bank_reconciliation_view;
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

-- Create trigger for updating matched_at
CREATE TRIGGER IF NOT EXISTS bank_movements_matched_at
    AFTER UPDATE ON bank_movements
    FOR EACH ROW
    WHEN NEW.matched_expense_id != OLD.matched_expense_id AND NEW.matched_expense_id IS NOT NULL
BEGIN
    UPDATE bank_movements
    SET matched_at = CURRENT_TIMESTAMP
    WHERE id = NEW.id;
END;