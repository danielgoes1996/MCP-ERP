# 🔐 Multi-Tenancy: Próximos Pasos para Completar

## ✅ LO QUE YA FUNCIONA (Commit Actual)

### Backend - Autenticación & Endpoints
- ✅ JWT incluye `tenant_id` en el token
- ✅ `enforce_tenant_isolation()` valida acceso por tenant
- ✅ 16 endpoints protegidos pasan `tenant_id` a servicios
- ✅ Migration 021: `employee_advances.tenant_id` creada

**Archivos modificados:**
```
core/auth_jwt.py (agregado tenant_id + helpers)
api/employee_advances_api.py (6 endpoints protegidos)
api/split_reconciliation_api.py (6 endpoints protegidos)
api/ai_reconciliation_api.py (4 endpoints protegidos)
migrations/021_add_tenant_to_employee_advances.sql (nueva)
```

---

## 🔴 LO QUE FALTA (CRÍTICO)

### 1. Modificar `employee_advances_service.py`

Todos los métodos necesitan agregar filtrado por `tenant_id`:

#### `create_advance()`
```python
# ANTES
cursor.execute("SELECT * FROM expense_records WHERE id = ?", (expense_id,))

# DESPUÉS
if tenant_id is None:
    raise ValueError("tenant_id required")

cursor.execute("""
    SELECT * FROM expense_records
    WHERE id = ? AND tenant_id = ?
""", (expense_id, tenant_id))

# Al insertar:
cursor.execute("""
    INSERT INTO employee_advances (
        ..., tenant_id
    ) VALUES (..., ?)
""", (..., tenant_id))
```

#### `list_advances()`
```python
# ANTES
query = "SELECT * FROM employee_advances WHERE 1=1"

# DESPUÉS
query = "SELECT * FROM employee_advances WHERE tenant_id = ?"
params = [tenant_id]
```

#### `get_advance_by_id()`
```python
# ANTES
cursor.execute("SELECT * FROM employee_advances WHERE id = ?", (id,))

# DESPUÉS
cursor.execute("""
    SELECT * FROM employee_advances
    WHERE id = ? AND tenant_id = ?
""", (id, tenant_id))
```

#### `reimburse_advance()`
```python
# Validar advance pertenece al tenant
cursor.execute("""
    SELECT * FROM employee_advances
    WHERE id = ? AND tenant_id = ?
""", (advance_id, tenant_id))

if not advance:
    raise ValueError(f"Advance {advance_id} not found in tenant {tenant_id}")
```

#### `get_advances_by_employee()`
```python
# DESPUÉS
cursor.execute("""
    SELECT * FROM employee_advances
    WHERE employee_id = ? AND tenant_id = ?
""", (employee_id, tenant_id))
```

#### `get_summary()`
```python
# DESPUÉS
cursor.execute("""
    SELECT COUNT(*), SUM(advance_amount), ...
    FROM employee_advances
    WHERE tenant_id = ?
""", (tenant_id,))
```

**Archivos a modificar:**
- `core/employee_advances_service.py` (~6 métodos, ~200 líneas)

---

### 2. Verificar/Modificar `split_reconciliation_service.py`

#### Verificar si tabla tiene `tenant_id`:
```bash
sqlite3 unified_mcp_system.db ".schema split_reconciliations"
```

#### Si NO tiene, crear migration:
```sql
ALTER TABLE split_reconciliations ADD COLUMN tenant_id INTEGER;

UPDATE split_reconciliations sr
SET tenant_id = (
    SELECT bm.tenant_id FROM bank_movements bm
    WHERE bm.split_group_id = sr.split_group_id
    LIMIT 1
);

CREATE INDEX idx_split_reconciliations_tenant ON split_reconciliations(tenant_id);
```

#### Modificar funciones:

##### `create_one_to_many_split()`
```python
# Validar movement pertenece al tenant
cursor.execute("""
    SELECT * FROM bank_movements
    WHERE id = ? AND tenant_id = ?
""", (movement_id, tenant_id))

# Validar TODAS las expenses pertenecen al tenant
for expense_item in request.expenses:
    cursor.execute("""
        SELECT * FROM expense_records
        WHERE id = ? AND tenant_id = ?
    """, (expense_item.expense_id, tenant_id))
```

##### `create_many_to_one_split()`
```python
# Validar expense pertenece al tenant
# Validar TODOS los movements pertenecen al tenant
```

##### `get_split_details(), list_splits(), undo_split(), get_split_summary()`
```python
# Agregar WHERE tenant_id = ? en todos los queries
```

