# 🔄 Integración del Sistema de Escalamiento Automático

## 📋 Resumen

Este documento describe cómo integrar el **Sistema de Escalamiento Automático** en los endpoints existentes para que los gastos creados en Voice Expenses se escalen automáticamente a Advanced Ticket Dashboard cuando corresponde.

---

## 🎯 Objetivo

**Problema:** Los gastos subidos por Voice Expenses (o WhatsApp) se procesan primero en Voice, pero si el usuario marca "facturable" o el sistema detecta "will_have_cfdi=True", el gasto debe escalar automáticamente al flujo Advanced Ticket Dashboard.

**Solución:** Escalamiento automático que crea un "ticket espejo" vinculado al mismo `expense_id`, sin duplicar datos.

---

## 📦 Archivos Creados

1. **`migrations/034_expense_ticket_escalation.sql`**
   - Migración de schema
   - Agrega campos de vinculación entre `expense_records` y `tickets`

2. **`core/expense_escalation_system.py`**
   - Sistema central de escalamiento
   - Lógica de decisión (cuándo escalar)
   - Creación de tickets espejo
   - Sincronización bidireccional

3. **`core/expense_escalation_hooks.py`**
   - Hooks para integrar con endpoints
   - Funciones async ready

---

## 🔧 Paso 1: Ejecutar Migración

```bash
cd /Users/danielgoes96/Desktop/mcp-server

# Ejecutar migración
sqlite3 unified_mcp_system.db < migrations/034_expense_ticket_escalation.sql

# Verificar que se aplicó
sqlite3 unified_mcp_system.db "SELECT * FROM schema_versions WHERE version = '1.1.0';"
```

**Campos nuevos agregados:**

**En `expense_records`:**
- `will_have_cfdi` (BOOLEAN) - Si requiere factura
- `escalated_to_invoicing` (BOOLEAN) - Si ya se escaló
- `escalated_ticket_id` (INTEGER) - ID del ticket espejo
- `escalation_reason` (TEXT) - Razón del escalamiento
- `escalated_at` (TIMESTAMP) - Cuándo se escaló

**En `tickets`:**
- `expense_id` (INTEGER) - ID del gasto original
- `is_mirror_ticket` (BOOLEAN) - Si es ticket espejo
- `raw_data`, `tipo`, `estado`, `company_id`, etc. - Campos de invoicing

---

## 🔧 Paso 2: Integrar en POST /expenses

### Código Actual (main.py:2935-3027)

```python
@app.post("/expenses", response_model=ExpenseResponse)
async def create_expense(
    expense: ExpenseCreate,
    tenancy_context: TenancyContext = Depends(get_tenancy_context)
) -> ExpenseResponse:
    """Crear un nuevo gasto en la base de datos."""
    # ... código existente de creación ...

    # Guardar en DB
    expense_id = record_internal_expense(...)

    # Retornar respuesta
    return ExpenseResponse(...)
```

### Código Modificado (con escalamiento)

```python
@app.post("/expenses", response_model=ExpenseResponse)
async def create_expense(
    expense: ExpenseCreate,
    tenancy_context: TenancyContext = Depends(get_tenancy_context)
) -> ExpenseResponse:
    """Crear un nuevo gasto en la base de datos."""
    from core.expense_escalation_hooks import post_expense_creation_hook

    # ... código existente de creación ...

    # Guardar en DB
    expense_id = record_internal_expense(...)

    # ✅ NUEVO: Hook de escalamiento automático
    escalation_info = await post_expense_creation_hook(
        expense_id=expense_id,
        expense_data={
            "id": expense_id,
            "monto_total": expense.monto_total,
            "descripcion": expense.descripcion,
            "rfc": expense.rfc,
            "proveedor": expense.proveedor,
            "categoria": expense.categoria,
            "will_have_cfdi": expense.will_have_cfdi,
            "company_id": expense.company_id,
        },
        user_id=getattr(tenancy_context, "user_id", None),
        company_id=expense.company_id,
    )

    # Log del resultado
    if escalation_info.get("escalated"):
        logger.info(
            f"✅ Expense {expense_id} escalado a ticket {escalation_info['ticket_id']}"
        )

    # Retornar respuesta (agregando info de escalamiento)
    response = ExpenseResponse(...)

    # Agregar metadata de escalamiento (opcional)
    if response.metadata is None:
        response.metadata = {}

    response.metadata["escalation"] = escalation_info

    return response
```

---

## 🔧 Paso 3: Integrar en POST /ocr/intake (Opcional)

**Nota:** Actualmente `/ocr/intake` NO crea gastos, solo retorna campos extraídos. Si modificas para crear gastos automáticamente, usa este hook.

