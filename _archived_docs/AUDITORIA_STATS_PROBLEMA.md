# Auditoría: Problema con Estadísticas en Frontend

**Fecha**: 2025-11-13
**Contexto**: Las estadísticas muestran "0 CFDI vigentes" aunque hay 31 facturas procesadas

---

## 🔍 Problemas Identificados

### **Problema #1: SAT Status = "desconocido" (29/31 facturas)**

**Causa Raíz**:
- Las 2 facturas "vigente" tienen `total: $0.00` en lugar de sus montos reales
- El reprocessing background NO actualizó `display_info.sat_status`
- Solo actualizó `sat_validation_status` en la tabla (campo separado)

**Evidencia**:
```
Suma de totales: $159,254.30
Suma de vigentes: $0.00 (2 facturas) ← ERROR: Las vigentes deberían tener montos
```

**Por qué pasó**:
1. El pipeline de reprocesamiento actualiza `sat_validation_status` en PostgreSQL
2. Pero NO actualiza `display_info.sat_status` que es lo que lee el frontend
3. Frontend calcula stats basándose en `display_info.sat_status`

---

### **Problema #2: Estadísticas muestran 0 vigentes**

**Causa Raíz**:
```typescript
// frontend/app/invoices/page.tsx línea ~805
const vigenteSessions = filteredSessions.filter(s => getSatStatus(s) === 'vigente');
```

La función `getSatStatus()` lee:
```typescript
session.display_info?.sat_status  // ← Siempre "desconocido"
```

Pero el backend actualizó:
```
sat_validation_status = 'vigente'  // ← Campo diferente
```

**Resultado**:
- Backend: 2 facturas con `sat_validation_status = 'vigente'`
- Frontend: 0 facturas con `display_info.sat_status = 'vigente'`
- Stats: 0 vigentes → $0.00

---

### **Problema #3: Las 2 facturas "vigentes" tienen total $0.00**

**Evidencia**:
```
Suma de vigentes: $0.00 (2 facturas)
```

Esto indica que cuando se validó contra SAT, el campo `total` se perdió o se sobrescribió con 0.

---

## 📊 Estado Actual de los Datos

```
Total sesiones: 31
├─ Con display_info: 31 ✓
├─ Sin display_info: 0 ✓
│
SAT Status (display_info.sat_status):
├─ desconocido: 29  ← PROBLEMA
└─ vigente: 2      ← Pero con total $0.00 (PROBLEMA)

Tipos de comprobante:
├─ I (Ingreso): 26
├─ E (Egreso): 1
└─ P (Pago): 4

Montos:
├─ Suma total: $159,254.30 ✓
├─ Suma vigentes: $0.00  ← ERROR
└─ RFC: POL210218264 (31 recibidas) ✓
```

---

## 🔧 Causa Raíz del Pipeline

### Flujo actual (INCORRECTO):
```
1. Reprocess endpoint → POST /universal-invoice/sessions/reprocess-failed/
2. Background worker procesa extracción
3. Background worker valida SAT
4. Actualiza: sat_validation_status = 'vigente'  ✓
5. NO actualiza: display_info.sat_status  ✗
6. Frontend lee display_info.sat_status  → "desconocido"
7. Stats calculan 0 vigentes
```

### Flujo esperado (CORRECTO):
```
1. Reprocess endpoint
2. Background worker procesa extracción
3. Background worker valida SAT
4. Actualiza sat_validation_status ✓
5. Actualiza display_info.sat_status ✓  ← FALTA
6. Frontend lee display_info.sat_status → "vigente"
7. Stats calculan correctamente
```

---

## ✅ Plan de Solución

### **Solución Inmediata** (10 minutos)

1. **Sincronizar display_info.sat_status con sat_validation_status**
   ```python
   # Script: scripts/sync_sat_status_to_display_info.py
   UPDATE sat_invoices
   SET display_info = jsonb_set(
       display_info,
       '{sat_status}',
       to_jsonb(sat_validation_status)
   )
   WHERE sat_validation_status IS NOT NULL
     AND sat_validation_status != 'pending'
     AND (display_info->>'sat_status' IS NULL
          OR display_info->>'sat_status' = 'desconocido')
   ```

2. **Validar las 29 facturas pendientes contra SAT**
   - Usar endpoint correcto que actualice ambos campos

---

### **Solución Permanente** (30 minutos)

#### **Fix #1: Actualizar display_info en SAT validation**

**Archivo**: `core/expenses/invoices/universal_invoice_engine_system.py`
**Método**: `_validate_sat()` (línea ~500)

**Cambio necesario**:
```python
# ANTES (solo actualiza sat_validation_status)
UPDATE sat_invoices
SET sat_validation_status = %s,
    sat_codigo_estatus = %s,
    ...
WHERE id = %s

# DESPUÉS (actualiza ambos)
UPDATE sat_invoices
SET sat_validation_status = %s,
    sat_codigo_estatus = %s,
    ...,
    display_info = jsonb_set(
        display_info,
        '{sat_status}',
        to_jsonb(%s)
    )
WHERE id = %s
```

