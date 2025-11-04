-- ============================================================================
-- MIGRACIÓN 024: Completar requisitos del sistema de gastos
-- Fecha: 2025-10-03
-- Objetivo: Agregar campos faltantes para cumplir con diseño completo
-- ============================================================================

-- ============================================================================
-- PASO 1: Agregar invoice_status_reason
-- ============================================================================

ALTER TABLE expense_records ADD COLUMN invoice_status_reason TEXT;

-- Índice parcial (solo para registros con razón)
CREATE INDEX idx_expense_records_invoice_status_reason
ON expense_records(invoice_status_reason)
WHERE invoice_status_reason IS NOT NULL;

-- ============================================================================
-- VERIFICACIÓN
-- ============================================================================

SELECT '✅ Campo invoice_status_reason agregado' as resultado;

-- Ver esquema actualizado
SELECT
    name,
    type,
    [notnull] as not_null,
    dflt_value as default_value
FROM pragma_table_info('expense_records')
WHERE name = 'invoice_status_reason';
