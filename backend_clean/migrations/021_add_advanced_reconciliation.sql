-- =====================================================
-- MIGRACIÓN 021: Conciliación Avanzada
-- =====================================================
-- Funcionalidades:
-- 1. Conciliación múltiple (split matching)
-- 2. Anticipos a empleados (gastos con tarjeta personal)
-- =====================================================

-- ======================================================
-- PARTE 1: CONCILIACIÓN MÚLTIPLE (SPLIT MATCHING)
-- ======================================================

-- Tabla para almacenar splits de conciliación
CREATE TABLE IF NOT EXISTS bank_reconciliation_splits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Identificador del grupo de conciliación
    split_group_id TEXT NOT NULL,

    -- Tipo de split
    split_type TEXT CHECK(split_type IN ('one_to_many', 'many_to_one')) NOT NULL,

    -- IDs relacionados
    expense_id INTEGER,
    movement_id INTEGER,

    -- Montos parciales
    allocated_amount REAL NOT NULL,
    percentage REAL,

    -- Metadata
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER,

    -- Verificación
    is_complete BOOLEAN DEFAULT FALSE,
    verified_at TIMESTAMP,

    FOREIGN KEY (expense_id) REFERENCES expense_records(id) ON DELETE CASCADE,
    FOREIGN KEY (movement_id) REFERENCES bank_movements(id) ON DELETE CASCADE
);

-- Índices para splits
CREATE INDEX IF NOT EXISTS idx_splits_group ON bank_reconciliation_splits(split_group_id);
CREATE INDEX IF NOT EXISTS idx_splits_expense ON bank_reconciliation_splits(expense_id);
CREATE INDEX IF NOT EXISTS idx_splits_movement ON bank_reconciliation_splits(movement_id);
CREATE INDEX IF NOT EXISTS idx_splits_type ON bank_reconciliation_splits(split_type);
CREATE INDEX IF NOT EXISTS idx_splits_complete ON bank_reconciliation_splits(is_complete);

-- Agregar columnas a expense_records para soporte de splits
ALTER TABLE expense_records ADD COLUMN reconciliation_type TEXT DEFAULT 'simple'
  CHECK(reconciliation_type IN ('simple', 'split', 'partial'));

ALTER TABLE expense_records ADD COLUMN split_group_id TEXT;

ALTER TABLE expense_records ADD COLUMN amount_reconciled REAL DEFAULT 0;

ALTER TABLE expense_records ADD COLUMN amount_pending REAL;

-- Agregar columnas a bank_movements para soporte de splits
ALTER TABLE bank_movements ADD COLUMN reconciliation_type TEXT DEFAULT 'simple'
  CHECK(reconciliation_type IN ('simple', 'split', 'partial'));

ALTER TABLE bank_movements ADD COLUMN split_group_id TEXT;

ALTER TABLE bank_movements ADD COLUMN amount_allocated REAL DEFAULT 0;

ALTER TABLE bank_movements ADD COLUMN amount_unallocated REAL;

-- Índices para columnas nuevas
CREATE INDEX IF NOT EXISTS idx_expense_reconciliation_type ON expense_records(reconciliation_type);
CREATE INDEX IF NOT EXISTS idx_expense_split_group ON expense_records(split_group_id);
CREATE INDEX IF NOT EXISTS idx_movement_reconciliation_type ON bank_movements(reconciliation_type);
CREATE INDEX IF NOT EXISTS idx_movement_split_group ON bank_movements(split_group_id);

-- ======================================================
-- PARTE 2: ANTICIPOS A EMPLEADOS
-- ======================================================

-- Tabla de anticipos a empleados
CREATE TABLE IF NOT EXISTS employee_advances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Empleado
    employee_id INTEGER NOT NULL,
    employee_name TEXT NOT NULL,

    -- Referencia al gasto
    expense_id INTEGER NOT NULL,

    -- Montos
    advance_amount REAL NOT NULL,
    reimbursed_amount REAL DEFAULT 0,
    pending_amount REAL,

    -- Tipo de reembolso
    reimbursement_type TEXT CHECK(reimbursement_type IN ('transfer', 'payroll', 'cash', 'pending')) DEFAULT 'pending',

    -- Fechas
    advance_date TIMESTAMP NOT NULL,
    reimbursement_date TIMESTAMP,

    -- Estado
    status TEXT CHECK(status IN ('pending', 'partial', 'completed', 'cancelled')) DEFAULT 'pending',

    -- Vinculación con reembolso
    reimbursement_movement_id INTEGER,

    -- Metadata
    notes TEXT,
    payment_method TEXT, -- 'tarjeta_personal', 'efectivo_personal', etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (expense_id) REFERENCES expense_records(id) ON DELETE CASCADE,
    FOREIGN KEY (reimbursement_movement_id) REFERENCES bank_movements(id) ON DELETE SET NULL
);

