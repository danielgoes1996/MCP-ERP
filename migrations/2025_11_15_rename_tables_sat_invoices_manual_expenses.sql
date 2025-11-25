-- =====================================================================
-- MIGRACIÓN: Renombrado de Tablas para Nomenclatura Clara
-- Fecha: 2025-11-15
-- Descripción:
--   - sat_invoices → sat_invoices
--   - expenses → manual_expenses
--   - Deprecar expense_invoices (legacy, sin uso)
-- =====================================================================

BEGIN;

-- =====================================================================
-- PASO 1: Renombrar sat_invoices → sat_invoices
-- =====================================================================

-- 1.1 Renombrar la tabla principal
ALTER TABLE sat_invoices RENAME TO sat_invoices;

-- 1.2 Renombrar índices
ALTER INDEX universal_invoice_sessions_pkey RENAME TO sat_invoices_pkey;
ALTER INDEX idx_universal_invoice_sessions_accounting_code RENAME TO idx_sat_invoices_accounting_code;
ALTER INDEX idx_universal_invoice_sessions_accounting_status RENAME TO idx_sat_invoices_accounting_status;
ALTER INDEX idx_universal_invoice_sessions_company RENAME TO idx_sat_invoices_company;
ALTER INDEX idx_universal_invoice_sessions_company_accounting RENAME TO idx_sat_invoices_company_accounting;
ALTER INDEX idx_universal_invoice_sessions_created RENAME TO idx_sat_invoices_created;
ALTER INDEX idx_universal_invoice_sessions_sat_pending RENAME TO idx_sat_invoices_sat_pending;
ALTER INDEX idx_universal_invoice_sessions_sat_status RENAME TO idx_sat_invoices_sat_status;
ALTER INDEX idx_universal_invoice_sessions_status RENAME TO idx_sat_invoices_status;

-- 1.3 Renombrar secuencias (si existen)
-- No hay secuencias auto-increment en esta tabla (usa TEXT id)

-- 1.4 Actualizar foreign keys que apuntan a sat_invoices
ALTER TABLE sat_verification_history
    DROP CONSTRAINT IF EXISTS sat_verification_history_session_id_fkey,
    ADD CONSTRAINT sat_verification_history_sat_invoice_id_fkey
    FOREIGN KEY (session_id) REFERENCES sat_invoices(id) ON DELETE CASCADE;

-- 1.5 Comentario de documentación
COMMENT ON TABLE sat_invoices IS
'Facturas SAT (CFDIs) procesadas desde XML.
Anteriormente: sat_invoices.
Features: Clasificación contable automática, validación SAT, embeddings.';

-- =====================================================================
-- PASO 2: Renombrar expenses → manual_expenses
-- =====================================================================

-- 2.1 Renombrar la tabla
ALTER TABLE manual_expenses RENAME TO manual_expenses;

-- 2.2 Renombrar índices
ALTER INDEX expenses_pkey RENAME TO manual_expenses_pkey;
ALTER INDEX idx_expenses_centro_costo RENAME TO idx_manual_expenses_centro_costo;
ALTER INDEX idx_expenses_company RENAME TO idx_manual_expenses_company;
ALTER INDEX idx_expenses_completion RENAME TO idx_manual_expenses_completion;
ALTER INDEX idx_expenses_date RENAME TO idx_manual_expenses_date;
ALTER INDEX idx_expenses_deducible RENAME TO idx_manual_expenses_deducible;
ALTER INDEX idx_expenses_duplicate_risk RENAME TO idx_manual_expenses_duplicate_risk;
ALTER INDEX idx_expenses_forma_pago RENAME TO idx_manual_expenses_forma_pago;
ALTER INDEX idx_expenses_metodo_forma RENAME TO idx_manual_expenses_metodo_forma;
ALTER INDEX idx_expenses_metodo_pago RENAME TO idx_manual_expenses_metodo_pago;
ALTER INDEX idx_expenses_provider_rfc RENAME TO idx_manual_expenses_provider_rfc;
ALTER INDEX idx_expenses_proyecto RENAME TO idx_manual_expenses_proyecto;
ALTER INDEX idx_expenses_tenant RENAME TO idx_manual_expenses_tenant;
ALTER INDEX idx_expenses_trend_category RENAME TO idx_manual_expenses_trend_category;

