-- =============================================
-- 📊 VISTA: Transacciones listas para conciliación
-- =============================================
-- Esta vista une transacciones bancarias con facturas
-- para facilitar la conciliación automática y manual

-- Determinar qué tabla de expenses usar
DO $$
DECLARE
  expenses_table TEXT;
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'expense_invoices') THEN
    expenses_table := 'expense_invoices';
  ELSIF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'expenses') THEN
    expenses_table := 'expenses';
  ELSE
    RAISE NOTICE 'No se encontró tabla de expenses, creando vista simplificada';
    expenses_table := NULL;
  END IF;

  IF expenses_table IS NOT NULL THEN
    -- Crear vista completa con join a expenses
    EXECUTE format($view$
      CREATE OR REPLACE VIEW vw_reconciliation_ready AS
      SELECT
        -- Datos de la transacción bancaria
        bt.id AS transaction_id,
        bt.transaction_date,
        bt.description AS transaction_description,
        bt.amount AS transaction_amount,
        bt.transaction_type,
        bt.reference AS transaction_reference,
        bt.balance AS transaction_balance,
        bt.company_id,
        bt.tenant_id,
        bt.account_id,
        bt.statement_id,

        -- Estado de conciliación
        bt.reconciled_invoice_id,
        bt.match_confidence,
        bt.reconciliation_status,
        bt.reconciled_by,
        bt.reconciled_at,
        bt.source_hash,

        -- Datos de la factura (si hay match)
        ei.id AS invoice_id,
        ei.uuid AS invoice_uuid,
        ei.total AS invoice_total,
        ei.fecha_emision::DATE AS invoice_date,
        ei.rfc_emisor,
        ei.rfc_receptor,
        ei.forma_pago,
        ei.metodo_pago,
        ei.tipo_comprobante,

        -- Cálculos de matching
        ABS(ABS(bt.amount) - ei.total) AS amount_difference,
        ABS(bt.transaction_date - ei.fecha_emision::DATE) AS days_difference,

        -- Estado de conciliación calculado
        CASE
          WHEN bt.reconciled_invoice_id IS NOT NULL AND bt.reconciliation_status = 'reviewed' THEN 'REVIEWED'
          WHEN bt.reconciled_invoice_id IS NOT NULL AND bt.reconciliation_status = 'manual' THEN 'MANUAL_MATCH'
          WHEN bt.reconciled_invoice_id IS NOT NULL THEN 'MATCHED'
          WHEN ABS(ABS(bt.amount) - ei.total) <= 2
               AND ABS(bt.transaction_date - ei.fecha_emision::DATE) <= 2 THEN 'AUTO_MATCH'
          ELSE 'PENDING'
        END AS match_status

      FROM bank_transactions bt
      LEFT JOIN %I ei
        ON ABS(ABS(bt.amount) - ei.total) <= 2
        AND bt.transaction_date BETWEEN (ei.fecha_emision::DATE - INTERVAL '2 days') AND (ei.fecha_emision::DATE + INTERVAL '2 days')
        AND bt.company_id = ei.company_id
        AND bt.tenant_id = ei.tenant_id
      WHERE bt.transaction_type = 'debit'  -- Solo débitos (gastos)
      ORDER BY bt.transaction_date DESC, bt.id DESC
    $view$, expenses_table);

  ELSE
    -- Crear vista simplificada sin expenses
    CREATE OR REPLACE VIEW vw_reconciliation_ready AS
    SELECT
      -- Datos de la transacción bancaria
      bt.id AS transaction_id,
      bt.transaction_date,
      bt.description AS transaction_description,
      bt.amount AS transaction_amount,
      bt.transaction_type,
      bt.reference AS transaction_reference,
      bt.balance AS transaction_balance,
      bt.company_id,
      bt.tenant_id,
      bt.account_id,
      bt.statement_id,

      -- Estado de conciliación
      bt.reconciled_invoice_id,
      bt.match_confidence,
      bt.reconciliation_status,
      bt.reconciled_by,
      bt.reconciled_at,
      bt.source_hash,

      -- Sin datos de factura
      NULL::INT AS invoice_id,
      NULL::VARCHAR AS invoice_uuid,
      NULL::NUMERIC AS invoice_total,
      NULL::DATE AS invoice_date,
      NULL::VARCHAR AS rfc_emisor,
      NULL::VARCHAR AS rfc_receptor,
      NULL::VARCHAR AS forma_pago,
      NULL::VARCHAR AS metodo_pago,
      NULL::VARCHAR AS tipo_comprobante,

      -- Sin cálculos de matching
      NULL::NUMERIC AS amount_difference,
      NULL::NUMERIC AS days_difference,

      -- Estado siempre pending sin expenses
      'PENDING'::TEXT AS match_status

    FROM bank_transactions bt
    WHERE bt.transaction_type = 'debit'
    ORDER BY bt.transaction_date DESC, bt.id DESC;
  END IF;
END $$;

COMMENT ON VIEW vw_reconciliation_ready IS
'Vista para conciliación de transacciones bancarias con facturas (expenses)';

-- =============================================
-- 📊 VISTAS ADICIONALES ÚTILES
-- =============================================

-- Vista: Transacciones pendientes de conciliación
CREATE OR REPLACE VIEW vw_pending_reconciliation AS
SELECT *
FROM vw_reconciliation_ready
WHERE match_status IN ('PENDING', 'AUTO_MATCH')
  AND reconciled_invoice_id IS NULL
ORDER BY transaction_date DESC;

COMMENT ON VIEW vw_pending_reconciliation IS
'Transacciones bancarias pendientes de conciliar';

-- Vista: Conciliaciones automáticas sugeridas
CREATE OR REPLACE VIEW vw_auto_match_suggestions AS
SELECT *
FROM vw_reconciliation_ready
WHERE match_status = 'AUTO_MATCH'
  AND reconciled_invoice_id IS NULL
  AND invoice_id IS NOT NULL
ORDER BY match_confidence DESC, amount_difference ASC;

COMMENT ON VIEW vw_auto_match_suggestions IS
'Sugerencias de conciliación automática con alta confianza';

-- Vista: Estadísticas de conciliación
CREATE OR REPLACE VIEW vw_reconciliation_stats AS
SELECT
  COUNT(*) AS total_transactions,
  COUNT(CASE WHEN reconciliation_status = 'matched' THEN 1 END) AS matched,
  COUNT(CASE WHEN reconciliation_status = 'manual' THEN 1 END) AS manual_matched,
  COUNT(CASE WHEN reconciliation_status = 'reviewed' THEN 1 END) AS reviewed,
  COUNT(CASE WHEN reconciliation_status = 'pending' THEN 1 END) AS pending,
  ROUND(AVG(match_confidence), 4) AS avg_confidence,
  SUM(CASE WHEN reconciliation_status != 'pending' THEN 1 ELSE 0 END)::FLOAT /
    NULLIF(COUNT(*), 0) * 100 AS reconciliation_rate
FROM bank_transactions
WHERE transaction_type = 'debit';

COMMENT ON VIEW vw_reconciliation_stats IS
'Estadísticas globales de conciliación';

COMMIT;

-- =============================================
-- ✅ VISTAS CREADAS
-- =============================================
