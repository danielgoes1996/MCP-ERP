# 📊 ANÁLISIS COMPLETO: Flujo Actual y Detección MSI

**Fecha**: 2025-11-09
**Pregunta**: "el parser actual lo hace? detalla el flujo actual y di donde podriamos ponerlo? ya viste bien la base de datos?"

---

## 🔍 RESPUESTA RÁPIDA

**NO, el parser actual NO detecta tipo de cuenta.**

### ✅ Lo que SÍ existe:
1. Campo `account_type` en tabla `payment_accounts` (PostgreSQL)
2. Parser de estados de cuenta robusto ([bank_file_parser.py](core/reconciliation/bank/bank_file_parser.py:1))
3. Sistema de clasificación tipo/subtipo en migraciones (SQLite legacy)

### ❌ Lo que NO existe:
1. Tabla `bank_statements` en PostgreSQL (solo existe migración SQLite)
2. Lógica para detectar si cuenta es crédito/débito en el parser
3. Filtro por tipo de cuenta antes de detectar MSI

---

## 📋 ESTRUCTURA DE BASE DE DATOS ACTUAL

### Tabla: `payment_accounts` (PostgreSQL - EN PRODUCCIÓN)

```
Columna          Tipo                      Nullable   Default
─────────────────────────────────────────────────────────────
id               integer                   NO         nextval(...)
tenant_id        integer                   NO
company_id       integer                   YES
account_name     varchar(255)              NO
account_number   varchar(100)              YES
bank_name        varchar(255)              YES
account_type     varchar(50)               YES        ← 🎯 ESTE CAMPO YA EXISTE!
currency         varchar(10)               YES        'MXN'
balance          double precision          YES        0
status           varchar(50)               YES        'active'
created_at       timestamp                 YES        CURRENT_TIMESTAMP
updated_at       timestamp                 YES        CURRENT_TIMESTAMP
```

**Estado Actual**:
- ✅ Campo `account_type` YA existe
- ❌ NO tiene datos (tabla vacía: 0 registros)
- ❌ NO tiene valores definidos (puede ser cualquier string)

### Tabla: `user_payment_accounts` (SQLite - LEGACY)

Esta tabla tiene un modelo más robusto con tipo/subtipo:

```sql
tipo = 'bancaria', subtipo = 'credito'  → Tarjeta de Crédito (MSI)
tipo = 'bancaria', subtipo = 'debito'   → Tarjeta de Débito (NO MSI)
tipo = 'efectivo', subtipo = NULL       → Efectivo (NO MSI)
tipo = 'terminal', subtipo = NULL       → Terminal (NO MSI)
```

**Problema**: Esta tabla es de SQLite legacy, NO está en PostgreSQL actual.

### Tabla: `bank_statements`

**Estado**: ❌ NO EXISTE en PostgreSQL
- Existe migración `019_add_bank_statements.sql` (SQLite)
- API [bank_statements_api.py](api/bank_statements_api.py:1) importa modelos que esperan esta tabla
- Parser [bank_file_parser.py](core/reconciliation/bank/bank_file_parser.py:1) funciona pero guarda a tabla inexistente

---

## 🔄 FLUJO ACTUAL (INCOMPLETO)

### Flujo Esperado (según código):

```
┌─────────────────────────────────────────────────────────────┐
│ 1. USUARIO SUBE ESTADO DE CUENTA                          │
│    POST /bank-statements/accounts/{account_id}/upload     │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. API VALIDA ARCHIVO                                      │
│    - Valida tipo: PDF, Excel, CSV                         │
│    - Valida tamaño: <50MB                                  │
│    - Crea registro en bank_statements (❌ NO EXISTE)      │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. BACKGROUND TASK: parse_statement_background()           │
│    - Actualiza status a 'processing'                       │
│    - Llama bank_file_parser.parse_file()                   │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. PARSER DETECTA BANCO Y EXTRAE TRANSACCIONES             │
│    ❌ NO detecta tipo de cuenta (crédito vs débito)       │
│    ✅ Detecta banco: Inbursa, BBVA, Santander, etc.       │
│    ✅ Extrae transacciones con fechas, montos, descrip.   │
│    ✅ Clasifica como income/expense                        │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. GUARDA TRANSACCIONES                                    │
│    - Guarda a bank_statements (❌ NO EXISTE)              │
│    - Actualiza status a 'completed'                        │
└─────────────────────────────────────────────────────────────┘
```