#### **Fix #2: Evitar sobrescribir totales con $0.00**

**Archivo**: `core/sat/sat_cfdi_verifier.py` o donde se actualice `display_info`

**Problema**: Al validar SAT se sobrescribe el `total` con 0.00

**Solución**: Preservar campos existentes al actualizar `display_info`:
```python
# ANTES
display_info = {
    'sat_status': status,
    'total': 0.0  # ← ERROR
}

# DESPUÉS
display_info = current_display_info.copy()
display_info['sat_status'] = status
# NO tocar 'total' si ya existe
```

#### **Fix #3: Frontend debería tener fallback**

**Archivo**: `frontend/app/invoices/page.tsx`
**Función**: `getSatStatus()` (línea ~698)

**Cambio**:
```typescript
const getSatStatus = (session: InvoiceSession): string => {
  // Prioridad 1: display_info.sat_status
  if (session.display_info?.sat_status &&
      session.display_info.sat_status !== 'desconocido') {
    return session.display_info.sat_status;
  }

  // Prioridad 2: sat_validation_status (fallback)
  if (session.sat_validation_status &&
      session.sat_validation_status !== 'pending') {
    return session.sat_validation_status;
  }

  // Prioridad 3: extracted_data
  const data = extractedData[session.session_id];
  if (data?.sat_status) {
    return data.sat_status;
  }

  return 'desconocido';
};
```

---

### **Fix #4: Agregar validación en API response**

**Archivo**: `modules/invoicing_agent/api.py`
**Endpoint**: `/universal-invoice/sessions/tenant/{tenant_id}`

**Agregar sincronización on-the-fly**:
```python
# Al construir display_info, sincronizar SAT status si está disponible
if session.sat_validation_status and session.sat_validation_status != 'pending':
    if 'sat_status' not in display_info or display_info['sat_status'] == 'desconocido':
        display_info['sat_status'] = session.sat_validation_status
```

---

## 🚫 Prevención de Recurrencia

### **1. Tests Automatizados**

```python
# tests/test_sat_validation.py
def test_sat_validation_updates_display_info():
    """Verify SAT validation updates both sat_validation_status AND display_info.sat_status"""
    session = create_test_session()
    validate_against_sat(session.id)

    updated = get_session(session.id)
    assert updated.sat_validation_status == 'vigente'
    assert updated.display_info['sat_status'] == 'vigente'  # ← Debe coincidir
    assert updated.display_info['total'] > 0  # ← No debe ser $0.00
```

### **2. Database Constraint**

```sql
-- Agregar constraint para validar consistencia
ALTER TABLE sat_invoices
ADD CONSTRAINT sat_status_consistency
CHECK (
    sat_validation_status IS NULL
    OR sat_validation_status = 'pending'
    OR display_info->>'sat_status' = sat_validation_status
);
```

### **3. Monitoring**

```python
# scripts/validate_sat_consistency.py
# Ejecutar diariamente vía cron
SELECT id, sat_validation_status, display_info->>'sat_status' as display_sat
FROM sat_invoices
WHERE sat_validation_status != display_info->>'sat_status'
  AND sat_validation_status IS NOT NULL
  AND sat_validation_status != 'pending';
```

### **4. Documentación**

Agregar a `docs/SAT_VALIDATION.md`:
```markdown
## IMPORTANTE: Sincronización de Estado SAT

Cuando se valida una factura contra SAT, se DEBEN actualizar 2 campos:

1. `sat_validation_status` (varchar) - Campo de base de datos
2. `display_info->>'sat_status'` (jsonb) - Campo que lee el frontend

**Ambos deben tener el mismo valor.**

Si solo actualizas uno, las estadísticas del frontend mostrarán datos incorrectos.
```

---

## 📋 Checklist de Implementación

- [ ] 1. Crear script `sync_sat_status_to_display_info.py`
- [ ] 2. Ejecutar sync para las 31 facturas actuales
- [ ] 3. Actualizar `_validate_sat()` para actualizar display_info
- [ ] 4. Actualizar `getSatStatus()` con fallback
- [ ] 5. Agregar validación en API response
- [ ] 6. Crear tests automatizados
- [ ] 7. Validar que stats muestren datos correctos
- [ ] 8. Agregar constraint de consistencia
- [ ] 9. Crear script de monitoring
- [ ] 10. Actualizar documentación

---

## 🎯 Resultado Esperado

Después de aplicar todos los fixes:

```
RESUMEN DEL PERIODO

27 CFDI vigentes
100% del total

Recibidas: 27 · $159,254.30
Emitidas: 0 · $0.00

Total CFDI: $159,254.30
```

```
IVA acreditable (recibidas): $25,480.68
```

```
PUE: 23 CFDI
PPD: 4 CFDI
```

```
27 vigentes (100% de 27 totales)
Canceladas: 0 · Sustituidas: 0
```
