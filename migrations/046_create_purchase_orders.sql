-- =====================================================================
-- MIGRACIÓN: Purchase Orders Module
-- Fecha: 2025-12-14
-- Descripción: Sistema de órdenes de compra con workflow de aprobación
--              y vinculación a facturas SAT.
--
-- SCOPE:
--   ✅ Tabla purchase_orders (estructura completa)
--   ✅ Budget tracking en projects (committed_mxn, spent_mxn)
--   ✅ Función calculate_project_remaining_budget()
--   ✅ Triggers automáticos
--   ✅ Índices de performance
--
-- INTEGRACIÓN CON TRINITY:
--   - PO → SAT Invoice (cuando llega factura)
--   - PO → Budget tracking (cuando se aprueba)
-- =====================================================================

BEGIN;

-- =====================================================================
-- PASO 1: Crear tabla PURCHASE_ORDERS
-- =====================================================================

CREATE TABLE IF NOT EXISTS purchase_orders (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,

    -- Numeración automática
    po_number VARCHAR(50) NOT NULL,  -- PO-2025-001

    -- Estructura organizacional
    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    department_id INTEGER REFERENCES departments(id) ON DELETE SET NULL,

    -- Usuarios involucrados
    requester_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    approver_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,

    -- Información del proveedor
    vendor_name VARCHAR(255) NOT NULL,
    vendor_rfc VARCHAR(13),
    vendor_email VARCHAR(255),
    vendor_phone VARCHAR(20),

    -- Detalles de la orden
    description TEXT NOT NULL,
    total_amount NUMERIC(15,2) NOT NULL CHECK (total_amount > 0),
    currency VARCHAR(3) DEFAULT 'MXN',

    -- Workflow states
    status VARCHAR(30) DEFAULT 'draft' CHECK (status IN (
        'draft',              -- Borrador (editable)
        'pending_approval',   -- Enviado a aprobación
        'approved',           -- Aprobado (compromete presupuesto)
        'rejected',           -- Rechazado
        'sent_to_vendor',     -- Enviado al proveedor
        'received',           -- Mercancía/servicio recibido
        'invoiced',           -- Factura recibida y vinculada
        'cancelled'           -- Cancelado
    )),

    -- Vinculación a factura SAT (cuando llega)
    sat_invoice_id TEXT REFERENCES sat_invoices(id) ON DELETE SET NULL,

    -- Archivos
    pdf_url TEXT,  -- PDF generado de la PO
    attachment_urls JSONB DEFAULT '[]',  -- Cotizaciones, especificaciones

    -- Notas y razones
    notes TEXT,
    rejection_reason TEXT,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    approved_at TIMESTAMP,
    rejected_at TIMESTAMP,
    sent_at TIMESTAMP,
    received_at TIMESTAMP,

    -- Denormalizados para performance
    is_approved BOOLEAN DEFAULT FALSE,
    is_cancelled BOOLEAN DEFAULT FALSE,

    -- Constraints
    CONSTRAINT unique_po_number_per_tenant UNIQUE (tenant_id, po_number)
);

-- Índices para purchase_orders
CREATE INDEX idx_purchase_orders_tenant ON purchase_orders(tenant_id);
CREATE INDEX idx_purchase_orders_project ON purchase_orders(project_id);
CREATE INDEX idx_purchase_orders_department ON purchase_orders(department_id);
CREATE INDEX idx_purchase_orders_requester ON purchase_orders(requester_user_id);
CREATE INDEX idx_purchase_orders_approver ON purchase_orders(approver_user_id);
CREATE INDEX idx_purchase_orders_status ON purchase_orders(status);
CREATE INDEX idx_purchase_orders_sat_invoice ON purchase_orders(sat_invoice_id) WHERE sat_invoice_id IS NOT NULL;
CREATE INDEX idx_purchase_orders_created_at ON purchase_orders(created_at DESC);
CREATE INDEX idx_purchase_orders_approved ON purchase_orders(is_approved) WHERE is_approved = TRUE;

COMMENT ON TABLE purchase_orders IS
'Órdenes de Compra (Purchase Orders).
Permite planificar compras ANTES de recibir factura.
Compromete presupuesto del proyecto cuando status = approved.

FLUJO:
1. Usuario crea PO (draft)
2. Envía a aprobación (pending_approval)
3. Manager aprueba (approved) → Compromete presupuesto
4. Cuando llega factura SAT → Vincula sat_invoice_id (invoiced)
5. PO completa, presupuesto pasa de committed a spent';

COMMENT ON COLUMN purchase_orders.po_number IS
'Número único de PO por tenant.
Formato: PO-YYYY-NNN (ej: PO-2025-001)
Se genera automáticamente al crear.';

