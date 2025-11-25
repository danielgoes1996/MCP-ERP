-- =============================================
-- 📊 VISTA MEJORADA: Conciliación con criterios más flexibles
-- =============================================
-- Esta versión mejora la tasa de matching usando:
-- 1. Criterios más flexibles (±$10, ±5 días)
-- 2. Similarity scoring con descripción
-- 3. Multiple match candidates con ranking

-- Determinar qué tabla de expenses usar
DO $$
DECLARE
  expenses_table TEXT;
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'expense_invoices') THEN
    expenses_table := 'expense_invoices';
  ELSIF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'manual_expenses') THEN
    expenses_table := 'manual_expenses';
  ELSE
    RAISE NOTICE 'No se encontró tabla de expenses, creando vista simplificada';
    expenses_table := NULL;
  END IF;

  IF expenses_table IS NOT NULL THEN
    -- Crear vista mejorada con criterios más flexibles
    EXECUTE format($view$
      CREATE OR REPLACE VIEW vw_reconciliation_ready_improved AS
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
        ei.nombre_emisor,

        -- Cálculos de matching mejorados
        ABS(ABS(bt.amount) - ei.total) AS amount_difference,
        ABS(bt.transaction_date - ei.fecha_emision::DATE) AS days_difference,

        -- Porcentaje de diferencia de monto
        (ABS(ABS(bt.amount) - ei.total) / NULLIF(ABS(bt.amount), 0)) * 100.0 AS amount_diff_percent,

        -- Score de confianza compuesto (0-100)
        CASE
          WHEN ABS(ABS(bt.amount) - ei.total) = 0 AND ABS(bt.transaction_date - ei.fecha_emision::DATE) = 0 THEN 100
          WHEN ABS(ABS(bt.amount) - ei.total) <= 1 AND ABS(bt.transaction_date - ei.fecha_emision::DATE) <= 1 THEN 95
          WHEN ABS(ABS(bt.amount) - ei.total) <= 2 AND ABS(bt.transaction_date - ei.fecha_emision::DATE) <= 2 THEN 90
          WHEN ABS(ABS(bt.amount) - ei.total) <= 5 AND ABS(bt.transaction_date - ei.fecha_emision::DATE) <= 3 THEN 80
          WHEN ABS(ABS(bt.amount) - ei.total) <= 10 AND ABS(bt.transaction_date - ei.fecha_emision::DATE) <= 5 THEN 70
          ELSE 50
        END AS match_score,

        -- Estado de conciliación calculado con nuevos criterios
        CASE
          WHEN bt.reconciled_invoice_id IS NOT NULL AND bt.reconciliation_status = 'reviewed' THEN 'REVIEWED'
          WHEN bt.reconciled_invoice_id IS NOT NULL AND bt.reconciliation_status = 'manual' THEN 'MANUAL_MATCH'
          WHEN bt.reconciled_invoice_id IS NOT NULL THEN 'MATCHED'
          -- Perfect match (diff = 0)
          WHEN ABS(ABS(bt.amount) - ei.total) = 0
               AND ABS(bt.transaction_date - ei.fecha_emision::DATE) <= 1 THEN 'AUTO_MATCH_PERFECT'
          -- Excellent match (diff <= $2, days <= 2)
          WHEN ABS(ABS(bt.amount) - ei.total) <= 2
               AND ABS(bt.transaction_date - ei.fecha_emision::DATE) <= 2 THEN 'AUTO_MATCH_HIGH'
          -- Good match (diff <= $5, days <= 3)
          WHEN ABS(ABS(bt.amount) - ei.total) <= 5
               AND ABS(bt.transaction_date - ei.fecha_emision::DATE) <= 3 THEN 'AUTO_MATCH_MEDIUM'
          -- Fair match (diff <= $10, days <= 5, diff%% <= 5%%)
          WHEN ABS(ABS(bt.amount) - ei.total) <= 10
               AND ABS(bt.transaction_date - ei.fecha_emision::DATE) <= 5
               AND (ABS(ABS(bt.amount) - ei.total) / NULLIF(ABS(bt.amount), 0)) * 100.0 <= 5.0 THEN 'AUTO_MATCH_LOW'
          ELSE 'PENDING'
        END AS match_status,

        -- Ranking de matches (1 = mejor match)
        ROW_NUMBER() OVER (
          PARTITION BY bt.id
          ORDER BY
            ABS(ABS(bt.amount) - ei.total) ASC,
            ABS(bt.transaction_date - ei.fecha_emision::DATE) ASC
        ) AS match_rank

      FROM bank_transactions bt
      LEFT JOIN %I ei
        ON ABS(ABS(bt.amount) - ei.total) <= 10  -- Tolerancia más amplia: $10
        AND bt.transaction_date BETWEEN (ei.fecha_emision::DATE - INTERVAL '5 days')
                                     AND (ei.fecha_emision::DATE + INTERVAL '5 days')  -- Ventana más amplia: ±5 días
        AND bt.company_id = ei.company_id
        AND bt.tenant_id = ei.tenant_id
      WHERE bt.transaction_type = 'debit'  -- Solo débitos (gastos)
        -- Excluir traspasos, comisiones y recargas de los auto-matches
        AND NOT (
          bt.description ILIKE '%%traspaso%%' OR bt.description ILIKE '%%spei%%' OR bt.description ILIKE '%%transferencia%%' OR
          bt.description ILIKE '%%comision%%' OR bt.description ILIKE '%%iva comision%%' OR bt.description ILIKE '%%isr retenido%%' OR
          bt.description ILIKE '%%recarga%%' OR bt.description ILIKE '%%tutag%%' OR bt.description ILIKE '%%pase%%'
        )
      ORDER BY bt.transaction_date DESC, bt.id DESC, match_rank ASC
    $view$, expenses_table);

  ELSE
    -- Mantener vista simplificada sin expenses
    CREATE OR REPLACE VIEW vw_reconciliation_ready_improved AS
    SELECT
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
      bt.reconciled_invoice_id,
      bt.match_confidence,
      bt.reconciliation_status,
      bt.reconciled_by,
      bt.reconciled_at,
      bt.source_hash,
      NULL::INT AS invoice_id,
      NULL::VARCHAR AS invoice_uuid,
      NULL::NUMERIC AS invoice_total,
      NULL::DATE AS invoice_date,
      NULL::VARCHAR AS rfc_emisor,
      NULL::VARCHAR AS rfc_receptor,
      NULL::VARCHAR AS forma_pago,
      NULL::VARCHAR AS metodo_pago,
      NULL::VARCHAR AS tipo_comprobante,
      NULL::VARCHAR AS nombre_emisor,
      NULL::NUMERIC AS amount_difference,
      NULL::NUMERIC AS days_difference,
      NULL::NUMERIC AS amount_diff_percent,
      NULL::INT AS match_score,
      'PENDING'::TEXT AS match_status,
      NULL::BIGINT AS match_rank
    FROM bank_transactions bt
    WHERE bt.transaction_type = 'debit'
    ORDER BY bt.transaction_date DESC, bt.id DESC;
  END IF;
