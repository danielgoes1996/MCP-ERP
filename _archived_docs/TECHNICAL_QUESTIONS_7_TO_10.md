# Respuestas Técnicas - Preguntas 7-10

## 7. Control de Estados - Anticipos a Empleados

### Pregunta
En anticipos a empleados, ¿qué pasa si un avance es parcialmente reembolsado y luego se cancela? ¿Cómo evitan que se dupliquen registros o que un empleado pueda solicitar más de lo que corresponde?

### Respuesta

#### Estado Actual del Sistema ✅

**Validación en `cancel_advance()` - `core/employee_advances_service.py:411-458`**:

```python
def cancel_advance(self, advance_id: int, reason: Optional[str] = None):
    advance = self.get_advance_by_id(advance_id)

    # ✅ VALIDACIÓN: No se puede cancelar si ya hay reembolsos
    if advance.reimbursed_amount > 0:
        raise ValueError("Cannot cancel advance that has been partially or fully reimbursed")

    # Si pasa validación:
    # 1. Marca advance como 'cancelled'
    # 2. Resetea expense.bank_status = 'pending'
    # 3. Permite que el gasto se use normalmente
```

**Escenario bloqueado**: ❌ No se permite cancelar si `reimbursed_amount > 0`

#### Escenario Problema Potencial ⚠️

```
Día 1: Crear anticipo de $1000
Día 2: Reembolsar $400 (status='partial', pending=$600)
Día 3: ¿Usuario intenta cancelar? → BLOQUEADO por validación ✅
```

**Pero... ¿qué pasa si necesitan cancelar el resto?**

#### Solución Propuesta: Estado "CANCELLED_PARTIAL"

```sql
ALTER TABLE employee_advances
ADD COLUMN cancellation_type TEXT
CHECK(cancellation_type IN ('full', 'remaining_amount', NULL));

-- Ejemplo:
UPDATE employee_advances
SET
    status = 'cancelled_partial',
    cancellation_type = 'remaining_amount',
    pending_amount = 0,
    notes = notes || '\nCancelado resto pendiente ($600) - Razón: Empleado renunció'
WHERE id = 1;
```

```python
def cancel_remaining_advance(self, advance_id: int, reason: str):
    """
    Nuevo método: Cancelar solo el monto PENDIENTE de un anticipo parcial
    """
    advance = self.get_advance_by_id(advance_id)

    # Validar que haya algo pendiente
    if advance.pending_amount <= 0:
        raise ValueError("No pending amount to cancel")

    # Si ya está completamente reembolsado
    if advance.status == 'completed':
        raise ValueError("Cannot cancel completed advance")

    cursor.execute("""
        UPDATE employee_advances
        SET
            status = 'cancelled_partial',
            cancellation_type = 'remaining_amount',
            pending_amount = 0,
            notes = notes || '\n' || ?
        WHERE id = ?
    """, (
        f"Cancelado resto pendiente (${advance.pending_amount:.2f}) - {reason}",
        advance_id
    ))

    # NO resetear expense.bank_status porque ya hubo reembolsos reales
```

#### Anti-Duplicados: Validaciones Múltiples

**1. Nivel Base de Datos** (Trigger existente):
```sql
-- En `mark_advance_non_reconcilable` trigger
-- Marca automáticamente expense_records.bank_status='advance'
-- Si intentas crear otro advance para el mismo expense_id:

CREATE UNIQUE INDEX idx_expense_advance_active
ON employee_advances(expense_id)
WHERE status IN ('pending', 'partial');
-- ✅ Esto previene duplicados a nivel DB
```

**2. Nivel Service** (Validación existente - línea 70):
```python
if expense['bank_status'] == 'advance':
    raise ValueError(f"Expense {request.expense_id} is already registered as an advance")
```

