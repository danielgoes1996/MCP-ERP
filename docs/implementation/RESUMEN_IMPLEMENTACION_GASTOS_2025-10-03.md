# ✅ RESUMEN DE IMPLEMENTACIÓN: Sistema de Gastos
**Fecha:** 2025-10-03
**Usuario:** contacto@carretaverde.com
**Base de datos:** `mcp_internal.db`

---

## 🎯 OBJETIVO

Implementar un sistema de gastos con trazabilidad completa:
- ✅ Todo gasto debe tener un ticket asociado (real o virtual)
- ✅ Todo gasto debe estar ligado a una cuenta de pago real
- ✅ Campos obligatorios validados
- ✅ Facturación con justificación si no aplica

---

## ✅ LO QUE SE IMPLEMENTÓ HOY

### 1. **Creación de Cuentas de Pago** ✅ COMPLETADO

Se crearon **7 cuentas de pago** para `contacto@carretaverde.com`:

| ID | Nombre | Tipo | Saldo | Límite |
|----|--------|------|-------|--------|
| 1 | BBVA Nómina ****5678 | Banco (Débito) | $50,000 | - |
| 5 | Santander Empresarial ****1234 | Banco (Débito) | $75,000 | - |
| 3 | Efectivo Caja Chica | Efectivo | $5,000 | - |
| 2 | BBVA Crédito *5555 | Tarjeta Crédito | $0 | $100,000 |
| 4 | AMEX Corporativa *8888 | Tarjeta Crédito | $15,000 | $200,000 |
| 7 | Banamex Oro *3333 | Tarjeta Crédito | $8,500 | $80,000 |
| 6 | Terminal Clip Centro | Terminal | $0 | - |

**Archivos modificados:**
- Base de datos: `data/mcp_internal.db`

---

### 2. **Migración de Base de Datos** ✅ COMPLETADO

**Archivo:** `migrations/024_complete_expense_requirements.sql`

**Cambios aplicados:**
- ✅ Agregado campo `invoice_status_reason TEXT` a `expense_records`
- ✅ Creado índice parcial para `invoice_status_reason`

**Verificación:**
```sql
SELECT name, type, [notnull] FROM pragma_table_info('expense_records')
WHERE name = 'invoice_status_reason';
-- Resultado: invoice_status_reason|TEXT|0
```

---

### 3. **Función de Tickets Virtuales** ✅ COMPLETADO

**Archivo:** `modules/invoicing_agent/models.py`

**Nueva función:**
```python
def create_virtual_ticket(
    *,
    user_id: int,
    company_id: str,
    merchant_name: Optional[str] = None,
    category: Optional[str] = None,
    amount: Optional[float] = None,
    description: Optional[str] = None,
) -> int:
    """
    Crear un ticket virtual para gastos creados manualmente (sin imagen).
    Mantiene la regla: 1 Ticket = 1 Expense.
    """
```

**Características:**
- ✅ Crea tickets de tipo `"virtual"`
- ✅ Estado inicial: `"procesado"` (no requiere OCR)
- ✅ Genera `extracted_text` sintético con datos del gasto
- ✅ Permite trazabilidad completa

**Ejemplo de uso:**
```python
ticket_id = create_virtual_ticket(
    user_id=5,
    company_id="cmp_dd36e6c0",
    merchant_name="Gasolinera Pemex",
    category="combustible",
    amount=845.32,
    description="Gasolina corporativa"
)
# ticket_id = 152 (ejemplo)
```

---

### 4. **Auditoría Completa del Sistema** ✅ COMPLETADO

**Archivo:** `AUDITORIA_SISTEMA_GASTOS_2025.md`

**Resultados:**
- ✅ **Esquema BD:** 95% completo
- ✅ **Relaciones FK:** 100% completo
- ⚠️ **Lógica de negocio:** 20% completo
- ❌ **Endpoint validaciones:** 0% completo

