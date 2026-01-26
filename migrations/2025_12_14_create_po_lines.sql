-- Migration: Create Purchase Order Lines table
-- Date: 2025-12-14
-- Description: Professional B2B-grade Purchase Orders with line items support
--              Allows detailed tracking of individual products/services per PO
--              Supports quantity tracking (ordered, received, invoiced)

CREATE TABLE IF NOT EXISTS po_lines (
    id SERIAL PRIMARY KEY,
    po_id INTEGER NOT NULL REFERENCES purchase_orders(id) ON DELETE CASCADE,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),

    -- Line identification
    line_number INTEGER NOT NULL,  -- Sequential within PO (1, 2, 3...)

    -- Product/Service details
    sku VARCHAR(100),                           -- Optional SKU/Part Number
    description TEXT NOT NULL,                   -- Line item description
    unit_of_measure VARCHAR(20) DEFAULT 'PZA',  -- 'PZA', 'KG', 'M', 'HR', etc.

    -- Pricing
    quantity DECIMAL(12,3) NOT NULL CHECK (quantity > 0),
    unit_price DECIMAL(12,2) NOT NULL CHECK (unit_price >= 0),
    line_total DECIMAL(12,2) NOT NULL CHECK (line_total >= 0),

    -- Tracking quantities
    quantity_received DECIMAL(12,3) DEFAULT 0 CHECK (quantity_received >= 0),
    quantity_invoiced DECIMAL(12,3) DEFAULT 0 CHECK (quantity_invoiced >= 0),

    -- Optional SAT product/service code from CFDI
    clave_prod_serv VARCHAR(20),  -- e.g., '43211500' for industrial machinery

    -- Notes
    notes TEXT,

    -- Audit fields
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Constraints
    CONSTRAINT unique_po_line_number UNIQUE (po_id, line_number),
    CONSTRAINT valid_received_quantity CHECK (quantity_received <= quantity),
    CONSTRAINT valid_invoiced_quantity CHECK (quantity_invoiced <= quantity)
);

-- Indexes for performance
CREATE INDEX idx_po_lines_po_id ON po_lines(po_id);
CREATE INDEX idx_po_lines_tenant_id ON po_lines(tenant_id);
CREATE INDEX idx_po_lines_sku ON po_lines(sku) WHERE sku IS NOT NULL;

-- Trigger to auto-update updated_at
CREATE OR REPLACE FUNCTION update_po_lines_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_po_lines_updated_at
    BEFORE UPDATE ON po_lines
    FOR EACH ROW
    EXECUTE FUNCTION update_po_lines_updated_at();

-- Comments
COMMENT ON TABLE po_lines IS 'Purchase Order line items - detailed product/service breakdown for B2B Purchase Orders';
COMMENT ON COLUMN po_lines.line_total IS 'Calculated as quantity * unit_price (stored for audit/history)';
COMMENT ON COLUMN po_lines.quantity_received IS 'Quantity physically received (goods receipt)';
COMMENT ON COLUMN po_lines.quantity_invoiced IS 'Total quantity covered by linked invoices';