**3. Nuevo: Límite por Empleado**
```python
def create_advance(self, request: CreateAdvanceRequest):
    # AGREGAR: Validar límite mensual por empleado
    cursor.execute("""
        SELECT SUM(pending_amount) as total_pending
        FROM employee_advances
        WHERE employee_id = ?
        AND status IN ('pending', 'partial')
        AND strftime('%Y-%m', advance_date) = strftime('%Y-%m', 'now')
    """, (request.employee_id,))

    result = cursor.fetchone()
    total_pending = result['total_pending'] or 0

    # Límite: $10,000 pendientes por empleado por mes
    MAX_PENDING_PER_EMPLOYEE = 10000.00

    if total_pending + request.advance_amount > MAX_PENDING_PER_EMPLOYEE:
        raise ValueError(
            f"Employee {request.employee_name} would exceed monthly advance limit. "
            f"Current pending: ${total_pending:.2f}, "
            f"Requested: ${request.advance_amount:.2f}, "
            f"Limit: ${MAX_PENDING_PER_EMPLOYEE:.2f}"
        )
```

#### Matriz de Estados Permitidos

| Estado Inicial | Acción | Estado Final | Notas |
|----------------|--------|--------------|-------|
| pending ($1000 pendiente) | Cancelar | cancelled | ✅ OK - no hay reembolsos |
| partial ($600 pendiente) | Cancelar completo | ❌ ERROR | "Cannot cancel - already reimbursed" |
| partial ($600 pendiente) | Cancelar resto | cancelled_partial | ✅ OK con nuevo método |
| completed | Cancelar | ❌ ERROR | "Already completed" |
| cancelled | Reembolsar | ❌ ERROR | "Advance is cancelled" |

---

## 8. Integración UI–Backend

### Pregunta
¿Cómo validan que los cambios en la UI (ej. aplicar sugerencia IA, crear un anticipo) realmente se reflejan en la BD y no solo en el frontend? ¿Qué mecanismos de notificación usan (polling, websockets, refresh)?

### Respuesta

#### Mecanismo Actual: Request → Response → Refresh ✅

**Ejemplo: Crear Anticipo** (`static/employee-advances.html:296-332`)

```javascript
async function createAdvance(event) {
    event.preventDefault();

    const payload = {
        employee_id: parseInt(document.getElementById('employee-id').value),
        // ...
    };

    try {
        // 1. POST al backend
        const response = await fetch('/employee_advances/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Error al crear anticipo');
        }

        // 2. Backend responde con el objeto completo (200 OK + data)
        const createdAdvance = await response.json();

        // 3. Cerrar modal
        closeCreateAdvanceModal();

        // 4. REFRESH desde BD (no solo agregar al array local)
        await loadSummary();   // Re-fetch totals desde /summary/all
        await loadAdvances();  // Re-fetch lista desde /employee_advances/

        // 5. Feedback al usuario
        alert('✅ Anticipo creado exitosamente');

    } catch (error) {
        alert(`❌ Error: ${error.message}`);
    }
}
```

**Ventajas**:
- ✅ Simple de implementar
- ✅ No requiere infraestructura adicional (no websockets)
- ✅ Datos siempre sincronizados con BD (cada acción = re-fetch)

**Desventajas**:
- ❌ Si otro usuario crea un anticipo, yo no lo veo hasta que recargue
- ❌ Cada operación hace 2 requests adicionales (summary + list)

#### Validación de Sincronización

**Prueba en test_employee_advances.py:90-121**:
```python
# Test 4: Partial reimbursement
response = requests.post("/employee_advances/reimburse", json={...})
result = response.json()

# ✅ Verificar que el response contiene datos de BD
assert result['status'] == 'partial'
assert result['pending_amount'] == 450.50

# Test 5: Verificar en summary (re-fetch)
summary = requests.get("/employee_advances/summary/all").json()
assert summary['total_reimbursed'] == 400.00  # ✅ BD actualizada
```

#### Mecanismos de Notificación: Actual vs Propuesto

| Mecanismo | Actual | Propuesto |
|-----------|--------|-----------|
| **Polling** | ❌ No | ⏳ Implementar para dashboard |
| **Websockets** | ❌ No | ⏳ Para notificaciones real-time |
| **Server-Sent Events (SSE)** | ❌ No | ✅ Mejor opción para updates |
| **Manual Refresh** | ✅ Sí (después de cada acción) | ✅ Mantener |