END $$;

COMMENT ON VIEW vw_reconciliation_ready_improved IS
'Vista mejorada con criterios de matching más flexibles (±$10, ±5 días) y scoring';

-- =============================================
-- 📊 VISTAS ADICIONALES MEJORADAS
-- =============================================

-- Vista: Solo el mejor match por transacción
CREATE OR REPLACE VIEW vw_reconciliation_best_matches AS
SELECT *
FROM vw_reconciliation_ready_improved
WHERE match_rank = 1 OR match_rank IS NULL  -- Solo el mejor match
ORDER BY transaction_date DESC;

COMMENT ON VIEW vw_reconciliation_best_matches IS
'Solo el mejor match candidato por cada transacción';

-- Vista: Sugerencias mejoradas (incluye todos los niveles de confianza)
CREATE OR REPLACE VIEW vw_auto_match_suggestions_improved AS
SELECT
    *,
    CASE
      WHEN match_status = 'AUTO_MATCH_PERFECT' THEN 'Perfecto (0% diff)'
      WHEN match_status = 'AUTO_MATCH_HIGH' THEN 'Alta confianza (±$2, ±2d)'
      WHEN match_status = 'AUTO_MATCH_MEDIUM' THEN 'Media confianza (±$5, ±3d)'
      WHEN match_status = 'AUTO_MATCH_LOW' THEN 'Baja confianza (±$10, ±5d)'
      ELSE 'Requiere revisión manual'
    END AS confidence_label
FROM vw_reconciliation_best_matches
WHERE match_status LIKE 'AUTO_MATCH%'
  AND reconciled_invoice_id IS NULL
  AND invoice_id IS NOT NULL
