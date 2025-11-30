-- Migration: Invoice to Expense Pending Assignments
-- Purpose: Track invoices that need manual assignment (Case 3: Multiple matches)
-- Date: 2025-11-25

-- Table to store pending invoice-to-expense assignments
CREATE TABLE IF NOT EXISTS invoice_expense_pending_assignments (
    id SERIAL PRIMARY KEY,
    invoice_id TEXT NOT NULL REFERENCES sat_invoices(id) ON DELETE CASCADE,
    possible_expense_ids JSONB NOT NULL,  -- Array of possible expense IDs
    status VARCHAR(50) NOT NULL DEFAULT 'needs_manual_assignment',
    resolved_expense_id INTEGER REFERENCES manual_expenses(id) ON DELETE SET NULL,
    resolved_by_user_id INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMP,

    CONSTRAINT valid_status CHECK (status IN ('needs_manual_assignment', 'resolved', 'cancelled'))
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_pending_assignments_status
ON invoice_expense_pending_assignments(status)
WHERE status = 'needs_manual_assignment';

CREATE INDEX IF NOT EXISTS idx_pending_assignments_invoice
ON invoice_expense_pending_assignments(invoice_id);

CREATE INDEX IF NOT EXISTS idx_pending_assignments_created
ON invoice_expense_pending_assignments(created_at DESC);

-- Comments
COMMENT ON TABLE invoice_expense_pending_assignments IS
'Tracks invoices that matched multiple expenses and need manual assignment (Case 3)';

COMMENT ON COLUMN invoice_expense_pending_assignments.possible_expense_ids IS
'JSON array of expense IDs that could match this invoice';

COMMENT ON COLUMN invoice_expense_pending_assignments.status IS
'needs_manual_assignment: Waiting for user action, resolved: User assigned to expense, cancelled: Invoice or expenses deleted';
