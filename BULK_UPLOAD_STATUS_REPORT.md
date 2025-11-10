# 📊 Reporte: Estado de Carga Masiva de Facturas CFDI 4.0 con PostgreSQL

**Fecha**: 8 de Noviembre 2025
**Sistema**: ContaFlow / mcp-server
**Migración**: SQLite → PostgreSQL (puerto 5433)

---

## ✅ LOGROS COMPLETADOS

### 1. Infraestructura PostgreSQL
- ✅ PostgreSQL corriendo en Docker (mcp-postgres:5433)
- ✅ Adaptador `pg_sync_adapter.py` creado como drop-in replacement de sqlite3
- ✅ Tablas creadas correctamente:
  - `expense_invoices` (0 registros actualmente)
  - `bulk_invoice_batches` (3 batches pendientes)
  - `bulk_invoice_batch_items`
  - `invoice_import_logs` (logs borrados para prueba fresca)

### 2. Parser CFDI 4.0
- ✅ Parser validado con +335 XML reales en `/test_invoices`
- ✅ Detección de duplicados funcionando correctamente (por file_hash)

### 3. Endpoint `/invoices/upload-bulk`
- ✅ Autenticación JWT funcionando
- ✅ Parsing de XMLs exitoso
- ✅ Creación de batch exitosa
- ✅ Response 200 OK con batch_id

### 4. Sistema de Testing
- ✅ Script `test_bulk_upload_postgres.py` creado
- ✅ Script `trigger_batch_processing.py` creado
- ✅ Servidor FastAPI corriendo en http://localhost:8000

---

## ❌ PROBLEMA ACTUAL: Error "cursor None"

### Error Específico
```
Error: 'NoneType' object has no attribute 'status'
```

