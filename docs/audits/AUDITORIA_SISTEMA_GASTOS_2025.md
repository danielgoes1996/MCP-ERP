# 🔍 AUDITORÍA COMPLETA: Sistema de Gastos
**Fecha:** 2025-10-03
**Base de datos:** `mcp_internal.db`

---

## ✅ RESUMEN EJECUTIVO

| Categoría | Estado | Detalles |
|-----------|--------|----------|
| **Tabla expense_records** | ⚠️ **90% completo** | Faltan 2 campos NOT NULL y 1 campo nuevo |
| **Tabla user_payment_accounts** | ✅ **100% completo** | Existe y está correctamente configurada |
| **Tabla tickets** | ✅ **100% completo** | Tiene todos los campos necesarios |
| **Relaciones FK** | ✅ **100% completo** | Todas las FK están definidas |
| **Endpoint POST /expenses** | ❌ **0% completo** | No valida campos obligatorios |

---

## 📊 REQUISITO 1: Campos obligatorios en `expense_records`

### ✅ Campos que SÍ existen y son NOT NULL:

| Campo | Tipo | NOT NULL | FK | Estado |
|-------|------|----------|-----|--------|
| `description` | TEXT | ✅ | - | ✅ **CORRECTO** |
| `amount` | REAL | ✅ | - | ✅ **CORRECTO** (alias de monto_total) |
| `payment_account_id` | INTEGER | ✅ | → user_payment_accounts(id) | ✅ **CORRECTO** |

### ❌ Campos que existen pero son NULLABLE (deben ser NOT NULL):

| Campo | Tipo | NOT NULL | Problema | Acción Requerida |
|-------|------|----------|----------|------------------|
| `expense_date` | TEXT | ❌ (nullable) | **HARD REQUIRED para contabilidad** | ⚠️ CRÍTICO: Migrar tabla completa a futuro |
| `payment_method` | TEXT | ❌ (nullable) | **HARD REQUIRED para contabilidad** | ⚠️ CRÍTICO: Migrar tabla completa a futuro |

> **⚠️ NOTA CRÍTICA:** En contabilidad estos campos son **obligatorios por ley**. Aunque SQLite no permite ALTER COLUMN fácilmente, **debe planearse una migración completa de tabla** para volverlos NOT NULL. Por ahora se validan en la capa de aplicación, pero esto es **deuda técnica que debe resolverse**.

### ❌ Campo faltante:

| Campo | Estado | Acción Requerida |
|-------|--------|------------------|
| `invoice_status_reason` | ❌ No existe | ALTER TABLE ADD COLUMN |

---

## 📊 REQUISITO 2: Campos opcionales en `expense_records`

### ✅ Todos existen correctamente:

| Campo | Tipo | Nullable | Default | Estado |
|-------|------|----------|---------|--------|
| `category` | TEXT | ✅ | NULL | ✅ **CORRECTO** |
| `provider_name` | TEXT | ✅ | NULL | ✅ **CORRECTO** |
| `provider_rfc` | TEXT | ✅ | NULL | ✅ **CORRECTO** |
| `ticket_id` | INTEGER | ✅ | NULL | ✅ **CORRECTO** (FK → tickets.id) |
| `will_have_cfdi` | INTEGER | ❌ NOT NULL | 0 | ⚠️ **PROBLEMA:** DEFAULT 0 hace que muchos gastos aparezcan como "sin factura" aunque el usuario no lo haya decidido. **Debe ser:** `BOOLEAN DEFAULT true NULL` |
| `invoice_status` | TEXT | ❌ NOT NULL | 'pendiente' | ✅ **CORRECTO** (debe ser NOT NULL) |
| `metadata` (notas) | TEXT | ✅ | NULL | ✅ **CORRECTO** |

---

## 📊 REQUISITO 3: Relación con tickets

### ✅ Estado actual:

| Aspecto | Estado | Detalles |
|---------|--------|----------|
| **Campo `ticket_id` en expenses** | ✅ Existe | INTEGER, nullable, FK → tickets(id) |
| **Campo `linked_expense_id` en tickets** | ✅ Existe | INTEGER, nullable |
| **Campo `tipo` en tickets** | ✅ Existe | TEXT NOT NULL, CHECK constraint |
| **Tickets virtuales** | ❌ No implementado | Falta lógica en endpoint |

