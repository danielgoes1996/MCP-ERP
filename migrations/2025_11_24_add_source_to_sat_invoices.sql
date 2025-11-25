-- Migration: Add source field to sat_invoices
-- Date: 2025-11-24
-- Purpose: Diferenciar facturas subidas manualmente vs descargadas automáticamente del SAT

-- Add source column to sat_invoices
ALTER TABLE sat_invoices
ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'manual';

-- Add index for filtering by source
CREATE INDEX IF NOT EXISTS idx_sat_invoices_source ON sat_invoices(source);

-- Add index for pending classification from SAT auto-sync
CREATE INDEX IF NOT EXISTS idx_sat_invoices_sat_auto_pending
ON sat_invoices(company_id, source, status)
WHERE source = 'sat_auto_sync' AND status = 'pending';

-- Update description
COMMENT ON COLUMN sat_invoices.source IS 'Origin of invoice: manual (uploaded by user) or sat_auto_sync (auto-downloaded from SAT)';
