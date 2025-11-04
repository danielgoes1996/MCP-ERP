# Respuestas Técnicas Completas - Sistema MCP

## Índice de Respuestas

1. ✅ [Integración Base de Datos](#1-integración-base-de-datos)
2. ✅ [Conciliación Compleja](#2-conciliación-compleja-efectivo--banco)
3. ⚠️ [Escalabilidad del Motor IA](#3-escalabilidad-del-motor-ia)
4. ✅ [Diseño de Endpoints](#4-diseño-de-endpoints)
5. ✅ [Experiencia de Usuario (UX)](#5-experiencia-de-usuario-ux)
6. ⏳ [Historial y Auditoría](#6-historial-y-auditoría)
7. ✅ [Control de Estados](#7-control-de-estados-anticipos)
8. ✅ [Integración UI–Backend](#8-integración-ui-backend)
9. ⏳ [Errores y Recuperación](#9-errores-y-recuperación)
10. ❌ [Seguridad y Roles](#10-seguridad-y-roles)

---

## 1. Integración Base de Datos

### ✅ Estado: IMPLEMENTADO

**Diseño de Integridad Referencial**:

```
expense_records (gasto principal)
├── id (PK)
├── bank_status: 'pending' | 'reconciled' | 'advance' | 'non_reconcilable'
├── is_employee_advance: BOOLEAN
├── advance_id → employee_advances.id
└── matched_movement_id → bank_movements.id

employee_advances (anticipos)
├── id (PK)
├── expense_id → expense_records.id (ON DELETE CASCADE)
├── reimbursement_movement_id → bank_movements.id (ON DELETE SET NULL)
├── status: 'pending' | 'partial' | 'completed' | 'cancelled'
└── pending_amount (calculado automáticamente)

bank_reconciliation_splits (conciliación 1:N, N:1)
├── id (PK)
├── split_group_id (identificador único)
├── expense_id → expense_records.id (ON DELETE CASCADE)
├── movement_id → bank_movements.id (ON DELETE CASCADE)
└── allocated_amount
```

**Medidas Anti-Duplicados**:

1. **Triggers Automáticos**:
   - `mark_advance_non_reconcilable`: Marca expense como `bank_status='advance'` al crear anticipo
   - `calculate_advance_pending_amount`: Calcula pending_amount = advance - reimbursed
   - `update_advance_pending_amount`: Auto-transición pending → partial → completed

2. **Validaciones en Service Layer**:
```python
# core/employee_advances_service.py:70-71
if expense['bank_status'] == 'advance':
    raise ValueError(f"Expense already registered as an advance")
```

3. **Índices Únicos** (propuestos):
```sql
CREATE UNIQUE INDEX idx_expense_advance_active
ON employee_advances(expense_id)
WHERE status IN ('pending', 'partial');
```

**Resultado**: ✅ Sin duplicados detectados en testing.

---

## 2. Conciliación Compleja (Efectivo + Banco)

### ✅ Estado: FUNCIONAL

**Escenario Real**: Empleado paga $1,000 en efectivo → Empresa reembolsa $1,000 por banco

**Flujo Implementado**:

```sql
-- 1. Crear gasto (efectivo)
INSERT INTO expense_records (
    amount = 1000,
    payment_method = 'efectivo',
    bank_status = 'non_reconcilable'  -- No esperamos mov. bancario
);

-- 2. Registrar como anticipo
INSERT INTO employee_advances (
    expense_id = 123,
    advance_amount = 1000,
    status = 'pending'
);
-- Trigger automático: expense.bank_status → 'advance'

-- 3. Cuando llega reembolso bancario
INSERT INTO bank_movements (
    amount = 1000,
    description = 'REEMBOLSO EMPLEADO'
);

-- 4. Procesar reembolso (vincula expense + bank_movement)
POST /employee_advances/reimburse
{
    "advance_id": 1,
    "reimbursement_amount": 1000,
    "reimbursement_type": "transfer",
    "reimbursement_movement_id": 8181  -- ✅ Link al banco
}

-- Resultado:
-- advance.status = 'completed'
-- advance.reimbursement_movement_id = 8181
-- expense.reimbursement_status = 'completed'
```

**Clave**: El gasto NO se concilia (bank_status='advance'), pero el **reembolso** sí se vincula vía `reimbursement_movement_id`.

---

## 3. Escalabilidad del Motor IA

### ⚠️ Estado: FUNCIONA HASTA ~100 MOVIMIENTOS, NO ESCALA A 10K

**Limitaciones Actuales**:

```python
# core/ai_reconciliation_service.py:169
cursor.execute("""
    SELECT * FROM expense_records
    WHERE bank_status = 'pending'
    ORDER BY amount DESC, date DESC
    LIMIT 50  -- ❌ Hardcoded
""")

# Algoritmo greedy: O(n²) sin optimización
# Sin índices full-text en descripciones
# Cálculo de similitud en Python (lento)
```

**Benchmark Estimado**:

| Movimientos | Expenses | Tiempo Actual | Tiempo Optimizado |
|-------------|----------|---------------|-------------------|
| 100 | 80 | 1.5s | 1.5s |
| 1,000 | 800 | ~15s | ~4s |
| 10,000 | 8,000 | ~300s (5 min) | ~20s |

**Mejoras Propuestas** (ver `SCALABILITY_IMPROVEMENTS.md`):

1. **Fase 1** (inmediata): Índices DB + pre-filtrado por monto
```sql
CREATE INDEX idx_expense_amount_date
ON expense_records(amount, date)
WHERE bank_status = 'pending';

CREATE INDEX idx_movement_amount_date
ON bank_movements(amount, date)
WHERE matched_expense_id IS NULL;
```

2. **Fase 2**: Algorithm Dynamic Programming (O(n * target * max_items) vs O(2^n))

3. **Fase 3**: Embeddings con FAISS para similitud de texto
```python
from sentence_transformers import SentenceTransformer
import faiss

# Búsqueda de texto en O(log n) vs O(n)
```

4. **Fase 4**: Procesamiento asíncrono con Celery

**Conclusión**: ⚠️ Requiere refactoring para escalar.

---

## 4. Diseño de Endpoints

### ✅ Estado: CONSISTENTE CON BUENAS PRÁCTICAS

**Estructura Actual**:

```
/employee_advances                    # CRUD anticipos
/employee_advances/summary/all        # Dashboard
/employee_advances/pending/all        # Pendientes
/employee_advances/reimburse          # Acción especial

/bank_reconciliation/ai/suggestions   # Sugerencias IA
/bank_reconciliation/ai/auto-apply    # Auto-aplicar
```

**Convenciones Aplicadas**:

- ✅ Prefijos semánticos (`/employee_advances`, `/bank_reconciliation/ai`)
- ✅ Tags para Swagger (["Employee Advances"], ["AI Reconciliation"])
- ✅ RESTful verbs (GET /list, POST /create, POST /reimburse)
- ✅ Sub-recursos con `/` (no guiones): `/summary/all`, `/pending/all`

**Inconsistencias Detectadas**:

- ⚠️ Algunos módulos usan `/api/v1`, otros no
- ⚠️ Mezcla de snake_case y kebab-case en rutas

**Migración Propuesta a v2** (ver `API_CONVENTIONS.md`):

```python
# Deprecation path
/api/v1/employee-advances  # Legacy
/api/v2/employee-advances  # Nuevo (breaking changes)
```

---

## 5. Experiencia de Usuario (UX)

### ✅ Estado: TRANSPARENTE CON SCORING VISUAL

**Elementos Implementados**:

1. **Semáforo de Confianza**:
```html
<!-- Verde: Alta confianza ≥85% -->
<div class="bg-green-100 border-green-400">
    92% ALTA CONFIANZA
</div>

<!-- Amarillo: Media confianza 60-84% -->
<div class="bg-yellow-100 border-yellow-400">
    76% CONFIANZA MEDIA
</div>
```

2. **Desglose de Scoring**:
```javascript
// Barras de progreso por factor
Monto:  47.5/50 pts (95%) ███████████░░
Fecha:  27/30 pts (90%)   ██████████░░░
Texto:  18/20 pts (90%)   █████████░░░░
```

3. **Acción Manual Prioritaria**:
```html
<!-- Botón "Revisar" siempre visible -->
<button onclick="reviewSuggestion()">
    <i class="fas fa-search"></i> Revisar
</button>

<!-- Botón "Aplicar" solo si ≥85% -->
${score >= 85 ? `<button>Aplicar</button>` : ''}
```

**Mejoras Propuestas** (ver `UX_TRANSPARENCY_IMPROVEMENTS.md`):

- Modal "¿Cómo se calculó esto?" con fórmulas
- Tutorial interactivo en primera visita
- Feedback loop (👍/👎 después de aplicar)
- Dashboard de accuracy histórico

---

## 6. Historial y Auditoría

### ⏳ Estado: PARCIAL - FALTA AUDIT LOG COMPLETO

**Datos Guardados Actualmente**:

```sql
-- En bank_reconciliation_splits:
✅ split_group_id (identificador único)
✅ created_at (timestamp)
❌ created_by (NULL - no captura usuario)
❌ ai_confidence_score (no se guarda)

-- En employee_advances:
✅ notes (historial texto libre)
✅ reimbursement_movement_id (link a banco)
❌ user_id (quién procesó reembolso)
```

**Datos FALTANTES para Auditoría en 2 años**:

- ❌ Quién creó/modificó cada registro
- ❌ Score de confianza IA al momento de aplicar
- ❌ Si fue manual vs automático
- ❌ Factura CFDI UUID vinculada
- ❌ Attachments (tickets, aprobaciones)

**Solución Propuesta** (ver `AUDIT_TRAIL_IMPLEMENTATION.md`):

```sql
-- Nueva tabla
CREATE TABLE expense_audit_log (
    id INTEGER PRIMARY KEY,
    expense_id INTEGER,
    action_type TEXT,  -- 'created', 'updated', 'reconciled'
    user_id INTEGER,
    user_name TEXT,
    field_changed TEXT,
    old_value TEXT,
    new_value TEXT,
    action_source TEXT,  -- 'manual', 'ai_suggestion', 'voice_input'
    ip_address TEXT,
    timestamp TIMESTAMP
);

CREATE TABLE reconciliation_evidence (
    id INTEGER PRIMARY KEY,
    expense_id INTEGER,
    movement_id INTEGER,
    ai_confidence_score REAL,
    ai_breakdown JSON,
    reconciliation_method TEXT,  -- 'ai_auto', 'manual'
    invoice_uuid TEXT,
    invoice_pdf_path TEXT,
    attachments JSON
);
```

**Endpoint de Auditoría**:
```python
GET /audit/expense/123

Response:
{
    "audit_log": [
        {
            "timestamp": "2025-01-15 10:30",
            "action": "created",
            "user": "Juan Pérez",
            "source": "voice_input"
        },
        {
            "timestamp": "2025-01-17 14:20",
            "action": "reconciled",
            "user": "María García",
            "source": "ai_suggestion",
            "ai_score": 92.5
        }
    ],
    "evidence": {
        "invoice_uuid": "A1B2C3D4...",
        "attachments": ["ticket.jpg"]
    }
}
```

---

## 7. Control de Estados (Anticipos)

### ✅ Estado: VALIDACIÓN ROBUSTA

**Validación Actual**:

```python
# core/employee_advances_service.py:422-423
if advance.reimbursed_amount > 0:
    raise ValueError("Cannot cancel advance that has been partially reimbursed")
```

**Matriz de Estados Permitidos**:

| Estado Inicial | Acción | Estado Final | Resultado |
|----------------|--------|--------------|-----------|
| pending ($1000) | Cancelar completo | cancelled | ✅ OK |
| partial ($600 pend) | Cancelar completo | ❌ ERROR | "Cannot cancel - already reimbursed" |
| partial ($600 pend) | Cancelar resto | cancelled_partial | ⏳ Propuesto |
| completed | Cancelar | ❌ ERROR | "Already completed" |
| cancelled | Reembolsar | ❌ ERROR | "Advance is cancelled" |

**Anti-Duplicados - 3 Niveles**:

1. **Trigger DB**:
```sql
-- Marca expense como 'advance' automáticamente
CREATE TRIGGER mark_advance_non_reconcilable ...
```

2. **Service Validation**:
```python
if expense['bank_status'] == 'advance':
    raise ValueError("Already registered as advance")
```

3. **Límite por Empleado** (propuesto):
```python
# Máximo $10,000 pendientes por mes por empleado
if total_pending + new_amount > 10000:
    raise ValueError("Exceeds monthly advance limit")
```

---

## 8. Integración UI–Backend

### ✅ Estado: REQUEST-RESPONSE + MANUAL REFRESH

**Flujo Actual**:

```javascript
// 1. POST al backend
const response = await fetch('/employee_advances/', {
    method: 'POST',
    body: JSON.stringify(payload)
});

// 2. Backend responde con objeto completo
const created = await response.json();

// 3. REFRESH desde BD (no solo agregar al array local)
await loadSummary();   // Re-fetch totals
await loadAdvances();  // Re-fetch lista

// 4. Feedback
alert('✅ Anticipo creado');
```

**Ventajas**:
- ✅ Simple, sin infraestructura adicional
- ✅ Datos siempre sincronizados con BD

**Desventajas**:
- ❌ Otro usuario crea anticipo → Yo no lo veo hasta refresh manual
- ❌ Cada acción = 2 requests extras (summary + list)

**Propuesta: Server-Sent Events (SSE)**:

```python
# Backend
@router.get("/notifications/stream")
async def notification_stream():
    async def event_generator():
        while True:
            event = await notification_queue.get()
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# Modificar servicios
async def create_advance(...):
    # ... crear ...
    await emit_notification("advance_created", {...})
```

```javascript
// Frontend
const eventSource = new EventSource('/notifications/stream');

eventSource.onmessage = function(event) {
    const notification = JSON.parse(event.data);

    if (notification.type === 'advance_created') {
        loadAdvances();  // Auto-refresh
        showToast(`Nuevo anticipo: ${notification.data.employee_name}`);
    }
};
```

**Fallback: Polling cada 30s** para navegadores antiguos.

---

## 9. Errores y Recuperación

### ⏳ Estado: BÁSICO - SOLO LOGGING, SIN ESTADO DE ERROR

**Problema Actual**:

```python
# modules/invoicing_agent/services/hybrid_processor.py
def process_bank_statement(pdf_path):
    try:
        movements = extract_with_pdfplumber(pdf_path)
        return movements
    except Exception as e:
        logger.error(f"Error parsing: {e}")
        return []  # ❌ Solo logea, no guarda estado
```

Si falla el parser → Movimientos simplemente no se procesan. **No hay registro del error en BD**.

**Solución Propuesta** (ver `TECHNICAL_QUESTIONS_7_TO_10.md`):

```sql
CREATE TABLE bank_statement_uploads (
    id INTEGER PRIMARY KEY,
    filename TEXT,
    status TEXT,  -- 'pending', 'processing', 'completed', 'partial_success', 'failed'
    movements_extracted INTEGER,
    movements_saved INTEGER,
    movements_failed INTEGER,
    error_type TEXT,  -- 'parse_error', 'corrupted_pdf'
    error_message TEXT,
    parser_method TEXT,  -- 'pdfplumber', 'pymupdf', 'ocr'
    retry_count INTEGER
);

CREATE TABLE bank_movement_errors (
    id INTEGER PRIMARY KEY,
    upload_id INTEGER,
    line_number INTEGER,
    raw_text TEXT,
    error_type TEXT,  -- 'invalid_date', 'invalid_amount'
    suggested_fix JSON,  -- IA sugiere corrección
    status TEXT  -- 'pending', 'fixed', 'ignored'
);
```

**UI de Recuperación**:

```html
<div class="upload-result">
    ✅ 85 movimientos guardados
    ⚠️ 5 líneas con errores
    <button onclick="showErrors()">Revisar Errores</button>
</div>

<!-- Modal de corrección -->
<div class="error-row">
    <div class="raw-text">15/01 PEMEX -85050</div>
    <div class="suggested-fix">
        <input type="date" value="2025-01-15">
        <input value="-850.50">
    </div>
    <button onclick="applyFix()">Aplicar</button>
</div>
```

**Reintentos Automáticos**:
```python
@router.post("/bank-statements/retry/{upload_id}")
async def retry_failed_upload(upload_id):
    if upload['retry_count'] >= 3:
        return {"error": "Max retries exceeded"}

    # Intentar con parser diferente
    if last_method == 'pdfplumber':
        result = process_with_pymupdf(...)
    elif last_method == 'pymupdf':
        result = process_with_ocr(...)
```

---

## 10. Seguridad y Roles

### ❌ Estado: **SIN AUTENTICACIÓN** (CRÍTICO)

**Problema CRÍTICO**:

```bash
curl http://localhost:8004/employee_advances/
# Retorna TODOS los anticipos sin credenciales ❌
```

Cualquiera con acceso al puerto puede:
- ❌ Ver todos los anticipos de todos
- ❌ Crear anticipos fraudulentos
- ❌ Procesar reembolsos
- ❌ Ver movimientos bancarios completos

**Solución: Sistema JWT + RBAC**:

1. **Tabla de usuarios**:
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE,
    email TEXT UNIQUE,
    password_hash TEXT,
    employee_id INTEGER,
    role TEXT CHECK(role IN ('employee', 'accountant', 'manager', 'admin'))
);

CREATE TABLE permissions (
    role TEXT,
    resource TEXT,  -- 'employee_advances', 'bank_reconciliation'
    action TEXT,    -- 'read', 'create', 'update'
    scope TEXT      -- 'own', 'all'
);

-- Ejemplos
INSERT INTO permissions VALUES
    ('employee', 'employee_advances', 'read', 'own'),
    ('employee', 'employee_advances', 'create', 'own'),
    ('accountant', 'employee_advances', 'read', 'all'),
    ('accountant', 'employee_advances', 'update', 'all'),
    ('accountant', 'bank_reconciliation', 'create', 'all');
```

2. **Auth middleware**:
```python
from fastapi.security import OAuth2PasswordBearer
from jose import jwt

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    payload = jwt.decode(token, SECRET_KEY)
    user = db.execute("SELECT * FROM users WHERE id = ?", payload["sub"])
    return User(**user)

def require_role(allowed_roles: List[str]):
    async def checker(user: User = Depends(get_current_user)):
        if user.role not in allowed_roles:
            raise HTTPException(403, "Not authorized")
        return user
    return checker
```

3. **Endpoints protegidos**:
```python
@router.get("/")
async def list_advances(
    current_user: User = Depends(get_current_user)  # ✅ Requiere auth
):
    # Si es empleado, solo sus anticipos
    if current_user.role == 'employee':
        employee_id = current_user.employee_id

    return service.list_advances(employee_id=employee_id)

@router.post("/reimburse")
async def reimburse(
    current_user: User = Depends(require_role(['accountant', 'admin']))  # ✅ Solo contadores
):
    # ...
```

4. **Frontend con tokens**:
```javascript
const token = localStorage.getItem('access_token');

await fetch('/employee_advances/', {
    headers: {
        'Authorization': `Bearer ${token}`
    }
});
```

**Matriz de Permisos**:

| Recurso | Acción | employee | accountant | admin |
|---------|--------|----------|------------|-------|
| employee_advances | Ver propios | ✅ | ✅ | ✅ |
| employee_advances | Ver todos | ❌ | ✅ | ✅ |
| employee_advances | Reembolsar | ❌ | ✅ | ✅ |
| bank_reconciliation | Ver | ❌ | ✅ | ✅ |
| bank_reconciliation/ai | Auto-aplicar | ❌ | ❌ | ✅ |

---

## Resumen de Prioridades

| # | Pregunta | Estado | Prioridad | Estimado |
|---|----------|--------|-----------|----------|
| 1 | Integración BD | ✅ COMPLETO | - | - |
| 2 | Conciliación mixta | ✅ FUNCIONAL | - | - |
| 3 | Escalabilidad IA | ⚠️ PARCIAL | 🔴 ALTA | 2-3 semanas |
| 4 | Diseño endpoints | ✅ CONSISTENTE | 🟡 MEDIA | 1 semana (v2) |
| 5 | UX transparencia | ✅ BUENO | 🟢 BAJA | 1 semana (mejoras) |
| 6 | Auditoría | ⏳ BÁSICO | 🔴 ALTA | 2 semanas |
| 7 | Control estados | ✅ ROBUSTO | 🟢 BAJA | - |
| 8 | UI-Backend sync | ✅ FUNCIONAL | 🟡 MEDIA | 1 semana (SSE) |
| 9 | Recuperación errores | ⏳ BÁSICO | 🟡 MEDIA | 1 semana |
| 10 | Seguridad | ❌ CRÍTICO | 🔴 CRÍTICA | 1 semana |

## Recomendación de Implementación

### Sprint Inmediato (1 semana)
1. **Seguridad** (Pregunta 10): JWT + RBAC básico
2. **Auditoría** (Pregunta 6): Tablas audit_log + evidence

### Sprint Corto Plazo (2-3 semanas)
3. **Escalabilidad IA** (Pregunta 3): Índices + pre-filtrado + DP algorithm
4. **Recuperación errores** (Pregunta 9): Upload tracking + error UI

### Sprint Medio Plazo (1-2 meses)
5. **UI-Backend sync** (Pregunta 8): SSE notifications
6. **UX mejoras** (Pregunta 5): Modal explicación + feedback loop
7. **API v2** (Pregunta 4): Versioning + deprecation path

---

## Archivos de Referencia

- `SCALABILITY_IMPROVEMENTS.md`: Detalles de optimización IA
- `API_CONVENTIONS.md`: Estándares de diseño de endpoints
- `UX_TRANSPARENCY_IMPROVEMENTS.md`: Propuestas de experiencia usuario
- `AUDIT_TRAIL_IMPLEMENTATION.md`: Implementación completa de auditoría
- `TECHNICAL_QUESTIONS_7_TO_10.md`: Respuestas detalladas 7-10
