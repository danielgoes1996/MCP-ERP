-- Migration: Modify Purchase Orders for B2B Multi-Invoice Support
-- Date: 2025-12-14
-- Description: Remove single-invoice limitation and add partial invoicing support
--              Fixes "The Myth of the Single Invoice" architectural flaw

BEGIN;

-- =====================================================================
-- PART 1: Drop project_budget_summary view (depends on sat_invoice_id)
-- =====================================================================

-- Drop the view first to avoid cascade dependency errors
DROP VIEW IF EXISTS project_budget_summary CASCADE;

-- =====================================================================
-- PART 2: Remove sat_invoice_id column (no longer needed)
-- =====================================================================

-- Drop the foreign key constraint if it exists
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name LIKE '%purchase_orders%sat_invoice%'
          AND table_name = 'purchase_orders'
    ) THEN
        ALTER TABLE purchase_orders DROP CONSTRAINT IF EXISTS purchase_orders_sat_invoice_id_fkey CASCADE;
    END IF;
END $$;

-- Drop the index if it exists
DROP INDEX IF EXISTS idx_purchase_orders_sat_invoice;

-- Drop the column
ALTER TABLE purchase_orders DROP COLUMN IF EXISTS sat_invoice_id;

-- =====================================================================
-- PART 2: Add invoiced_amount column for tracking
-- =====================================================================

-- Add column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'purchase_orders'
          AND column_name = 'invoiced_amount'
    ) THEN
        ALTER TABLE purchase_orders
        ADD COLUMN invoiced_amount DECIMAL(12,2) DEFAULT 0
        CHECK (invoiced_amount >= 0);
    END IF;
END $$;

COMMENT ON COLUMN purchase_orders.invoiced_amount IS
'Total amount invoiced against this PO so far (sum of linked invoices via po_invoices table).
Updated automatically when invoices are linked/unlinked.
For partial invoicing pattern: anticipo + finiquito <= total_amount';

-- =====================================================================
-- PART 3: Update status column to support partial invoicing
-- =====================================================================

-- First, we need to drop the existing CHECK constraint for status
DO $$
BEGIN
    -- Drop old constraint if it exists
    IF EXISTS (
        SELECT 1 FROM information_schema.constraint_column_usage
        WHERE table_name = 'purchase_orders'
          AND constraint_name LIKE '%status%check%'
    ) THEN
        ALTER TABLE purchase_orders DROP CONSTRAINT IF EXISTS purchase_orders_status_check;
        ALTER TABLE purchase_orders DROP CONSTRAINT IF EXISTS check_po_status;
    END IF;
END $$;

-- Add new constraint with partial/full invoicing states
ALTER TABLE purchase_orders
ADD CONSTRAINT check_po_status CHECK (
    status IN (
        'draft',              -- Initial state
        'pending_approval',   -- Awaiting manager approval
        'approved',           -- Approved, ready for goods receipt
        'partially_invoiced', -- Some invoices received (anticipo received, awaiting finiquito)
        'fully_invoiced',     -- All invoices received (total invoiced >= total amount)
        'cancelled'           -- Cancelled before completion
    )
);

-- =====================================================================
-- PART 4: Create trigger to auto-update invoiced_amount
-- =====================================================================

-- Function to recalculate invoiced_amount when po_invoices change
CREATE OR REPLACE FUNCTION update_po_invoiced_amount()
RETURNS TRIGGER AS $$
DECLARE
    po_total DECIMAL(12,2);
    invoiced_total DECIMAL(12,2);
    new_status VARCHAR(50);
BEGIN
    -- Get the PO ID (works for INSERT, UPDATE, DELETE)
    DECLARE
        target_po_id INTEGER;
    BEGIN
        IF TG_OP = 'DELETE' THEN
            target_po_id := OLD.po_id;
        ELSE
            target_po_id := NEW.po_id;
        END IF;

        -- Calculate total invoiced for this PO
        SELECT COALESCE(SUM(invoice_amount), 0)
        INTO invoiced_total
        FROM po_invoices
        WHERE po_id = target_po_id;

        -- Get PO total amount
        SELECT total_amount INTO po_total
        FROM purchase_orders
        WHERE id = target_po_id;

        -- Determine new status based on invoicing
        IF invoiced_total = 0 THEN
            -- No invoices yet, keep current status unless it's partially/fully invoiced
            UPDATE purchase_orders
            SET invoiced_amount = 0
            WHERE id = target_po_id
              AND status NOT IN ('partially_invoiced', 'fully_invoiced');
        ELSIF invoiced_total >= po_total THEN
            -- Fully invoiced
            UPDATE purchase_orders
            SET invoiced_amount = invoiced_total,
                status = 'fully_invoiced'
            WHERE id = target_po_id
              AND status != 'cancelled';
        ELSE
            -- Partially invoiced
            UPDATE purchase_orders
            SET invoiced_amount = invoiced_total,
                status = 'partially_invoiced'
            WHERE id = target_po_id
              AND status IN ('approved', 'partially_invoiced');
        END IF;
    END;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Drop trigger if exists, then create
DROP TRIGGER IF EXISTS trigger_update_po_invoiced_amount ON po_invoices;

CREATE TRIGGER trigger_update_po_invoiced_amount
    AFTER INSERT OR UPDATE OR DELETE ON po_invoices
    FOR EACH ROW
    EXECUTE FUNCTION update_po_invoiced_amount();

-- =====================================================================
-- PART 5: Add helpful indexes
-- =====================================================================

CREATE INDEX IF NOT EXISTS idx_purchase_orders_invoiced_amount
    ON purchase_orders(invoiced_amount)
    WHERE invoiced_amount > 0;