### Flujo Real (lo que pasa ahora):

1. ✅ API recibe archivo
2. ❌ Falla al crear registro en `bank_statements` (tabla no existe)
3. ❌ Background task nunca se ejecuta
4. Parser existe pero nunca se llama

---

## 🎯 DÓNDE PONER DETECCIÓN DE TIPO DE CUENTA

### OPCIÓN 1: Durante Creación de Cuenta (RECOMENDADO)

**Ubicación**: Al crear `payment_accounts`

**Ventaja**:
- Usuario especifica el tipo UNA VEZ
- Todas las operaciones futuras ya saben el tipo
- Más simple, menos procesamiento

**Implementación**:
```python
# En API de creación de payment_accounts
class CreatePaymentAccountRequest(BaseModel):
    account_name: str
    bank_name: str
    account_number: str
    account_type: Literal["credit_card", "debit_card", "checking"]  # ← Obligatorio

@router.post("/payment-accounts")
def create_account(request: CreatePaymentAccountRequest):
    # Validar que account_type esté definido
    if not request.account_type:
        raise HTTPException(400, "Tipo de cuenta es obligatorio")

    # Guardar con tipo
    account = PaymentAccount(
        account_type=request.account_type,  # "credit_card", "debit_card", "checking"
        ...
    )
```

**Valores permitidos**:
```python
ACCOUNT_TYPES = {
    "credit_card": "Tarjeta de Crédito",      # ← Solo este puede tener MSI
    "debit_card": "Tarjeta de Débito",        # ← NO MSI
    "checking": "Cuenta de Cheques",          # ← NO MSI
    "savings": "Cuenta de Ahorro",            # ← NO MSI
    "cash": "Efectivo"                        # ← NO MSI
}
```

---

### OPCIÓN 2: Durante Upload de Estado de Cuenta (AUTOMÁTICO)

**Ubicación**: En [bank_file_parser.py](core/reconciliation/bank/bank_file_parser.py:1)

**Ventaja**:
- Automático, no requiere input del usuario
- Detecta por contenido del archivo

**Desventaja**:
- Requiere heurísticas (puede fallar)
- Más complejo

**Implementación**:
```python
# En bank_file_parser.py
def detect_account_type(self, transactions: List, summary: dict) -> str:
    """
    Detecta si es tarjeta de crédito o débito por indicadores
    """

    # INDICADOR 1: Tiene "Pago Mínimo" o "Límite de Crédito"
    if summary.get('limite_credito') or summary.get('pago_minimo'):
        return "credit_card"

    # INDICADOR 2: Balance se muestra como negativo = crédito
    if summary.get('closing_balance', 0) < 0:
        return "credit_card"

    # INDICADOR 3: Buscar keywords en transacciones
    credit_keywords = ['PAGO RECIBIDO', 'LIMITE CREDITO', 'INTERESES']
    for txn in transactions:
        desc = txn.description.upper()
        if any(kw in desc for kw in credit_keywords):
            return "credit_card"

    # Default: débito
    return "debit_card"

def parse_file(self, file_path, file_type, account_id, user_id, tenant_id):
    transactions, summary = self._parse_with_intelligent_parser(...)

    # Detectar tipo de cuenta automáticamente
    account_type = self.detect_account_type(transactions, summary)

    # Actualizar payment_accounts
    update_payment_account_type(account_id, account_type)

    return transactions, summary
```

---

### OPCIÓN 3: Híbrida (MEJOR)

**Combinación**:
1. Usuario especifica tipo al crear cuenta (Opción 1)
2. Parser valida/corrige automáticamente (Opción 2)

**Ventaja**:
- Lo mejor de ambos mundos
- Usuario tiene control pero sistema valida

