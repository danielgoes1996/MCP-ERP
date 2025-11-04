# 🗺️ MAPEO COMPLETO DEL SISTEMA DE FACTURAS Y GASTOS - ContaFlow

**Fecha:** 2025-11-03
**Propósito:** Documentación técnica exacta del flujo de subida, vinculación y reconciliación de facturas

---

## 📍 1. ENDPOINTS PRINCIPALES

### **1.1. POST /expenses** (Crear Gasto)

**Archivo:** `/Users/danielgoes96/Desktop/mcp-server/main.py:2935`

**Función:**
```python
@app.post("/expenses", response_model=ExpenseResponse)
async def create_expense(
    expense: ExpenseCreate,
    tenancy_context: TenancyContext = Depends(get_tenancy_context)
) -> ExpenseResponse:
```

**Request Model:** `ExpenseCreate` (core/api_models.py:255)
```python
class ExpenseCreate(BaseModel):
    descripcion: str
    monto_total: float
    fecha_gasto: Optional[str] = None
    categoria: Optional[str] = None
    proveedor: Optional[Dict[str, Any]] = None
    rfc: Optional[str] = None
    forma_pago: Optional[str] = None
    payment_account_id: Optional[int] = None
    paid_by: str = "company_account"
    will_have_cfdi: bool = True
    company_id: str = "default"
    # ... otros campos opcionales
```

**Response Model:** `ExpenseResponse` (core/api_models.py:9)
```python
class ExpenseResponse(BaseModel):
    id: int
    descripcion: str
    monto_total: float
    fecha_gasto: Optional[str] = None
    categoria: Optional[str] = None
    proveedor: Optional[Dict[str, Any]] = None
    rfc: Optional[str] = None
    tax_info: Optional[Dict[str, Any]] = None
```

**Dependencias llamadas:**
1. `record_internal_expense()` - core/internal_db.py:1247
2. `post_expense_creation_hook()` - core/expense_escalation_hooks.py (si will_have_cfdi=True)

**Tabla que escribe:** `expense_records`

---

### **1.2. POST /invoices/parse** (Parsear CFDI XML)

**Archivo:** `/Users/danielgoes96/Desktop/mcp-server/main.py:2873`

**Función:**
```python
@app.post("/invoices/parse", response_model=InvoiceParseResponse)
async def parse_invoice(file: UploadFile = File(...)) -> InvoiceParseResponse:
```

**Input:**
- `file`: UploadFile (multipart/form-data)
- Tipo: CFDI XML (.xml)

**Response Model:** `InvoiceParseResponse` (core/api_models.py:101)
```python
class InvoiceParseResponse(BaseModel):
    subtotal: float
    iva_amount: float
    total: float
    currency: str = "MXN"
    uuid: Optional[str] = None
    rfc_emisor: Optional[str] = None
    nombre_emisor: Optional[str] = None
    fecha_emision: Optional[str] = None
    file_name: Optional[str] = None
    taxes: List[Dict[str, Any]] = Field(default_factory=list)
```

**Dependencias llamadas:**
1. `parse_cfdi_xml(content)` - core/invoice_parser.py:32

**Tabla que escribe:** Ninguna (solo parsing, no persiste)

---

### **1.3. POST /api/bulk-invoice/process-batch** (Procesamiento Masivo)

**Archivo:** `/Users/danielgoes96/Desktop/mcp-server/api/bulk_invoice_api.py:30`

**Función:**
```python
@router.post("/process-batch", response_model=BulkInvoiceMatchResponse)
async def process_invoice_batch(
    request: BulkInvoiceMatchRequest,
    background_tasks: BackgroundTasks
):
```

**Request Model:** `BulkInvoiceMatchRequest` (core/api_models.py:427)
```python
class BulkInvoiceMatchRequest(BaseModel):
    company_id: str
    invoices: List[InvoiceInput]
    auto_link_threshold: float = 0.8
    auto_mark_invoiced: bool = False
    max_concurrent_items: Optional[int] = None
    batch_metadata: Optional[Dict[str, Any]] = None
```

**Response Model:** `BulkInvoiceMatchResponse` (core/api_models.py:434)
```python
class BulkInvoiceMatchResponse(BaseModel):
    company_id: str
    batch_id: str
    processed: int
    linked: int
    no_matches: int
    errors: int
    results: List[InvoiceMatchResult]
    processing_time_ms: Optional[int] = None
    batch_metadata: Optional[Dict[str, Any]] = None
    status: str
    started_at: Optional[datetime] = None
```

