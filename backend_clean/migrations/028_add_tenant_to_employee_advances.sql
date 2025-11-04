-- Migration 021: Add tenant_id to employee_advances table
-- Purpose: Enable multi-tenancy support for employee advances
-- Date: 2025-10-03

-- Step 1: Add tenant_id column
ALTER TABLE employee_advances ADD COLUMN tenant_id INTEGER;

-- Step 2: Populate tenant_id from linked expense_records
UPDATE employee_advances
SET tenant_id = (
    SELECT er.tenant_id
    FROM expense_records er
    WHERE er.id = employee_advances.expense_id
)
WHERE tenant_id IS NULL;

-- Step 3: Handle orphaned records (advances without valid expense)
-- Mark them as tenant=1 (default) for manual review
UPDATE employee_advances
SET tenant_id = 1
WHERE tenant_id IS NULL;

-- Step 4: Create index for performance
CREATE INDEX IF NOT EXISTS idx_employee_advances_tenant
ON employee_advances(tenant_id);

-- Step 5: Create composite index for common queries
CREATE INDEX IF NOT EXISTS idx_employee_advances_tenant_status
ON employee_advances(tenant_id, status);

CREATE INDEX IF NOT EXISTS idx_employee_advances_tenant_employee
ON employee_advances(tenant_id, employee_id);

-- Step 6: Verify migration
SELECT
    COUNT(*) as total_advances,
    COUNT(DISTINCT tenant_id) as unique_tenants,
    tenant_id,
    COUNT(*) as advances_per_tenant
FROM employee_advances
GROUP BY tenant_id
ORDER BY tenant_id;

-- Expected result: All advances should have tenant_id populated
-- No NULL values should exist
