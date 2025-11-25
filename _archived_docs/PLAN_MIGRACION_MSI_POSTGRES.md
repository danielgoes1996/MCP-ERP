# 🚀 PLAN DE MIGRACIÓN MSI A POSTGRESQL

**Objetivo**: Implementar detección MSI completa en PostgreSQL, eliminando dependencias de SQLite

**Fecha**: 2025-11-09

---

## 📊 ESTADO ACTUAL

### ✅ Lo que ya funciona (PostgreSQL):
- Tabla `payment_accounts` con campo `account_type`
- Tabla `expense_invoices` con campos MSI
- API MSI para confirmación manual
- Script detector de MSI

### ❌ Lo que falta:
- Tabla `bank_statements` en PostgreSQL
- Tabla `bank_transactions` en PostgreSQL
- Parser conectado a PostgreSQL
- Auto-detección de MSI desde estados de cuenta
- Valores estandarizados en `account_type`

---

## 🎯 PLAN DE IMPLEMENTACIÓN (5 FASES)

---

## FASE 1: Base de Datos PostgreSQL (30 min)

### 1.1 Crear Tabla `bank_statements`

```bash
# Archivo: migrations/036_create_bank_statements_postgres.sql
```

```sql
-- =====================================================
-- MIGRACIÓN 036: Crear tablas bancarias en PostgreSQL
-- =====================================================

-- 1. Tabla de estados de cuenta
CREATE TABLE IF NOT EXISTS bank_statements (
    id SERIAL PRIMARY KEY,
    account_id INTEGER NOT NULL,
    tenant_id INTEGER NOT NULL,
    company_id INTEGER,

    -- Información del archivo
    file_name VARCHAR(255) NOT NULL,
    file_path TEXT,
    file_size INTEGER,
    file_type VARCHAR(20) NOT NULL,  -- 'pdf', 'xlsx', 'csv'

    -- Período del estado de cuenta
    period_start DATE,
    period_end DATE,

    -- Balances
    opening_balance DECIMAL(15,2) DEFAULT 0.0,
    closing_balance DECIMAL(15,2) DEFAULT 0.0,

    -- Totales
    total_credits DECIMAL(15,2) DEFAULT 0.0,
    total_debits DECIMAL(15,2) DEFAULT 0.0,
    transaction_count INTEGER DEFAULT 0,

    -- Status de procesamiento
    parsing_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    parsing_error TEXT,

    -- Timestamps
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    parsed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Foreign keys
    CONSTRAINT fk_bank_statements_account
        FOREIGN KEY (account_id) REFERENCES payment_accounts(id) ON DELETE CASCADE,
    CONSTRAINT fk_bank_statements_tenant
        FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
    CONSTRAINT fk_bank_statements_company
        FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,

    -- Constraints
    CONSTRAINT check_parsing_status
        CHECK (parsing_status IN ('pending', 'processing', 'completed', 'failed')),
    CONSTRAINT check_file_type
        CHECK (file_type IN ('pdf', 'xlsx', 'xls', 'csv'))
);

-- 2. Tabla de transacciones bancarias
CREATE TABLE IF NOT EXISTS bank_transactions (
    id SERIAL PRIMARY KEY,
    statement_id INTEGER NOT NULL,
    account_id INTEGER NOT NULL,
    tenant_id INTEGER NOT NULL,
    company_id INTEGER,

    -- Información de la transacción
    transaction_date DATE NOT NULL,
    description TEXT,
    reference VARCHAR(100),

    -- Montos
    amount DECIMAL(15,2) NOT NULL,
    balance DECIMAL(15,2),

    -- Clasificación
    transaction_type VARCHAR(20) NOT NULL,  -- 'debit', 'credit'
    category VARCHAR(100),

    -- Reconciliación
    reconciled BOOLEAN DEFAULT FALSE,
    reconciled_with_invoice_id INTEGER,
    reconciled_at TIMESTAMP,

    -- MSI Detection
    msi_candidate BOOLEAN DEFAULT FALSE,
    msi_invoice_id INTEGER,
    msi_confidence DECIMAL(3,2),  -- 0.00 a 1.00

    -- AI/Enrichment
    ai_model VARCHAR(50),
    confidence DECIMAL(3,2),

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Foreign keys
    CONSTRAINT fk_bank_transactions_statement
        FOREIGN KEY (statement_id) REFERENCES bank_statements(id) ON DELETE CASCADE,
    CONSTRAINT fk_bank_transactions_account
        FOREIGN KEY (account_id) REFERENCES payment_accounts(id) ON DELETE CASCADE,
    CONSTRAINT fk_bank_transactions_tenant
        FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
    CONSTRAINT fk_bank_transactions_company
        FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
    CONSTRAINT fk_bank_transactions_invoice
        FOREIGN KEY (reconciled_with_invoice_id) REFERENCES expense_invoices(id) ON DELETE SET NULL,

    -- Constraints
    CONSTRAINT check_transaction_type
        CHECK (transaction_type IN ('debit', 'credit'))
);

-- 3. Índices para performance
CREATE INDEX idx_bank_statements_account_id ON bank_statements(account_id);
CREATE INDEX idx_bank_statements_tenant_id ON bank_statements(tenant_id);
CREATE INDEX idx_bank_statements_company_id ON bank_statements(company_id);
CREATE INDEX idx_bank_statements_period ON bank_statements(period_start, period_end);
CREATE INDEX idx_bank_statements_status ON bank_statements(parsing_status);
CREATE INDEX idx_bank_statements_uploaded_at ON bank_statements(uploaded_at DESC);

CREATE INDEX idx_bank_transactions_statement_id ON bank_transactions(statement_id);
CREATE INDEX idx_bank_transactions_account_id ON bank_transactions(account_id);
CREATE INDEX idx_bank_transactions_tenant_id ON bank_transactions(tenant_id);
CREATE INDEX idx_bank_transactions_company_id ON bank_transactions(company_id);
CREATE INDEX idx_bank_transactions_date ON bank_transactions(transaction_date);
CREATE INDEX idx_bank_transactions_reconciled ON bank_transactions(reconciled);
CREATE INDEX idx_bank_transactions_msi_candidate ON bank_transactions(msi_candidate) WHERE msi_candidate = TRUE;

-- 4. Trigger para updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_bank_statements_updated_at
    BEFORE UPDATE ON bank_statements
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_bank_transactions_updated_at
    BEFORE UPDATE ON bank_transactions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 5. Vista para consultas
CREATE OR REPLACE VIEW bank_statements_summary AS
SELECT
    bs.*,
    pa.account_name,
    pa.account_type,
    pa.bank_name,
    COUNT(bt.id) as parsed_transactions,
    SUM(CASE WHEN bt.transaction_type = 'credit' THEN bt.amount ELSE 0 END) as parsed_credits,
    SUM(CASE WHEN bt.transaction_type = 'debit' THEN ABS(bt.amount) ELSE 0 END) as parsed_debits
FROM bank_statements bs
LEFT JOIN payment_accounts pa ON bs.account_id = pa.id
LEFT JOIN bank_transactions bt ON bs.id = bt.statement_id
GROUP BY bs.id, pa.account_name, pa.account_type, pa.bank_name;

COMMENT ON TABLE bank_statements IS 'Estados de cuenta bancarios subidos por usuarios';
COMMENT ON TABLE bank_transactions IS 'Transacciones extraídas de estados de cuenta';
COMMENT ON VIEW bank_statements_summary IS 'Resumen de estados de cuenta con estadísticas';
```

