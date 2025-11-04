-- Migración 015: Crear tabla de cuentas de pago de usuarios
-- Fecha: 2025-09-27
-- Descripción: Tabla para gestionar cuentas bancarias, efectivo, terminales y tarjetas de crédito

-- =====================================================
-- TABLA: user_payment_accounts
-- =====================================================

CREATE TABLE IF NOT EXISTS user_payment_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Información básica de la cuenta
    nombre TEXT NOT NULL,                           -- "BBVA terminación 5678", "Amex corporativa"
    tipo TEXT NOT NULL CHECK (tipo IN (            -- Categoría general
        'banco',
        'efectivo',
        'terminal',
        'tarjeta_credito',
        'tarjeta_debito'
    )),

    -- Configuración financiera básica
    moneda TEXT NOT NULL DEFAULT 'MXN',            -- MXN, USD, etc.
    saldo_inicial REAL NOT NULL DEFAULT 0.0,       -- Saldo inicial o deuda inicial
    saldo_actual REAL NOT NULL DEFAULT 0.0,        -- Saldo actual (calculado)

    -- Configuración específica para tarjetas de crédito
    limite_credito REAL DEFAULT NULL,              -- Monto máximo disponible (solo tarjetas crédito)
    fecha_corte INTEGER DEFAULT NULL,              -- Día del mes que cierra (1-31, solo tarjetas crédito)
    fecha_pago INTEGER DEFAULT NULL,               -- Día límite de pago (1-31, solo tarjetas crédito)
    credito_disponible REAL DEFAULT NULL,          -- Calculado: limite_credito - saldo_actual

    -- Relaciones
    propietario_id INTEGER NOT NULL,               -- user_id del dueño
    tenant_id INTEGER NOT NULL,                    -- tenant al que pertenece

    -- Metadatos específicos por tipo
    proveedor_terminal TEXT,                       -- Solo para tipo='terminal': Clip, MercadoPago, Zettle
    banco_nombre TEXT,                             -- Para tipo='banco' o tarjetas: BBVA, Banamex, etc.
    numero_tarjeta TEXT,                           -- Últimos 4 dígitos para tarjetas: "1234"
    numero_cuenta_enmascarado TEXT,                -- "****5678" para cuentas bancarias
    numero_identificacion TEXT,                    -- CLABE, número completo enmascarado, etc.

    -- Estado y auditoría
    activo BOOLEAN NOT NULL DEFAULT TRUE,          -- Para desactivar sin borrar
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Claves foráneas
    FOREIGN KEY (propietario_id) REFERENCES users(id),
    FOREIGN KEY (tenant_id) REFERENCES tenants(id),

    -- Constraints para validar campos específicos de tarjetas de crédito
    CHECK (
        CASE
            WHEN tipo = 'tarjeta_credito' THEN
                limite_credito IS NOT NULL AND
                fecha_corte IS NOT NULL AND
                fecha_pago IS NOT NULL AND
                numero_tarjeta IS NOT NULL AND
                fecha_corte BETWEEN 1 AND 31 AND
                fecha_pago BETWEEN 1 AND 31
            ELSE TRUE
        END
    ),

    -- Constraint para validar que límite de crédito sea positivo
    CHECK (limite_credito IS NULL OR limite_credito > 0),

    -- Constraint para validar que fechas sean válidas
    CHECK (fecha_corte IS NULL OR (fecha_corte BETWEEN 1 AND 31)),
    CHECK (fecha_pago IS NULL OR (fecha_pago BETWEEN 1 AND 31))
);

-- =====================================================
-- ÍNDICES
-- =====================================================

-- Índice por propietario y estado activo (consulta más común)
CREATE INDEX IF NOT EXISTS idx_user_payment_accounts_propietario_activo
ON user_payment_accounts(propietario_id, activo);

-- Índice por tenant
CREATE INDEX IF NOT EXISTS idx_user_payment_accounts_tenant
ON user_payment_accounts(tenant_id);

-- Índice por tipo de cuenta
CREATE INDEX IF NOT EXISTS idx_user_payment_accounts_tipo
ON user_payment_accounts(tipo);