-- 2.3 Renombrar secuencia
ALTER SEQUENCE expenses_id_seq RENAME TO manual_expenses_id_seq;

-- 2.4 Actualizar default del ID para usar nueva secuencia
ALTER TABLE manual_expenses
    ALTER COLUMN id SET DEFAULT nextval('manual_expenses_id_seq'::regclass);

-- 2.5 Actualizar foreign keys que apuntan a manual_expenses
ALTER TABLE bulk_invoice_batch_items
    DROP CONSTRAINT IF EXISTS bulk_invoice_batch_items_matched_expense_id_fkey,
    ADD CONSTRAINT bulk_invoice_batch_items_matched_manual_expense_id_fkey
    FOREIGN KEY (matched_expense_id) REFERENCES manual_expenses(id);

ALTER TABLE expense_field_changes
    DROP CONSTRAINT IF EXISTS expense_field_changes_expense_id_fkey,
    ADD CONSTRAINT expense_field_changes_manual_expense_id_fkey
    FOREIGN KEY (expense_id) REFERENCES manual_expenses(id) ON DELETE CASCADE;

ALTER TABLE expense_non_reconciliation
    DROP CONSTRAINT IF EXISTS expense_non_reconciliation_expense_id_fkey,
    ADD CONSTRAINT expense_non_reconciliation_manual_expense_id_fkey
    FOREIGN KEY (expense_id) REFERENCES manual_expenses(id) ON DELETE CASCADE;

-- 2.6 Actualizar foreign keys desde manual_expenses a otras tablas
ALTER TABLE manual_expenses
    DROP CONSTRAINT IF EXISTS expenses_company_id_fkey,
    ADD CONSTRAINT manual_expenses_company_id_fkey
    FOREIGN KEY (company_id) REFERENCES companies(id);

ALTER TABLE manual_expenses
    DROP CONSTRAINT IF EXISTS expenses_invoice_id_fkey,
    ADD CONSTRAINT manual_expenses_invoice_id_fkey
    FOREIGN KEY (invoice_id) REFERENCES expense_invoices(id);

ALTER TABLE manual_expenses
    DROP CONSTRAINT IF EXISTS expenses_payment_account_id_fkey,
    ADD CONSTRAINT manual_expenses_payment_account_id_fkey
    FOREIGN KEY (payment_account_id) REFERENCES payment_accounts(id);

ALTER TABLE manual_expenses
    DROP CONSTRAINT IF EXISTS expenses_tenant_id_fkey,
    ADD CONSTRAINT manual_expenses_tenant_id_fkey
    FOREIGN KEY (tenant_id) REFERENCES tenants(id);

-- 2.7 Actualizar CHECK constraints
ALTER TABLE manual_expenses
    DROP CONSTRAINT IF EXISTS expenses_metodo_pago_check,
    ADD CONSTRAINT manual_expenses_metodo_pago_check
    CHECK (metodo_pago::text = ANY (ARRAY['PUE'::character varying, 'PPD'::character varying, 'PIP'::character varying]::text[]));

-- 2.8 Comentario de documentación
COMMENT ON TABLE manual_expenses IS
'Gastos capturados manualmente por usuarios (voz, foto, texto).
Anteriormente: expenses.
Features: ML autocomplete, duplicate detection, voice/photo capture.
Puede vincularse opcionalmente con sat_invoices via invoice_id.';

-- =====================================================================
-- PASO 3: Deprecar expense_invoices (legacy, sin uso)
-- =====================================================================

