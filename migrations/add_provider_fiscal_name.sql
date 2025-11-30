-- Migración: Agregar campo para nombre fiscal del proveedor
-- Este campo almacena el nombre legal/fiscal que aparece en la factura
-- que puede ser diferente del nombre comercial

ALTER TABLE manual_expenses
ADD COLUMN IF NOT EXISTS provider_fiscal_name VARCHAR(500);

-- Crear índice para búsquedas por nombre fiscal
CREATE INDEX IF NOT EXISTS idx_manual_expenses_provider_fiscal_name
ON manual_expenses(provider_fiscal_name);

-- Comentarios para documentar
COMMENT ON COLUMN manual_expenses.provider_name IS 'Nombre comercial del proveedor (ej: "Costco", "Office Depot")';
COMMENT ON COLUMN manual_expenses.provider_fiscal_name IS 'Nombre fiscal/legal del proveedor que aparece en la factura (ej: "Costco de México S.A. de C.V.")';
COMMENT ON COLUMN manual_expenses.provider_rfc IS 'RFC del proveedor';
