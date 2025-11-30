-- Migration: Add ticket concept extraction fields to manual_expenses
-- Date: 2025-11-25
-- Purpose: Store extracted concepts from tickets for improved invoice matching

-- Add column for storing extracted concepts from ticket
ALTER TABLE manual_expenses
ADD COLUMN IF NOT EXISTS ticket_extracted_concepts JSONB;

-- Add column for storing full extracted data from ticket
ALTER TABLE manual_expenses
ADD COLUMN IF NOT EXISTS ticket_extracted_data JSONB;

-- Add column for ticket folio (for reference)
ALTER TABLE manual_expenses
ADD COLUMN IF NOT EXISTS ticket_folio VARCHAR(100);

-- Create GIN index for fast JSONB queries on concepts
CREATE INDEX IF NOT EXISTS idx_manual_expenses_ticket_concepts
ON manual_expenses USING gin(ticket_extracted_concepts);

-- Create index on ticket_folio for lookups
CREATE INDEX IF NOT EXISTS idx_manual_expenses_ticket_folio
ON manual_expenses(ticket_folio) WHERE ticket_folio IS NOT NULL;

-- Add comments for documentation
COMMENT ON COLUMN manual_expenses.ticket_extracted_concepts IS
'Array of product/service descriptions extracted from ticket OCR. Example: ["MAGNA 40 LITROS", "Precio: $21.50/L"]';

COMMENT ON COLUMN manual_expenses.ticket_extracted_data IS
'Full extracted data from ticket including RFC, folio, dates, amounts, etc. Stores the complete TicketProcessor output.';

COMMENT ON COLUMN manual_expenses.ticket_folio IS
'Folio number extracted from ticket for cross-reference';

-- Example data structure for ticket_extracted_concepts:
-- ["MAGNA 40 LITROS"]
-- ["COCA COLA 600ML", "SANDWICH JAMON"]

-- Example data structure for ticket_extracted_data:
-- {
--   "merchant_name": "Pemex",
--   "rfc": "PRE850101ABC",
--   "folio": "A-12345",
--   "fecha": "2025-11-20",
--   "subtotal": 800.00,
--   "total": 860.00,
--   "litros": 40.0,
--   "precio_litro": 21.50,
--   "concepts": ["MAGNA 40 LITROS"],
--   "extraction_method": "ocr_claude",
--   "confidence": 0.95
-- }