-- 3.1 Agregar comentario de deprecación
COMMENT ON TABLE expense_invoices IS
'⚠️ DEPRECADA - Sistema legacy de facturas (sin uso actual).
Esta tabla será eliminada en futuras migraciones.
Usar sat_invoices para nuevas facturas SAT.
Estado: 0 registros, sin referencias activas.';

-- 3.2 Verificar que no tiene datos (safety check)
DO $$
DECLARE
    record_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO record_count FROM expense_invoices;

    IF record_count > 0 THEN
        RAISE EXCEPTION 'expense_invoices contiene % registros. Migrar datos antes de deprecar.', record_count;
    END IF;

    RAISE NOTICE 'expense_invoices verificada: 0 registros (segura para deprecar)';
END $$;

-- =====================================================================
-- PASO 4: Crear vistas de compatibilidad (opcional)
-- =====================================================================

-- Vista de compatibilidad para código legacy que use sat_invoices
CREATE OR REPLACE VIEW sat_invoices AS
SELECT * FROM sat_invoices;

COMMENT ON VIEW sat_invoices IS
'Vista de compatibilidad temporal.
Apunta a sat_invoices (renombrada el 2025-11-15).
⚠️ DEPRECADA - Actualizar código para usar sat_invoices directamente.';

-- Vista de compatibilidad para código legacy que use expenses
CREATE OR REPLACE VIEW expenses AS
SELECT * FROM manual_expenses;

COMMENT ON VIEW expenses IS
'Vista de compatibilidad temporal.
Apunta a manual_expenses (renombrada el 2025-11-15).
⚠️ DEPRECADA - Actualizar código para usar manual_expenses directamente.';

-- =====================================================================
-- PASO 5: Documentación y resumen
-- =====================================================================

-- Crear tabla de registro de migración (si no existe)
-- La tabla ya existe, solo registrar la migración
INSERT INTO schema_migrations (id, version, description)
VALUES (
    8,
    '2025_11_15_rename_tables_sat_invoices_manual_expenses',
    'Renombrado de tablas para nomenclatura clara:
    - sat_invoices → sat_invoices
    - expenses → manual_expenses
    - expense_invoices marcada como DEPRECADA
    Incluye actualización de índices, secuencias, y foreign keys.'
)
ON CONFLICT (version) DO NOTHING;

-- =====================================================================
-- COMMIT
-- =====================================================================

COMMIT;

-- =====================================================================
-- VERIFICACIÓN POST-MIGRACIÓN
-- =====================================================================

-- Verificar que las tablas existen
SELECT
    'sat_invoices' as tabla,
    COUNT(*) as registros
FROM sat_invoices
UNION ALL
SELECT
    'manual_expenses' as tabla,
    COUNT(*) as registros
FROM manual_expenses
UNION ALL
SELECT
    'expense_invoices (legacy)' as tabla,
    COUNT(*) as registros
FROM expense_invoices;

-- Listar índices de las nuevas tablas
SELECT
    tablename,
    indexname
FROM pg_indexes
WHERE tablename IN ('sat_invoices', 'manual_expenses')
ORDER BY tablename, indexname;

-- Verificar foreign keys
SELECT
    conname AS constraint_name,
    conrelid::regclass AS table_name,
    confrelid::regclass AS referenced_table
FROM pg_constraint
WHERE contype = 'f'
AND (conrelid::regclass::text IN ('sat_invoices', 'manual_expenses')
     OR confrelid::regclass::text IN ('sat_invoices', 'manual_expenses'))
ORDER BY table_name, constraint_name;

DO $$
BEGIN
    RAISE NOTICE '✅ Migración completada exitosamente';
    RAISE NOTICE 'Nuevas tablas: sat_invoices, manual_expenses';
    RAISE NOTICE 'Tablas deprecadas: expense_invoices';
    RAISE NOTICE 'Vistas de compatibilidad: sat_invoices → sat_invoices, expenses → manual_expenses';
END $$;
