-- Migración 017: Agregar campos bancarios adicionales
-- Fecha: 2025-09-27
-- Descripción: Agregar campos para número de cuenta bancaria y CLABE

-- =====================================================
-- PASO 1: AGREGAR NUEVOS CAMPOS
-- =====================================================

-- Agregar campo para número de cuenta bancaria completo
ALTER TABLE user_payment_accounts ADD COLUMN numero_cuenta TEXT;

-- Agregar campo para CLABE interbancaria
ALTER TABLE user_payment_accounts ADD COLUMN clabe TEXT;

-- =====================================================
-- PASO 2: CREAR ÍNDICES PARA BÚSQUEDAS
-- =====================================================

-- Índice para búsquedas por CLABE
CREATE INDEX IF NOT EXISTS idx_user_payment_accounts_clabe
ON user_payment_accounts(clabe) WHERE clabe IS NOT NULL;

-- Índice para búsquedas por número de cuenta
CREATE INDEX IF NOT EXISTS idx_user_payment_accounts_numero_cuenta
ON user_payment_accounts(numero_cuenta) WHERE numero_cuenta IS NOT NULL;

-- =====================================================
-- PASO 3: ACTUALIZAR VISTA
-- =====================================================

-- Recrear la vista con los nuevos campos
DROP VIEW IF EXISTS user_payment_accounts_view;

CREATE VIEW user_payment_accounts_view AS
SELECT
    upa.id,
    upa.nombre,
    upa.tipo,
    upa.subtipo,
    upa.moneda,
    upa.saldo_inicial,
    upa.saldo_actual,
    upa.limite_credito,
    upa.credito_disponible,
    upa.fecha_corte,
    upa.fecha_pago,
    upa.propietario_id,
    u.email as propietario_email,
    u.full_name as propietario_nombre,
    upa.tenant_id,
    t.name as tenant_nombre,
    upa.proveedor_terminal,
    upa.banco_nombre,
    upa.numero_tarjeta,
    upa.numero_cuenta,
    upa.numero_cuenta_enmascarado,
    upa.clabe,
    upa.activo,
    upa.created_at,
    upa.updated_at,

    -- Nombre completo mejorado
    CASE
        WHEN upa.tipo = 'bancaria' AND upa.subtipo = 'debito' THEN
            upa.banco_nombre || ' Débito ' || COALESCE(upa.numero_cuenta_enmascarado, COALESCE(upa.numero_tarjeta, ''))
        WHEN upa.tipo = 'bancaria' AND upa.subtipo = 'credito' THEN
            upa.banco_nombre || ' Crédito ' || upa.numero_tarjeta
        WHEN upa.tipo = 'terminal' THEN
            'Terminal ' || COALESCE(upa.proveedor_terminal, 'Genérico')
        ELSE upa.nombre
    END as nombre_completo,

    -- Tipo descriptivo
    CASE
        WHEN upa.tipo = 'bancaria' AND upa.subtipo = 'debito' THEN 'Cuenta Bancaria (Débito)'
        WHEN upa.tipo = 'bancaria' AND upa.subtipo = 'credito' THEN 'Cuenta Bancaria (Crédito)'
        WHEN upa.tipo = 'efectivo' THEN 'Efectivo'
        WHEN upa.tipo = 'terminal' THEN 'Terminal de Pago'
        ELSE upa.tipo
    END as tipo_descriptivo,

    -- Estado del saldo (mejorado)
    CASE
        WHEN upa.tipo = 'bancaria' AND upa.subtipo = 'credito' THEN
            CASE
                WHEN upa.credito_disponible > (upa.limite_credito * 0.8) THEN 'disponible'
                WHEN upa.credito_disponible > (upa.limite_credito * 0.5) THEN 'medio'
                WHEN upa.credito_disponible > 0 THEN 'bajo'
                ELSE 'sin_credito'
            END
        WHEN upa.saldo_actual > 0 THEN 'positivo'
        WHEN upa.saldo_actual = 0 THEN 'cero'
        ELSE 'negativo'
    END as estado_saldo,

    -- Información específica de tarjetas de crédito
    CASE
        WHEN upa.tipo = 'bancaria' AND upa.subtipo = 'credito' THEN
            ROUND((upa.saldo_actual / NULLIF(upa.limite_credito, 0)) * 100, 2)
        ELSE NULL
    END as porcentaje_usado

FROM user_payment_accounts upa
LEFT JOIN users u ON upa.propietario_id = u.id
LEFT JOIN tenants t ON upa.tenant_id = t.id;

-- =====================================================
-- PASO 4: AGREGAR CONSTRAINTS PARA VALIDACIÓN
-- =====================================================

-- Constraint para validar formato de CLABE (18 dígitos)
-- Nota: SQLite no tiene CHECK constraints completos, se maneja en la aplicación

-- =====================================================
-- REGISTRAR MIGRACIÓN
-- =====================================================

INSERT OR IGNORE INTO schema_migrations (version, description, applied_at)
VALUES ('017', 'Add numero_cuenta and clabe fields to payment accounts', CURRENT_TIMESTAMP);

-- =====================================================
-- EJEMPLOS DE VALIDACIÓN
-- =====================================================

/*
-- Verificar que los nuevos campos se agregaron correctamente:
PRAGMA table_info(user_payment_accounts);

-- Verificar la vista actualizada:
SELECT * FROM user_payment_accounts_view LIMIT 5;

-- Verificar índices creados:
SELECT name, sql FROM sqlite_master
WHERE type = 'index' AND tbl_name = 'user_payment_accounts'
AND name LIKE '%clabe%' OR name LIKE '%numero_cuenta%';
*/