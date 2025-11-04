-- ============================================================================
-- MIGRACIÓN: Reemplazar paid_by por payment_account_id
-- Fecha: 2025-10-03
-- Objetivo: Establecer trazabilidad real con cuentas bancarias/efectivo
-- ============================================================================

-- ============================================================================
-- PASO 1: Crear cuenta "Desconocida" para gastos históricos
-- ============================================================================

INSERT OR IGNORE INTO user_payment_accounts (
    nombre,
    tipo,
    moneda,
    saldo_inicial,
    saldo_actual,
    propietario_id,
    company_id,
    activo,
    created_at,
    updated_at
)
SELECT
    'Cuenta Desconocida (Migración)',
    'efectivo',
    'MXN',
    0.0,
    0.0,
    1,  -- Usuario por defecto (ajustar según tu sistema)
    'default',
    1,
    datetime('now'),
    datetime('now')
WHERE NOT EXISTS (
    SELECT 1 FROM user_payment_accounts WHERE nombre = 'Cuenta Desconocida (Migración)'
);

-- ============================================================================
-- PASO 2: Agregar columna payment_account_id a expense_records
-- ============================================================================

ALTER TABLE expense_records ADD COLUMN payment_account_id INTEGER;

-- ============================================================================
-- PASO 3: Migrar datos existentes (mapeo inteligente)
-- ============================================================================

-- Crear tabla temporal para mapeo de paid_by → payment_account_id
CREATE TEMP TABLE paid_by_mapping (
    paid_by_text TEXT PRIMARY KEY,
    payment_account_id INTEGER,
    priority INTEGER
);

-- Mapear textos comunes a cuentas existentes
-- (Ajustar según tus cuentas reales en user_payment_accounts)
INSERT INTO paid_by_mapping (paid_by_text, payment_account_id, priority)
SELECT 'company_account', id, 1 FROM user_payment_accounts
WHERE tipo = 'banco' AND activo = 1
ORDER BY saldo_actual DESC LIMIT 1;

INSERT INTO paid_by_mapping (paid_by_text, payment_account_id, priority)
SELECT 'own_account', id, 2 FROM user_payment_accounts
WHERE tipo = 'efectivo' AND activo = 1
LIMIT 1;

-- Cuenta por defecto para valores desconocidos
INSERT INTO paid_by_mapping (paid_by_text, payment_account_id, priority)
SELECT 'default', id, 99 FROM user_payment_accounts
WHERE nombre = 'Cuenta Desconocida (Migración)'
LIMIT 1;

-- Actualizar expense_records con mapeo
UPDATE expense_records
SET payment_account_id = (
    SELECT COALESCE(
        (SELECT payment_account_id FROM paid_by_mapping WHERE paid_by_text = expense_records.paid_by),
        (SELECT payment_account_id FROM paid_by_mapping WHERE paid_by_text = 'default')
    )
)
WHERE payment_account_id IS NULL;

-- ============================================================================
-- PASO 4: Hacer payment_account_id obligatorio (NOT NULL)
-- ============================================================================

-- Verificar que NO haya NULLs antes de continuar
SELECT
    COUNT(*) as gastos_sin_cuenta,
    CASE
        WHEN COUNT(*) = 0 THEN '✅ LISTO para NOT NULL'
        ELSE '❌ HAY GASTOS SIN CUENTA - REVISAR'
    END as status
FROM expense_records
WHERE payment_account_id IS NULL;

-- Si la verificación pasa, crear tabla nueva con constraint
CREATE TABLE expense_records_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    external_reference TEXT,
    description TEXT NOT NULL,
    amount REAL NOT NULL,
    currency TEXT DEFAULT 'MXN',
    expense_date TEXT,
    category TEXT,
    provider_name TEXT,
    provider_rfc TEXT,
    workflow_status TEXT NOT NULL DEFAULT 'draft',
    invoice_status TEXT NOT NULL DEFAULT 'pendiente',
    invoice_uuid TEXT,
    invoice_folio TEXT,
    invoice_url TEXT,
    tax_total REAL,
    tax_metadata TEXT,
    payment_method TEXT,
    payment_account_id INTEGER NOT NULL,  -- ← AHORA OBLIGATORIO
    will_have_cfdi INTEGER NOT NULL DEFAULT 1,
    bank_status TEXT NOT NULL DEFAULT 'pendiente',
    account_code TEXT,
    metadata TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    company_id TEXT NOT NULL DEFAULT 'default',
    ticket_id INTEGER,  -- ← Nuevo campo
    is_advance INTEGER NOT NULL DEFAULT 0,
    is_ppd INTEGER NOT NULL DEFAULT 0,
    asset_class TEXT,
    payment_terms TEXT,
    last_payment_date TEXT,
    total_paid REAL DEFAULT 0,
    FOREIGN KEY (account_code) REFERENCES accounts(code),
    FOREIGN KEY (payment_account_id) REFERENCES user_payment_accounts(id),
    FOREIGN KEY (ticket_id) REFERENCES tickets(id)
);

