-- Migración 016 Fix: Completar refactorización de cuentas de pago
-- Fecha: 2025-09-27
-- Descripción: Completar migración que falló parcialmente

-- =====================================================
-- PASO 1: MIGRAR DATOS EXISTENTES
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
-- PASO 2: CREAR TABLA TEMPORAL CON NUEVA ESTRUCTURA
-- =====================================================

CREATE TABLE user_payment_accounts_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Información básica de la cuenta
    nombre TEXT NOT NULL,
    tipo TEXT NOT NULL,
    subtipo TEXT,

    -- Configuración financiera básica
    moneda TEXT NOT NULL DEFAULT 'MXN',
    saldo_inicial REAL NOT NULL DEFAULT 0.0,
    saldo_actual REAL NOT NULL DEFAULT 0.0,

    -- Configuración específica para tarjetas de crédito
    limite_credito REAL DEFAULT NULL,
    fecha_corte INTEGER DEFAULT NULL,
    fecha_pago INTEGER DEFAULT NULL,
    credito_disponible REAL DEFAULT NULL,

    -- Relaciones
    propietario_id INTEGER NOT NULL,
    tenant_id INTEGER NOT NULL,

    -- Metadatos específicos por tipo
    proveedor_terminal TEXT,
    banco_nombre TEXT,
    numero_tarjeta TEXT,
    numero_cuenta_enmascarado TEXT,
    numero_identificacion TEXT,

    -- Estado y auditoría
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Claves foráneas
    FOREIGN KEY (propietario_id) REFERENCES users(id),
    FOREIGN KEY (tenant_id) REFERENCES tenants(id),

    -- Constraints para el nuevo modelo
    CHECK (tipo IN ('bancaria', 'efectivo', 'terminal')),
    CHECK (
        (tipo = 'bancaria' AND subtipo IN ('debito', 'credito')) OR
        (tipo IN ('efectivo', 'terminal') AND subtipo IS NULL)
    ),
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
    ),
    CHECK (
        CASE
            WHEN tipo = 'bancaria' THEN
                banco_nombre IS NOT NULL
            ELSE TRUE
        END
    ),
    CHECK (
        CASE
            WHEN tipo = 'terminal' THEN
                proveedor_terminal IS NOT NULL
            ELSE TRUE
        END
    ),
    CHECK (limite_credito IS NULL OR limite_credito > 0),
    CHECK (fecha_corte IS NULL OR (fecha_corte BETWEEN 1 AND 31)),
    CHECK (fecha_pago IS NULL OR (fecha_pago BETWEEN 1 AND 31))
);

-- =====================================================
-- PASO 3: COPIAR DATOS A LA NUEVA TABLA
-- =====================================================

INSERT INTO user_payment_accounts_new (
    id, nombre, tipo, subtipo, moneda, saldo_inicial, saldo_actual,
    limite_credito, fecha_corte, fecha_pago, credito_disponible,
    propietario_id, tenant_id, proveedor_terminal, banco_nombre,
    numero_tarjeta, numero_cuenta_enmascarado, numero_identificacion,
    activo, created_at, updated_at
)
SELECT
    id, nombre, tipo_nuevo, subtipo, moneda, saldo_inicial, saldo_actual,
    limite_credito, fecha_corte, fecha_pago, credito_disponible,
    propietario_id, tenant_id, proveedor_terminal, banco_nombre,
    numero_tarjeta, numero_cuenta_enmascarado, numero_identificacion,
    activo, created_at, updated_at
FROM user_payment_accounts;

-- =====================================================
-- PASO 4: REEMPLAZAR LA TABLA ORIGINAL
-- =====================================================

DROP TABLE user_payment_accounts;
ALTER TABLE user_payment_accounts_new RENAME TO user_payment_accounts;

-- =====================================================
-- PASO 5: RECREAR ÍNDICES
-- =====================================================

CREATE INDEX idx_user_payment_accounts_propietario_activo
ON user_payment_accounts(propietario_id, activo);

CREATE INDEX idx_user_payment_accounts_tenant
ON user_payment_accounts(tenant_id);

CREATE INDEX idx_user_payment_accounts_fecha_corte
ON user_payment_accounts(fecha_corte) WHERE tipo = 'bancaria' AND subtipo = 'credito';

CREATE INDEX idx_user_payment_accounts_tipo_subtipo
ON user_payment_accounts(tipo, subtipo);

CREATE INDEX idx_user_payment_accounts_usuario_tipo_subtipo_activo
ON user_payment_accounts(propietario_id, tipo, subtipo, activo);

-- =====================================================
-- PASO 6: RECREAR TRIGGERS
-- =====================================================

CREATE TRIGGER trigger_user_payment_accounts_updated_at
    AFTER UPDATE ON user_payment_accounts
    FOR EACH ROW
BEGIN
    UPDATE user_payment_accounts
    SET updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.id;
END;

CREATE TRIGGER trigger_user_payment_accounts_init_saldo
    AFTER INSERT ON user_payment_accounts
    FOR EACH ROW
    WHEN NEW.saldo_actual = 0 AND NEW.saldo_inicial != 0
BEGIN
    UPDATE user_payment_accounts
    SET saldo_actual = NEW.saldo_inicial
    WHERE id = NEW.id;
END;

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
-- PASO 7: RECREAR VISTA
-- =====================================================

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
-- REGISTRAR MIGRACIÓN
-- =====================================================

INSERT OR IGNORE INTO schema_migrations (version, description, applied_at)
VALUES ('016_fix', 'Complete payment accounts tipo/subtipo refactor', CURRENT_TIMESTAMP);