CREATE INDEX IF NOT EXISTS idx_purchase_orders_partial_invoicing
    ON purchase_orders(id, total_amount, invoiced_amount)
    WHERE status IN ('partially_invoiced', 'fully_invoiced');

-- =====================================================================
-- PART 6: Comments and documentation
-- =====================================================================

COMMENT ON TABLE purchase_orders IS
'Professional B2B Purchase Orders with multi-invoice support.
Supports partial invoicing pattern (anticipo/finiquito) common in Mexican B2B.
Related tables:
  - po_lines: Line items for this PO
  - po_invoices: SAT invoices linked to this PO (one-to-many)
Budget impact: approved POs reserve budget (committed), invoiced POs reduce budget (spent).';

COMMENT ON COLUMN purchase_orders.status IS
'PO Lifecycle:
  draft → pending_approval → approved → partially_invoiced → fully_invoiced

  - draft: Initial creation
  - pending_approval: Awaiting manager sign-off
  - approved: Ready for goods receipt & invoicing
  - partially_invoiced: Some invoices linked (e.g., 50% anticipo received)
  - fully_invoiced: All invoices linked (invoiced_amount >= total_amount)
  - cancelled: Cancelled at any stage';

-- =====================================================================
-- PART 7: Recreate project_budget_summary with CORRECTED formulas
-- =====================================================================

-- Fixes "The Voodoo Mathematics" architectural flaw
-- OLD (wrong): Money appeared when PO was invoiced (sat_invoice_id IS NOT NULL)
-- NEW (correct): Money transforms from committed→spent based on invoiced_amount

CREATE OR REPLACE VIEW project_budget_summary AS
SELECT
    p.id AS project_id,
    p.tenant_id,
    p.name AS project_name,
    p.budget_mxn AS budget_total,

    -- COMMITTED: Approved POs not yet fully invoiced
    -- (Reserved budget, not yet spent)
    COALESCE(SUM(
        CASE
            WHEN po.status IN ('approved', 'partially_invoiced')
                 AND po.is_cancelled = false
            THEN (po.total_amount - COALESCE(po.invoiced_amount, 0))
            ELSE 0
        END
    ), 0) AS committed_mxn,

    -- SPENT (Manual): Direct expenses not tied to POs
    COALESCE((
        SELECT SUM(amount)
        FROM manual_expenses
        WHERE project_id = p.id
    ), 0) AS spent_manual_mxn,

    -- SPENT (POs): Invoiced amounts from Purchase Orders
    -- (Money that has actually been billed via SAT invoices)
    COALESCE(SUM(
        CASE
            WHEN po.is_cancelled = false
            THEN COALESCE(po.invoiced_amount, 0)
            ELSE 0
        END
    ), 0) AS spent_pos_mxn,

    -- TOTAL SPENT: Manual + PO invoiced amounts
    COALESCE((
        SELECT SUM(amount)
        FROM manual_expenses
        WHERE project_id = p.id
    ), 0) + COALESCE(SUM(
        CASE
            WHEN po.is_cancelled = false
            THEN COALESCE(po.invoiced_amount, 0)
            ELSE 0
        END
    ), 0) AS spent_total_mxn,

    -- REMAINING BUDGET
    p.budget_mxn - (
        -- Committed (reserved, not yet spent)
        COALESCE(SUM(
            CASE
                WHEN po.status IN ('approved', 'partially_invoiced')
                     AND po.is_cancelled = false
                THEN (po.total_amount - COALESCE(po.invoiced_amount, 0))
                ELSE 0
            END
        ), 0) +
        -- Manual expenses
        COALESCE((
            SELECT SUM(amount)
            FROM manual_expenses
            WHERE project_id = p.id
        ), 0) +
        -- PO invoiced
        COALESCE(SUM(
            CASE
                WHEN po.is_cancelled = false
                THEN COALESCE(po.invoiced_amount, 0)
                ELSE 0
            END
        ), 0)
    ) AS remaining_mxn,

    -- BUDGET UTILIZATION %
    ROUND(CAST((
            COALESCE(SUM(
                CASE
                    WHEN po.status IN ('approved', 'partially_invoiced')
                         AND po.is_cancelled = false
                    THEN (po.total_amount - COALESCE(po.invoiced_amount, 0))
                    ELSE 0
                END
            ), 0) +
            COALESCE((
                SELECT SUM(amount)
                FROM manual_expenses
                WHERE project_id = p.id
            ), 0) +
            COALESCE(SUM(
                CASE
                    WHEN po.is_cancelled = false
                    THEN COALESCE(po.invoiced_amount, 0)
                    ELSE 0
                END
            ), 0)
        ) / NULLIF(p.budget_mxn, 0) * 100 AS NUMERIC), 2) AS budget_used_percentage,

    -- PO STATISTICS
    COUNT(
        CASE
            WHEN po.is_cancelled = false
                 AND COALESCE(po.invoiced_amount, 0) < po.total_amount
            THEN 1
        END
    ) AS pos_pending_count,

    COUNT(
        CASE
            WHEN po.is_cancelled = false
                 AND po.status = 'fully_invoiced'
            THEN 1
        END
    ) AS pos_invoiced_count

FROM projects p
LEFT JOIN purchase_orders po ON po.project_id = p.id
GROUP BY p.id, p.tenant_id, p.name, p.budget_mxn;

COMMENT ON VIEW project_budget_summary IS
'Corrected budget summary for projects - fixes "The Voodoo Mathematics" flaw.

Budget Formula (CORRECT):
  remaining = budget_total - (committed + spent_manual + spent_pos)

Where:
  - committed: Approved POs not yet fully invoiced (money reserved)
  - spent_pos: Sum of invoiced_amount from POs (money actually billed)
  - spent_manual: Direct manual expenses

Key Fix: Money no longer appears/disappears - it transforms from committed→spent';

COMMIT;