**Dependencias llamadas:**
1. `bulk_invoice_processor.create_batch()` - core/bulk_invoice_processor.py:170
2. `bulk_invoice_processor.process_batch()` - core/bulk_invoice_processor.py:240 (background)
3. `_find_matching_expenses()` - core/bulk_invoice_processor.py:397
4. `_calculate_match_confidence()` - core/bulk_invoice_processor.py:451
5. `_mark_expense_invoiced()` - core/bulk_invoice_processor.py:585

**Tablas que escribe:**
- `bulk_invoice_batches`
- `bulk_invoice_batch_items`
- `expense_records` (si auto_mark_invoiced=True)

---

### **1.4. POST /expenses/{expense_id}/invoice** (Vincular Factura a Gasto)

**Archivo:** `/Users/danielgoes96/Desktop/mcp-server/main.py:3195`

**Función:**
```python
@app.post("/expenses/{expense_id}/invoice", response_model=ExpenseResponse)
async def register_expense_invoice_endpoint(
    expense_id: int,
    payload: ExpenseInvoicePayload,
    tenancy: TenancyContext = Depends(get_tenancy_context)
):
```

**Request Model:** `ExpenseInvoicePayload` (core/api_models.py:562)
```python
class ExpenseInvoicePayload(BaseModel):
    expense_id: int
    invoice_uuid: str
    invoice_data: Optional[Dict[str, Any]] = None
```

**Dependencias llamadas:**
1. `register_expense_invoice()` - core/internal_db.py (función a buscar)

**Tabla que escribe:** `expense_invoices`

---

### **1.5. POST /expenses/{expense_id}/mark-invoiced** (Marcar Gasto como Facturado)

**Archivo:** `/Users/danielgoes96/Desktop/mcp-server/main.py:3221`

**Función:**
```python
@app.post("/expenses/{expense_id}/mark-invoiced", response_model=ExpenseResponse)
async def mark_expense_as_invoiced(
    expense_id: int,
    request: ExpenseActionRequest
) -> ExpenseResponse:
```

**Request Model:** `ExpenseActionRequest` (core/api_models.py:214)
```python
class ExpenseActionRequest(BaseModel):
    actor: Optional[str] = None
    notes: Optional[str] = None
```

**Dependencias llamadas:**
1. `mark_expense_invoiced(expense_id, actor=request.actor)` - core/internal_db.py:1794

**Tabla que actualiza:** `expense_records`
- Campos: `invoice_status = 'facturado'`, `bank_status`, `updated_at`

---

### **1.6. POST /bank_reconciliation/suggestions** (Sugerencias de Conciliación)

**Archivo:** `/Users/danielgoes96/Desktop/mcp-server/main.py` (buscar en backups)

**Función:** `bank_reconciliation_suggestions()`

**Request Model:** `BankSuggestionExpense`

**Response Model:** `BankSuggestionResponse`

**Tabla que lee:** `bank_movements`, `expense_records`

---

## 📊 2. TABLAS DE BASE DE DATOS

### **2.1. Table: `expense_records`**

**Schema:**
```sql
CREATE TABLE IF NOT EXISTS "expense_records" (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Identificación
    external_reference TEXT,
    description TEXT NOT NULL,

    -- Montos
    amount REAL NOT NULL,
    currency TEXT DEFAULT 'MXN',
    tax_total REAL,
    total_paid REAL DEFAULT 0,

    -- Fechas
    expense_date TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_payment_date TEXT,

    -- Clasificación
    category TEXT,
    sat_account_code TEXT,
    sat_product_service_code TEXT,
    asset_class TEXT,

    -- Proveedor
    provider_name TEXT,
    provider_rfc TEXT,

    -- Estados del workflow
    workflow_status TEXT NOT NULL DEFAULT 'draft',
    invoice_status TEXT NOT NULL DEFAULT 'pendiente',
    invoice_status_reason TEXT,
    bank_status TEXT NOT NULL DEFAULT 'pendiente',
    validation_status TEXT DEFAULT 'pending',
    estado_iva TEXT DEFAULT 'pendiente',

    -- Datos de factura
    invoice_uuid TEXT,
    invoice_folio TEXT,
    invoice_url TEXT,
    will_have_cfdi INTEGER NOT NULL DEFAULT 1,

    -- Pago
    payment_method TEXT,
    payment_account_id INTEGER NOT NULL,
    paid_by TEXT DEFAULT 'company_account',
    payment_terms TEXT,

    -- Vinculación
    account_code TEXT,
    ticket_id INTEGER,

    -- Escalamiento
    escalated_to_invoicing BOOLEAN DEFAULT 0,
    escalated_ticket_id INTEGER,
    escalation_reason TEXT,
    escalated_at TIMESTAMP,

    -- Metadata
    tax_metadata TEXT,
    metadata TEXT,
    company_id TEXT NOT NULL DEFAULT 'default',
    periodo TEXT,

    -- Procesamiento
    processing_stage TEXT DEFAULT 'converted',
    classification_stage TEXT DEFAULT 'catalog_context',
    tax_source TEXT DEFAULT 'ocr',

    -- Flags especiales
    is_advance INTEGER NOT NULL DEFAULT 0,
    is_ppd INTEGER NOT NULL DEFAULT 0,

    -- Foreign Keys
    FOREIGN KEY (account_code) REFERENCES accounts(code),
    FOREIGN KEY (payment_account_id) REFERENCES user_payment_accounts(id),
    FOREIGN KEY (ticket_id) REFERENCES tickets(id)
);
```