-- Índices para employee_advances
CREATE INDEX IF NOT EXISTS idx_advances_employee ON employee_advances(employee_id);
CREATE INDEX IF NOT EXISTS idx_advances_expense ON employee_advances(expense_id);
CREATE INDEX IF NOT EXISTS idx_advances_status ON employee_advances(status);
CREATE INDEX IF NOT EXISTS idx_advances_date ON employee_advances(advance_date DESC);
CREATE INDEX IF NOT EXISTS idx_advances_pending ON employee_advances(pending_amount) WHERE status IN ('pending', 'partial');
CREATE INDEX IF NOT EXISTS idx_advances_employee_status ON employee_advances(employee_id, status);

-- Actualizar expense_records para soporte de anticipos
ALTER TABLE expense_records ADD COLUMN is_employee_advance BOOLEAN DEFAULT FALSE;

ALTER TABLE expense_records ADD COLUMN advance_id INTEGER;

ALTER TABLE expense_records ADD COLUMN reimbursement_status TEXT
  CHECK(reimbursement_status IN ('pending', 'partial', 'completed', 'not_required')) DEFAULT 'not_required';

-- Índices para anticipos en expense_records
CREATE INDEX IF NOT EXISTS idx_expense_advance ON expense_records(is_employee_advance, reimbursement_status);
CREATE INDEX IF NOT EXISTS idx_expense_advance_id ON expense_records(advance_id);

-- ======================================================
-- TRIGGERS PARA AUTOMATIZACIÓN
-- ======================================================

-- Trigger: Calcular pending_amount en employee_advances
CREATE TRIGGER IF NOT EXISTS calculate_advance_pending_amount
AFTER INSERT ON employee_advances
FOR EACH ROW
BEGIN
    UPDATE employee_advances
    SET pending_amount = advance_amount - reimbursed_amount
    WHERE id = NEW.id;
END;

-- Trigger: Actualizar pending_amount cuando cambia reimbursed_amount
CREATE TRIGGER IF NOT EXISTS update_advance_pending_amount
AFTER UPDATE OF reimbursed_amount ON employee_advances
FOR EACH ROW
BEGIN
    UPDATE employee_advances
    SET
        pending_amount = advance_amount - reimbursed_amount,
        status = CASE
            WHEN advance_amount - reimbursed_amount <= 0.01 THEN 'completed'
            WHEN reimbursed_amount > 0 THEN 'partial'
            ELSE 'pending'
        END,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.id;
END;

-- Trigger: Calcular amount_pending en expense_records (splits)
CREATE TRIGGER IF NOT EXISTS calculate_expense_pending_amount
AFTER INSERT ON expense_records
FOR EACH ROW
WHEN NEW.reconciliation_type IN ('split', 'partial')
BEGIN
    UPDATE expense_records
    SET amount_pending = amount - COALESCE(amount_reconciled, 0)
    WHERE id = NEW.id;
END;

-- Trigger: Actualizar amount_pending cuando cambia amount_reconciled
CREATE TRIGGER IF NOT EXISTS update_expense_pending_amount
AFTER UPDATE OF amount_reconciled ON expense_records
FOR EACH ROW
WHEN NEW.reconciliation_type IN ('split', 'partial')
BEGIN
    UPDATE expense_records
    SET amount_pending = amount - COALESCE(amount_reconciled, 0)
    WHERE id = NEW.id;
END;

-- Trigger: Calcular amount_unallocated en bank_movements (splits)
CREATE TRIGGER IF NOT EXISTS calculate_movement_unallocated
AFTER INSERT ON bank_movements
FOR EACH ROW
WHEN NEW.reconciliation_type IN ('split', 'partial')
BEGIN
    UPDATE bank_movements
    SET amount_unallocated = ABS(amount) - COALESCE(amount_allocated, 0)
    WHERE id = NEW.id;
END;

-- Trigger: Actualizar amount_unallocated cuando cambia amount_allocated
CREATE TRIGGER IF NOT EXISTS update_movement_unallocated
AFTER UPDATE OF amount_allocated ON bank_movements
FOR EACH ROW
WHEN NEW.reconciliation_type IN ('split', 'partial')
BEGIN
    UPDATE bank_movements
    SET amount_unallocated = ABS(amount) - COALESCE(amount_allocated, 0)
    WHERE id = NEW.id;