#### Propuesta: Server-Sent Events (SSE)

**Backend** (`api/notifications_api.py`):
```python
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import asyncio
import json

router = APIRouter(prefix="/notifications", tags=["Notifications"])

# Global event queue (mejor usar Redis en producción)
notification_queue = asyncio.Queue()

@router.get("/stream")
async def notification_stream():
    """
    Server-Sent Events stream para notificaciones real-time
    """
    async def event_generator():
        while True:
            # Esperar por nuevo evento
            event = await notification_queue.get()

            # Formatear como SSE
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )

# Función helper para emitir eventos
async def emit_notification(event_type: str, data: dict):
    await notification_queue.put({
        "type": event_type,
        "data": data,
        "timestamp": datetime.now().isoformat()
    })
```

**Modificar `employee_advances_service.py`**:
```python
async def create_advance(self, request: CreateAdvanceRequest):
    # ... crear anticipo ...

    # Emitir notificación
    await emit_notification("advance_created", {
        "advance_id": advance_id,
        "employee_name": request.employee_name,
        "amount": request.advance_amount
    })

    return result
```

**Frontend** (`employee-advances.html`):
```javascript
// Establecer conexión SSE
const eventSource = new EventSource('/notifications/stream');

eventSource.onmessage = function(event) {
    const notification = JSON.parse(event.data);

    switch(notification.type) {
        case 'advance_created':
            // Re-cargar solo si afecta a esta vista
            loadAdvances();
            showToast(`Nuevo anticipo: ${notification.data.employee_name}`, 'info');
            break;

        case 'advance_reimbursed':
            loadAdvances();
            loadSummary();
            showToast(`Reembolso procesado`, 'success');
            break;
    }
};

eventSource.onerror = function(error) {
    console.error('SSE error:', error);
    // Reconectar automáticamente después de 5s
    setTimeout(() => location.reload(), 5000);
};
```

#### Polling como Fallback

```javascript
// Si SSE no está disponible, usar polling cada 30s
let pollingInterval;

function startPolling() {
    pollingInterval = setInterval(async () => {
        const summary = await fetch('/employee_advances/summary/all').then(r => r.json());

        // Comparar con estado local
        if (summary.total_pending !== currentSummary.total_pending) {
            // Algo cambió, recargar
            await loadAdvances();
            currentSummary = summary;
        }
    }, 30000);  // 30 segundos
}

// Detener polling cuando el usuario no está activo
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        clearInterval(pollingInterval);
    } else {
        startPolling();
    }
});
```

#### Optimistic Updates (Propuesto)

```javascript
async function createAdvance(event) {
    event.preventDefault();

    const payload = {...};

    // 1. UPDATE OPTIMISTA: Agregar al array local inmediatamente
    const tempAdvance = {
        id: 'temp_' + Date.now(),
        ...payload,
        status: 'pending',
        pending_amount: payload.advance_amount,
        reimbursed_amount: 0,
        _isPending: true  // Flag para mostrar spinner
    };

    currentAdvances.unshift(tempAdvance);
    renderAdvances();  // Mostrar inmediatamente con spinner

    try {
        // 2. ENVIAR al backend
        const response = await fetch('/employee_advances/', {
            method: 'POST',
            body: JSON.stringify(payload)
        });

        const realAdvance = await response.json();

        // 3. REEMPLAZAR temporal con real
        const index = currentAdvances.findIndex(a => a.id === tempAdvance.id);
        currentAdvances[index] = realAdvance;
        renderAdvances();

    } catch (error) {
        // 4. ROLLBACK si falla
        currentAdvances = currentAdvances.filter(a => a.id !== tempAdvance.id);
        renderAdvances();
        alert(`❌ Error: ${error.message}`);
    }
}
```

---

## 9. Errores y Recuperación