**Índices:**
```sql
CREATE INDEX idx_expense_records_date ON expense_records(expense_date);
CREATE INDEX idx_expense_records_status ON expense_records(invoice_status);
CREATE INDEX idx_expense_records_bank_status ON expense_records(bank_status);
CREATE INDEX idx_expense_records_company ON expense_records(company_id);
CREATE INDEX idx_expense_records_payment_account ON expense_records(payment_account_id);
CREATE INDEX idx_expense_records_ticket ON expense_records(ticket_id);
CREATE INDEX idx_expense_escalated ON expense_records(escalated_to_invoicing, will_have_cfdi);
CREATE INDEX idx_expense_escalated_ticket ON expense_records(escalated_ticket_id);
CREATE UNIQUE INDEX idx_expense_ticket ON expense_records (ticket_id);
```

**Campos críticos para facturación:**
- `invoice_status`: Estados posibles = `'pendiente'`, `'facturado'`, `'sin_factura'`
- `invoice_uuid`: UUID del CFDI del SAT
- `invoice_folio`: Folio fiscal
- `will_have_cfdi`: Si el gasto requiere factura (0 o 1)
- `escalated_to_invoicing`: Si fue escalado a Advanced Dashboard (0 o 1)
- `escalated_ticket_id`: ID del ticket espejo creado

---

### **2.2. Table: `expense_invoices`**

**Schema:**
```sql
CREATE TABLE expense_invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    expense_id INTEGER NOT NULL,
    uuid TEXT,
    folio TEXT,
    url TEXT,
    issued_at TEXT,
    status TEXT NOT NULL DEFAULT 'registrada',
    raw_xml TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    company_id TEXT NOT NULL DEFAULT 'default',

    FOREIGN KEY (expense_id) REFERENCES expense_records(id)
);
```

**Propósito:** Almacena facturas XML completas vinculadas a gastos

**Índices:**
```sql
CREATE INDEX idx_expense_invoices_company ON expense_invoices(company_id);
```

---

### **2.3. Table: `tickets`**

**Schema:**
```sql
CREATE TABLE tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,

    -- Datos principales
    raw_data TEXT NOT NULL,
    tipo TEXT NOT NULL,
    estado TEXT NOT NULL DEFAULT 'pendiente',

    -- Identificación externa
    whatsapp_message_id TEXT,
    merchant_id INTEGER,

    -- Análisis
    llm_analysis TEXT,
    merchant_name TEXT,
    category TEXT,
    confidence REAL,

    -- Facturación
    invoice_status TEXT DEFAULT 'pendiente',
    invoice_data TEXT,
    invoice_pdf_path TEXT,
    invoice_xml_path TEXT,
    invoice_metadata TEXT,
    invoice_failure_reason TEXT,
    invoice_last_check TEXT,
    invoice_uuid TEXT,
    invoice_sat_validation TEXT,

    -- OCR
    original_image TEXT,
    extracted_text TEXT,

    -- Vinculación
    payment_account_id INTEGER,
    linked_expense_id INTEGER,
    linked_job_id INTEGER,
    expense_id INTEGER,
    is_mirror_ticket BOOLEAN DEFAULT 0,

    -- Procesamiento
    source_module TEXT DEFAULT 'ocr_upload',
    processing_stage TEXT DEFAULT 'extracted',
    validation_status TEXT DEFAULT 'pending',

    -- Auditoría
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    company_id TEXT NOT NULL DEFAULT 'default',

    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (merchant_id) REFERENCES merchants(id)
);
```