### ❌ Pendiente:

- **Lógica de negocio**: Endpoint POST /expenses debe crear ticket virtual si no se envía `ticket_id`

> **🔴 BLOQUEANTE CRÍTICO:** Sin tickets virtuales, se rompe la regla **1 Ticket = 1 Expense**, perdiendo toda la trazabilidad del sistema. Este es el núcleo del diseño y debe implementarse **YA**.

---

## 📊 REQUISITO 4: Relación con cuentas de pago

### ✅ Estado actual:

| Aspecto | Estado | Detalles |
|---------|--------|----------|
| **Tabla `user_payment_accounts`** | ✅ Existe | 19 columnas, con constraints CHECK |
| **FK `payment_account_id`** | ✅ Existe | En expense_records, NOT NULL, FK válido |
| **Campo `paid_by` (texto)** | ✅ No existe | **CORRECTO** - eliminado |
| **Cuentas de ejemplo** | ✅ Existen | 7 cuentas para contacto@carretaverde.com |

---

## 📊 REQUISITO 5: Flujo de facturación

### ✅ Campos existentes:

| Campo | Tipo | NOT NULL | Default | Estado |
|-------|------|----------|---------|--------|
| `will_have_cfdi` | INTEGER | ❌ | 0 | ⚠️ Debe ser nullable |
| `invoice_status` | TEXT | ✅ | 'pendiente' | ✅ **CORRECTO** |
| `invoice_status_reason` | - | - | - | ❌ **NO EXISTE** |

### ❌ Pendiente:

- Agregar campo `invoice_status_reason TEXT`
- Cambiar `will_have_cfdi` a nullable (permitir NULL)

---

## 🔧 MIGRACIÓN SQL REQUERIDA

```sql
-- 1. Agregar campo invoice_status_reason
ALTER TABLE expense_records ADD COLUMN invoice_status_reason TEXT;

-- 2. Nota sobre expense_date y payment_method:
-- SQLite no permite ALTER COLUMN para agregar NOT NULL
-- Opción 1: Dejar como nullable (más seguro para producción)
-- Opción 2: Recrear tabla completa (requiere downtime)
-- RECOMENDACIÓN: Validar en la capa de aplicación (Python/FastAPI)

-- 3. Índice para invoice_status_reason
CREATE INDEX idx_expense_records_invoice_status_reason
ON expense_records(invoice_status_reason)
WHERE invoice_status_reason IS NOT NULL;
```

---

## 🚀 ENDPOINT POST /expenses - Cambios requeridos

### Validaciones a agregar:

```python
@app.post("/expenses")
async def create_expense(expense: ExpenseCreate):
    # 1. Validar campos obligatorios
    if not expense.description:
        raise HTTPException(400, "description es obligatorio")

    if not expense.amount or expense.amount <= 0:
        raise HTTPException(400, "amount debe ser mayor a 0")

    if not expense.expense_date:
        raise HTTPException(400, "expense_date es obligatorio")

    if not expense.payment_method:
        raise HTTPException(400, "payment_method es obligatorio")

    if not expense.payment_account_id:
        raise HTTPException(400, "payment_account_id es obligatorio")

    # 2. Validar que payment_account_id existe
    account = get_payment_account(expense.payment_account_id)
    if not account:
        raise HTTPException(404, f"Cuenta {expense.payment_account_id} no existe")

    # 3. Crear ticket virtual si no se envió ticket_id
    if not expense.ticket_id:
        ticket_id = create_virtual_ticket(
            user_id=current_user.id,
            company_id=expense.company_id,
            merchant_name=expense.provider_name,
            category=expense.category,
            amount=expense.amount
        )
        expense.ticket_id = ticket_id

    # 4. Validar invoice_status_reason si invoice_status = 'no_aplica'
    if expense.invoice_status == 'no_aplica' and not expense.invoice_status_reason:
        raise HTTPException(400, "invoice_status_reason es obligatorio cuando invoice_status = 'no_aplica'")

    # 5. Crear gasto
    expense_id = record_internal_expense(expense.dict())

    # 6. Actualizar ticket con linked_expense_id
    if expense.ticket_id:
        update_ticket(expense.ticket_id, linked_expense_id=expense_id)

    # 7. Response consistente (siempre devolver ticket_id)
    return {
        "id": expense_id,
        "ticket_id": expense.ticket_id,  # ← SIEMPRE presente, aunque sea virtual
        "success": True,
        "message": "Gasto creado exitosamente"
    }
```