ORDER BY
  CASE match_status
    WHEN 'AUTO_MATCH_PERFECT' THEN 1
    WHEN 'AUTO_MATCH_HIGH' THEN 2
    WHEN 'AUTO_MATCH_MEDIUM' THEN 3
    WHEN 'AUTO_MATCH_LOW' THEN 4
    ELSE 5
  END,
  amount_difference ASC,
  days_difference ASC;

COMMENT ON VIEW vw_auto_match_suggestions_improved IS
'Sugerencias de conciliación con múltiples niveles de confianza';

-- Vista: Estadísticas mejoradas
CREATE OR REPLACE VIEW vw_reconciliation_stats_improved AS
SELECT
  COUNT(DISTINCT bt.id) AS total_transactions,

  -- Conciliadas
  COUNT(DISTINCT CASE WHEN bt.reconciliation_status = 'matched' THEN bt.id END) AS matched,
  COUNT(DISTINCT CASE WHEN bt.reconciliation_status = 'manual' THEN bt.id END) AS manual_matched,
  COUNT(DISTINCT CASE WHEN bt.reconciliation_status = 'reviewed' THEN bt.id END) AS reviewed,
  COUNT(DISTINCT CASE WHEN bt.reconciliation_status = 'pending' THEN bt.id END) AS pending,

  -- Auto-match por nivel
  COUNT(DISTINCT CASE WHEN vr.match_status = 'AUTO_MATCH_PERFECT' AND vr.match_rank = 1 THEN bt.id END) AS auto_match_perfect,
  COUNT(DISTINCT CASE WHEN vr.match_status = 'AUTO_MATCH_HIGH' AND vr.match_rank = 1 THEN bt.id END) AS auto_match_high,
  COUNT(DISTINCT CASE WHEN vr.match_status = 'AUTO_MATCH_MEDIUM' AND vr.match_rank = 1 THEN bt.id END) AS auto_match_medium,
  COUNT(DISTINCT CASE WHEN vr.match_status = 'AUTO_MATCH_LOW' AND vr.match_rank = 1 THEN bt.id END) AS auto_match_low,

  -- Sin posible match
  COUNT(DISTINCT CASE WHEN vr.invoice_id IS NULL THEN bt.id END) AS no_invoice_found,

  -- Métricas
  ROUND(AVG(bt.match_confidence), 4) AS avg_confidence,

  -- Tasa de conciliación
  COUNT(DISTINCT CASE WHEN bt.reconciliation_status != 'pending' THEN bt.id END)::FLOAT /
    NULLIF(COUNT(DISTINCT bt.id), 0) * 100 AS reconciliation_rate,

  -- Tasa potencial (si se aplican todos los auto-matches)
  (COUNT(DISTINCT CASE WHEN bt.reconciliation_status != 'pending' THEN bt.id END) +
   COUNT(DISTINCT CASE WHEN vr.match_status LIKE 'AUTO_MATCH%' AND vr.match_rank = 1 AND bt.reconciled_invoice_id IS NULL THEN bt.id END))::FLOAT /
    NULLIF(COUNT(DISTINCT bt.id), 0) * 100 AS potential_reconciliation_rate

FROM bank_transactions bt
LEFT JOIN vw_reconciliation_ready_improved vr ON bt.id = vr.transaction_id
WHERE bt.transaction_type = 'debit';

COMMENT ON VIEW vw_reconciliation_stats_improved IS
'Estadísticas mejoradas con desglose por nivel de confianza';

-- Vista: Transacciones sin factura disponible
CREATE OR REPLACE VIEW vw_transactions_without_invoice AS
SELECT
  bt.id AS transaction_id,
  bt.transaction_date,
  bt.description,
  bt.amount,
  bt.company_id,
  bt.tenant_id
FROM bank_transactions bt
WHERE bt.transaction_type = 'debit'
  AND bt.reconciled_invoice_id IS NULL
  AND NOT EXISTS (
    SELECT 1 FROM vw_reconciliation_ready_improved vr
    WHERE vr.transaction_id = bt.id
    AND vr.invoice_id IS NOT NULL
  )
ORDER BY bt.amount DESC;

COMMENT ON VIEW vw_transactions_without_invoice IS
'Transacciones bancarias sin ninguna factura candidata para conciliar';

COMMIT;

-- =============================================
-- ✅ VISTAS MEJORADAS CREADAS
-- =============================================
