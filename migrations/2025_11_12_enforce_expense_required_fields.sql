-- 📌 Migration: Enforce required fields for expense_records (PostgreSQL)
-- Fecha: 2025-11-12

BEGIN;

-- 1) Crear columna invoice_status_reason si aún no existe
ALTER TABLE expense_records
    ADD COLUMN IF NOT EXISTS invoice_status_reason TEXT;

COMMENT ON COLUMN expense_records.invoice_status_reason IS
    'Detalle textual del estado de facturación (rechazo, justificación, etc.)';

-- 2) Backfill expense_date y volverla NOT NULL
UPDATE expense_records
   SET expense_date = to_char(COALESCE(expense_date::date, created_at::date), 'YYYY-MM-DD')
 WHERE expense_date IS NULL;

ALTER TABLE expense_records
    ALTER COLUMN expense_date SET NOT NULL;

-- 3) Backfill payment_method y volverlo NOT NULL
UPDATE expense_records
   SET payment_method = COALESCE(payment_method, 'no_especificado')
 WHERE payment_method IS NULL;

ALTER TABLE expense_records
    ALTER COLUMN payment_method SET NOT NULL;

-- 4) Permitir NULL en will_have_cfdi para representar "sin decisión"
ALTER TABLE expense_records
    ALTER COLUMN will_have_cfdi DROP NOT NULL;

COMMIT;