-- Índice compuesto para búsquedas por usuario, tipo y estado
CREATE INDEX IF NOT EXISTS idx_user_payment_accounts_usuario_tipo_activo
ON user_payment_accounts(propietario_id, tipo, activo);

-- Índice para tarjetas por fecha de corte (útil para reportes de facturación)
CREATE INDEX IF NOT EXISTS idx_user_payment_accounts_fecha_corte
ON user_payment_accounts(fecha_corte) WHERE tipo = 'tarjeta_credito';

-- =====================================================
-- TRIGGERS PARA MANTENER CÁLCULOS AUTOMÁTICOS
-- =====================================================

-- Trigger para actualizar updated_at automáticamente
CREATE TRIGGER IF NOT EXISTS trigger_user_payment_accounts_updated_at
    AFTER UPDATE ON user_payment_accounts
    FOR EACH ROW
BEGIN
    UPDATE user_payment_accounts
    SET updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.id;
END;

-- Trigger para inicializar saldo_actual con saldo_inicial
CREATE TRIGGER IF NOT EXISTS trigger_user_payment_accounts_init_saldo
    AFTER INSERT ON user_payment_accounts
    FOR EACH ROW
    WHEN NEW.saldo_actual = 0 AND NEW.saldo_inicial != 0
BEGIN
    UPDATE user_payment_accounts
    SET saldo_actual = NEW.saldo_inicial
    WHERE id = NEW.id;
END;

-- Trigger para calcular crédito disponible en tarjetas de crédito
CREATE TRIGGER IF NOT EXISTS trigger_user_payment_accounts_credito_disponible
    AFTER UPDATE OF saldo_actual, limite_credito ON user_payment_accounts
    FOR EACH ROW
    WHEN NEW.tipo = 'tarjeta_credito'
BEGIN
    UPDATE user_payment_accounts
    SET credito_disponible = COALESCE(NEW.limite_credito, 0) - COALESCE(NEW.saldo_actual, 0)
    WHERE id = NEW.id;
END;

-- Trigger para calcular crédito disponible al insertar tarjeta de crédito
CREATE TRIGGER IF NOT EXISTS trigger_user_payment_accounts_credito_disponible_insert
    AFTER INSERT ON user_payment_accounts
    FOR EACH ROW
    WHEN NEW.tipo = 'tarjeta_credito'
BEGIN
    UPDATE user_payment_accounts
    SET credito_disponible = COALESCE(NEW.limite_credito, 0) - COALESCE(NEW.saldo_actual, 0)
    WHERE id = NEW.id;
END;

-- =====================================================
-- DATOS DE EJEMPLO
-- =====================================================

-- Insertar cuentas de ejemplo para el usuario de prueba (si existe)
INSERT OR IGNORE INTO user_payment_accounts (
    nombre, tipo, moneda, saldo_inicial, saldo_actual,
    propietario_id, tenant_id, banco_nombre, numero_cuenta_enmascarado
)
SELECT
    'BBVA Empresarial ****5678', 'banco', 'MXN', 50000.00, 50000.00,
    u.id, u.tenant_id, 'BBVA', '****5678'
FROM users u
WHERE u.email = 'dgomezes96@gmail.com'
AND NOT EXISTS (
    SELECT 1 FROM user_payment_accounts
    WHERE propietario_id = u.id AND tipo = 'banco'
);

INSERT OR IGNORE INTO user_payment_accounts (
    nombre, tipo, moneda, saldo_inicial, saldo_actual,
    propietario_id, tenant_id
)
SELECT
    'Efectivo Caja Chica', 'efectivo', 'MXN', 5000.00, 5000.00,
    u.id, u.tenant_id
FROM users u
WHERE u.email = 'dgomezes96@gmail.com'
AND NOT EXISTS (
    SELECT 1 FROM user_payment_accounts
    WHERE propietario_id = u.id AND tipo = 'efectivo'
);