**Campos críticos:**
- `tipo`: `'expense_mirror'` cuando es ticket espejo del sistema de escalación
- `estado`: `'pendiente'`, `'pendiente_factura'`, `'completado'`
- `expense_id`: ID del gasto en expense_records (cuando es_mirror_ticket=1)
- `is_mirror_ticket`: Flag que indica si es ticket espejo (1) o ticket normal (0)
- `invoice_data`: JSON con datos de la factura descargada

**Índices:**
```sql
CREATE INDEX idx_tickets_user_id ON tickets(user_id);
CREATE INDEX idx_tickets_estado ON tickets(estado);
CREATE INDEX idx_tickets_company_id ON tickets(company_id);
CREATE INDEX idx_tickets_invoice_status ON tickets(invoice_status);
CREATE INDEX idx_tickets_expense_id ON tickets(expense_id);
CREATE INDEX idx_tickets_mirror ON tickets(is_mirror_ticket, expense_id);
```

---

### **2.4. Table: `invoice_attachments`**

**Schema:**
```sql
CREATE TABLE invoice_attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL,
    file_type TEXT NOT NULL,  -- 'pdf', 'xml', 'image'
    file_path TEXT NOT NULL,
    file_size INTEGER,
    uploaded_at TEXT NOT NULL,
    is_valid BOOLEAN DEFAULT 0,
    validation_details TEXT,

    FOREIGN KEY (ticket_id) REFERENCES tickets(id)
);
```

**Propósito:** Almacena archivos adjuntos (PDF, XML) asociados a tickets

**Índices:**
```sql
CREATE INDEX idx_invoice_attachments_ticket_id ON invoice_attachments(ticket_id);
```

---

### **2.5. Table: `bank_movements`**

**Schema:**
```sql
CREATE TABLE bank_movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Identificación
    movement_id TEXT NOT NULL UNIQUE,
    movement_date TEXT NOT NULL,

    -- Datos del movimiento
    description TEXT NOT NULL,
    amount REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'MXN',
    bank TEXT NOT NULL,
    account TEXT,
    movement_type TEXT,
    balance REAL,
    reference TEXT,

    -- Vinculación
    expense_id INTEGER,
    payment_account_id INTEGER,

    -- Metadata
    tags TEXT,
    metadata TEXT,

    -- Auditoría
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    company_id TEXT NOT NULL DEFAULT 'default'
);
```

**Campos críticos:**
- `expense_id`: ID del gasto conciliado (si existe)
- `payment_account_id`: Cuenta bancaria asociada

**Índices:**
```sql
CREATE INDEX idx_bank_movements_company ON bank_movements(company_id);
CREATE INDEX idx_bank_movements_payment_account ON bank_movements(payment_account_id);
```

---

### **2.6. Table: `bulk_invoice_batches`**

**Schema:** (inferido del código)
```sql
CREATE TABLE bulk_invoice_batches (
    batch_id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL,
    total_invoices INTEGER NOT NULL,
    auto_link_threshold REAL NOT NULL,
    auto_mark_invoiced BOOLEAN NOT NULL,
    status TEXT NOT NULL,  -- 'pending', 'processing', 'completed', 'failed'

    -- Progress
    processed_count INTEGER DEFAULT 0,
    linked_count INTEGER DEFAULT 0,
    no_matches_count INTEGER DEFAULT 0,
    errors_count INTEGER DEFAULT 0,
    failed_invoices INTEGER DEFAULT 0,

    -- Metrics
    success_rate REAL,
    processing_time_ms INTEGER,
    avg_processing_time_per_invoice INTEGER,
    throughput_invoices_per_second REAL,
    peak_memory_usage_mb INTEGER,
    cpu_usage_percent REAL,

    -- Retry
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    error_summary TEXT,

    -- Metadata
    batch_metadata TEXT,
    request_metadata TEXT,
    system_metrics TEXT,

    -- Timestamps
    started_at TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT,
    created_by INTEGER
);
```

---

### **2.7. Table: `bulk_invoice_batch_items`**

**Schema:** (inferido del código)
```sql
CREATE TABLE bulk_invoice_batch_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id TEXT NOT NULL,

    -- Invoice data
    filename TEXT NOT NULL,
    uuid TEXT,
    total_amount REAL NOT NULL,
    subtotal_amount REAL,
    iva_amount REAL,
    currency TEXT DEFAULT 'MXN',
    issued_date TEXT,
    provider_name TEXT,
    provider_rfc TEXT,
    file_size INTEGER,
    file_hash TEXT,
    raw_xml TEXT,

    -- Processing status
    item_status TEXT NOT NULL DEFAULT 'pending',
    processing_started_at TEXT,
    processing_completed_at TEXT,
    processing_time_ms INTEGER,

    -- Matching results
    matched_expense_id INTEGER,
    match_confidence REAL,
    match_method TEXT,
    match_reasons TEXT,  -- JSON array
    candidates_found INTEGER DEFAULT 0,
    candidates_data TEXT,  -- JSON array

    -- Errors
    error_message TEXT,
    error_code TEXT,
    error_details TEXT,  -- JSON

    -- Timestamps
    created_at TEXT NOT NULL,
    updated_at TEXT,

    FOREIGN KEY (batch_id) REFERENCES bulk_invoice_batches(batch_id)
);
```

