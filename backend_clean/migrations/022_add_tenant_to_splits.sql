-- Migration 022: Add tenant_id to bank_reconciliation_splits table
-- Purpose: Enable multi-tenancy support for split reconciliation
-- Date: 2025-10-03

-- Step 1: Add tenant_id column
ALTER TABLE bank_reconciliation_splits ADD COLUMN tenant_id INTEGER;

-- Step 2: Populate tenant_id from bank_movements (for one_to_many splits)
UPDATE bank_reconciliation_splits
SET tenant_id = (
    SELECT bm.tenant_id
    FROM bank_movements bm
    WHERE bm.id = bank_reconciliation_splits.movement_id
    LIMIT 1
)
WHERE tenant_id IS NULL AND movement_id IS NOT NULL;

-- Step 3: Populate tenant_id from expense_records (for many_to_one splits or fallback)
UPDATE bank_reconciliation_splits
SET tenant_id = (
    SELECT er.tenant_id
    FROM expense_records er
    WHERE er.id = bank_reconciliation_splits.expense_id
    LIMIT 1
)
WHERE tenant_id IS NULL AND expense_id IS NOT NULL;

-- Step 4: Handle orphaned records (splits without valid expense/movement)
-- Mark them as tenant=1 (default) for manual review
UPDATE bank_reconciliation_splits
SET tenant_id = 1
WHERE tenant_id IS NULL;

-- Step 5: Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_splits_tenant
ON bank_reconciliation_splits(tenant_id);

CREATE INDEX IF NOT EXISTS idx_splits_tenant_group
ON bank_reconciliation_splits(tenant_id, split_group_id);

CREATE INDEX IF NOT EXISTS idx_splits_tenant_type
ON bank_reconciliation_splits(tenant_id, split_type);

-- Step 6: Verify migration
SELECT
    COUNT(*) as total_splits,
    COUNT(DISTINCT tenant_id) as unique_tenants,
    tenant_id,
    COUNT(*) as splits_per_tenant,
    split_type
FROM bank_reconciliation_splits
GROUP BY tenant_id, split_type
ORDER BY tenant_id;

-- Expected result: All splits should have tenant_id populated
-- No NULL values should exist