END;

-- Trigger: Marcar gasto como non_reconcilable si es advance
CREATE TRIGGER IF NOT EXISTS mark_advance_non_reconcilable
AFTER INSERT ON employee_advances
FOR EACH ROW
BEGIN
    UPDATE expense_records
    SET
        bank_status = 'non_reconcilable',
        is_employee_advance = TRUE,
        advance_id = NEW.id,
        reimbursement_status = 'pending'
    WHERE id = NEW.expense_id;
END;

-- ======================================================
-- VISTAS ÚTILES
-- ======================================================

-- Vista: Anticipos pendientes con días de atraso
CREATE VIEW IF NOT EXISTS v_pending_advances AS
SELECT
    ea.id,
    ea.employee_id,
    ea.employee_name,
    ea.expense_id,
    er.description as expense_description,
    ea.advance_amount,
    ea.reimbursed_amount,
    ea.pending_amount,
    ea.advance_date,
    CAST(JULIANDAY('now') - JULIANDAY(ea.advance_date) AS INTEGER) as days_pending,
    ea.reimbursement_type,
    ea.status,
    CASE
        WHEN JULIANDAY('now') - JULIANDAY(ea.advance_date) > 15 THEN 'urgent'
        WHEN JULIANDAY('now') - JULIANDAY(ea.advance_date) > 7 THEN 'warning'
        ELSE 'normal'
    END as priority
FROM employee_advances ea
JOIN expense_records er ON ea.expense_id = er.id
WHERE ea.status IN ('pending', 'partial')
ORDER BY days_pending DESC;

-- Vista: Resumen de splits por grupo
CREATE VIEW IF NOT EXISTS v_split_summary AS
SELECT
    split_group_id,
    split_type,
    COUNT(DISTINCT expense_id) as expenses_count,
    COUNT(DISTINCT movement_id) as movements_count,
    SUM(allocated_amount) as total_allocated,
    MIN(created_at) as created_at,
    MAX(is_complete) as is_complete
FROM bank_reconciliation_splits
GROUP BY split_group_id;

-- Vista: Gastos con conciliación split incompleta
CREATE VIEW IF NOT EXISTS v_incomplete_splits AS
SELECT
    er.id as expense_id,
    er.description,
    er.amount as expense_amount,
    er.amount_reconciled,
    er.amount_pending,
    er.split_group_id,
    vs.total_allocated,
    vs.is_complete
FROM expense_records er
JOIN v_split_summary vs ON er.split_group_id = vs.split_group_id
WHERE er.reconciliation_type = 'split'
  AND vs.is_complete = 0;

-- ======================================================
-- DATOS DE EJEMPLO (OPCIONAL - COMENTADO)
-- ======================================================

-- Ejemplo de split one-to-many
-- INSERT INTO bank_reconciliation_splits (split_group_id, split_type, expense_id, movement_id, allocated_amount, percentage, is_complete)
-- VALUES
--   ('split_demo_123', 'one_to_many', 10244, 10350, 2500, 50.0, 1),
--   ('split_demo_123', 'one_to_many', 10245, 10350, 1500, 30.0, 1),
--   ('split_demo_123', 'one_to_many', 10246, 10350, 1000, 20.0, 1);

-- Ejemplo de anticipo
-- INSERT INTO employee_advances (employee_id, employee_name, expense_id, advance_amount, advance_date, reimbursement_type, payment_method, notes)
-- VALUES (42, 'Juan Pérez', 10248, 850.50, '2025-01-15', 'transfer', 'tarjeta_personal', 'Gasto urgente de gasolina');

-- ======================================================
-- VERIFICACIÓN
-- ======================================================

-- Verificar que las tablas se crearon
SELECT 'bank_reconciliation_splits' as table_name, COUNT(*) as count FROM bank_reconciliation_splits
UNION ALL
SELECT 'employee_advances', COUNT(*) FROM employee_advances;

-- Verificar nuevas columnas en expense_records
SELECT
    'expense_records' as table_name,
    COUNT(*) FILTER (WHERE reconciliation_type IS NOT NULL) as has_reconciliation_type,
    COUNT(*) FILTER (WHERE is_employee_advance IS NOT NULL) as has_advance_flag
FROM expense_records;

-- Verificar nuevas columnas en bank_movements
SELECT
    'bank_movements' as table_name,
    COUNT(*) FILTER (WHERE reconciliation_type IS NOT NULL) as has_reconciliation_type,
    COUNT(*) FILTER (WHERE split_group_id IS NOT NULL) as has_split_group
FROM bank_movements;