**Flujo**:
```
Usuario crea cuenta → Especifica "Tarjeta de Crédito"
                      ↓
Sube estado de cuenta → Parser detecta tipo automáticamente
                      ↓
                   ¿Coincide con lo especificado?
                      ├─ SÍ → Continúa normal
                      └─ NO → Alerta al usuario para confirmar
```

---

## 🚀 IMPLEMENTACIÓN RECOMENDADA PASO A PASO

### PASO 1: Normalizar Campo `account_type` en PostgreSQL

```sql
-- migrations/add_account_type_enum.sql

-- Definir valores permitidos
ALTER TABLE payment_accounts
ADD CONSTRAINT check_account_type_values
CHECK (account_type IN (
    'credit_card',      -- Tarjeta de Crédito → Puede tener MSI
    'debit_card',       -- Tarjeta de Débito → NO MSI
    'checking',         -- Cuenta de Cheques → NO MSI
    'savings',          -- Cuenta de Ahorro → NO MSI
    'cash'              -- Efectivo → NO MSI
));

-- Hacer obligatorio
ALTER TABLE payment_accounts
ALTER COLUMN account_type SET NOT NULL;

-- Índice para búsquedas rápidas
CREATE INDEX idx_payment_accounts_account_type
ON payment_accounts(account_type);

-- Comentario
COMMENT ON COLUMN payment_accounts.account_type IS
'Tipo de cuenta: credit_card (MSI posible), debit_card, checking, savings, cash';
```

---

### PASO 2: Crear Tabla `bank_statements` en PostgreSQL

```sql
-- migrations/create_bank_statements_postgres.sql

CREATE TABLE IF NOT EXISTS bank_statements (
    id SERIAL PRIMARY KEY,
    account_id INTEGER NOT NULL,
    tenant_id INTEGER NOT NULL,
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
    FOREIGN KEY (account_id) REFERENCES payment_accounts(id) ON DELETE CASCADE,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,

    -- Constraints
    CHECK (parsing_status IN ('pending', 'processing', 'completed', 'failed')),
    CHECK (file_type IN ('pdf', 'xlsx', 'xls', 'csv'))
);

-- Índices
CREATE INDEX idx_bank_statements_account_id ON bank_statements(account_id);
CREATE INDEX idx_bank_statements_tenant_id ON bank_statements(tenant_id);
CREATE INDEX idx_bank_statements_period ON bank_statements(period_start, period_end);
CREATE INDEX idx_bank_statements_status ON bank_statements(parsing_status);
CREATE INDEX idx_bank_statements_uploaded_at ON bank_statements(uploaded_at DESC);
```

---

### PASO 3: Modificar Parser para Filtrar por Tipo de Cuenta

```python
# En bank_file_parser.py

def parse_file(self, file_path, file_type, account_id, user_id, tenant_id):
    """
    Parse bank statement file

    NUEVO: Obtiene tipo de cuenta ANTES de parsear
    """

    # 🎯 PASO 1: Obtener tipo de cuenta de payment_accounts
    account_type = self._get_account_type(account_id, tenant_id)

    logger.info(f"Parsing statement for account {account_id} - Type: {account_type}")

    # Parse normal
    transactions, summary = self._intelligent_parse(file_path, file_type)

    # 🎯 PASO 2: Marcar transacciones con tipo de cuenta
    for txn in transactions:
        txn.account_type = account_type
        txn.msi_eligible = (account_type == 'credit_card')  # Solo crédito puede MSI

    return transactions, summary

def _get_account_type(self, account_id: int, tenant_id: int) -> str:
    """
    Obtiene el tipo de cuenta desde payment_accounts
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT account_type
        FROM payment_accounts
        WHERE id = %s AND tenant_id = %s
    """, [account_id, tenant_id])

    result = cursor.fetchone()
    conn.close()

    if not result or not result[0]:
        raise ValueError(f"Account {account_id} no tiene tipo definido")

    return result[0]
```

---

### PASO 4: Modificar API MSI para Filtrar Solo Tarjetas de Crédito

