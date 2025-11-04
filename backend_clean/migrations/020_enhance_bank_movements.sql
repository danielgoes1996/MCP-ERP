-- Migración para mejorar tabla bank_movements
-- Agregar columnas para categorización y reconciliación

-- Agregar columnas nuevas
ALTER TABLE bank_movements ADD COLUMN cleaned_description TEXT;
ALTER TABLE bank_movements ADD COLUMN category_auto TEXT;
ALTER TABLE bank_movements ADD COLUMN category_manual TEXT;
ALTER TABLE bank_movements ADD COLUMN is_reconciled BOOLEAN DEFAULT FALSE;
ALTER TABLE bank_movements ADD COLUMN notes TEXT;
ALTER TABLE bank_movements ADD COLUMN confidence_score REAL DEFAULT 0.0;

-- Índices para mejorar performance
CREATE INDEX IF NOT EXISTS idx_bank_movements_category ON bank_movements(category_manual, category_auto);
CREATE INDEX IF NOT EXISTS idx_bank_movements_reconciled ON bank_movements(is_reconciled);
CREATE INDEX IF NOT EXISTS idx_bank_movements_amount_range ON bank_movements(amount) WHERE amount BETWEEN -1000000 AND 1000000;

-- Vista mejorada para transacciones
CREATE VIEW IF NOT EXISTS bank_transactions_enhanced AS
SELECT
    bm.id,
    bm.date,
    bm.description,
    bm.cleaned_description,
    bm.amount,
    bm.transaction_type,
    COALESCE(bm.category_manual, bm.category_auto, 'Sin categoría') as category,
    bm.is_reconciled,
    bm.notes,
    bm.confidence_score,
    bm.raw_data,
    bm.statement_id,
    bm.account_id,
    bm.user_id,
    bm.tenant_id,
    bm.created_at,
    -- Formato de monto en pesos mexicanos
    CASE
        WHEN bm.transaction_type = 'debit' THEN '-$' || printf("%.2f", bm.amount)
        ELSE '+$' || printf("%.2f", bm.amount)
    END as formatted_amount,
    -- Estado de categorización
    CASE
        WHEN bm.category_manual IS NOT NULL THEN 'Manual'
        WHEN bm.category_auto IS NOT NULL THEN 'Automática'
        ELSE 'Sin categorizar'
    END as category_status
FROM bank_movements bm
WHERE bm.amount > 0 AND bm.amount < 1000000; -- Filtrar montos irreales