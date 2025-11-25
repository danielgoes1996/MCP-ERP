# ✅ Fix: GET /expenses ahora filtra por company_id

## 🐛 Problema Identificado

El endpoint `GET /expenses?company_id=2` **NO estaba filtrando por company_id**.

Solo filtraba por `tenant_id` del usuario autenticado, ignorando el parámetro `company_id` de la query.

### Datos en la BD:
```sql
-- Empresa 2: 4 gastos
SELECT COUNT(*) FROM expense_records WHERE company_id = '2' AND tenant_id = 2;
-- Resultado: 4 gastos

-- Pero la UI mostraba: 0 gastos
```

## 🔧 Solución Implementada

### Cambio 1: main.py (línea 3177-3180)

**Antes:**
```python
records = fetch_expense_records(
    tenant_id=tenant_id,
    limit=limit,
)
```

**Después:**
```python
records = fetch_expense_records(
    tenant_id=tenant_id,
    limit=limit,
    company_id=company_id,  # ← Ahora usa company_id de la query
)
```

### Cambio 2: core/unified_db_adapter.py (línea 643)

**Antes:**
```python
def fetch_expense_records(self, tenant_id: int = 1, limit: int = 100) -> List[Dict]:
    cursor.execute("""
        SELECT e.*, pa.*
        FROM expense_records e
        LEFT JOIN user_payment_accounts pa ON e.payment_account_id = pa.id
        WHERE e.tenant_id = ?
        LIMIT ?
    """, (tenant_id, limit))
```

**Después:**
```python
def fetch_expense_records(self, tenant_id: int = 1, limit: int = 100, company_id: Optional[str] = None) -> List[Dict]:
    where_conditions = ["e.tenant_id = ?"]
    params = [tenant_id]

    if company_id:
        where_conditions.append("e.company_id = ?")
        params.append(company_id)

    where_clause = " AND ".join(where_conditions)
    params.append(limit)

    query = f"""
        SELECT e.*, pa.*
        FROM expense_records e
        LEFT JOIN user_payment_accounts pa ON e.payment_account_id = pa.id
        WHERE {where_clause}
        ORDER BY e.created_at DESC
        LIMIT ?
    """

    cursor.execute(query, tuple(params))
```

### Cambio 3: core/unified_db_adapter.py (línea 1995)

**Antes:**
```python
def fetch_expense_records(tenant_id: int = 1, limit: int = 100) -> List[Dict]:
    return get_unified_adapter().fetch_expense_records(tenant_id, limit)
```

**Después:**
```python
def fetch_expense_records(tenant_id: int = 1, limit: int = 100, company_id: Optional[str] = None) -> List[Dict]:
    return get_unified_adapter().fetch_expense_records(tenant_id, limit, company_id)
```

---

## 🚀 Cómo Aplicar los Cambios

### 1. Reiniciar el Servidor

```bash
# Si estás usando uvicorn:
pkill -f uvicorn
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

# O si usas otro método de inicio:
# Detén el servidor actual y reinícialo
```

### 2. Verificar en la UI

1. Recarga la página: `http://localhost:8000/voice-expenses`
2. Deberías ver ahora:
   - **GASTOS DEMO: 4** (o el número de gastos en empresa 2)
   - Los 4 gastos listados abajo

### 3. Verificar con curl (opcional)

```bash
# Con token
TOKEN=$(cat <<EOF | python3
import json
print(json.loads(open('localStorage.json').read())['access_token'])
EOF
)

curl -H "Authorization: Bearer YOUR_TOKEN" \
  "http://localhost:8000/expenses?company_id=2"
```

---

## 🧪 Pruebas

### Caso 1: Filtrar por company_id
```bash
GET /expenses?company_id=2
# Debería retornar 4 gastos
```

### Caso 2: Sin company_id (usa todos del tenant)
```bash
GET /expenses
# Debería retornar todos los gastos del tenant_id del usuario
```

### Caso 3: company_id que no existe
```bash
GET /expenses?company_id=999
# Debería retornar 0 gastos
```

---

## 📝 Cambios Relacionados

También se aplicó el fix de autenticación (ver `SOLUCION_ERROR_401.md`):
- Redirección automática al login si no hay token
- Manejo de error 401 con limpieza de token inválido

---

## ✅ Resultado Esperado

Después de reiniciar el servidor:

1. ✅ La UI carga los gastos de la empresa seleccionada
2. ✅ El filtro por `company_id` funciona correctamente
3. ✅ El dashboard muestra las métricas correctas
4. ✅ Los 4 gastos de la empresa 2 son visibles

---

## 🔍 SQL para Verificar Datos

```sql
-- Ver todos los gastos por empresa
sqlite3 unified_mcp_system.db "
  SELECT company_id, COUNT(*) as total
  FROM expense_records
  GROUP BY company_id;
"

-- Ver gastos de empresa 2
sqlite3 unified_mcp_system.db "
  SELECT id, description, amount, company_id, tenant_id, status
  FROM expense_records
  WHERE company_id = '2';
"

-- Verificar usuario autenticado
sqlite3 unified_mcp_system.db "
  SELECT id, username, email, tenant_id
  FROM users
  WHERE username = 'admin';
"
```

---

¡Listo! Reinicia el servidor y deberías ver los gastos correctamente. 🎉