COMMENT ON COLUMN purchase_orders.status IS
'Estados del workflow:
- draft: Borrador, editable por creador
- pending_approval: Enviado a manager para aprobación
- approved: Aprobado, compromete presupuesto del proyecto
- rejected: Rechazado por manager
- sent_to_vendor: Enviado al proveedor (opcional)
- received: Mercancía/servicio recibido
- invoiced: Factura SAT vinculada (status final exitoso)
- cancelled: Cancelado (libera presupuesto si estaba approved)';

COMMENT ON COLUMN purchase_orders.sat_invoice_id IS
'FK a sat_invoices.id
Se vincula cuando el proveedor emite la factura SAT.
Al vincularse, el presupuesto pasa de committed → spent.';

-- Trigger para auto-actualizar updated_at
CREATE OR REPLACE FUNCTION update_purchase_orders_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_purchase_orders_updated_at
    BEFORE UPDATE ON purchase_orders
    FOR EACH ROW
    EXECUTE FUNCTION update_purchase_orders_updated_at();

-- =====================================================================
-- PASO 2: Extender projects con budget tracking
-- =====================================================================

ALTER TABLE projects
ADD COLUMN IF NOT EXISTS committed_mxn NUMERIC(15,2) DEFAULT 0;

ALTER TABLE projects
ADD COLUMN IF NOT EXISTS spent_mxn NUMERIC(15,2) DEFAULT 0;

COMMENT ON COLUMN projects.budget_mxn IS
'Presupuesto TOTAL asignado al proyecto (no cambia).
Ejemplo: $500,000 MXN';

COMMENT ON COLUMN projects.committed_mxn IS
'Dinero COMPROMETIDO en POs aprobadas pero no facturadas aún.
Se calcula: SUM(purchase_orders.total_amount)
WHERE status = approved AND sat_invoice_id IS NULL
Ejemplo: $150,000 MXN en 3 POs aprobadas esperando factura.';

COMMENT ON COLUMN projects.spent_mxn IS
'Dinero ya GASTADO (facturas pagadas + gastos manuales).
Se calcula: SUM(manual_expenses.amount) + SUM(facturas vinculadas a POs)
Ejemplo: $200,000 MXN ya pagados.';

-- =====================================================================
-- PASO 3: Función para calcular presupuesto restante
-- =====================================================================

CREATE OR REPLACE FUNCTION calculate_project_remaining_budget(p_project_id INTEGER)
RETURNS NUMERIC AS $$
DECLARE
    v_budget NUMERIC;
    v_committed NUMERIC;
    v_spent NUMERIC;
    v_remaining NUMERIC;
BEGIN
    -- Obtener presupuesto total
    SELECT COALESCE(budget_mxn, 0) INTO v_budget
    FROM projects WHERE id = p_project_id;

    -- Calcular comprometido: POs aprobadas sin factura
    SELECT COALESCE(SUM(total_amount), 0) INTO v_committed
    FROM purchase_orders
    WHERE project_id = p_project_id
      AND status = 'approved'
      AND sat_invoice_id IS NULL
      AND is_cancelled = FALSE;

    -- Calcular gastado: Gastos manuales + POs con factura
    SELECT COALESCE(SUM(amount), 0) INTO v_spent
    FROM manual_expenses
    WHERE project_id = p_project_id;

    -- Sumar facturas de POs
    SELECT v_spent + COALESCE(SUM(po.total_amount), 0) INTO v_spent
    FROM purchase_orders po
    WHERE po.project_id = p_project_id
      AND po.sat_invoice_id IS NOT NULL
      AND po.is_cancelled = FALSE;

    -- Calcular restante
    v_remaining := v_budget - v_committed - v_spent;

    RETURN GREATEST(v_remaining, 0);  -- No permitir negativo
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION calculate_project_remaining_budget IS
'Calcula presupuesto disponible de un proyecto.

FÓRMULA:
  remaining = budget_total - committed - spent

DONDE:
  - budget_total: projects.budget_mxn
  - committed: SUM(POs aprobadas sin factura)
  - spent: SUM(gastos manuales) + SUM(POs con factura)

EJEMPLO:
  Budget total: $500,000
  POs aprobadas pendientes: $150,000 (committed)
  Gastos + POs facturadas: $200,000 (spent)
  Remaining: $150,000 disponible para nuevas POs';

-- =====================================================================
-- PASO 4: Vista para budget summary por proyecto
-- =====================================================================

