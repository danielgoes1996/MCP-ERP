# 🚀 PLAN DE EJECUCIÓN: Completar Sistema de Gastos
**Fecha ejecución:** 2025-10-04
**Tiempo estimado:** 3-4 horas
**Prioridad:** Backend primero, UI después

---

## 📋 ORDEN DE EJECUCIÓN (ESTRICTO)

### 🔴 PASO 1: Modelo ExpenseCreate (30-45 min)

**Archivo:** `core/api_models.py`

**Objetivo:** Definir campos obligatorios y validaciones

**Cambios exactos:**

```python
class ExpenseCreate(BaseModel):
    """Model for creating a new expense record"""

    # ✅ OBLIGATORIOS (NOT NULL en lógica)
    descripcion: str = Field(..., min_length=1, description="Descripción del gasto")
    monto_total: float = Field(..., gt=0, description="Monto total del gasto")
    fecha_gasto: str = Field(..., description="Fecha del gasto (YYYY-MM-DD)")
    payment_method: str = Field(..., description="Método de pago (efectivo|tarjeta|transferencia)")
    payment_account_id: int = Field(..., gt=0, description="ID de cuenta de pago (FK)")

    # 🟡 OPCIONALES (pueden ser NULL)
    ticket_id: Optional[int] = Field(None, description="ID del ticket (si NULL, se crea virtual)")
    proveedor: Optional[str] = Field(None, description="Nombre del proveedor")
    categoria: Optional[str] = Field(None, description="Categoría del gasto")
    rfc_proveedor: Optional[str] = Field(None, description="RFC del proveedor")
    notas: Optional[str] = Field(None, description="Notas adicionales")

    # 🟢 CON DEFAULTS
    will_have_cfdi: bool = Field(True, description="¿Espera factura? (default: true)")
    invoice_status: str = Field("pendiente", description="Estado de facturación")
    invoice_status_reason: Optional[str] = Field(None, description="Razón si no_aplica")

    # 🔵 AUTOMÁTICOS
    company_id: str = Field("default", description="ID de la empresa")
    moneda: str = Field("MXN", description="Moneda")

    # Validaciones
    @validator('fecha_gasto')
    def validate_date(cls, v):
        """Validar formato de fecha"""
        try:
            datetime.strptime(v, '%Y-%m-%d')
            return v
        except ValueError:
            raise ValueError('fecha_gasto debe ser formato YYYY-MM-DD')

    @validator('payment_method')
    def validate_payment_method(cls, v):
        """Validar método de pago"""
        allowed = ['efectivo', 'tarjeta_empresa', 'tarjeta_personal', 'transferencia', 'cheque']
        if v not in allowed:
            raise ValueError(f'payment_method debe ser uno de: {allowed}')
        return v

    @validator('invoice_status_reason')
    def validate_invoice_reason(cls, v, values):
        """Si invoice_status=no_aplica, reason es obligatorio"""
        if values.get('invoice_status') == 'no_aplica' and not v:
            raise ValueError('invoice_status_reason es obligatorio cuando invoice_status=no_aplica')
        return v
```

**Verificación:**
- ✅ Todos los campos obligatorios están marcados con `...`
- ✅ Validaciones de formato y lógica de negocio
- ✅ Documentación clara de qué es obligatorio y qué no

---

### 🔴 PASO 2: Endpoint POST /expenses (60-90 min)

**Archivo:** `main.py`

**Objetivo:** Implementar lógica completa con tickets virtuales

**Ubicación:** Buscar función `async def create_expense` (línea ~2990)

**Reemplazar con:**