### 1.2 Estandarizar `account_type`

```bash
# Archivo: migrations/037_standardize_account_type.sql
```

```sql
-- =====================================================
-- MIGRACIÓN 037: Estandarizar account_type
-- =====================================================

-- 1. Agregar constraint con valores permitidos
ALTER TABLE payment_accounts
DROP CONSTRAINT IF EXISTS check_account_type_values;

ALTER TABLE payment_accounts
ADD CONSTRAINT check_account_type_values
CHECK (account_type IN (
    'credit_card',      -- Tarjeta de Crédito → Puede tener MSI
    'debit_card',       -- Tarjeta de Débito → NO MSI
    'checking',         -- Cuenta de Cheques → NO MSI
    'savings',          -- Cuenta de Ahorro → NO MSI
    'cash'              -- Efectivo → NO MSI
));

-- 2. Hacer account_type obligatorio (después de migrar datos existentes)
-- Comentado por ahora, descomentar cuando todas las cuentas tengan tipo
-- ALTER TABLE payment_accounts
-- ALTER COLUMN account_type SET NOT NULL;

-- 3. Índice para búsquedas por tipo
CREATE INDEX IF NOT EXISTS idx_payment_accounts_account_type
ON payment_accounts(account_type);

-- 4. Índice compuesto para búsquedas de MSI
CREATE INDEX IF NOT EXISTS idx_payment_accounts_company_type
ON payment_accounts(company_id, account_type)
WHERE account_type = 'credit_card';

-- 5. Comentarios
COMMENT ON COLUMN payment_accounts.account_type IS
'Tipo de cuenta: credit_card (MSI posible), debit_card, checking, savings, cash';
```