### Pregunta
Si falla el parser de un banco o se sube un PDF dañado, ¿qué pasa con los movimientos? ¿El sistema los ignora, los marca como error, o interrumpe el proceso completo?

### Respuesta

#### Sistema Actual: Parsers Bancarios

**Inbursa Parser** (`modules/invoicing_agent/services/hybrid_processor.py`):

```python
def process_bank_statement(self, pdf_path: str):
    try:
        # Intenta pdfplumber primero
        movements = self._extract_with_pdfplumber(pdf_path)

        if not movements:
            # Fallback a pymupdf
            movements = self._extract_with_pymupdf(pdf_path)

        if not movements:
            # Último intento: OCR
            movements = self._extract_with_ocr(pdf_path)

        return movements

    except Exception as e:
        logger.error(f"Error parsing bank statement: {e}")
        # ❌ PROBLEMA: Solo logea error, no guarda estado
        return []  # Retorna vacío
```

**Problema**: Si falla el parser, los movimientos simplemente no se procesan. No hay registro del error en BD.

#### Propuesta: Estado de Error con Recuperación

**Nueva tabla**:
```sql
CREATE TABLE bank_statement_uploads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Archivo
    filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_hash TEXT,  -- MD5 para detectar duplicados
    file_size_bytes INTEGER,

    -- Banco
    bank_name TEXT,
    statement_period TEXT,  -- '2025-01'

    -- Procesamiento
    status TEXT CHECK(status IN (
        'pending',
        'processing',
        'completed',
        'partial_success',
        'failed',
        'requires_manual_review'
    )) DEFAULT 'pending',

    -- Resultados
    movements_extracted INTEGER DEFAULT 0,
    movements_saved INTEGER DEFAULT 0,
    movements_failed INTEGER DEFAULT 0,

    -- Errores
    error_type TEXT,  -- 'parse_error', 'corrupted_pdf', 'unknown_format'
    error_message TEXT,
    error_details JSON,

    -- Parser usado
    parser_method TEXT,  -- 'pdfplumber', 'pymupdf', 'ocr', 'manual'

    -- Timestamps
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP,
    retry_count INTEGER DEFAULT 0,

    UNIQUE(file_hash)  -- Prevenir duplicados
);

CREATE TABLE bank_movement_errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    upload_id INTEGER NOT NULL,
    line_number INTEGER,
    raw_text TEXT,

    error_type TEXT,  -- 'invalid_date', 'invalid_amount', 'missing_description'
    error_message TEXT,

    suggested_fix JSON,  -- {"date": "2025-01-15", "amount": -850.50}

    status TEXT DEFAULT 'pending',  -- 'pending', 'fixed', 'ignored'
    fixed_by INTEGER,
    fixed_at TIMESTAMP,

    FOREIGN KEY (upload_id) REFERENCES bank_statement_uploads(id)
);
```