```python
@app.post("/expenses", response_model=ExpenseResponse)
async def create_expense(
    expense: ExpenseCreate,
    tenancy_context: TenancyContext = Depends(get_tenancy_context),
    current_user: dict = Depends(get_current_active_user)
) -> ExpenseResponse:
    """
    Crear un nuevo gasto en la base de datos.

    REGLAS DE NEGOCIO:
    1. Si no tiene ticket_id, se crea ticket virtual automáticamente
    2. payment_account_id debe existir en user_payment_accounts
    3. expense_date y payment_method son obligatorios
    4. Si invoice_status=no_aplica, debe tener invoice_status_reason
    """
    endpoint = "POST /expenses"
    log_endpoint_entry(endpoint, amount=expense.monto_total, company_id=expense.company_id)

    try:
        # ================================
        # VALIDACIÓN 1: Campos obligatorios
        # ================================
        if not expense.descripcion or not expense.descripcion.strip():
            raise HTTPException(400, detail="descripcion es obligatorio")

        if not expense.fecha_gasto:
            raise HTTPException(400, detail="fecha_gasto es obligatorio")

        if not expense.payment_method:
            raise HTTPException(400, detail="payment_method es obligatorio")

        if not expense.payment_account_id:
            raise HTTPException(400, detail="payment_account_id es obligatorio")

        if expense.monto_total <= 0:
            raise HTTPException(400, detail="monto_total debe ser mayor a cero")

        # ================================
        # VALIDACIÓN 2: payment_account_id existe
        # ================================
        from core.payment_accounts_models import payment_account_service

        try:
            account = payment_account_service.get_account(
                expense.payment_account_id,
                current_user.get('id'),
                tenancy_context.tenant_id
            )
            if not account:
                raise HTTPException(404, detail=f"Cuenta {expense.payment_account_id} no encontrada")
        except Exception as e:
            logger.error(f"Error validando payment_account_id: {e}")
            raise HTTPException(404, detail=f"Cuenta {expense.payment_account_id} no existe")

        # ================================
        # VALIDACIÓN 3: invoice_status_reason
        # ================================
        if expense.invoice_status == 'no_aplica' and not expense.invoice_status_reason:
            raise HTTPException(
                400,
                detail="invoice_status_reason es obligatorio cuando invoice_status='no_aplica'"
            )

        # ================================
        # LÓGICA: Crear ticket virtual si no existe ticket_id
        # ================================
        ticket_id = expense.ticket_id

        if not ticket_id:
            from modules.invoicing_agent.models import create_virtual_ticket

            logger.info(f"📸 Creando ticket virtual para gasto sin ticket")

            ticket_id = create_virtual_ticket(
                user_id=current_user.get('id', 1),
                company_id=expense.company_id or tenancy_context.tenant_id,
                merchant_name=expense.proveedor,
                category=expense.categoria,
                amount=expense.monto_total,
                description=expense.descripcion
            )

            logger.info(f"✅ Ticket virtual creado: ID={ticket_id}")

        # ================================
        # CREAR GASTO
        # ================================
        provider_name = expense.proveedor

        account_code = "6180"
        if expense.categoria:
            account_mapping = {
                'combustible': '6140',
                'combustibles': '6140',
                'viajes': '6150',
                'viaticos': '6150',
                'alimentos': '6150',
                'servicios': '6130',
                'oficina': '6180',
                'honorarios': '6110',
                'renta': '6120',
                'publicidad': '6160',
                'marketing': '6160'
            }
            account_code = account_mapping.get(expense.categoria.lower(), account_code)

        from core.internal_db import record_internal_expense

        expense_id = record_internal_expense(
            description=expense.descripcion,
            amount=expense.monto_total,
            currency=expense.moneda,
            expense_date=expense.fecha_gasto,
            category=expense.categoria,
            provider_name=provider_name,
            provider_rfc=expense.rfc_proveedor,
            workflow_status="draft",
            invoice_status=expense.invoice_status,
            bank_status="pendiente_factura" if expense.will_have_cfdi else "sin_factura",
            account_code=account_code,
            payment_method=expense.payment_method,
            payment_account_id=expense.payment_account_id,
            ticket_id=ticket_id,
            will_have_cfdi=expense.will_have_cfdi,
            invoice_status_reason=expense.invoice_status_reason,
            company_id=expense.company_id or tenancy_context.tenant_id,
            metadata={"notas": expense.notas} if expense.notas else None
        )

        # ================================
        # ACTUALIZAR TICKET CON linked_expense_id
        # ================================
        from modules.invoicing_agent.models import update_ticket

        update_ticket(ticket_id, linked_expense_id=expense_id)

        logger.info(f"✅ Gasto creado: ID={expense_id}, Ticket={ticket_id}")

        # ================================
        # RESPONSE CONSISTENTE
        # ================================
        return ExpenseResponse(
            id=expense_id,
            descripcion=expense.descripcion,
            monto_total=expense.monto_total,
            fecha_gasto=expense.fecha_gasto,
            proveedor=provider_name,
            categoria=expense.categoria,
            company_id=expense.company_id or tenancy_context.tenant_id,
            estado_factura=expense.invoice_status,
            ticket_id=ticket_id,  # ← SIEMPRE presente
            payment_account_id=expense.payment_account_id,
            success=True,
            message="Gasto creado exitosamente"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error creating expense: {e}")
        raise HTTPException(status_code=500, detail=f"Error al crear gasto: {str(e)}")
```