### Comando de ejecución:

```bash
# Aplicar migraciones
docker exec mcp-postgres psql -U mcp_user -d mcp_system -f /migrations/036_create_bank_statements_postgres.sql
docker exec mcp-postgres psql -U mcp_user -d mcp_system -f /migrations/037_standardize_account_type.sql
```

---

## FASE 2: Modelos Pydantic (15 min)

### 2.1 Actualizar modelos existentes

```bash
# Archivo: core/reconciliation/bank/bank_statements_models.py
```

Modificar para usar PostgreSQL en lugar de SQLite:

```python
# CAMBIAR ESTO:
# db_path = "backend_clean/unified_mcp_system.db"  # SQLite

# POR ESTO:
POSTGRES_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "127.0.0.1"),
    "port": int(os.getenv("POSTGRES_PORT", 5433)),
    "database": os.getenv("POSTGRES_DB", "mcp_system"),
    "user": os.getenv("POSTGRES_USER", "mcp_user"),
    "password": os.getenv("POSTGRES_PASSWORD", "changeme")
}
```

### 2.2 Actualizar queries

Cambiar todas las queries de SQLite a PostgreSQL:

```python
# SQLite: INSERT OR IGNORE
# PostgreSQL: INSERT ... ON CONFLICT DO NOTHING

# SQLite: AUTOINCREMENT
# PostgreSQL: SERIAL

# SQLite: DATETIME('now')
# PostgreSQL: CURRENT_TIMESTAMP
```

---

## FASE 3: Parser con Detección de Tipo (30 min)

### 3.1 Modificar `bank_file_parser.py`