**Servicio mejorado**:
```python
class BankStatementProcessor:
    def process_upload(self, pdf_path: str, bank_name: str):
        # 1. Registrar upload
        file_hash = self._calculate_md5(pdf_path)

        upload_id = db.execute("""
            INSERT INTO bank_statement_uploads (
                filename, file_path, file_hash, bank_name, status
            ) VALUES (?, ?, ?, ?, 'processing')
        """, (os.path.basename(pdf_path), pdf_path, file_hash, bank_name))

        try:
            # 2. Intentar parsear
            movements, errors = self._parse_with_error_tracking(pdf_path)

            # 3. Guardar movimientos válidos
            saved_count = 0
            for movement in movements:
                try:
                    db.execute("""
                        INSERT INTO bank_movements (...)
                        VALUES (...)
                    """)
                    saved_count += 1
                except Exception as e:
                    # Guardar error específico
                    db.execute("""
                        INSERT INTO bank_movement_errors (
                            upload_id, raw_text, error_type, error_message
                        ) VALUES (?, ?, ?, ?)
                    """, (upload_id, movement.get('raw'), 'save_error', str(e)))

            # 4. Guardar errores de parsing
            for error in errors:
                db.execute("""
                    INSERT INTO bank_movement_errors (
                        upload_id, line_number, raw_text,
                        error_type, error_message, suggested_fix
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    upload_id, error['line'],
                    error['text'], error['type'],
                    error['message'],
                    json.dumps(error.get('suggestion'))
                ))

            # 5. Actualizar estado del upload
            if len(errors) == 0 and saved_count > 0:
                status = 'completed'
            elif saved_count > 0:
                status = 'partial_success'
            else:
                status = 'failed'

            db.execute("""
                UPDATE bank_statement_uploads
                SET status = ?,
                    movements_extracted = ?,
                    movements_saved = ?,
                    movements_failed = ?,
                    processed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (status, len(movements), saved_count, len(errors), upload_id))

            return {
                "upload_id": upload_id,
                "status": status,
                "saved": saved_count,
                "errors": len(errors)
            }

        except Exception as e:
            # 6. Fallo catastrófico (PDF corrupto, etc)
            db.execute("""
                UPDATE bank_statement_uploads
                SET status = 'failed',
                    error_type = 'fatal_error',
                    error_message = ?,
                    processed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (str(e), upload_id))

            return {
                "upload_id": upload_id,
                "status": "failed",
                "error": str(e)
            }

    def _parse_with_error_tracking(self, pdf_path: str):
        """
        Parser que retorna (movements, errors) en vez de solo movements
        """
        movements = []
        errors = []

        try:
            # Leer PDF
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    text = page.extract_text()

                    for line_num, line in enumerate(text.split('\n')):
                        try:
                            # Intentar parsear línea
                            movement = self._parse_line(line)
                            movements.append(movement)

                        except ValueError as e:
                            # Línea no parseada - guardar error
                            errors.append({
                                'line': (page_num * 100) + line_num,
                                'text': line,
                                'type': 'parse_error',
                                'message': str(e),
                                'suggestion': self._suggest_fix(line)
                            })

        except Exception as e:
            # PDF corrupto o sin texto
            raise Exception(f"Cannot read PDF: {e}")

        return movements, errors

    def _suggest_fix(self, line: str):
        """
        IA para sugerir corrección de líneas mal parseadas
        """
        # Usar LLM para intentar extraer fecha/monto/descripción
        prompt = f"Extract date, amount, description from: {line}"
        suggestion = call_llm(prompt)
        return suggestion
```

**UI de Recuperación** (`bank-statement-errors.html`):
```html
<div class="upload-result">
    <h3>Resultado del Procesamiento</h3>

    <div class="success">
        ✅ 85 movimientos guardados correctamente
    </div>

    <div class="warning">
        ⚠️ 5 líneas con errores de parsing
        <button onclick="showErrors()">Revisar Errores</button>
    </div>

    <!-- Modal de errores -->
    <div class="error-list">
        <div class="error-row">
            <div class="raw-text">
                15/01/2025 GASOLINERA PEMEX -85050  <!-- Falta punto decimal -->
            </div>

            <div class="error-message">
                Error: Invalid amount format
            </div>

            <div class="suggested-fix">
                Sugerencia IA:
                <input type="date" value="2025-01-15">
                <input type="number" value="-850.50">
                <input type="text" value="GASOLINERA PEMEX">
            </div>

            <button onclick="applyFix()">Aplicar Corrección</button>
            <button onclick="ignoreError()">Ignorar</button>
        </div>
    </div>
</div>
```

#### Estrategia de Reintentos

```python
@router.post("/bank-statements/retry/{upload_id}")
async def retry_failed_upload(upload_id: int):
    """
    Reintentar procesamiento de un upload fallido
    """
    upload = db.execute("""
        SELECT * FROM bank_statement_uploads WHERE id = ?
    """, (upload_id,))

    # Limitar reintentos
    if upload['retry_count'] >= 3:
        return {"error": "Max retries exceeded"}

    # Incrementar contador
    db.execute("""
        UPDATE bank_statement_uploads
        SET retry_count = retry_count + 1,
            status = 'processing'
        WHERE id = ?
    """, (upload_id,))

    # Intentar con parser diferente
    if upload['parser_method'] == 'pdfplumber':
        result = process_with_pymupdf(upload['file_path'])
    elif upload['parser_method'] == 'pymupdf':
        result = process_with_ocr(upload['file_path'])
    else:
        result = process_manual_review(upload['file_path'])

    return result
```