```python
# En api/msi_confirmation_api.py

@router.get("/pending")
def get_pending_msi_confirmations(company_id: int):
    """
    Obtiene facturas que requieren confirmación de MSI

    NUEVO: Solo muestra si existe cuenta de CRÉDITO asociada
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
            pa.account_type,
            pa.account_name
        FROM expense_invoices ei

        -- 🎯 JOIN con payment_accounts para verificar tipo
        LEFT JOIN payment_accounts pa ON ei.payment_account_id = pa.id

        WHERE ei.company_id = %s
        AND ei.metodo_pago = 'PUE'
        AND ei.forma_pago = '04'                     -- Tarjeta de crédito en CFDI
        AND ei.total > 100
        AND ei.sat_status = 'vigente'
        AND (ei.msi_confirmado = FALSE OR ei.msi_confirmado IS NULL)

        -- 🎯 FILTRO CLAVE: Solo si cuenta es tarjeta de crédito
        AND (pa.account_type = 'credit_card' OR pa.account_type IS NULL)

        ORDER BY ei.fecha_emision DESC;
    """

    # ... resto del código
```

---

### PASO 5: Workflow Automático MSI

```python
# En api/bank_statements_api.py - parse_statement_background()

async def parse_statement_background(
    statement_id: int,
    file_path: str,
    file_type: str,
    account_id: int,
    user_id: int,
    tenant_id: int,
    is_reparse: bool = False
):
    """
    Background task con detección automática de MSI
    """

    # Parse statement
    transactions, summary = bank_file_parser.parse_file(...)

    # 🎯 PASO 1: Verificar si es tarjeta de crédito
    account = get_payment_account(account_id)

    if account.account_type != 'credit_card':
        logger.info(f"Account {account_id} is {account.account_type} - Skipping MSI detection")
        # Guardar transacciones y terminar
        return

    logger.info(f"Account {account_id} is credit card - Detecting MSI")

    # 🎯 PASO 2: Buscar posibles MSI
    msi_candidates = detect_msi_from_transactions(
        transactions,
        company_id=account.company_id,
        period_start=summary.get('period_start'),
        period_end=summary.get('period_end')
    )

    # 🎯 PASO 3: Auto-confirmar casos obvios
    for candidate in msi_candidates:
        if candidate.confidence > 0.95:  # 95% confianza
            auto_confirm_msi(candidate)
            logger.info(f"Auto-confirmed MSI: Invoice {candidate.invoice_id}")
        else:
            # Marcar para revisión manual
            mark_for_manual_review(candidate)
            logger.info(f"Requires manual review: Invoice {candidate.invoice_id}")

def detect_msi_from_transactions(
    transactions: List[BankTransaction],
    company_id: int,
    period_start: date,
    period_end: date
) -> List[MSICandidate]:
    """
    Detecta posibles MSI comparando transacciones con facturas

    Lógica:
    1. Obtener facturas PUE + FormaPago 04 del período
    2. Para cada factura, buscar transacción con:
       - Monto = Total / N (donde N = 3, 6, 9, 12, 18, 24)
       - Fecha cercana a fecha_emision (±5 días)
    3. Si encuentra match → Posible MSI a N meses
    """

    conn = get_db_connection()
    cursor = conn.cursor()

    # Obtener facturas candidatas
    cursor.execute("""
        SELECT id, uuid, fecha_emision, total, nombre_emisor
        FROM expense_invoices
        WHERE company_id = %s
        AND metodo_pago = 'PUE'
        AND forma_pago = '04'
        AND total > 100
        AND fecha_emision BETWEEN %s AND %s
        AND (msi_confirmado = FALSE OR msi_confirmado IS NULL)
    """, [company_id, period_start, period_end])

    facturas = cursor.fetchall()
    candidates = []

    for factura in facturas:
        total = factura['total']
        fecha = factura['fecha_emision']

        # Buscar match en transacciones
        for meses in [3, 6, 9, 12, 18, 24]:
            pago_esperado = total / meses

            for txn in transactions:
                # Match por monto (±2%)
                if abs(txn.amount - pago_esperado) < (pago_esperado * 0.02):
                    # Match por fecha (±5 días)
                    days_diff = abs((txn.date - fecha).days)
                    if days_diff <= 5:
                        candidates.append(MSICandidate(
                            invoice_id=factura['id'],
                            invoice_uuid=factura['uuid'],
                            invoice_total=total,
                            meses_msi=meses,
                            pago_mensual=pago_esperado,
                            transaction_amount=txn.amount,
                            transaction_date=txn.date,
                            transaction_description=txn.description,
                            confidence=calculate_confidence(
                                monto_match=(1 - abs(txn.amount - pago_esperado) / pago_esperado),
                                fecha_match=(1 - days_diff / 5)
                            )
                        ))

    return candidates
```