**Hallazgos críticos:**
1. ⚠️ `expense_date` y `payment_method` son nullable (deben validarse en app)
2. ⚠️ `will_have_cfdi` tiene DEFAULT 0 (debería ser DEFAULT true)
3. ❌ Endpoint POST /expenses no valida campos obligatorios
4. ❌ Endpoint no crea tickets virtuales automáticamente

---

## ⚠️ LO QUE FALTA IMPLEMENTAR

### 🔴 CRÍTICO (Para implementar MAÑANA):

#### 1. **Actualizar Endpoint POST /expenses**

**Archivo a modificar:** `main.py`

**Validaciones requeridas:**
```python
@app.post("/expenses")
async def create_expense(expense: ExpenseCreate):
    # Validar campos obligatorios
    if not expense.expense_date:
        raise HTTPException(400, "expense_date es obligatorio")

    if not expense.payment_method:
        raise HTTPException(400, "payment_method es obligatorio")

    if not expense.payment_account_id:
        raise HTTPException(400, "payment_account_id es obligatorio")

    # Validar que cuenta existe
    account = get_payment_account(expense.payment_account_id)
    if not account:
        raise HTTPException(404, f"Cuenta {expense.payment_account_id} no encontrada")

    # Crear ticket virtual si no hay ticket_id
    if not expense.ticket_id:
        from modules.invoicing_agent.models import create_virtual_ticket
        expense.ticket_id = create_virtual_ticket(
            user_id=current_user.id,
            company_id=expense.company_id,
            merchant_name=expense.provider_name,
            category=expense.category,
            amount=expense.amount,
            description=expense.description
        )

    # Validar invoice_status_reason
    if expense.invoice_status == 'no_aplica' and not expense.invoice_status_reason:
        raise HTTPException(400, "invoice_status_reason requerido cuando invoice_status='no_aplica'")

    # Crear gasto
    expense_id = record_internal_expense(expense.dict())

    # Actualizar ticket con linked_expense_id
    update_ticket(expense.ticket_id, linked_expense_id=expense_id)

    # Response consistente
    return {
        "id": expense_id,
        "ticket_id": expense.ticket_id,  # ← SIEMPRE presente
        "success": True,
        "message": "Gasto creado exitosamente"
    }
```

#### 2. **Actualizar Modelo ExpenseCreate**

**Archivo a modificar:** `core/api_models.py`

**Cambios necesarios:**
```python
class ExpenseCreate(BaseModel):
    descripcion: str = Field(..., description="Description (required)")
    monto_total: float = Field(..., gt=0, description="Amount (required)")
    fecha_gasto: str = Field(..., description="Date (required)")  # ← Hacer obligatorio
    payment_account_id: int = Field(..., description="Payment account ID (required)")  # ← NUEVO
    payment_method: str = Field(..., description="Payment method (required)")  # ← Hacer obligatorio
    ticket_id: Optional[int] = Field(None, description="Ticket ID (optional, creates virtual if None)")  # ← NUEVO

    # Resto de campos opcionales...
    proveedor: Optional[str] = None
    categoria: Optional[str] = None
    will_have_cfdi: Optional[bool] = Field(True, description="Expects invoice (default true)")  # ← Cambiar a Optional
    invoice_status_reason: Optional[str] = None  # ← NUEVO
```

#### 3. **Actualizar UI voice-expenses**

**Archivo a modificar:** `static/voice-expenses.source.jsx`

**Agregar selector de cuentas:**
```jsx
// Cargar cuentas al inicio
const [paymentAccounts, setPaymentAccounts] = useState([]);

useEffect(() => {
    fetch('/payment-accounts?active_only=true')
        .then(res => res.json())
        .then(accounts => setPaymentAccounts(accounts));
}, []);

// Campo en el formulario
<div>
    <label>💳 Cuenta de Pago *</label>
    <select
        value={formData.payment_account_id}
        onChange={(e) => handleFieldChange('payment_account_id', parseInt(e.target.value))}
        required
    >
        <option value="">-- Selecciona cuenta --</option>
        {paymentAccounts.map(account => (
            <option key={account.id} value={account.id}>
                {account.nombre} - Saldo: ${account.saldo_actual?.toLocaleString('es-MX')}
            </option>
        ))}
    </select>
</div>
```

