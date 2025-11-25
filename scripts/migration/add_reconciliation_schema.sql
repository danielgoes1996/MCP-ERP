-- =============================================
-- 🚀 EXTENSIÓN: Preparar conciliación automática
-- =============================================
-- Ejecuta este script para agregar capacidades de conciliación
-- entre transacciones bancarias y facturas (CFDIs)

-- 1️⃣ Agregar identificador de fuente única (hash)
ALTER TABLE bank_transactions
ADD COLUMN IF NOT EXISTS source_hash VARCHAR(64) UNIQUE;

COMMENT ON COLUMN bank_transactions.source_hash IS
'Hash SHA-256 único de la transacción para detección de duplicados';

-- 2️⃣ Enlace con factura (CFDI)
ALTER TABLE bank_transactions
ADD COLUMN IF NOT EXISTS reconciled_invoice_id INT NULL;

-- Nota: Agregar FK solo si la tabla expense_invoices existe
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'expense_invoices') THEN
    ALTER TABLE bank_transactions
    ADD CONSTRAINT fk_bank_transactions_invoice
    FOREIGN KEY (reconciled_invoice_id)
    REFERENCES expense_invoices(id)
    ON DELETE SET NULL;
  ELSIF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'manual_expenses') THEN
    ALTER TABLE bank_transactions
    ADD CONSTRAINT fk_bank_transactions_expense
    FOREIGN KEY (reconciled_invoice_id)
    REFERENCES expenses(id)
    ON DELETE SET NULL;
  END IF;
END $$;

COMMENT ON COLUMN bank_transactions.reconciled_invoice_id IS
'ID de la factura (expense) conciliada con esta transacción';

-- 3️⃣ Confianza de conciliación
ALTER TABLE bank_transactions
ADD COLUMN IF NOT EXISTS match_confidence NUMERIC(5,4) DEFAULT 0.0;

COMMENT ON COLUMN bank_transactions.match_confidence IS
'Confianza de la conciliación (0.0 = sin match, 1.0 = match perfecto)';

-- 4️⃣ Estado de conciliación
ALTER TABLE bank_transactions
ADD COLUMN IF NOT EXISTS reconciliation_status VARCHAR(20) DEFAULT 'pending';

COMMENT ON COLUMN bank_transactions.reconciliation_status IS
'Estado de conciliación: pending, matched, manual, reviewed';

-- 5️⃣ Usuario que revisó la conciliación
ALTER TABLE bank_transactions
ADD COLUMN IF NOT EXISTS reconciled_by INT NULL;

COMMENT ON COLUMN bank_transactions.reconciled_by IS
'ID del usuario que confirmó la conciliación manualmente';

-- 6️⃣ Fecha de conciliación
ALTER TABLE bank_transactions
ADD COLUMN IF NOT EXISTS reconciled_at TIMESTAMP NULL;

COMMENT ON COLUMN bank_transactions.reconciled_at IS
'Timestamp de cuando se concilió la transacción';

-- 7️⃣ Índices para búsquedas rápidas
CREATE INDEX IF NOT EXISTS idx_bank_transactions_confidence
  ON bank_transactions (match_confidence DESC);

CREATE INDEX IF NOT EXISTS idx_bank_transactions_reconciled
  ON bank_transactions (reconciled_invoice_id)
  WHERE reconciled_invoice_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_bank_transactions_source_hash
  ON bank_transactions (source_hash)
  WHERE source_hash IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_bank_transactions_status
  ON bank_transactions (reconciliation_status);

CREATE INDEX IF NOT EXISTS idx_bank_transactions_amount_date
  ON bank_transactions (amount, transaction_date);

-- 8️⃣ Función: generar hash único por transacción
CREATE OR REPLACE FUNCTION fn_generate_source_hash()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.source_hash IS NULL THEN
    NEW.source_hash := encode(
      digest(
        concat_ws('|',
          COALESCE(NEW.transaction_date::TEXT,''),
          COALESCE(NEW.description,''),
          COALESCE(NEW.amount::TEXT,''),
          COALESCE(NEW.balance::TEXT,''),
          COALESCE(NEW.reference,''),
          COALESCE(NEW.account_id::TEXT,'')
        ),
        'sha256'
      ),
      'hex'
    );
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fn_generate_source_hash() IS
'Genera hash SHA-256 único para detectar transacciones duplicadas';

-- 9️⃣ Trigger: aplicar hash automáticamente
DROP TRIGGER IF EXISTS trg_generate_source_hash ON bank_transactions;

CREATE TRIGGER trg_generate_source_hash
BEFORE INSERT OR UPDATE ON bank_transactions
FOR EACH ROW
EXECUTE FUNCTION fn_generate_source_hash();

-- 🔟 Actualizar hashes de transacciones existentes
UPDATE bank_transactions
SET source_hash = NULL
WHERE source_hash IS NULL;

-- Esto disparará el trigger para generar los hashes

COMMIT;

-- =============================================
-- ✅ EXTENSIÓN COMPLETADA
-- =============================================