```python
@app.post("/ocr/intake")
async def ocr_intake(file: UploadFile = File(...), ...):
    """OCR intake endpoint - Create expense directly from OCR."""
    from core.expense_escalation_hooks import post_ocr_intake_hook

    # ... código existente de OCR ...

    # Si decides crear gasto automáticamente:
    expense_id = record_internal_expense(...)

    # ✅ NUEVO: Hook de escalamiento
    escalation_info = await post_ocr_intake_hook(
        expense_id=expense_id,
        ocr_data=ocr_result,
        extracted_fields=extracted_fields,
        company_id=company_id,
    )

    # Retornar con info de escalamiento
    return {
        "intake_id": intake_id,
        "fields": extracted_fields,
        "escalation": escalation_info,  # ← Info de escalamiento
    }
```

---

## 🔧 Paso 4: Integrar en RPA Completion (Advanced Dashboard)

Cuando RPA completa descarga de factura, sincronizar de vuelta a expense:

```python
# modules/invoicing_agent/api.py
# En el endpoint que procesa jobs de facturación

@router.post("/jobs/{job_id}/process")
async def process_invoicing_job(job_id: int):
    """Procesar job de facturación con RPA."""
    from core.expense_escalation_hooks import post_rpa_completion_hook

    # ... código existente de RPA ...

    # Cuando RPA completa exitosamente:
    if job_status == "completado" and invoice_data:
        # Actualizar ticket
        update_ticket(
            ticket_id=ticket_id,
            invoice_data=invoice_data,
            estado="procesado",
        )

        # ✅ NUEVO: Sincronizar de vuelta a expense
        sync_result = await post_rpa_completion_hook(
            ticket_id=ticket_id,
            invoice_data=invoice_data,
        )

        if sync_result.get("synced"):
            logger.info(
                f"✅ Factura sincronizada a expense {sync_result['expense_id']}"
            )

    return {"status": "success", "sync_result": sync_result}
```

---

## 🔧 Paso 5: Actualizar GET /invoicing/tickets

Modificar para incluir tickets espejo en la lista:

```python
# modules/invoicing_agent/models.py

def list_tickets(company_id: str = "default", limit: int = 100):
    """Listar tickets con filtros opcionales."""
    query = """
        SELECT
            t.*,
            m.nombre as merchant_name,
            e.description as expense_description,
            e.amount as expense_amount
        FROM tickets t
        LEFT JOIN merchants m ON t.merchant_id = m.id
        LEFT JOIN expense_records e ON t.expense_id = e.id  ← NUEVO JOIN
        WHERE t.company_id = ?
        ORDER BY t.created_at DESC
        LIMIT ?
    """

    with sqlite3.connect(_get_db_path()) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(query, (company_id, limit)).fetchall()

        tickets = []
        for row in rows:
            ticket = dict(row)

            # ✅ NUEVO: Indicar si es ticket espejo
            if ticket.get("is_mirror_ticket"):
                ticket["source"] = "voice_expenses"
                ticket["expense_url"] = f"/voice-expenses?highlight={ticket['expense_id']}"

            tickets.append(ticket)

        return tickets
```

---

## 📊 Paso 6: Actualizar UI de Voice Expenses

Mostrar badge de "En facturación" cuando el gasto está escalado:

```javascript
// static/voice-expenses.source.jsx

// Al cargar gastos, verificar si están escalados
const loadExpenses = async () => {
    const response = await fetch('/expenses?company_id=default');
    const expenses = await response.json();

    // Para cada gasto, verificar escalamiento
    for (const expense of expenses) {
        if (expense.metadata?.escalation?.escalated) {
            expense.inInvoicing = true;
            expense.ticketId = expense.metadata.escalation.ticket_id;
        }
    }

    setExpensesData(expenses);
};

// En el render
{expense.inInvoicing && (
    <span className="badge badge-info">
        <i className="fas fa-file-invoice"></i>
        En facturación (Ticket #{expense.ticketId})
    </span>
)}
```

---

## 🧪 Paso 7: Probar el Flujo Completo

### Test 1: Escalamiento Automático desde Voice Expenses

```bash
# 1. Crear gasto con will_have_cfdi=True
curl -X POST http://localhost:8000/expenses \
  -H "Content-Type: application/json" \
  -d '{
    "descripcion": "Servicios de consultoría",
    "monto_total": 5000,
    "fecha_gasto": "2025-01-15",
    "rfc": "CON123456789",
    "proveedor": {"nombre": "Consultores SA"},
    "categoria": "servicios",
    "will_have_cfdi": true,
    "company_id": "default"
  }'

# 2. Verificar que se creó expense
sqlite3 unified_mcp_system.db "SELECT id, description, escalated_to_invoicing FROM expense_records ORDER BY id DESC LIMIT 1;"

# 3. Verificar que se creó ticket espejo
sqlite3 unified_mcp_system.db "SELECT id, title, expense_id, is_mirror_ticket FROM tickets ORDER BY id DESC LIMIT 1;"

# 4. Verificar que se creó job
sqlite3 unified_mcp_system.db "SELECT id, ticket_id, estado FROM invoicing_jobs ORDER BY id DESC LIMIT 1;"
```