---

## 🔧 3. FUNCIONES QUE ESCRIBEN/ACTUALIZAN TABLAS

### **3.1. `record_internal_expense()`**

**Archivo:** `core/internal_db.py:1247`

**Signatura:**
```python
def record_internal_expense(
    *,
    description: str,
    amount: float,
    account_code: Optional[str] = None,
    currency: str = "MXN",
    expense_date: Optional[str] = None,
    category: Optional[str] = None,
    provider_name: Optional[str] = None,
    provider_rfc: Optional[str] = None,
    workflow_status: str = "draft",
    invoice_status: str = "pendiente",
    invoice_uuid: Optional[str] = None,
    invoice_folio: Optional[str] = None,
    invoice_url: Optional[str] = None,
    tax_total: Optional[float] = None,
    tax_metadata: Optional[Dict[str, Any]] = None,
    payment_method: Optional[str] = None,
    paid_by: str = "company_account",
    will_have_cfdi: bool = True,
    bank_status: str = "pendiente",
    payment_account_id: Optional[int] = None,
    company_id: str = "default",
    tenant_id: Optional[int] = None,
    # ... otros parámetros
) -> int:  # Retorna expense_id
```

**Tabla:** `expense_records` (INSERT)

**SQL Ejecutado:**
```sql
INSERT INTO expense_records (
    description, amount, currency, expense_date, category,
    provider_name, provider_rfc, workflow_status, invoice_status,
    invoice_uuid, invoice_folio, invoice_url, tax_total, tax_metadata,
    payment_method, payment_account_id, will_have_cfdi, bank_status,
    account_code, metadata, created_at, updated_at, company_id
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
```

---

### **3.2. `mark_expense_invoiced()`**

**Archivo:** `core/internal_db.py:1794`

**Signatura:**
```python
def mark_expense_invoiced(
    expense_id: int,
    *,
    actor: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
```

**Tabla:** `expense_records` (UPDATE)

**SQL Ejecutado:**
```sql
UPDATE expense_records
SET invoice_status = 'facturado',
    bank_status = CASE
        WHEN bank_status = 'pendiente' THEN 'pendiente_bancaria'
        ELSE bank_status
    END,
    updated_at = ?
WHERE id = ?
```

**Campos que actualiza:**
- `invoice_status` → `'facturado'`
- `bank_status` → `'pendiente_bancaria'` (si estaba en `'pendiente'`)
- `updated_at` → timestamp actual

---

### **3.3. `_mark_expense_invoiced()` (Bulk Invoice Processor)**

**Archivo:** `core/bulk_invoice_processor.py:585`

**Signatura:**
```python
async def _mark_expense_invoiced(self, expense_id: int, item: InvoiceItem):
```

**Tabla:** `expense_records` (UPDATE)

**SQL Ejecutado:**
```python
await db.execute(
    "UPDATE expenses SET invoice_status = ?, metadata = json_patch(COALESCE(metadata, '{}'), ?) WHERE id = ?",
    ("invoiced", json.dumps(update_data), expense_id)
)
```

**Campos que actualiza:**
- `invoice_status` → `'invoiced'`
- `metadata` → Agrega:
  ```json
  {
    "invoice_status": "invoiced",
    "invoice_uuid": "...",
    "invoice_filename": "...",
    "invoice_linked_at": "2025-11-03T..."
  }
  ```

---

### **3.4. `_create_mirror_ticket()`**

**Archivo:** `core/expense_escalation_system.py:318`

**Signatura:**
```python
def _create_mirror_ticket(
    self,
    expense_id: int,
    expense_data: Dict[str, Any],
    user_id: Optional[int],
    company_id: str,
) -> Optional[int]:  # Retorna ticket_id
```

**Tabla:** `tickets` (INSERT)

**SQL Ejecutado:**
```python
INSERT INTO tickets (
    user_id, raw_data, tipo, estado, company_id,
    merchant_name, category, expense_id, is_mirror_ticket,
    created_at, updated_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
```