-- Copiar datos
INSERT INTO expense_records_new
SELECT
    id, external_reference, description, amount, currency,
    expense_date, category, provider_name, provider_rfc,
    workflow_status, invoice_status, invoice_uuid, invoice_folio,
    invoice_url, tax_total, tax_metadata, payment_method,
    payment_account_id,  -- Ya no incluimos paid_by
    will_have_cfdi, bank_status, account_code, metadata,
    created_at, updated_at, company_id,
    NULL as ticket_id,  -- Por ahora NULL, se llenará después
    is_advance, is_ppd, asset_class, payment_terms,
    last_payment_date, total_paid
FROM expense_records;

-- Reemplazar tabla
DROP TABLE expense_records;
ALTER TABLE expense_records_new RENAME TO expense_records;

-- Recrear índices
CREATE INDEX idx_expense_records_date ON expense_records(expense_date);
CREATE INDEX idx_expense_records_status ON expense_records(invoice_status);
CREATE INDEX idx_expense_records_bank_status ON expense_records(bank_status);
CREATE INDEX idx_expense_records_company ON expense_records(company_id);
CREATE INDEX idx_expense_records_payment_account ON expense_records(payment_account_id);
CREATE INDEX idx_expense_records_ticket ON expense_records(ticket_id);

-- ============================================================================
-- PASO 5: Agregar payment_account_id a tickets
-- ============================================================================

ALTER TABLE tickets ADD COLUMN payment_account_id INTEGER;
ALTER TABLE tickets ADD COLUMN linked_expense_id INTEGER;

CREATE INDEX idx_tickets_payment_account ON tickets(payment_account_id);
CREATE INDEX idx_tickets_linked_expense ON tickets(linked_expense_id);

-- ============================================================================
-- PASO 6: Agregar payment_account_id a expense_payments
-- ============================================================================

ALTER TABLE expense_payments ADD COLUMN payment_account_id INTEGER;

CREATE INDEX idx_expense_payments_payment_account ON expense_payments(payment_account_id);

-- ============================================================================
-- PASO 7: Agregar payment_account_id a bank_movements
-- ============================================================================

ALTER TABLE bank_movements ADD COLUMN payment_account_id INTEGER;

CREATE INDEX idx_bank_movements_payment_account ON bank_movements(payment_account_id);

-- ============================================================================
-- VERIFICACIÓN FINAL
-- ============================================================================

SELECT '✅ MIGRACIÓN COMPLETADA' as status;

-- Ver estadísticas
SELECT
    'Gastos migrados' as tipo,
    COUNT(*) as total,
    COUNT(DISTINCT payment_account_id) as cuentas_distintas
FROM expense_records

UNION ALL

SELECT
    'Cuentas disponibles',
    COUNT(*),
    COUNT(DISTINCT tipo)
FROM user_payment_accounts
WHERE activo = 1;

-- ============================================================================
-- NOTAS IMPORTANTES
-- ============================================================================

/*
⚠️  DESPUÉS DE ESTA MIGRACIÓN:

1. Actualizar endpoint POST /expenses para requerir payment_account_id
2. Actualizar UI para mostrar selector de cuentas
3. Eliminar referencias a paid_by en el código frontend
4. Actualizar validaciones del backend

🔧 ROLLBACK (si algo sale mal):
    - Restaurar backup de la base de datos
    - Revisar logs de errores en la consola

✅ PRÓXIMOS PASOS:
    - Implementar selector de cuentas en voice-expenses
    - Implementar selector de cuentas en tickets
    - Conectar con conciliación bancaria
*/
