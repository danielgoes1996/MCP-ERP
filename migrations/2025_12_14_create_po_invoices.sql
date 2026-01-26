-- Migration: Create Purchase Order Invoices linking table
-- Date: 2025-12-14
-- Description: Professional B2B-grade Purchase Orders with multiple invoices support
--              Supports partial invoicing pattern (anticipo/finiquito) common in B2B
--              Fixes "The Myth of the Single Invoice" architectural flaw

CREATE TABLE IF NOT EXISTS po_invoices (
    id SERIAL PRIMARY KEY,
    po_id INTEGER NOT NULL REFERENCES purchase_orders(id) ON DELETE CASCADE,
    sat_invoice_id TEXT NOT NULL REFERENCES sat_invoices(id),
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),

    -- Invoice classification
    invoice_type VARCHAR(20) NOT NULL CHECK (invoice_type IN ('anticipo', 'parcial', 'finiquito', 'total')),

    -- Amount tracking
    invoice_amount DECIMAL(12,2) NOT NULL CHECK (invoice_amount > 0),

    -- Optional: Which PO lines does this invoice cover (JSONB for flexibility)
    -- Example: {"lines": [{"line_id": 1, "quantity": 50, "amount": 25000}]}
    covered_lines JSONB,

    -- Audit trail
    linked_by INTEGER REFERENCES users(id),  -- Who linked this invoice to the PO
    linked_at TIMESTAMP DEFAULT NOW(),

    -- Notes about this specific invoice linkage
    notes TEXT,

    -- Constraints
    CONSTRAINT unique_po_sat_invoice UNIQUE (po_id, sat_invoice_id)
);

-- Indexes for performance
CREATE INDEX idx_po_invoices_po_id ON po_invoices(po_id);
CREATE INDEX idx_po_invoices_sat_invoice_id ON po_invoices(sat_invoice_id);
CREATE INDEX idx_po_invoices_tenant_id ON po_invoices(tenant_id);
CREATE INDEX idx_po_invoices_type ON po_invoices(invoice_type);

-- View to get PO invoicing summary
CREATE OR REPLACE VIEW po_invoice_summary AS
SELECT
    po.id as po_id,
    po.po_number,
    po.total_amount as po_total,
    COALESCE(SUM(poi.invoice_amount), 0) as total_invoiced,
    po.total_amount - COALESCE(SUM(poi.invoice_amount), 0) as pending_to_invoice,
    COUNT(poi.id) as invoice_count,
    CASE
        WHEN COUNT(poi.id) = 0 THEN 'not_invoiced'
        WHEN COALESCE(SUM(poi.invoice_amount), 0) < po.total_amount THEN 'partially_invoiced'
        WHEN COALESCE(SUM(poi.invoice_amount), 0) >= po.total_amount THEN 'fully_invoiced'
        ELSE 'unknown'
    END as invoicing_status
FROM purchase_orders po
LEFT JOIN po_invoices poi ON po.id = poi.po_id
GROUP BY po.id, po.po_number, po.total_amount;

-- Comments
COMMENT ON TABLE po_invoices IS 'Links SAT invoices to Purchase Orders - supports multiple invoices per PO (anticipo/finiquito pattern)';
COMMENT ON COLUMN po_invoices.invoice_type IS 'anticipo=advance payment, parcial=partial payment, finiquito=final payment, total=full payment';
COMMENT ON COLUMN po_invoices.covered_lines IS 'Optional JSON mapping to PO lines - which line items this invoice covers';
COMMENT ON COLUMN po_invoices.invoice_amount IS 'Amount from SAT invoice allocated to this PO (may be partial if invoice covers multiple POs)';

COMMENT ON VIEW po_invoice_summary IS 'Summary view of PO invoicing status - used for budget calculations';
