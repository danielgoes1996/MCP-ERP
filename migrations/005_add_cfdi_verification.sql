-- ========================================
-- MIGRATION 005: CFDI SAT Verification
-- ========================================
-- Purpose: Add SAT verification status to invoices
-- Author: ContaFlow Backend Team
-- Date: 2025-01-08
-- Phase: 3.2 - CFDI Verification

-- ========================================
-- Add SAT verification columns to expense_invoices
-- ========================================

ALTER TABLE expense_invoices
ADD COLUMN IF NOT EXISTS sat_status VARCHAR(20),
ADD COLUMN IF NOT EXISTS sat_codigo_estatus VARCHAR(10),
ADD COLUMN IF NOT EXISTS sat_es_cancelable BOOLEAN,
ADD COLUMN IF NOT EXISTS sat_estado TEXT,
ADD COLUMN IF NOT EXISTS sat_validacion_efos TEXT,
ADD COLUMN IF NOT EXISTS sat_fecha_verificacion TIMESTAMP,
ADD COLUMN IF NOT EXISTS sat_verificacion_count INTEGER DEFAULT 0;

-- Create index on sat_status for filtering
CREATE INDEX IF NOT EXISTS idx_expense_invoices_sat_status
ON expense_invoices(sat_status);

-- Create index on sat_fecha_verificacion for sorting
CREATE INDEX IF NOT EXISTS idx_expense_invoices_sat_verificacion
ON expense_invoices(sat_fecha_verificacion);

-- ========================================
-- Add comments
-- ========================================

COMMENT ON COLUMN expense_invoices.sat_status IS 'Status SAT: vigente, cancelado, sustituido, por_cancelar, no_encontrado, error';
COMMENT ON COLUMN expense_invoices.sat_codigo_estatus IS 'Código de estatus del SAT (S=Success, N=Not Found)';
COMMENT ON COLUMN expense_invoices.sat_es_cancelable IS 'Indica si el CFDI puede ser cancelado';
COMMENT ON COLUMN expense_invoices.sat_estado IS 'Estado detallado del SAT';
COMMENT ON COLUMN expense_invoices.sat_validacion_efos IS 'Validación de EFOS (Empresas Facturadoras de Operaciones Simuladas)';
COMMENT ON COLUMN expense_invoices.sat_fecha_verificacion IS 'Fecha de última verificación en el SAT';
COMMENT ON COLUMN expense_invoices.sat_verificacion_count IS 'Número de veces que se ha verificado este CFDI';

-- ========================================
-- Create view for invalid CFDIs
-- ========================================

CREATE OR REPLACE VIEW vw_cfdis_invalidos AS
SELECT
    id,
    company_id,
    uuid,
    filename,
    rfc_emisor,
    rfc_receptor,
    total,
    fecha_emision,
    sat_status,
    sat_estado,
    sat_fecha_verificacion,
    tipo_comprobante
FROM expense_invoices
WHERE sat_status IN ('cancelado', 'sustituido', 'no_encontrado')
ORDER BY sat_fecha_verificacion DESC;

COMMENT ON VIEW vw_cfdis_invalidos IS 'Vista de CFDIs que no son válidos para deducción fiscal';

-- ========================================
-- Create view for CFDIs pending verification
-- ========================================

CREATE OR REPLACE VIEW vw_cfdis_sin_verificar AS
SELECT
    id,
    company_id,
    uuid,
    filename,
    rfc_emisor,
    rfc_receptor,
    total,
    fecha_emision,
    created_at
FROM expense_invoices
WHERE sat_status IS NULL
   OR sat_fecha_verificacion IS NULL
   OR sat_fecha_verificacion < NOW() - INTERVAL '30 days'
ORDER BY fecha_emision DESC;

COMMENT ON VIEW vw_cfdis_sin_verificar IS 'CFDIs que nunca se han verificado o cuya verificación tiene más de 30 días';

-- ========================================
-- Verification statistics function
-- ========================================

CREATE OR REPLACE FUNCTION get_cfdi_verification_stats(p_company_id INTEGER DEFAULT NULL)
RETURNS TABLE(
    total_cfdis BIGINT,
    vigentes BIGINT,
    cancelados BIGINT,
    sustituidos BIGINT,
    por_cancelar BIGINT,
    no_encontrados BIGINT,
    sin_verificar BIGINT,
    porcentaje_vigentes NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*) as total_cfdis,
        COUNT(*) FILTER (WHERE sat_status = 'vigente') as vigentes,
        COUNT(*) FILTER (WHERE sat_status = 'cancelado') as cancelados,
        COUNT(*) FILTER (WHERE sat_status = 'sustituido') as sustituidos,
        COUNT(*) FILTER (WHERE sat_status = 'por_cancelar') as por_cancelar,
        COUNT(*) FILTER (WHERE sat_status = 'no_encontrado') as no_encontrados,
        COUNT(*) FILTER (WHERE sat_status IS NULL) as sin_verificar,
        ROUND(
            (COUNT(*) FILTER (WHERE sat_status = 'vigente')::NUMERIC /
             NULLIF(COUNT(*) FILTER (WHERE sat_status IS NOT NULL), 0) * 100),
            2
        ) as porcentaje_vigentes
    FROM expense_invoices
    WHERE p_company_id IS NULL OR company_id = p_company_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_cfdi_verification_stats IS 'Obtiene estadísticas de verificación de CFDIs';

-- ========================================
-- Verification queries examples
-- ========================================

-- Verificar estadísticas de una compañía
-- SELECT * FROM get_cfdi_verification_stats(2);

-- Listar CFDIs cancelados
-- SELECT * FROM vw_cfdis_invalidos WHERE company_id = 2;

-- Listar CFDIs que necesitan verificación
-- SELECT * FROM vw_cfdis_sin_verificar WHERE company_id = 2 LIMIT 100;

-- Buscar CFDIs vigentes para deducción
-- SELECT id, uuid, total, rfc_emisor
-- FROM expense_invoices
-- WHERE company_id = 2
--   AND sat_status = 'vigente'
--   AND fecha_emision BETWEEN '2025-01-01' AND '2025-01-31';
