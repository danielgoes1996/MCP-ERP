-- =====================================================
-- MIGRACIÓN 037: Estandarizar account_type
-- =====================================================
-- Fecha: 2025-11-09
-- Descripción: Agregar constraint para account_type con valores estandarizados
--              Esto permite filtrar MSI solo para tarjetas de crédito

-- =====================================================
-- 1. ELIMINAR CONSTRAINT ANTERIOR (si existe)
-- =====================================================

ALTER TABLE payment_accounts
DROP CONSTRAINT IF EXISTS check_account_type_values;

-- =====================================================
-- 2. AGREGAR CONSTRAINT CON VALORES PERMITIDOS
-- =====================================================

ALTER TABLE payment_accounts
ADD CONSTRAINT check_account_type_values
CHECK (account_type IN (
    'credit_card',      -- Tarjeta de Crédito → Puede tener MSI
    'debit_card',       -- Tarjeta de Débito → NO MSI
    'checking',         -- Cuenta de Cheques → NO MSI
    'savings',          -- Cuenta de Ahorro → NO MSI
    'cash'              -- Efectivo → NO MSI
));

-- =====================================================
-- 3. HACER account_type OBLIGATORIO (OPCIONAL)
-- =====================================================

-- Comentado por ahora - descomentar cuando todas las cuentas tengan tipo
-- ALTER TABLE payment_accounts
-- ALTER COLUMN account_type SET NOT NULL;

-- =====================================================
-- 4. ÍNDICES PARA BÚSQUEDAS POR TIPO
-- =====================================================

-- Índice simple por tipo
CREATE INDEX IF NOT EXISTS idx_payment_accounts_account_type
ON payment_accounts(account_type);

-- Índice compuesto para búsquedas de MSI (solo credit cards)
CREATE INDEX IF NOT EXISTS idx_payment_accounts_company_credit_card
ON payment_accounts(company_id, account_type)
WHERE account_type = 'credit_card';

-- Índice por tenant y tipo
CREATE INDEX IF NOT EXISTS idx_payment_accounts_tenant_type
ON payment_accounts(tenant_id, account_type);

-- =====================================================
-- 5. ACTUALIZAR VALORES EXISTENTES (si los hay)
-- =====================================================

-- Convertir valores legacy a nuevos estándares
UPDATE payment_accounts
SET account_type = 'credit_card'
WHERE account_type IN ('tarjeta_credito', 'credito', 'tc', 'credit');

UPDATE payment_accounts
SET account_type = 'debit_card'
WHERE account_type IN ('tarjeta_debito', 'debito', 'td', 'debit', 'banco');

UPDATE payment_accounts
SET account_type = 'checking'
WHERE account_type IN ('cuenta_cheques', 'cheques', 'cuenta');

UPDATE payment_accounts
SET account_type = 'savings'
WHERE account_type IN ('ahorro', 'cuenta_ahorro');

UPDATE payment_accounts
SET account_type = 'cash'
WHERE account_type IN ('efectivo', 'caja');

-- =====================================================
-- 6. COMENTARIOS PARA DOCUMENTACIÓN
-- =====================================================

COMMENT ON COLUMN payment_accounts.account_type IS
'Tipo de cuenta:
- credit_card: Tarjeta de Crédito (puede tener MSI)
- debit_card: Tarjeta de Débito (sin MSI)
- checking: Cuenta de Cheques (sin MSI)
- savings: Cuenta de Ahorro (sin MSI)
- cash: Efectivo (sin MSI)';

-- =====================================================
-- 7. VISTA PARA VERIFICAR DISTRIBUCIÓN
-- =====================================================

CREATE OR REPLACE VIEW payment_accounts_type_distribution AS
SELECT
    account_type,
    COUNT(*) as total_accounts,
    COUNT(CASE WHEN status = 'active' THEN 1 END) as active_accounts,
    ARRAY_AGG(DISTINCT bank_name) as banks,
    CASE
        WHEN account_type = 'credit_card' THEN 'MSI Elegible'
        ELSE 'NO MSI'
    END as msi_eligibility
FROM payment_accounts
WHERE account_type IS NOT NULL
GROUP BY account_type
ORDER BY total_accounts DESC;

COMMENT ON VIEW payment_accounts_type_distribution IS
'Distribución de cuentas por tipo - útil para verificar migración';

-- =====================================================
-- 8. EJEMPLOS DE USO
-- =====================================================

/*
-- Ver distribución de tipos de cuenta:
SELECT * FROM payment_accounts_type_distribution;

-- Buscar solo tarjetas de crédito (para MSI):
SELECT * FROM payment_accounts
WHERE account_type = 'credit_card'
AND status = 'active';

-- Verificar cuentas sin tipo definido:
SELECT
    id,
    account_name,
    bank_name,
    account_type
FROM payment_accounts
WHERE account_type IS NULL;

-- Contar facturas por tipo de cuenta de pago:
SELECT
    pa.account_type,
    COUNT(ei.id) as total_invoices,
    SUM(CASE WHEN ei.forma_pago = '04' THEN 1 ELSE 0 END) as card_payments,
    SUM(CASE WHEN ei.es_msi = TRUE THEN 1 ELSE 0 END) as msi_payments
FROM expense_invoices ei
LEFT JOIN payment_accounts pa ON ei.payment_account_id = pa.id
WHERE pa.account_type IS NOT NULL
GROUP BY pa.account_type;
*/