**Funciones helper necesarias:**

```python
# Agregar función update_ticket en modules/invoicing_agent/models.py
def update_ticket(ticket_id: int, **kwargs) -> bool:
    """Actualizar campos de un ticket"""
    if not kwargs:
        return False

    fields = ', '.join([f"{k} = ?" for k in kwargs.keys()])
    values = list(kwargs.values()) + [ticket_id]

    with _DB_LOCK:
        with sqlite3.connect(_get_db_path()) as connection:
            cursor = connection.execute(
                f"UPDATE tickets SET {fields}, updated_at = ? WHERE id = ?",
                values + [datetime.utcnow().isoformat()]
            )
            connection.commit()
            return cursor.rowcount > 0
```

**Verificación:**
- ✅ Todas las validaciones implementadas
- ✅ Tickets virtuales se crean automáticamente
- ✅ Response incluye ticket_id siempre
- ✅ Manejo de errores robusto

---

### 🔴 PASO 3: UI Voice Expenses (45-60 min)

**Archivo:** `static/voice-expenses.source.jsx`

**Objetivo:** Agregar selector de cuentas de pago

**Cambios necesarios:**

**3.1. Cargar cuentas al inicio:**

```jsx
// Buscar donde se define el componente principal
const [paymentAccounts, setPaymentAccounts] = useState([]);

useEffect(() => {
    // Cargar cuentas de pago
    fetch('/payment-accounts?active_only=true', {
        headers: getAuthHeaders()
    })
        .then(res => res.json())
        .then(accounts => {
            console.log('✅ Cuentas cargadas:', accounts.length);
            setPaymentAccounts(accounts);
        })
        .catch(err => {
            console.error('❌ Error cargando cuentas:', err);
        });
}, []);
```

**3.2. Agregar campo al formulario:**

```jsx
{/* Buscar el formulario de captura y agregar DESPUÉS del campo forma_pago */}

{/* Cuenta de Pago */}
<div>
    <label className="block text-sm font-medium text-gray-700 mb-1">
        💳 Cuenta de Pago *
    </label>
    <select
        value={formData.payment_account_id || ''}
        onChange={(e) => handleFieldChange('payment_account_id', parseInt(e.target.value))}
        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
        required
    >
        <option value="">-- Selecciona cuenta --</option>
        {paymentAccounts.map(account => (
            <option key={account.id} value={account.id}>
                {account.nombre} -
                {account.tipo === 'tarjeta_credito' ? (
                    ` Disponible: $${account.credito_disponible?.toLocaleString('es-MX')}`
                ) : (
                    ` Saldo: $${account.saldo_actual?.toLocaleString('es-MX')}`
                )}
            </option>
        ))}
    </select>
    {!formData.payment_account_id && (
        <p className="text-xs text-red-600 mt-1">Campo obligatorio</p>
    )}
</div>
```

**3.3. Actualizar validación de campos requeridos:**

```jsx
// Buscar la función de validación de campos requeridos
const requiredFields = [
    'descripcion',
    'monto_total',
    'fecha_gasto',
    'proveedor.nombre',
    'forma_pago',
    'payment_account_id',  // ← AGREGAR
    'will_have_cfdi'
];
```

**3.4. Actualizar buildExpenseData:**