**Valores:**
- `tipo` = `'expense_mirror'`
- `estado` = `'pendiente_factura'`
- `expense_id` = ID del gasto original
- `is_mirror_ticket` = `1`

---

### **3.5. `_mark_expense_as_escalated()`**

**Archivo:** `core/expense_escalation_system.py:442`

**Signatura:**
```python
def _mark_expense_as_escalated(
    self,
    expense_id: int,
    ticket_id: int,
    reason: str
):
```

**Tabla:** `expense_records` (UPDATE)

**SQL Ejecutado:**
```python
UPDATE expense_records
SET
    escalated_to_invoicing = 1,
    escalated_ticket_id = ?,
    escalation_reason = ?,
    escalated_at = ?
WHERE id = ?
```

**Campos que actualiza:**
- `escalated_to_invoicing` → `1`
- `escalated_ticket_id` → ID del ticket espejo
- `escalation_reason` → Razón del escalamiento
- `escalated_at` → timestamp actual

---

### **3.6. `sync_ticket_back_to_expense()`**

**Archivo:** `core/expense_escalation_system.py:199`

**Signatura:**
```python
def sync_ticket_back_to_expense(
    self,
    ticket_id: int
) -> Optional[Dict[str, Any]]:
```

**Tabla:** `expense_records` (UPDATE)

**SQL Ejecutado:**
```python
UPDATE expense_records
SET
    workflow_status = 'facturado',
    estado_factura = 'facturado',
    cfdi_uuid = ?,
    rfc_proveedor = ?,
    monto_total = ?,
    subtotal = ?,
    updated_at = ?
WHERE id = ?
```

**Propósito:** Sincronizar datos del ticket (con factura descargada por RPA) de vuelta al expense original

---

## 🔄 4. FLUJO COMPLETO DE VINCULACIÓN

### **Escenario 1: Subida Individual de Factura XML**

```
┌──────────────────────────────────────────────────────────┐
│ 1. Usuario sube factura.xml                              │
│    POST /invoices/parse                                  │
└────────────────┬─────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────┐
│ 2. parse_cfdi_xml(content)                               │
│    Extrae: uuid, total, iva, emisor, receptor            │
│    NO escribe a BD                                       │
└────────────────┬─────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────┐
│ 3. Frontend recibe InvoiceParseResponse                  │
│    {uuid, total, rfc_emisor, ...}                        │
└────────────────┬─────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────┐
│ 4. Usuario busca gasto manualmente                       │
│    GET /expenses?search=...                              │
└────────────────┬─────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────┐
│ 5. Usuario vincula factura a gasto                       │
│    POST /expenses/{expense_id}/invoice                   │
│    {invoice_uuid, invoice_data}                          │
└────────────────┬─────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────┐
│ 6. INSERT INTO expense_invoices                          │
│    UPDATE expense_records                                │
│    SET invoice_status='facturado', invoice_uuid=...      │
└──────────────────────────────────────────────────────────┘
```

---

### **Escenario 2: Subida Masiva con Auto-Link**

```
┌──────────────────────────────────────────────────────────┐
│ 1. Usuario sube 1000 facturas XML                        │
│    POST /api/bulk-invoice/process-batch                  │
│    {invoices: [...], auto_link_threshold: 0.8}           │
└────────────────┬─────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────┐
│ 2. create_batch()                                        │
│    INSERT INTO bulk_invoice_batches                      │
│    INSERT INTO bulk_invoice_batch_items (x1000)          │
└────────────────┬─────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────┐
│ 3. process_batch() [Background Task]                     │
│    Procesa 10 facturas concurrentemente                  │
└────────────────┬─────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────┐
│ 4. Para cada factura:                                    │
│    _process_single_item()                                │
│    ├─ _find_matching_expenses()                          │
│    │  SELECT * FROM expense_records WHERE ...            │
│    ├─ _calculate_match_confidence()                      │
│    │  Score = 40% monto + 30% proveedor + 20% fecha      │
│    └─ Si confidence >= 0.8 →  Auto-link                  │
└────────────────┬─────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────┐
│ 5. _mark_expense_invoiced(expense_id, item)              │
│    UPDATE expense_records                                │
│    SET invoice_status='invoiced', metadata=...           │
└────────────────┬─────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────┐
│ 6. _finalize_batch()                                     │
│    UPDATE bulk_invoice_batches                           │
│    SET status='completed', success_rate=0.85             │
└──────────────────────────────────────────────────────────┘
```

---

### **Escenario 3: Escalamiento Automático + RPA**