**Resultado esperado:**
```
expense_records: id=123, escalated_to_invoicing=1
tickets: id=456, expense_id=123, is_mirror_ticket=1
invoicing_jobs: id=789, ticket_id=456, estado='pendiente'
```

### Test 2: Ver Ticket en Advanced Dashboard

```bash
# Listar tickets
curl http://localhost:8000/invoicing/tickets?company_id=default

# Debería incluir el ticket espejo con:
# {
#   "id": 456,
#   "title": "Facturación: Servicios de consultoría",
#   "expense_id": 123,
#   "is_mirror_ticket": true,
#   "merchant_name": "Consultores SA",
#   "source": "voice_expenses"
# }
```

### Test 3: Completar RPA y Verificar Sincronización

```bash
# 1. Simular que RPA completa (manualmente actualizar ticket)
sqlite3 unified_mcp_system.db "UPDATE tickets SET invoice_data = '{\"uuid\": \"ABC-123\", \"total\": 5000}' WHERE id = 456;"

# 2. Ejecutar hook de sincronización
python3 << EOF
from core.expense_escalation_hooks import post_rpa_completion_hook
import asyncio

result = asyncio.run(post_rpa_completion_hook(
    ticket_id=456,
    invoice_data={"uuid": "ABC-123", "total": 5000}
))
print(result)
EOF

# 3. Verificar que expense se actualizó
sqlite3 unified_mcp_system.db "SELECT id, cfdi_uuid, workflow_status FROM expense_records WHERE id = 123;"

# Resultado esperado:
# id=123, cfdi_uuid='ABC-123', workflow_status='facturado'
```

---

## 📈 Criterios de Escalamiento

El sistema escala automáticamente cuando:

1. **Usuario explícito:** `will_have_cfdi = True`
2. **Monto alto:** > $2,000 MXN
3. **Tiene RFC:** Proveedor identificado
4. **Origen WhatsApp:** Mensaje con expectativa de factura
5. **Categoría facturable:** servicios, honorarios, renta, software, etc.

**Escalamiento ocurre si:**
- `will_have_cfdi = True` (siempre)
- O cumple 2+ de los criterios anteriores

---

## 🔍 Monitoreo y Debugging

### Ver estado de escalamiento de un gasto

```python
from core.expense_escalation_hooks import get_expense_escalation_info

status = get_expense_escalation_info(expense_id=123)
print(status)
# {
#   "is_escalated": true,
#   "ticket_id": 456,
#   "escalation_reason": "Usuario marcó will_have_cfdi=True | Monto alto ($5,000.00 MXN)",
#   "escalated_at": "2025-01-15T10:30:00",
#   "ticket_estado": "pendiente",
#   "job_estado": "pendiente"
# }
```

### Logs importantes

```bash
# Ver logs de escalamiento
tail -f app.log | grep -i "escalando\|escalated"

# Salida esperada:
# 2025-01-15 10:30:00 INFO 🚀 Escalando expense 123 a facturación. Razón: Usuario marcó will_have_cfdi=True
# 2025-01-15 10:30:01 INFO ✅ Expense 123 escalado exitosamente. Ticket: 456, Job: 789
```

---

## ❓ FAQ

### 1. ¿Se duplican los datos?

❌ **NO**. Solo se crea un "ticket espejo" que apunta al `expense_id` original. Ambas interfaces trabajan sobre el mismo gasto en `expense_records`.

### 2. ¿Qué pasa si el gasto ya tiene factura?

Si el usuario ya subió factura en Voice Expenses antes del escalamiento, el ticket espejo se crea con `estado="procesado"` y no dispara RPA.

### 3. ¿Puedo desactivar el escalamiento automático?

Sí, simplemente no llames el hook en los endpoints. O agrega un feature flag:

```python
EXPENSE_ESCALATION_ENABLED = os.getenv("EXPENSE_ESCALATION_ENABLED", "true") == "true"

if EXPENSE_ESCALATION_ENABLED:
    escalation_info = await post_expense_creation_hook(...)
```

### 4. ¿Qué pasa si falla el escalamiento?

El gasto se crea correctamente en `expense_records`. El escalamiento falla silenciosamente y se loguea el error. El usuario puede disparar manualmente desde Advanced Dashboard.

### 5. ¿Voice Expenses muestra el progreso de RPA?

Sí, si implementas polling del campo `metadata.escalation.ticket_id` puedes mostrar el estado del job de facturación.

---

## 🎯 Siguiente Paso

Aplicar migración y modificar `main.py:2935-3027` para integrar el hook.

**Comando:**
```bash
cd /Users/danielgoes96/Desktop/mcp-server
sqlite3 unified_mcp_system.db < migrations/034_expense_ticket_escalation.sql
```

Luego editar `main.py` según las instrucciones del Paso 2.

---

**Última actualización:** 2025-01-15
**Autor:** Sistema de Backend
**Versión:** 1.0