CREATE OR REPLACE VIEW project_budget_summary AS
SELECT
    p.id as project_id,
    p.tenant_id,
    p.name as project_name,
    p.budget_mxn as budget_total,

    -- Comprometido (POs aprobadas sin factura)
    COALESCE(SUM(CASE
        WHEN po.status = 'approved'
         AND po.sat_invoice_id IS NULL
         AND po.is_cancelled = FALSE
        THEN po.total_amount
        ELSE 0
    END), 0) as committed_mxn,

    -- Gastado (gastos manuales)
    COALESCE((
        SELECT SUM(amount)
        FROM manual_expenses
        WHERE project_id = p.id
    ), 0) as spent_manual_mxn,

    -- Gastado (POs con factura)
    COALESCE(SUM(CASE
        WHEN po.sat_invoice_id IS NOT NULL
         AND po.is_cancelled = FALSE
        THEN po.total_amount
        ELSE 0
    END), 0) as spent_pos_mxn,

    -- Total gastado
    COALESCE((
        SELECT SUM(amount)
        FROM manual_expenses
        WHERE project_id = p.id
    ), 0) + COALESCE(SUM(CASE
        WHEN po.sat_invoice_id IS NOT NULL
         AND po.is_cancelled = FALSE
        THEN po.total_amount
        ELSE 0
    END), 0) as spent_total_mxn,

    -- Restante
    p.budget_mxn - (
        COALESCE(SUM(CASE
            WHEN po.status = 'approved'
             AND po.sat_invoice_id IS NULL
             AND po.is_cancelled = FALSE
            THEN po.total_amount
            ELSE 0
        END), 0) +
        COALESCE((
            SELECT SUM(amount)
            FROM manual_expenses
            WHERE project_id = p.id
        ), 0) +
        COALESCE(SUM(CASE
            WHEN po.sat_invoice_id IS NOT NULL
             AND po.is_cancelled = FALSE
            THEN po.total_amount
            ELSE 0
        END), 0)
    ) as remaining_mxn,

    -- Porcentaje usado
    CASE
        WHEN p.budget_mxn > 0 THEN
            ROUND(((
                COALESCE(SUM(CASE
                    WHEN po.status = 'approved'
                     AND po.sat_invoice_id IS NULL
                     AND po.is_cancelled = FALSE
                    THEN po.total_amount
                    ELSE 0
                END), 0) +
                COALESCE((
                    SELECT SUM(amount)
                    FROM manual_expenses
                    WHERE project_id = p.id
                ), 0) +
                COALESCE(SUM(CASE
                    WHEN po.sat_invoice_id IS NOT NULL
                     AND po.is_cancelled = FALSE
                    THEN po.total_amount
                    ELSE 0
                END), 0)
            )::NUMERIC / p.budget_mxn) * 100, 2)
        ELSE 0
    END as budget_used_percentage,

    -- Contadores
    COUNT(CASE WHEN po.status = 'approved' AND po.sat_invoice_id IS NULL THEN 1 END) as pos_pending_count,
    COUNT(CASE WHEN po.sat_invoice_id IS NOT NULL THEN 1 END) as pos_invoiced_count

FROM projects p
LEFT JOIN purchase_orders po ON po.project_id = p.id
GROUP BY p.id, p.tenant_id, p.name, p.budget_mxn;

COMMENT ON VIEW project_budget_summary IS
'Vista consolidada del presupuesto por proyecto.
Muestra en tiempo real: budget total, comprometido, gastado, restante.
Útil para dashboards y validaciones de presupuesto antes de aprobar POs.';

-- =====================================================================
-- PASO 5: Trigger para actualizar denormalized fields
-- =====================================================================

CREATE OR REPLACE FUNCTION sync_purchase_order_denormalized()
RETURNS TRIGGER AS $$
BEGIN
    -- Actualizar is_approved
    NEW.is_approved := (NEW.status = 'approved');

    -- Actualizar is_cancelled
    NEW.is_cancelled := (NEW.status = 'cancelled');

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_sync_purchase_order_denormalized
    BEFORE INSERT OR UPDATE ON purchase_orders
    FOR EACH ROW
    EXECUTE FUNCTION sync_purchase_order_denormalized();

COMMENT ON FUNCTION sync_purchase_order_denormalized IS
'Mantiene sincronizados los campos denormalizados:
- is_approved: TRUE si status = approved
- is_cancelled: TRUE si status = cancelled
Facilita queries de performance sin hacer WHERE status IN (...).';

COMMIT;

-- =====================================================================
-- VERIFICACIÓN FINAL
-- =====================================================================

DO $$
BEGIN
    RAISE NOTICE '✅ Migración 046: Purchase Orders completada exitosamente';
    RAISE NOTICE '   - Tabla purchase_orders creada';
    RAISE NOTICE '   - Budget tracking agregado a projects';
    RAISE NOTICE '   - Función calculate_project_remaining_budget() creada';
    RAISE NOTICE '   - Vista project_budget_summary creada';
    RAISE NOTICE '   - Triggers configurados';
END $$;