### Ubicación del Error
**Endpoint**: `POST /invoices/process-batch/{batch_id}`
**Archivo**: [main.py:3569-3573](main.py#L3569)

```python
# Line 3569
batch = await bulk_invoice_processor.process_batch(batch_id)

# Line 3573 - FALLA AQUÍ
return {
    "batch_id": batch.batch_id,  # batch es None
    "status": batch.status.value,  # ❌ 'NoneType' object has no attribute 'status'
    ...
}
```

### Causa Raíz

El método `bulk_invoice_processor.process_batch()` llama a `_load_batch_record()` que retorna `None` porque:

1. **Batch existe en BD** (verificado con SQL):
   ```sql
   SELECT * FROM bulk_invoice_batches WHERE batch_id = 'batch_e43cc56195264935';
   -- Resultado: 1 row con status='pending', total_invoices=10
   ```

2. **Pero `_load_batch_record()` falla** al intentar cargar:
   - Línea 1136: `batch_data = await self.db.fetch_one(batch_query, (batch_id,))`
   - Línea 1145: `items_data = await self.db.fetch_all(items_query, (batch_id,))`

3. **Posibles razones del fallo**:
   - El adaptador `pg_sync_adapter` no está manejando correctamente los cursores
   - El wrapper `SyncDBWrapper` en `bulk_invoice_processor.py` puede tener problemas
   - Problemas con la conversión de datos PostgreSQL → Python

---

## 🔍 DIAGNÓSTICO TÉCNICO

### Batch Creado Exitosamente
```json
{
  "batch_id": "batch_e43cc56195264935",
  "status": "processing",
  "total_files": 10,
  "total_invoices": 10,
  "errors": 0,
  "duplicates": 0,
  "message": "Batch created successfully. 10 invoices queued for processing."
}
```

### Estado en Base de Datos
```sql
-- Batch record
batch_id: batch_e43cc56195264935
company_id: 2
status: pending
total_invoices: 10
processed_count: 0

-- Items NO se están insertando en bulk_invoice_batch_items
```

### Problema Identificado

El método `_load_batch_record()` en `bulk_invoice_processor.py` está intentando:

1. **Cargar batch**:
   ```python
   batch_data = await self.db.fetch_one(batch_query, (batch_id,))
   # batch_data probablemente es None o vacío
   ```

2. **Cargar items**:
   ```python
   items_data = await self.db.fetch_all(items_query, (batch_id,))
   # items_data probablemente vacío
   ```

3. **Si no hay datos, retorna None**:
   ```python
   if not batch_data:
       return None  # ❌ Esto causa el error
   ```

---

## 🐛 ERRORES RELACIONADOS

### 1. Items no se están guardando
- `_store_batch_items()` se llama pero los items no aparecen en la tabla
- Query: `SELECT * FROM bulk_invoice_batch_items WHERE batch_id = 'batch_e43cc56195264935'`
- Resultado: 0 rows

### 2. Adaptador PostgreSQL
El wrapper `SyncDBWrapper` en `bulk_invoice_processor.py`:

```python
async def execute(self, query, params=None):
    conn = self.adapter.connect()
    try:
        cursor = conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        conn.commit()
        return f"OK {cursor.rowcount}"
    finally:
        conn.close()
```

**Posible problema**: El `cursor` puede no estar funcionando correctamente con el adaptador PostgreSQL.

---

## 🔧 SOLUCIONES PROPUESTAS

### Solución 1: Verificar inserción de items
```python
# Agregar logs en _store_batch_items()
logger.info(f"Storing {len(batch.items)} items for batch {batch.batch_id}")

# Verificar que los items se inserten
for item in batch.items:
    result = await self.db.execute(query, (...))
    logger.info(f"Inserted item: {item.filename}, result: {result}")
```

### Solución 2: Debugging del cursor
```python
# En _load_batch_record()
logger.info(f"Loading batch {batch_id}")
batch_data = await self.db.fetch_one(batch_query, (batch_id,))
logger.info(f"Batch data loaded: {batch_data}")

if not batch_data:
    logger.error(f"Batch {batch_id} not found in database!")
    return None
```

### Solución 3: Verificar adaptador PostgreSQL
```python
# En pg_sync_adapter.py, agregar logs
def execute(self, query: str, params=None):
    pg_query = convert_query_sqlite_to_pg(query)
    logger.debug(f"Executing: {pg_query} with params: {params}")

    if params:
        self._cursor.execute(pg_query, params)
    else:
        self._cursor.execute(pg_query)

    logger.debug(f"Rows affected: {self._cursor.rowcount}")
    return self
```

---

## 📝 PRÓXIMOS PASOS

### Paso 1: Agregar logs detallados
1. Modificar `bulk_invoice_processor.py` para agregar logs en:
   - `_store_batch_items()`
   - `_load_batch_record()`
2. Ver exactamente dónde falla

### Paso 2: Verificar datos en PostgreSQL
```sql
-- Verificar batch
SELECT * FROM bulk_invoice_batches WHERE batch_id = 'batch_e43cc56195264935';

-- Verificar items
SELECT COUNT(*) FROM bulk_invoice_batch_items WHERE batch_id = 'batch_e43cc56195264935';

-- Verificar estructura
\d bulk_invoice_batch_items
```

### Paso 3: Testear adaptador directamente
```python
# Script de prueba para pg_sync_adapter
from core.database import pg_sync_adapter

conn = pg_sync_adapter.connect()
cursor = conn.cursor()

cursor.execute("SELECT * FROM bulk_invoice_batches LIMIT 1")
row = cursor.fetchone()
print(f"Row: {row}")
print(f"Type: {type(row)}")
```

---

## 🎯 OBJETIVO FINAL

**Lograr que la carga masiva funcione end-to-end**:
1. ✅ Upload de XMLs → Batch creado
2. ❌ Trigger procesamiento → **Items insertados en expense_invoices**
3. ❌ Verificación en PostgreSQL → **Datos correctos**

---

## 📊 MÉTRICAS ACTUALES

| Métrica | Valor | Estado |
|---------|-------|--------|
| XMLs disponibles | 335 | ✅ |
| Batches creados | 3 | ✅ |
| Batches procesados | 0 | ❌ |
| Facturas en expense_invoices | 0 | ❌ |
| Items en batch_items | 0 | ❌ |

---

## 🔗 ARCHIVOS RELEVANTES

- `main.py` (línea 3176-3585): Endpoints de bulk upload
- `core/expenses/invoices/bulk_invoice_processor.py`: Procesador batch
- `core/database/pg_sync_adapter.py`: Adaptador PostgreSQL
- `test_bulk_upload_postgres.py`: Script de prueba
- `trigger_batch_processing.py`: Trigger manual

---

**Siguiente acción recomendada**: Agregar logs detallados y debuggear el flujo de inserción de items en `bulk_invoice_batch_items`.
