-- Mejoras al esquema de bank_movements para producción
-- Basado en el análisis de problemas identificados

-- 1. Agregar campos para separar cargo/abono
ALTER TABLE bank_movements ADD COLUMN cargo_amount REAL DEFAULT 0.0;
ALTER TABLE bank_movements ADD COLUMN abono_amount REAL DEFAULT 0.0;

-- 2. Agregar campo para descripción completa (raw)
ALTER TABLE bank_movements ADD COLUMN description_raw TEXT;

-- 3. Agregar campos para mejor categorización
ALTER TABLE bank_movements ADD COLUMN category_confidence REAL DEFAULT 0.0;
ALTER TABLE bank_movements ADD COLUMN transaction_subtype TEXT; -- 'balance_inicial', 'deposito_spei', 'gasto_gasolina', etc.

-- 4. Agregar campos para tracking de balance
ALTER TABLE bank_movements ADD COLUMN balance_before REAL;
ALTER TABLE bank_movements ADD COLUMN running_balance REAL;

-- 5. Agregar campo para estado mejorado
ALTER TABLE bank_movements ADD COLUMN display_type TEXT DEFAULT 'transaction'; -- 'balance_inicial', 'transaction', 'transfer'

-- 6. Agregar índices para las nuevas columnas
CREATE INDEX IF NOT EXISTS idx_bank_movements_cargo ON bank_movements(cargo_amount) WHERE cargo_amount > 0;
CREATE INDEX IF NOT EXISTS idx_bank_movements_abono ON bank_movements(abono_amount) WHERE abono_amount > 0;
CREATE INDEX IF NOT EXISTS idx_bank_movements_subtype ON bank_movements(transaction_subtype);
CREATE INDEX IF NOT EXISTS idx_bank_movements_display_type ON bank_movements(display_type);
CREATE INDEX IF NOT EXISTS idx_bank_movements_running_balance ON bank_movements(running_balance);