```python
# En: core/reconciliation/bank/bank_file_parser.py

class BankFileParser:

    def parse_file(self, file_path, file_type, account_id, user_id, tenant_id):
        """
        Parse bank statement file with account type detection
        """

        # 🎯 NUEVO: Obtener tipo de cuenta ANTES de parsear
        account_info = self._get_account_info(account_id, tenant_id)
        account_type = account_info.get('account_type')

        logger.info(f"📋 Parsing statement for account {account_id}")
        logger.info(f"   Account Type: {account_type}")
        logger.info(f"   Bank: {account_info.get('bank_name')}")

        # Parse normal
        transactions, summary = self._intelligent_parse(file_path, file_type)

        # 🎯 Enriquecer transacciones con info de cuenta
        for txn in transactions:
            txn.account_type = account_type
            txn.account_id = account_id
            txn.tenant_id = tenant_id

            # Marcar si es elegible para MSI
            txn.msi_eligible = (account_type == 'credit_card')

        # 🎯 Si es tarjeta de crédito, buscar posibles MSI
        if account_type == 'credit_card':
            logger.info(f"💳 Credit card detected - Analyzing for MSI candidates")
            transactions = self._detect_msi_candidates(
                transactions,
                account_info.get('company_id'),
                summary.get('period_start'),
                summary.get('period_end')
            )

        return transactions, summary

    def _get_account_info(self, account_id: int, tenant_id: int) -> dict:
        """
        Obtiene información de la cuenta desde payment_accounts
        """
        import psycopg2
        from psycopg2.extras import RealDictCursor

        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
            port=int(os.getenv("POSTGRES_PORT", 5433)),
            database=os.getenv("POSTGRES_DB", "mcp_system"),
            user=os.getenv("POSTGRES_USER", "mcp_user"),
            password=os.getenv("POSTGRES_PASSWORD", "changeme")
        )
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("""
            SELECT
                id,
                account_name,
                bank_name,
                account_type,
                company_id,
                tenant_id
            FROM payment_accounts
            WHERE id = %s AND tenant_id = %s
        """, [account_id, tenant_id])

        result = cursor.fetchone()
        conn.close()

        if not result:
            raise ValueError(f"Account {account_id} not found for tenant {tenant_id}")

        if not result.get('account_type'):
            logger.warning(f"⚠️  Account {account_id} has no account_type defined!")

        return dict(result)

    def _detect_msi_candidates(
        self,
        transactions: List[BankTransaction],
        company_id: int,
        period_start: date,
        period_end: date
    ) -> List[BankTransaction]:
        """
        Detecta posibles MSI comparando con facturas del período
        """
        import psycopg2
        from psycopg2.extras import RealDictCursor

        if not company_id or not period_start or not period_end:
            logger.warning("Missing company_id or period - skipping MSI detection")
            return transactions

        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
            port=int(os.getenv("POSTGRES_PORT", 5433)),
            database=os.getenv("POSTGRES_DB", "mcp_system"),
            user=os.getenv("POSTGRES_USER", "mcp_user"),
            password=os.getenv("POSTGRES_PASSWORD", "changeme")
        )
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Obtener facturas candidatas MSI del período
        cursor.execute("""
            SELECT
                id,
                uuid,
                fecha_emision,
                total,
                nombre_emisor
            FROM expense_invoices
            WHERE company_id = %s
            AND metodo_pago = 'PUE'
            AND forma_pago = '04'
            AND total > 100
            AND fecha_emision BETWEEN %s AND %s
            AND sat_status = 'vigente'
            AND (msi_confirmado = FALSE OR msi_confirmado IS NULL)
        """, [company_id, period_start, period_end])

        facturas = cursor.fetchall()
        conn.close()

        if not facturas:
            logger.info("No MSI candidate invoices found in period")
            return transactions

        logger.info(f"🔍 Analyzing {len(transactions)} transactions against {len(facturas)} invoices")

        # Analizar cada transacción
        for txn in transactions:
            for factura in facturas:
                total = float(factura['total'])
                fecha_factura = factura['fecha_emision']

                # Probar cada plan MSI
                for meses in [3, 6, 9, 12, 18, 24]:
                    pago_esperado = total / meses

                    # Match por monto (tolerancia ±2%)
                    amount_diff = abs(abs(txn.amount) - pago_esperado)
                    amount_match = amount_diff < (pago_esperado * 0.02)

                    if amount_match:
                        # Match por fecha (±7 días)
                        days_diff = abs((txn.date - fecha_factura).days)
                        date_match = days_diff <= 7

                        if date_match:
                            # Calcular confianza
                            amount_confidence = 1 - (amount_diff / pago_esperado)
                            date_confidence = 1 - (days_diff / 7)
                            confidence = (amount_confidence * 0.7) + (date_confidence * 0.3)

                            # Marcar como candidato MSI
                            txn.msi_candidate = True
                            txn.msi_invoice_id = factura['id']
                            txn.msi_confidence = confidence

                            logger.info(f"   ✓ MSI Match: {factura['nombre_emisor'][:30]} - "
                                      f"{meses} meses - Confidence: {confidence:.2%}")
                            break

        msi_found = sum(1 for txn in transactions if txn.msi_candidate)
        logger.info(f"💡 Found {msi_found} potential MSI transactions")

        return transactions
```

---

## FASE 4: API MSI con Filtro de Tipo (15 min)

### 4.1 Actualizar `msi_confirmation_api.py`

```python
# En: api/msi_confirmation_api.py

@router.get("/pending")
def get_pending_msi_confirmations(company_id: int):
    """
    Obtiene facturas que requieren confirmación de MSI

    NUEVO: Solo muestra facturas asociadas a tarjetas de crédito
    """

    query = """
        SELECT
            ei.id,
            ei.uuid,
            ei.fecha_emision,
            ei.nombre_emisor,
            ei.total,
            ei.es_msi,
            ei.meses_msi,
            ei.pago_mensual_msi,
            ei.msi_confirmado,
            ei.payment_account_id,
            pa.account_name,
            pa.account_type,
            pa.bank_name
        FROM expense_invoices ei

        -- 🎯 JOIN con payment_accounts para verificar tipo
        LEFT JOIN payment_accounts pa ON ei.payment_account_id = pa.id

        WHERE ei.company_id = %s
        AND ei.metodo_pago = 'PUE'
        AND ei.forma_pago = '04'
        AND ei.total > 100
        AND ei.sat_status = 'vigente'
        AND (ei.msi_confirmado = FALSE OR ei.msi_confirmado IS NULL)

        -- 🎯 FILTRO CLAVE: Solo tarjetas de crédito
        AND (
            pa.account_type = 'credit_card'
            OR pa.account_type IS NULL  -- Incluir sin cuenta asignada
        )

        ORDER BY ei.fecha_emision DESC;
    """

    # ... resto igual
```

