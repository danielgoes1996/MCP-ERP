# Aplicar Migración: Método y Forma de Pago

## Opción 1: Ejecutar SQL directamente

```bash
# Conectar a tu base de datos PostgreSQL
psql -h localhost -p 5433 -U danielgoes96 -d mcp_server

# Copiar y pegar el siguiente SQL:
```

```sql
-- Add metodo_pago column
ALTER TABLE manual_expenses
ADD COLUMN IF NOT EXISTS metodo_pago VARCHAR(3) CHECK (metodo_pago IN ('PUE', 'PPD', 'PIP'));

-- Add forma_pago column
ALTER TABLE manual_expenses
ADD COLUMN IF NOT EXISTS forma_pago VARCHAR(2);

-- Add comments
COMMENT ON COLUMN expenses.metodo_pago IS 'Método de pago SAT (CUÁNDO): PUE=Pago inmediato, PPD=Pago diferido, PIP=Pago inicial+parcialidades';
COMMENT ON COLUMN expenses.forma_pago IS 'Forma de pago SAT (CÓMO): 01=Efectivo, 02=Cheque, 03=Transferencia, 04=Tarjeta crédito, 28=Tarjeta débito, 99=Por definir, etc.';

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_expenses_metodo_pago ON expenses(metodo_pago);
CREATE INDEX IF NOT EXISTS idx_expenses_forma_pago ON expenses(forma_pago);
CREATE INDEX IF NOT EXISTS idx_expenses_metodo_forma ON expenses(metodo_pago, forma_pago);

-- Verify
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'manual_expenses'
AND column_name IN ('metodo_pago', 'forma_pago');
```

## Opción 2: Desde archivo SQL

```bash
psql -h localhost -p 5433 -U danielgoes96 -d mcp_server -f migrations/add_metodo_forma_pago.sql
```

## Opción 3: Desde Docker (si usas Docker)

```bash
docker exec -i mcp-postgres psql -U danielgoes96 -d mcp_server < migrations/add_metodo_forma_pago.sql
```

## Verificar migración exitosa

```sql
-- Ver columnas creadas
\d expenses

-- Ver índices creados
\di idx_expenses_metodo*
```

Deberías ver:
- ✓ `metodo_pago` VARCHAR(3)
- ✓ `forma_pago` VARCHAR(2)
- ✓ 3 índices creados