```
┌──────────────────────────────────────────────────────────┐
│ 1. Usuario crea gasto con will_have_cfdi=True            │
│    POST /expenses                                        │
│    {descripcion, monto_total, will_have_cfdi: true}      │
└────────────────┬─────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────┐
│ 2. record_internal_expense()                             │
│    INSERT INTO expense_records                           │
│    Retorna expense_id = 128                              │
└────────────────┬─────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────┐
│ 3. post_expense_creation_hook(expense_id=128)            │
│    if should_escalate() → True                           │
└────────────────┬─────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────┐
│ 4. escalate_expense_to_invoicing()                       │
│    ├─ _create_mirror_ticket()                            │
│    │  INSERT INTO tickets                                │
│    │  (tipo='expense_mirror', expense_id=128,            │
│    │   is_mirror_ticket=1)                               │
│    │  → Retorna ticket_id = 436                          │
│    ├─ _create_invoicing_job()                            │
│    │  INSERT INTO invoicing_jobs                         │
│    │  (ticket_id=436, estado='pendiente')                │
│    └─ _mark_expense_as_escalated()                       │
│       UPDATE expense_records                             │
│       SET escalated_to_invoicing=1,                      │
│           escalated_ticket_id=436                        │
└────────────────┬─────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────┐
│ 5. RPA Worker procesa ticket 436                         │
│    - Navega al portal del proveedor                      │
│    - Descarga PDF y XML                                  │
│    - Guarda en invoice_attachments                       │
│    - UPDATE tickets SET invoice_data={...}               │
└────────────────┬─────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────┐
│ 6. sync_ticket_back_to_expense(ticket_id=436)            │
│    UPDATE expense_records (expense_id=128)               │
│    SET workflow_status='facturado',                      │
│        cfdi_uuid='...', updated_at=now                   │
└──────────────────────────────────────────────────────────┘
```

---

## 📋 5. ESTADOS Y TRANSICIONES

### **5.1. Estados de `invoice_status` en `expense_records`**

```
┌─────────────┐
│ 'pendiente' │ ← Estado inicial
└──────┬──────┘
       │
       ├─────────────────────────┐
       │                         │
       ▼                         ▼
┌──────────────┐        ┌─────────────────┐
│ 'facturado'  │        │ 'sin_factura'   │
└──────────────┘        └─────────────────┘
```

**Transiciones:**
- `'pendiente'` → `'facturado'`: Cuando se vincula factura (mark_expense_invoiced)
- `'pendiente'` → `'sin_factura'`: Cuando usuario marca "no requiere factura"

---

### **5.2. Estados de `bank_status` en `expense_records`**

```
┌─────────────┐
│ 'pendiente' │ ← Estado inicial
└──────┬──────┘
       │
       ├─────────────────────────────────┐
       │                                 │
       ▼                                 ▼
┌───────────────────┐          ┌──────────────────┐
│ 'pendiente_       │          │ 'conciliado'     │
│  bancaria'        │          └──────────────────┘
└───────────────────┘
       │
       │
       ▼
┌──────────────────┐
│ 'conciliado'     │
└──────────────────┘
```

**Transiciones:**
- `'pendiente'` → `'pendiente_bancaria'`: Cuando se factura pero no se reconcilia con banco
- `'pendiente'` → `'conciliado'`: Cuando se reconcilia directamente con movimiento bancario
- `'pendiente_bancaria'` → `'conciliado'`: Cuando se reconcilia después de facturar

---

### **5.3. Estados de `item_status` en `bulk_invoice_batch_items`**

```
┌─────────────┐
│ 'pending'   │ ← Estado inicial
└──────┬──────┘
       │
       ▼
┌──────────────┐
│ 'processing' │
└──────┬───────┘
       │
       ├──────────────────┬─────────────────┬──────────────────┐
       │                  │                 │                  │
       ▼                  ▼                 ▼                  ▼
┌──────────┐    ┌────────────────┐  ┌───────────┐   ┌────────────┐
│'matched' │    │'manual_review_ │  │'no_match' │   │  'error'   │
│          │    │ required'      │  │           │   │            │
└──────────┘    └────────────────┘  └───────────┘   └────────────┘
```

---

## 🎯 6. CASOS DE USO PRINCIPALES

### **Caso 1: Gasto SIN factura (efectivo, sin comprobante)**
```
1. POST /expenses {will_have_cfdi: false}
2. record_internal_expense() → expense_id
3. NO se llama a escalation hook
4. invoice_status = 'pendiente'
5. Usuario marca: POST /expenses/{id}/close-no-invoice
6. invoice_status → 'sin_factura'
```