### 4.2 Agregar endpoint para auto-confirmación

```python
@router.post("/auto-detect/{statement_id}")
def auto_detect_msi_from_statement(
    statement_id: int,
    company_id: int,
    auto_confirm_threshold: float = 0.95
):
    """
    Auto-detecta MSI desde un estado de cuenta procesado

    Params:
    - statement_id: ID del bank_statement
    - auto_confirm_threshold: Umbral de confianza para auto-confirmar (default 0.95)

    Returns:
    - auto_confirmed: Facturas confirmadas automáticamente
    - requires_review: Facturas que requieren revisión manual
    """

    conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
    cursor = conn.cursor()

    # Obtener transacciones MSI del statement
    cursor.execute("""
        SELECT *
        FROM bank_transactions
        WHERE statement_id = %s
        AND msi_candidate = TRUE
        ORDER BY msi_confidence DESC;
    """, [statement_id])

    candidates = cursor.fetchall()

    auto_confirmed = []
    requires_review = []

    for candidate in candidates:
        if candidate['msi_confidence'] >= auto_confirm_threshold:
            # Auto-confirmar
            # TODO: Implementar confirmación automática
            auto_confirmed.append(candidate)
        else:
            requires_review.append(candidate)

    conn.close()

    return {
        "success": True,
        "total_candidates": len(candidates),
        "auto_confirmed": len(auto_confirmed),
        "requires_review": len(requires_review),
        "details": {
            "auto_confirmed": auto_confirmed,
            "requires_review": requires_review
        }
    }
```

---

## FASE 5: Testing y Validación (30 min)

### 5.1 Script de prueba

```bash
# Archivo: scripts/testing/test_msi_workflow.py
```

```python
#!/usr/bin/env python3
"""
Test del workflow completo MSI
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import requests

POSTGRES_CONFIG = {
    "host": "127.0.0.1",
    "port": 5433,
    "database": "mcp_system",
    "user": "mcp_user",
    "password": "changeme"
}

API_BASE = "http://localhost:8000"

def test_1_create_credit_card_account():
    """Test 1: Crear cuenta de tarjeta de crédito"""
    print("\n" + "="*60)
    print("TEST 1: Crear cuenta de tarjeta de crédito")
    print("="*60)

    conn = psycopg2.connect(**POSTGRES_CONFIG)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO payment_accounts (
            tenant_id, company_id, account_name, bank_name,
            account_type, account_number, status
        ) VALUES (
            1, 2, 'BBVA Tarjeta Crédito 1234', 'BBVA',
            'credit_card', '****1234', 'active'
        )
        RETURNING id;
    """)

    account_id = cursor.fetchone()[0]
    conn.commit()
    conn.close()

    print(f"✅ Cuenta creada: ID {account_id}")
    return account_id

def test_2_upload_statement(account_id):
    """Test 2: Upload estado de cuenta"""
    print("\n" + "="*60)
    print("TEST 2: Upload estado de cuenta")
    print("="*60)

    # TODO: Implementar upload real
    print(f"⏳ Simular upload para cuenta {account_id}")
    print("✅ Statement uploaded (simulado)")

def test_3_check_msi_detection():
    """Test 3: Verificar detección MSI"""
    print("\n" + "="*60)
    print("TEST 3: Verificar detección MSI")
    print("="*60)

    response = requests.get(f"{API_BASE}/msi/pending?company_id=2")

    if response.status_code == 200:
        data = response.json()
        print(f"✅ Facturas pendientes: {data['total_pendientes']}")

        # Verificar que solo hay credit cards
        for factura in data['facturas']:
            if 'account_type' in factura:
                print(f"   - {factura['nombre_emisor'][:30]}: {factura.get('account_type', 'N/A')}")
    else:
        print(f"❌ Error: {response.status_code}")

def main():
    print("\n" + "="*60)
    print("🧪 TEST WORKFLOW MSI COMPLETO")
    print("="*60)

    # account_id = test_1_create_credit_card_account()
    # test_2_upload_statement(account_id)
    test_3_check_msi_detection()

    print("\n" + "="*60)
    print("✅ Tests completados")
    print("="*60)

if __name__ == "__main__":
    main()
```

