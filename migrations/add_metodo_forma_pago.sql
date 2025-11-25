-- Migration: Add metodo_pago and forma_pago columns to expenses table
-- Date: 2025-11-08
-- Purpose: Capture payment method (WHEN) and payment form (HOW) from CFDI

-- Add metodo_pago column
-- Values: PUE (Pago en Una Exhibición), PPD (Pago en Parcialidades o Diferido), PIP (Pago Inicial y Parcialidades)
ALTER TABLE manual_expenses
ADD COLUMN IF NOT EXISTS metodo_pago VARCHAR(3) CHECK (metodo_pago IN ('PUE', 'PPD', 'PIP'));

-- Add forma_pago column
-- Values: 01-31, 99 (see SAT c_FormaPago catalog)
ALTER TABLE manual_expenses
ADD COLUMN IF NOT EXISTS forma_pago VARCHAR(2);

-- Add comments for documentation
COMMENT ON COLUMN expenses.metodo_pago IS 'Método de pago SAT (CUÁNDO): PUE=Pago inmediato, PPD=Pago diferido, PIP=Pago inicial+parcialidades';
COMMENT ON COLUMN expenses.forma_pago IS 'Forma de pago SAT (CÓMO): 01=Efectivo, 02=Cheque, 03=Transferencia, 04=Tarjeta crédito, 28=Tarjeta débito, 99=Por definir, etc.';

-- Create index for common queries
CREATE INDEX IF NOT EXISTS idx_expenses_metodo_pago ON expenses(metodo_pago);
CREATE INDEX IF NOT EXISTS idx_expenses_forma_pago ON expenses(forma_pago);
CREATE INDEX IF NOT EXISTS idx_expenses_metodo_forma ON expenses(metodo_pago, forma_pago);