---

## 📊 RESUMEN: DÓNDE PONER QUÉ

| Componente | Ubicación | Qué hacer |
|------------|-----------|-----------|
| **Campo tipo de cuenta** | `payment_accounts.account_type` | ✅ Ya existe, normalizar valores |
| **Tabla bank_statements** | Crear en PostgreSQL | ❌ No existe, crear migración |
| **Detección tipo cuenta** | Durante creación de cuenta | Usuario especifica manualmente |
| **Validación tipo** | [bank_file_parser.py](core/reconciliation/bank/bank_file_parser.py:1) | Parser verifica que coincida |
| **Filtro MSI** | [msi_confirmation_api.py](api/msi_confirmation_api.py:1) | JOIN con `payment_accounts.account_type = 'credit_card'` |
| **Auto-detección MSI** | [bank_statements_api.py](api/bank_statements_api.py:361) `parse_statement_background()` | Comparar transacciones con facturas |

---

## ✅ PRÓXIMOS PASOS (ORDEN RECOMENDADO)

1. ✅ **Migración PostgreSQL**: Crear tabla `bank_statements`
2. ✅ **Normalizar `account_type`**: Agregar constraint con valores válidos
3. ✅ **API payment_accounts**: Agregar campo obligatorio al crear cuenta
4. ✅ **Modificar parser**: Obtener y validar `account_type` antes de parsear
5. ✅ **Modificar API MSI**: Filtrar solo `account_type = 'credit_card'`
6. ✅ **Auto-detección MSI**: Implementar lógica de matching transacciones-facturas
7. ✅ **Testing**: Probar con estados de cuenta reales

---

## 🎯 RESPUESTA A TU PREGUNTA

**"el parser actual lo hace?"**
→ NO. El parser extrae transacciones pero NO detecta tipo de cuenta.

**"detalla el flujo actual"**
→ Ver sección "FLUJO ACTUAL (INCOMPLETO)" arriba.

**"di donde podriamos ponerlo?"**
→ Ver sección "DÓNDE PONER DETECCIÓN DE TIPO DE CUENTA" - Recomiendo OPCIÓN 3 (Híbrida).

**"ya viste bien la base de datos?"**
→ SÍ. Hallazgos:
- ✅ Campo `account_type` existe en `payment_accounts` (pero vacío)
- ❌ Tabla `bank_statements` NO existe en PostgreSQL
- ❌ No hay datos de ejemplo para probar
- ✅ Estructura es correcta, solo falta implementar la lógica

---

## 📝 NOTAS FINALES

**El flujo ideal sería**:

```
Usuario crea cuenta → Especifica "Tarjeta Crédito BBVA"
                      ↓
Sube estado cuenta → Parser detecta banco + valida tipo
                      ↓
Background task → Parsea transacciones
                      ↓
                   ¿Cuenta es credit_card?
                      ├─ SÍ → Buscar MSI automáticamente
                      │       Comparar montos con facturas
                      │       Auto-confirmar si confianza >95%
                      │       Marcar para revisión si confianza <95%
                      │
                      └─ NO → Solo guardar transacciones normales
                             (debit_card, checking, etc.)
```

**Ventajas**:
- ✅ Filtro en el origen (tipo de cuenta)
- ✅ Solo procesa MSI para tarjetas de crédito
- ✅ Auto-detecta mayoría de casos
- ✅ Solo 2-3 casos requieren confirmación manual
- ✅ Operador no ve ruido innecesario