**Archivos a modificar:**
- `migrations/022_add_tenant_to_split_reconciliations.sql` (nueva)
- `core/split_reconciliation_service.py` (~6 funciones, ~300 líneas)

---

### 3. Modificar `ai_reconciliation_service.py`

#### `get_all_suggestions()`
```python
# Filtrar movements por tenant
unmatched_movements = cursor.execute("""
    SELECT * FROM bank_movements
    WHERE matched_expense_id IS NULL
    AND tenant_id = ?
""", (tenant_id,)).fetchall()

# Filtrar expenses por tenant
unmatched_expenses = cursor.execute("""
    SELECT * FROM expense_records
    WHERE bank_status = 'pending'
    AND tenant_id = ?
""", (tenant_id,)).fetchall()
```

#### `suggest_one_to_many_splits()`
```python
# Mismo patrón: WHERE tenant_id = ?
```

#### `suggest_many_to_one_splits()`
```python
# Mismo patrón: WHERE tenant_id = ?
```

**Archivos a modificar:**
- `core/ai_reconciliation_service.py` (~3 métodos, ~150 líneas)

---

## 🧪 Testing (Paso Final)

### Test 1: Aislamiento básico
```python
# Usuario tenant=1
login("demo", "password")  # tenant_id=1
advances = GET /employee_advances/
# Debe retornar solo advances con tenant_id=1

# Usuario tenant=3
login("dgomezes96", "password")  # tenant_id=3
advances = GET /employee_advances/
# Debe retornar solo advances con tenant_id=3
```

### Test 2: Intento de acceso cross-tenant
```python
# Usuario tenant=1 intenta acceder a advance de tenant=3
login("demo", "password")  # tenant_id=1
response = GET /employee_advances/123  # advance pertenece a tenant=3

# Esperado: 404 Not Found (porque no existe en su tenant)
# O 403 Forbidden si implementamos validación explícita
```

### Test 3: Split reconciliation multi-tenant
```python
# Usuario tenant=1 intenta crear split con movement de tenant=3
POST /bank_reconciliation/split/one-to-many
{
  "movement_id": 999,  # pertenece a tenant=3
  "manual_expenses": [...]    # pertenecen a tenant=1
}

# Esperado: 400 Bad Request - "Movement not found in tenant 1"
```

---

## 📊 Estimación de Esfuerzo

| Tarea | Archivos | Líneas | Tiempo |
|-------|----------|--------|--------|
| Modificar employee_advances_service.py | 1 | ~200 | 2-3 horas |
| Crear migration split_reconciliations | 1 | ~50 | 30 min |
| Modificar split_reconciliation_service.py | 1 | ~300 | 3-4 horas |
| Modificar ai_reconciliation_service.py | 1 | ~150 | 1-2 horas |
| Testing completo | - | - | 2 horas |
| **Total** | **4** | **~700** | **9-12 horas** |

---

## 🎯 Recomendación de Ejecución

### Opción A: Implementación Completa (recomendada)
```
1. Modificar employee_advances_service.py (CRÍTICO)
2. Crear migration + modificar split_reconciliation_service.py
3. Modificar ai_reconciliation_service.py
4. Testing exhaustivo
5. Commit final
```

### Opción B: Implementación por Fases
```
Fase 1 (Ahora):
- Commit actual (JWT + endpoints + migration)
- Documentación (este archivo)

Fase 2 (Siguiente sesión):
- Modificar employee_advances_service.py
- Testing básico

Fase 3 (Final):
- Modificar split_reconciliation + ai_reconciliation
- Testing completo
```

---

## 🚨 IMPORTANTE

**Estado actual:** El sistema está **PARCIALMENTE PROTEGIDO**.

- ✅ Endpoints validan tenant_id
- ❌ Servicios NO filtran por tenant_id

**Riesgo:** Un usuario podría acceder a datos de otro tenant si:
1. Adivina el ID de un recurso de otro tenant
2. El servicio no valida tenant_id

**Mitigación temporal:**
- Los endpoints ya bloquean acceso (HTTPException 403)
- Pero es mejor completar la implementación en servicios

**Próximo commit debería incluir:**
- Servicios modificados (al menos employee_advances_service.py)
- Tests de aislamiento multi-tenant

---

**Última actualización:** 2025-10-03
**Status:** 🟡 IMPLEMENTACIÓN PARCIAL (40% completo)
**Próximo paso:** Modificar servicios para filtrado real