---

## 📋 CHECKLIST FINAL

### Requisitos de Diseño:

#### 1. Todo gasto debe tener campos obligatorios:
- ✅ `amount` (monto_total) - NOT NULL
- ⚠️ `expense_date` - **Existe pero nullable** (validar en app)
- ⚠️ `payment_method` - **Existe pero nullable** (validar en app)
- ✅ `payment_account_id` - NOT NULL con FK
- ✅ `description` - NOT NULL

#### 2. Campos opcionales:
- ✅ `category` - nullable
- ✅ `provider_name` - nullable
- ✅ `provider_rfc` - nullable
- ✅ `ticket_id` - nullable con FK
- ✅ `will_have_cfdi` - NOT NULL (pero debería ser nullable)
- ✅ `invoice_status` - NOT NULL
- ❌ `invoice_status_reason` - **NO EXISTE**
- ✅ `metadata` (notas) - nullable

#### 3. Relación con tickets:
- ✅ Campo `ticket_id` en expenses existe
- ✅ Campo `linked_expense_id` en tickets existe
- ✅ Campo `tipo` en tickets existe
- ❌ Lógica de tickets virtuales **NO IMPLEMENTADA**

#### 4. Relación con cuentas:
- ✅ Tabla `user_payment_accounts` existe
- ✅ `payment_account_id` con FK
- ✅ Campo `paid_by` NO existe (correcto)

#### 5. Flujo de facturación:
- ✅ Campo `will_have_cfdi` existe
- ✅ Campo `invoice_status` existe
- ❌ Campo `invoice_status_reason` **NO EXISTE**

---

## 🎯 RESUMEN DE ACCIONES PENDIENTES

### 🔴 CRÍTICO (Bloqueante - Implementar HOY):
1. ❌ **Agregar campo `invoice_status_reason TEXT`** a `expense_records`
2. ❌ **Implementar creación de tickets virtuales** (núcleo del sistema)
3. ❌ **Implementar validaciones en endpoint POST /expenses**
4. ❌ **Response consistente con `ticket_id` siempre presente**

### 🟡 IMPORTANTE (Implementar esta semana):
5. ⚠️ **Validar `expense_date` y `payment_method` en capa de aplicación** (hard required)
6. ⚠️ **Cambiar `will_have_cfdi`** de DEFAULT 0 a DEFAULT true NULL
7. ⚠️ **Planear migración completa** de tabla para volver `expense_date` y `payment_method` NOT NULL

### 🟣 DEUDA TÉCNICA (Planear para siguiente sprint):
8. 📋 **Migración completa de tabla `expense_records`** para:
   - Volver `expense_date` NOT NULL
   - Volver `payment_method` NOT NULL
   - Cambiar `will_have_cfdi` a BOOLEAN DEFAULT true NULL

### 🟢 MEJORAS (Nice to have):
6. ✅ Todo lo demás ya está implementado correctamente

---

## 📊 PORCENTAJE DE COMPLETITUD

| Componente | Completitud |
|------------|-------------|
| **Esquema BD** | 95% ✅ |
| **Relaciones FK** | 100% ✅ |
| **Lógica de negocio** | 20% ❌ |
| **Validaciones** | 0% ❌ |
| **TOTAL SISTEMA** | **54%** ⚠️ |

---

## ✅ CONCLUSIÓN

**El esquema de base de datos está casi completo (95%)**, solo falta 1 campo.

**La lógica de negocio está incompleta (20%)**, faltan validaciones críticas en el endpoint.

**Próximos pasos:**
1. Ejecutar migración SQL para agregar `invoice_status_reason`
2. Actualizar modelo `ExpenseCreate` con validaciones
3. Implementar lógica de tickets virtuales
4. Agregar validaciones en endpoint POST /expenses