```jsx
const buildExpenseData = useCallback(() => {
    return {
        descripcion: getFieldValue('descripcion') || 'Gasto demo',
        monto_total: getFieldValue('monto_total') || 0,
        fecha_gasto: getFieldValue('fecha_gasto'),
        payment_account_id: getFieldValue('payment_account_id'),  // ← AGREGAR
        payment_method: getFieldValue('forma_pago'),  // ← Cambiar de forma_pago a payment_method
        proveedor: getFieldValue('proveedor.nombre'),
        categoria: getFieldValue('categoria'),
        rfc_proveedor: getFieldValue('rfc'),
        will_have_cfdi: getFieldValue('will_have_cfdi'),
        invoice_status: 'pendiente',
        company_id: resolvedCompanyId,
        notas: getFieldValue('notas')
    };
}, [getFieldValue, resolvedCompanyId]);
```

**Verificación:**
- ✅ Selector de cuentas visible
- ✅ Muestra saldo/crédito disponible
- ✅ Validación de campo obligatorio
- ✅ Se envía payment_account_id al backend

---

## ✅ CHECKLIST DE VERIFICACIÓN

### Después de cada paso:

**PASO 1 - Modelo:**
- [ ] Archivo `core/api_models.py` modificado
- [ ] Campos obligatorios marcados con `...`
- [ ] Validadores implementados
- [ ] No hay errores de sintaxis (revisar con editor)

**PASO 2 - Endpoint:**
- [ ] Archivo `main.py` modificado
- [ ] Función `update_ticket()` agregada a `models.py`
- [ ] Import de `create_virtual_ticket` correcto
- [ ] Servidor arranca sin errores: `uvicorn main:app --reload`

**PASO 3 - UI:**
- [ ] Archivo `voice-expenses.source.jsx` modificado
- [ ] Selector de cuentas visible en navegador
- [ ] Compilar bundle: `npm run build` o similar
- [ ] Probar en navegador con devtools abierto

---

## 🧪 PRUEBAS END-TO-END

### Test 1: Gasto manual (sin ticket)

```bash
curl -X POST http://localhost:8004/expenses \
  -H "Content-Type: application/json" \
  -d '{
    "descripcion": "Gasolina corporativa",
    "monto_total": 845.32,
    "fecha_gasto": "2025-10-04",
    "payment_method": "tarjeta_empresa",
    "payment_account_id": 2,
    "proveedor": "Gasolinera Pemex",
    "categoria": "combustible",
    "will_have_cfdi": true,
    "company_id": "cmp_dd36e6c0"
  }'
```

**Resultado esperado:**
```json
{
  "id": 1,
  "ticket_id": 153,  // ← Ticket virtual creado
  "success": true,
  "message": "Gasto creado exitosamente"
}
```

### Test 2: Verificar ticket virtual

```bash
sqlite3 data/mcp_internal.db "SELECT id, tipo, estado, merchant_name FROM tickets WHERE id=153"
```

**Resultado esperado:**
```
153|virtual|procesado|Gasolinera Pemex
```

### Test 3: Verificar gasto creado

```bash
sqlite3 data/mcp_internal.db "SELECT id, description, amount, payment_account_id, ticket_id FROM expense_records WHERE id=1"
```

**Resultado esperado:**
```
1|Gasolina corporativa|845.32|2|153
```

---

## ⚠️ SI ALGO FALLA

### Error común 1: "payment_account_id not found"

**Causa:** Usuario no tiene cuentas creadas
**Solución:** Ejecutar script de creación de cuentas del resumen

### Error común 2: "Module create_virtual_ticket not found"

**Causa:** Import incorrecto
**Solución:** Verificar que está en `modules.invoicing_agent.models`

### Error común 3: "Field payment_account_id required"

**Causa:** Frontend no envía el campo
**Solución:** Verificar `buildExpenseData()` incluye el campo

---

## 🎯 ÉXITO TOTAL

Al terminar los 3 pasos, el sistema debe:

✅ Aceptar solo gastos con `payment_account_id` válido
✅ Crear tickets virtuales automáticamente
✅ Mostrar selector de cuentas en UI
✅ Validar todos los campos obligatorios
✅ Devolver `ticket_id` en response siempre

**Sistema de gastos: 100% funcional** 🚀

---

**Tiempo total estimado:** 3-4 horas
**Prioridad:** Backend funcional primero, UI después
**Resultado:** Sistema robusto y listo para producción
