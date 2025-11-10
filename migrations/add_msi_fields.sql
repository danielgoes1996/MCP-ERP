-- Migración: Agregar campos MSI
-- ================================
-- Fecha: 2025-11-09
-- Descripción: Agregar campos para identificar y manejar facturas MSI

-- 1. Agregar columnas para MSI
ALTER TABLE expense_invoices
ADD COLUMN IF NOT EXISTS es_msi BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS meses_msi INTEGER,
ADD COLUMN IF NOT EXISTS pago_mensual_msi DECIMAL(10,2),
ADD COLUMN IF NOT EXISTS msi_confirmado BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS msi_confirmado_por INTEGER REFERENCES users(id),
ADD COLUMN IF NOT EXISTS msi_confirmado_fecha TIMESTAMP;

-- 2. Comentarios para documentación
COMMENT ON COLUMN expense_invoices.es_msi IS 'Indica si la factura fue pagada a meses sin intereses';
COMMENT ON COLUMN expense_invoices.meses_msi IS 'Número de meses del plan MSI (3, 6, 9, 12, 18, 24)';
COMMENT ON COLUMN expense_invoices.pago_mensual_msi IS 'Monto del pago mensual MSI';
COMMENT ON COLUMN expense_invoices.msi_confirmado IS 'Indica si se confirmó manualmente el estado MSI';
COMMENT ON COLUMN expense_invoices.msi_confirmado_por IS 'Usuario que confirmó el estado MSI';
COMMENT ON COLUMN expense_invoices.msi_confirmado_fecha IS 'Fecha de confirmación del estado MSI';

-- 3. Crear índice para búsquedas de MSI
CREATE INDEX IF NOT EXISTS idx_expense_invoices_msi ON expense_invoices(es_msi) WHERE es_msi = TRUE;

-- 4. Vista para facturas que requieren confirmación MSI
CREATE OR REPLACE VIEW facturas_requieren_confirmacion_msi AS
SELECT
    id,
    uuid,
    fecha_emision,
    nombre_emisor,
    total,
    forma_pago,
    msi_confirmado
FROM expense_invoices
WHERE metodo_pago = 'PUE'
AND forma_pago = '04'
AND total > 100
AND sat_status = 'vigente'
AND (msi_confirmado = FALSE OR msi_confirmado IS NULL)
ORDER BY total DESC;

COMMENT ON VIEW facturas_requieren_confirmacion_msi IS 'Facturas PUE + Tarjeta crédito + >$100 que requieren confirmación de MSI';