INSERT OR IGNORE INTO user_payment_accounts (
    nombre, tipo, moneda, saldo_inicial, saldo_actual,
    propietario_id, tenant_id, proveedor_terminal
)
SELECT
    'Terminal Clip Centro', 'terminal', 'MXN', 0.00, 0.00,
    u.id, u.tenant_id, 'Clip'
FROM users u
WHERE u.email = 'dgomezes96@gmail.com'
AND NOT EXISTS (
    SELECT 1 FROM user_payment_accounts
    WHERE propietario_id = u.id AND tipo = 'terminal'
);

-- Ejemplo de tarjeta de crédito
INSERT OR IGNORE INTO user_payment_accounts (
    nombre, tipo, moneda, saldo_inicial, saldo_actual,
    propietario_id, tenant_id, banco_nombre, numero_tarjeta,
    limite_credito, fecha_corte, fecha_pago
)
SELECT
    'BBVA Visa Corporativa 1234', 'tarjeta_credito', 'MXN', 5000.00, 5000.00,
    u.id, u.tenant_id, 'BBVA', '1234',
    100000.00, 15, 5  -- Límite 100k, corte día 15, pago día 5
FROM users u
WHERE u.email = 'dgomezes96@gmail.com'
AND NOT EXISTS (
    SELECT 1 FROM user_payment_accounts
    WHERE propietario_id = u.id AND tipo = 'tarjeta_credito'
);

-- =====================================================
-- VISTA PARA CONSULTAS COMUNES
-- =====================================================

CREATE VIEW IF NOT EXISTS user_payment_accounts_view AS
SELECT
    upa.id,
    upa.nombre,
    upa.tipo,
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

    -- Campos calculados
    CASE
        WHEN upa.tipo = 'banco' THEN upa.banco_nombre || ' ' || COALESCE(upa.numero_cuenta_enmascarado, '')
        WHEN upa.tipo = 'tarjeta_credito' THEN upa.banco_nombre || ' ' || upa.numero_tarjeta
        WHEN upa.tipo = 'terminal' THEN 'Terminal ' || COALESCE(upa.proveedor_terminal, 'Genérico')
        ELSE upa.nombre
    END as nombre_completo,

    CASE
        WHEN upa.tipo = 'tarjeta_credito' THEN
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
        WHEN upa.tipo = 'tarjeta_credito' THEN
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
VALUES ('015', 'Add user_payment_accounts table with credit card support', CURRENT_TIMESTAMP);

-- =====================================================
-- EJEMPLOS DE USO COMENTADOS
-- =====================================================

/*
EJEMPLOS DE USO:

1. Crear tarjeta de crédito:
INSERT INTO user_payment_accounts (
    nombre, tipo, moneda, saldo_inicial, propietario_id, tenant_id,
    banco_nombre, numero_tarjeta, limite_credito, fecha_corte, fecha_pago
) VALUES (
    'Amex Corporativa 9876', 'tarjeta_credito', 'MXN', 15000.00, 1, 1,
    'American Express', '9876', 200000.00, 20, 10
);

2. Crear cuenta bancaria:
INSERT INTO user_payment_accounts (
    nombre, tipo, moneda, saldo_inicial, propietario_id, tenant_id,
    banco_nombre, numero_cuenta_enmascarado
) VALUES (
    'BBVA Empresarial ****1234', 'banco', 'MXN', 100000.00, 1, 1,
    'BBVA', '****1234'
);

3. Consultar tarjetas con crédito disponible:
SELECT nombre, credito_disponible, porcentaje_usado, estado_saldo
FROM user_payment_accounts_view
WHERE propietario_id = 1 AND tipo = 'tarjeta_credito' AND activo = TRUE
ORDER BY credito_disponible DESC;

4. Consultar cuentas por fechas de corte próximas:
SELECT nombre, fecha_corte, fecha_pago, saldo_actual, limite_credito
FROM user_payment_accounts_view
WHERE tipo = 'tarjeta_credito'
AND activo = TRUE
AND fecha_corte BETWEEN DAY(date('now')) AND DAY(date('now', '+7 days'));
*/