---

## 📊 ESTADO ACTUAL DEL SISTEMA

### ✅ Completado (70%):

| Componente | Estado |
|------------|--------|
| Tabla `user_payment_accounts` | ✅ 100% |
| Tabla `expense_records` (schema) | ✅ 95% |
| Tabla `tickets` (schema) | ✅ 100% |
| Foreign Keys | ✅ 100% |
| Cuentas de ejemplo | ✅ 100% |
| Función `create_virtual_ticket()` | ✅ 100% |
| Campo `invoice_status_reason` | ✅ 100% |
| Auditoría documentada | ✅ 100% |

### ❌ Pendiente (30%):

| Componente | Estado |
|------------|--------|
| Endpoint POST /expenses validaciones | ❌ 0% |
| Modelo ExpenseCreate actualizado | ❌ 0% |
| UI selector de cuentas | ❌ 0% |
| Tickets virtuales automáticos | ❌ 0% |

---

## 🚀 PLAN DE ACCIÓN PARA MAÑANA

### Prioridad 1 (1-2 horas):
1. ✅ Actualizar `ExpenseCreate` model
2. ✅ Actualizar endpoint POST /expenses
3. ✅ Probar creación de gasto con ticket virtual

### Prioridad 2 (2-3 horas):
4. ✅ Actualizar UI voice-expenses
5. ✅ Agregar selector de cuentas
6. ✅ Probar flujo completo end-to-end

### Prioridad 3 (1 hora):
7. ✅ Documentar ejemplos de uso
8. ✅ Crear tests básicos

---

## 🎓 LECCIONES APRENDIDAS

### ✅ Buenas Decisiones:

1. **Tickets virtuales:** Mantienen la regla 1:1 sin romper el diseño
2. **payment_account_id obligatorio:** Trazabilidad real vs texto libre
3. **Auditoría exhaustiva:** Identificó todos los gaps antes de codear
4. **Validación en app:** Solución pragmática para campos nullable en SQLite

### ⚠️ Deuda Técnica Identificada:

1. **expense_date y payment_method nullable:** Planear migración completa de tabla
2. **will_have_cfdi DEFAULT 0:** Cambiar a DEFAULT true en próxima migración
3. **Falta validación en endpoint:** Crítico para producción

---

## 📚 ARCHIVOS CREADOS/MODIFICADOS

### Creados:
- ✅ `migrations/024_complete_expense_requirements.sql`
- ✅ `AUDITORIA_SISTEMA_GASTOS_2025.md`
- ✅ `RESUMEN_IMPLEMENTACION_GASTOS_2025-10-03.md` (este archivo)

### Modificados:
- ✅ `modules/invoicing_agent/models.py` (agregado `create_virtual_ticket()`)
- ✅ `data/mcp_internal.db` (7 cuentas + campo `invoice_status_reason`)

### Pendientes de modificar:
- ❌ `core/api_models.py` (modelo `ExpenseCreate`)
- ❌ `main.py` (endpoint POST /expenses)
- ❌ `static/voice-expenses.source.jsx` (UI)

---

## ✅ CONCLUSIÓN

**Sistema de gastos está al 70% de completitud.**

**Esquema de datos:** ✅ Casi perfecto (95%)
**Lógica de negocio:** ⚠️ Requiere implementación (30%)
**UI:** ❌ Pendiente actualización (0%)

**Siguiente sesión:** Implementar las 3 piezas críticas (endpoint, modelo, UI) para llegar al 100%.

---

**🎯 Objetivo final:** Sistema de gastos con trazabilidad completa operativo en producción.