### **Caso 2: Gasto CON factura (tarjeta corporativa)**
```
1. POST /expenses {will_have_cfdi: true}
2. record_internal_expense() → expense_id = 128
3. post_expense_creation_hook(128)
4. Escalamiento automático:
   - Crea ticket 436 (tipo='expense_mirror', expense_id=128)
   - Crea invoicing_job (ticket_id=436)
   - UPDATE expense_records SET escalated_to_invoicing=1
5. RPA descarga factura del portal del proveedor
6. sync_ticket_back_to_expense(436)
7. UPDATE expense_records SET invoice_status='facturado', cfdi_uuid='...'
```

### **Caso 3: Subida masiva de 1000 XMLs**
```
1. POST /api/bulk-invoice/process-batch
   {invoices: [...1000...], auto_link_threshold: 0.8}
2. create_batch() → batch_id = 'batch_abc123'
3. process_batch() [background]
   - Para cada factura: busca gastos candidatos
   - Calcula confidence score
   - Si ≥ 0.8 → auto-link
4. Resultado:
   - 847 vinculadas automáticamente
   - 128 sin coincidencias
   - 25 errores
```

---

## 🔍 7. QUERIES SQL IMPORTANTES

### **7.1. Buscar gastos candidatos para una factura**

```sql
SELECT
    id, description, amount, provider_name, expense_date,
    category, metadata, created_at
FROM expense_records
WHERE company_id = ?
  AND invoice_status != 'facturado'  -- Solo gastos sin factura
  AND ABS(amount - ?) <= (? * 0.1)   -- Tolerancia 10% en monto
ORDER BY ABS(amount - ?) ASC, created_at DESC
LIMIT 10
```

**Parámetros:**
- `company_id`: "default"
- `amount`: 15000.00 (monto de la factura)

---

### **7.2. Obtener estado de escalamiento de un gasto**

```sql
SELECT
    e.escalated_to_invoicing,
    e.escalated_ticket_id,
    e.escalation_reason,
    e.escalated_at,
    t.estado AS ticket_estado,
    j.estado AS job_estado
FROM expense_records e
LEFT JOIN tickets t ON e.escalated_ticket_id = t.id
LEFT JOIN invoicing_jobs j ON t.id = j.ticket_id
WHERE e.id = ?
```

---

### **7.3. Buscar tickets espejo de un gasto**

```sql
SELECT * FROM tickets
WHERE expense_id = ?
  AND is_mirror_ticket = 1
  AND tipo = 'expense_mirror'
```

---

### **7.4. Obtener gastos pendientes de facturar**

```sql
SELECT * FROM expense_records
WHERE invoice_status = 'pendiente'
  AND will_have_cfdi = 1
  AND company_id = ?
ORDER BY expense_date DESC
```

---

### **7.5. Estadísticas de procesamiento masivo**

```sql
SELECT
    COUNT(*) as total_batches,
    SUM(total_invoices) as total_invoices,
    SUM(linked_count) as total_linked,
    AVG(success_rate) as avg_success_rate,
    AVG(processing_time_ms) / 1000.0 as avg_processing_seconds
FROM bulk_invoice_batches
WHERE company_id = ?
  AND created_at >= ?
```

---

## 📌 RESUMEN EJECUTIVO

### **Endpoints clave:**
1. `POST /expenses` - Crear gasto
2. `POST /invoices/parse` - Parsear CFDI XML
3. `POST /api/bulk-invoice/process-batch` - Procesamiento masivo
4. `POST /expenses/{id}/invoice` - Vincular factura
5. `POST /expenses/{id}/mark-invoiced` - Marcar facturado

### **Tablas clave:**
1. `expense_records` - Gastos principales
2. `expense_invoices` - Facturas vinculadas
3. `tickets` - Tickets (incluye tickets espejo)
4. `bank_movements` - Movimientos bancarios
5. `bulk_invoice_batches` - Lotes de procesamiento masivo

### **Flujos principales:**
1. **Manual:** Subir XML → Parsear → Buscar gasto → Vincular
2. **Automático:** Crear gasto → Escalamiento → RPA descarga → Sincronizar
3. **Masivo:** Subir lote → Matching automático → Vinculación batch

### **Campos críticos:**
- `invoice_status`: `'pendiente'`, `'facturado'`, `'sin_factura'`
- `will_have_cfdi`: `0` (no requiere) o `1` (requiere factura)
- `escalated_to_invoicing`: `0` o `1` (si fue escalado)
- `escalated_ticket_id`: ID del ticket espejo
- `is_mirror_ticket`: `0` o `1` (en tabla tickets)

---

**Fin del Mapeo**
