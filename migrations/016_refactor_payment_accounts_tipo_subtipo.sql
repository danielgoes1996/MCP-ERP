-- Migración 016: Refactorizar cuentas de pago con tipo/subtipo
-- Fecha: 2025-09-27
-- Descripción: Unificar modelo de cuentas eliminando confusión entre tarjetas y cuentas bancarias

-- =====================================================
-- PASO 1: AGREGAR NUEVAS COLUMNAS
-- =====================================================

-- Agregar columnas tipo_nuevo y subtipo
ALTER TABLE user_payment_accounts ADD COLUMN tipo_nuevo TEXT;
ALTER TABLE user_payment_accounts ADD COLUMN subtipo TEXT;

-- =====================================================
-- PASO 2: MIGRAR DATOS EXISTENTES
-- =====================================================

-- Mapear tipos actuales al nuevo esquema
UPDATE user_payment_accounts SET
    tipo_nuevo = 'bancaria',
    subtipo = 'debito'
WHERE tipo = 'banco';

UPDATE user_payment_accounts SET
    tipo_nuevo = 'bancaria',
    subtipo = 'debito'
WHERE tipo = 'tarjeta_debito';

UPDATE user_payment_accounts SET
    tipo_nuevo = 'bancaria',
    subtipo = 'credito'
WHERE tipo = 'tarjeta_credito';

UPDATE user_payment_accounts SET
    tipo_nuevo = 'efectivo',
    subtipo = NULL
WHERE tipo = 'efectivo';

UPDATE user_payment_accounts SET
    tipo_nuevo = 'terminal',
    subtipo = NULL
WHERE tipo = 'terminal';

-- =====================================================
-- PASO 3: RENOMBRAR COLUMNAS
-- =====================================================

-- Renombrar la columna tipo actual como tipo_legacy
ALTER TABLE user_payment_accounts RENAME COLUMN tipo TO tipo_legacy;

-- Renombrar tipo_nuevo como tipo
ALTER TABLE user_payment_accounts RENAME COLUMN tipo_nuevo TO tipo;

-- =====================================================
-- PASO 4: ACTUALIZAR CONSTRAINTS
-- =====================================================

-- Eliminar el constraint anterior
DROP INDEX IF EXISTS idx_user_payment_accounts_tipo;

-- Crear nuevos constraints
ALTER TABLE user_payment_accounts ADD CONSTRAINT check_tipo_values
CHECK (tipo IN ('bancaria', 'efectivo', 'terminal'));

ALTER TABLE user_payment_accounts ADD CONSTRAINT check_subtipo_values
CHECK (
    (tipo = 'bancaria' AND subtipo IN ('debito', 'credito')) OR
    (tipo IN ('efectivo', 'terminal') AND subtipo IS NULL)
);

-- Constraint para campos obligatorios de tarjetas de crédito
ALTER TABLE user_payment_accounts ADD CONSTRAINT check_credito_fields
CHECK (
    CASE
        WHEN tipo = 'bancaria' AND subtipo = 'credito' THEN
            limite_credito IS NOT NULL AND
            fecha_corte IS NOT NULL AND
            fecha_pago IS NOT NULL AND
            numero_tarjeta IS NOT NULL AND
            banco_nombre IS NOT NULL
        ELSE TRUE
    END
);

-- Constraint para campos bancarios
ALTER TABLE user_payment_accounts ADD CONSTRAINT check_bancaria_fields
CHECK (
    CASE
        WHEN tipo = 'bancaria' THEN
            banco_nombre IS NOT NULL
        ELSE TRUE
    END
);

-- Constraint para terminales
ALTER TABLE user_payment_accounts ADD CONSTRAINT check_terminal_fields
CHECK (
    CASE
        WHEN tipo = 'terminal' THEN
            proveedor_terminal IS NOT NULL
        ELSE TRUE
    END
);

-- =====================================================
-- PASO 5: ACTUALIZAR ÍNDICES
-- =====================================================

-- Índice por tipo y subtipo
CREATE INDEX IF NOT EXISTS idx_user_payment_accounts_tipo_subtipo
ON user_payment_accounts(tipo, subtipo);

-- Índice compuesto mejorado
DROP INDEX IF EXISTS idx_user_payment_accounts_usuario_tipo_activo;
CREATE INDEX IF NOT EXISTS idx_user_payment_accounts_usuario_tipo_subtipo_activo
ON user_payment_accounts(propietario_id, tipo, subtipo, activo);

-- =====================================================
-- PASO 6: ACTUALIZAR VISTA
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
    upa.numero_cuenta_enmascarado,
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
-- PASO 7: ACTUALIZAR TRIGGERS
-- =====================================================

-- Recrear trigger para crédito disponible (solo para tarjetas de crédito)
DROP TRIGGER IF EXISTS trigger_user_payment_accounts_credito_disponible;
DROP TRIGGER IF EXISTS trigger_user_payment_accounts_credito_disponible_insert;

CREATE TRIGGER trigger_user_payment_accounts_credito_disponible
    AFTER UPDATE OF saldo_actual, limite_credito ON user_payment_accounts
    FOR EACH ROW
    WHEN NEW.tipo = 'bancaria' AND NEW.subtipo = 'credito'
BEGIN
    UPDATE user_payment_accounts
    SET credito_disponible = COALESCE(NEW.limite_credito, 0) - COALESCE(NEW.saldo_actual, 0)
    WHERE id = NEW.id;
END;

CREATE TRIGGER trigger_user_payment_accounts_credito_disponible_insert
    AFTER INSERT ON user_payment_accounts
    FOR EACH ROW
    WHEN NEW.tipo = 'bancaria' AND NEW.subtipo = 'credito'
BEGIN
    UPDATE user_payment_accounts
    SET credito_disponible = COALESCE(NEW.limite_credito, 0) - COALESCE(NEW.saldo_actual, 0)
    WHERE id = NEW.id;
END;

-- =====================================================
-- PASO 8: DATOS DE EJEMPLO ACTUALIZADOS
-- =====================================================

-- Actualizar ejemplos existentes (si existen)
UPDATE user_payment_accounts
SET nombre = 'BBVA Cuenta Débito ****5678'
WHERE tipo_legacy = 'banco' AND banco_nombre = 'BBVA';

UPDATE user_payment_accounts
SET nombre = 'BBVA Tarjeta Crédito 1234'
WHERE tipo_legacy = 'tarjeta_credito' AND banco_nombre = 'BBVA';

-- =====================================================
-- PASO 9: LIMPIAR DATOS LEGACY (OPCIONAL)
-- =====================================================

-- Comentado por seguridad - descomentar después de validar migración
-- ALTER TABLE user_payment_accounts DROP COLUMN tipo_legacy;

-- =====================================================
-- REGISTRAR MIGRACIÓN
-- =====================================================

INSERT OR IGNORE INTO schema_migrations (version, description, applied_at)
VALUES ('016', 'Refactor payment accounts with tipo/subtipo structure', CURRENT_TIMESTAMP);

-- =====================================================
-- EJEMPLOS DE VALIDACIÓN
-- =====================================================

/*
-- Verificar migración exitosa:
SELECT
    tipo,
    subtipo,
    COUNT(*) as cantidad,
    GROUP_CONCAT(nombre, '; ') as ejemplos
FROM user_payment_accounts
GROUP BY tipo, subtipo;

-- Verificar constraints:
SELECT name, sql FROM sqlite_master
WHERE type = 'table' AND name = 'user_payment_accounts';

-- Verificar vista:
SELECT * FROM user_payment_accounts_view LIMIT 5;
*/