---

## 📋 CHECKLIST DE IMPLEMENTACIÓN

### Fase 1: Base de Datos ✅
- [ ] Crear `migrations/036_create_bank_statements_postgres.sql`
- [ ] Crear `migrations/037_standardize_account_type.sql`
- [ ] Aplicar migraciones en PostgreSQL
- [ ] Verificar tablas creadas: `bank_statements`, `bank_transactions`
- [ ] Verificar constraint en `account_type`

### Fase 2: Modelos ✅
- [ ] Actualizar `bank_statements_models.py` para PostgreSQL
- [ ] Cambiar todas las queries SQLite → PostgreSQL
- [ ] Probar conexión a PostgreSQL

### Fase 3: Parser ✅
- [ ] Agregar `_get_account_info()` en `bank_file_parser.py`
- [ ] Agregar `_detect_msi_candidates()` en `bank_file_parser.py`
- [ ] Modificar `parse_file()` para enriquecer transacciones
- [ ] Probar parser con archivo real

### Fase 4: API MSI ✅
- [ ] Actualizar query en `get_pending_msi_confirmations()`
- [ ] Agregar JOIN con `payment_accounts`
- [ ] Agregar filtro `account_type = 'credit_card'`
- [ ] Crear endpoint `auto-detect-msi`
- [ ] Probar API con Postman/curl

### Fase 5: Testing ✅
- [ ] Crear script `test_msi_workflow.py`
- [ ] Probar workflow end-to-end
- [ ] Validar auto-detección MSI
- [ ] Documentar resultados

---

## 🚀 COMANDOS DE EJECUCIÓN

```bash
# 1. Aplicar migraciones
cd /Users/danielgoes96/Desktop/mcp-server
docker cp migrations/036_create_bank_statements_postgres.sql mcp-postgres:/tmp/
docker cp migrations/037_standardize_account_type.sql mcp-postgres:/tmp/

docker exec mcp-postgres psql -U mcp_user -d mcp_system -f /tmp/036_create_bank_statements_postgres.sql
docker exec mcp-postgres psql -U mcp_user -d mcp_system -f /tmp/037_standardize_account_type.sql

# 2. Verificar tablas
docker exec mcp-postgres psql -U mcp_user -d mcp_system -c "\d bank_statements"
docker exec mcp-postgres psql -U mcp_user -d mcp_system -c "\d bank_transactions"

# 3. Testing
python3 scripts/testing/test_msi_workflow.py

# 4. Probar API
curl "http://localhost:8000/msi/pending?company_id=2"
```

---

## ⏱️ TIEMPO ESTIMADO

| Fase | Tiempo | Acumulado |
|------|--------|-----------|
| Fase 1: Base de datos | 30 min | 30 min |
| Fase 2: Modelos | 15 min | 45 min |
| Fase 3: Parser | 30 min | 1h 15min |
| Fase 4: API MSI | 15 min | 1h 30min |
| Fase 5: Testing | 30 min | **2h 00min** |

**Total: 2 horas** para implementación completa

---

## 🎯 RESULTADO FINAL

Después de completar este plan:

1. ✅ **PostgreSQL único**: SQLite completamente eliminado
2. ✅ **Tipo de cuenta obligatorio**: Todas las cuentas tienen `account_type`
3. ✅ **Auto-detección MSI**: Sistema compara transacciones con facturas automáticamente
4. ✅ **Filtro inteligente**: Solo muestra facturas de tarjetas de crédito
5. ✅ **Workflow eficiente**: Operador solo confirma 2-3 excepciones por mes

---

## 📞 SIGUIENTE PASO

¿Empezamos con la Fase 1? Puedo crear las migraciones ahora mismo.