---

## 10. Seguridad y Roles

### Pregunta
¿Qué controles implementaron para que un empleado normal no pueda acceder a los módulos de anticipos de otros, o que no pueda manipular la conciliación bancaria de la empresa?

### Respuesta

#### Estado Actual: ❌ SIN AUTENTICACIÓN

**Verificación**:
```bash
curl http://localhost:8004/employee_advances/
# Retorna TODOS los anticipos sin pedir credenciales
```

**Problema crítico**: Cualquiera con acceso al puerto puede:
- Ver todos los anticipos de todos los empleados
- Crear anticipos fraudulentos
- Procesar reembolsos
- Ver movimientos bancarios completos

#### Implementación de Seguridad - Fase 1: JWT Auth

**1. Tabla de usuarios y roles**:
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name TEXT,
    employee_id INTEGER,  -- Link a employee_advances

    role TEXT CHECK(role IN (
        'employee',      -- Solo sus propios gastos/anticipos
        'accountant',    -- Ver todo, conciliar
        'manager',       -- Aprobar gastos grandes
        'admin'          -- Acceso completo
    )) NOT NULL,

    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

CREATE TABLE permissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL,
    resource TEXT NOT NULL,  -- 'employee_advances', 'bank_reconciliation'
    action TEXT NOT NULL,    -- 'read', 'create', 'update', 'delete'
    scope TEXT,              -- 'own', 'all'

    UNIQUE(role, resource, action)
);

-- Permisos iniciales
INSERT INTO permissions VALUES
    (1, 'employee', 'employee_advances', 'read', 'own'),
    (2, 'employee', 'employee_advances', 'create', 'own'),
    (3, 'accountant', 'employee_advances', 'read', 'all'),
    (4, 'accountant', 'employee_advances', 'update', 'all'),
    (5, 'accountant', 'bank_reconciliation', 'read', 'all'),
    (6, 'accountant', 'bank_reconciliation', 'create', 'all'),
    (7, 'admin', '*', '*', 'all');
```

**2. Sistema de autenticación**:
```python
# core/auth_system.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-here")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

class User(BaseModel):
    id: int
    username: str
    email: str
    full_name: str
    role: str
    employee_id: Optional[int]

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("sub")

        if user_id is None:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    # Load user from DB
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,))

    if user is None:
        raise credentials_exception

    return User(**user)

def require_role(allowed_roles: List[str]):
    async def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role}' not authorized"
            )
        return current_user
    return role_checker
```

**3. Endpoints protegidos**:
```python
# api/employee_advances_api.py (MODIFICADO)
from core.auth_system import get_current_user, require_role, User

@router.get("/")
async def list_advances(
    status: Optional[AdvanceStatus] = None,
    employee_id: Optional[int] = None,
    current_user: User = Depends(get_current_user)  # ✅ Requiere auth
):
    """
    Listar anticipos según rol:
    - employee: Solo sus propios anticipos
    - accountant/admin: Todos los anticipos
    """
    # Si es empleado, forzar filtro por su employee_id
    if current_user.role == 'employee':
        if employee_id and employee_id != current_user.employee_id:
            raise HTTPException(403, "Cannot view other employees' advances")

        employee_id = current_user.employee_id

    service = get_employee_advances_service()
    results = service.list_advances(
        status=status,
        employee_id=employee_id,
        limit=100
    )

    return results

@router.post("/reimburse")
async def reimburse_advance(
    request: ReimburseAdvanceRequest,
    current_user: User = Depends(require_role(['accountant', 'admin']))  # ✅ Solo contadores
):
    """
    Solo accountants pueden procesar reembolsos
    """
    service = get_employee_advances_service()
    result = service.reimburse_advance(request, user_id=current_user.id)

    return result

@router.post("/")
async def create_advance(
    request: CreateAdvanceRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Empleados solo pueden crear anticipos para sí mismos
    """
    if current_user.role == 'employee':
        # Validar que el anticipo sea para sí mismo
        if request.employee_id != current_user.employee_id:
            raise HTTPException(403, "Cannot create advance for other employee")

    service = get_employee_advances_service()
    result = service.create_advance(request, user_id=current_user.id)

    return result
```

**4. Conciliación bancaria protegida**:
```python
# api/bank_reconciliation_api.py
@router.get("/movements")
async def list_movements(
    current_user: User = Depends(require_role(['accountant', 'admin']))
):
    """
    Solo accountants pueden ver movimientos bancarios
    """
    # ...

@router.post("/splits")
async def create_split(
    request: CreateSplitRequest,
    current_user: User = Depends(require_role(['accountant', 'admin']))
):
    """
    Solo accountants pueden conciliar
    """
    # Registrar quién hizo la conciliación
    service.create_split(request, created_by=current_user.id)
```

**5. Frontend con auth**:
```javascript
// static/employee-advances.html (MODIFICADO)

// Al cargar página, verificar token
async function checkAuth() {
    const token = localStorage.getItem('access_token');

    if (!token) {
        window.location.href = '/auth-login.html';
        return;
    }

    // Verificar token válido
    try {
        const response = await fetch('/auth/me', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) throw new Error('Invalid token');

        const user = await response.json();

        // Mostrar info de usuario
        document.getElementById('current-user-name').textContent = user.full_name;
        document.getElementById('current-user-role').textContent = user.role;

        // Ocultar botones según rol
        if (user.role === 'employee') {
            document.getElementById('btn-reimburse').style.display = 'none';
            document.getElementById('filter-employee').value = user.employee_id;
            document.getElementById('filter-employee').disabled = true;
        }

    } catch (error) {
        localStorage.removeItem('access_token');
        window.location.href = '/auth-login.html';
    }
}

// Agregar token a todas las requests
async function loadAdvances() {
    const token = localStorage.getItem('access_token');

    const response = await fetch('/employee_advances/', {
        headers: {
            'Authorization': `Bearer ${token}`
        }
    });

    // ...
}
```

#### Matriz de Permisos

| Recurso | Acción | employee | accountant | admin |
|---------|--------|----------|------------|-------|
| **employee_advances** | Ver propios | ✅ | ✅ | ✅ |
| **employee_advances** | Ver todos | ❌ | ✅ | ✅ |
| **employee_advances** | Crear propio | ✅ | ✅ | ✅ |
| **employee_advances** | Crear para otro | ❌ | ❌ | ✅ |
| **employee_advances** | Reembolsar | ❌ | ✅ | ✅ |
| **employee_advances** | Cancelar | ❌ | ✅ | ✅ |
| **bank_reconciliation** | Ver movimientos | ❌ | ✅ | ✅ |
| **bank_reconciliation** | Conciliar | ❌ | ✅ | ✅ |
| **bank_reconciliation/ai** | Ver sugerencias | ❌ | ✅ | ✅ |
| **bank_reconciliation/ai** | Auto-aplicar | ❌ | ❌ | ✅ |

#### Logging de Accesos

```python
CREATE TABLE access_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    endpoint TEXT,
    method TEXT,
    status_code INTEGER,
    ip_address TEXT,
    user_agent TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

# Middleware en main.py
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()

    response = await call_next(request)

    # Log request
    if request.user:  # Si está autenticado
        db.execute("""
            INSERT INTO access_log (
                user_id, username, endpoint, method, status_code, ip_address
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            request.user.id,
            request.user.username,
            str(request.url.path),
            request.method,
            response.status_code,
            request.client.host
        ))

    return response
```

#### Rate Limiting

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@router.post("/")
@limiter.limit("10/minute")  # Máximo 10 anticipos por minuto
async def create_advance(request: Request, ...):
    # ...
```
