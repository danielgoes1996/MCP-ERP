# 📋 SPRINT 2 - ANÁLISIS TABLAS DEFINED_NO_DATA

**Fecha:** 2025-10-03
**Sprint:** Database Optimization - Tablas sin datos
**Prioridad:** 🟡 MEDIA
**Estado:** 🔄 EN PROGRESO

---

## 🎯 OBJETIVO

Analizar 18 tablas DEFINED_NO_DATA (definidas pero con 0 registros) para:
1. Identificar cuáles mantener (KEEP)
2. Identificar cuáles requieren evaluación (EVALUATE)
3. Identificar cuáles eliminar (DELETE)

---

## 📊 RESUMEN EJECUTIVO

**Total tablas analizadas:** 18
- ✅ **KEEP:** 3 tablas (17%) - Alto uso en código
- ⚠️ **EVALUATE:** 14 tablas (78%) - Poco uso, requiere decisión
- 🗑️ **DELETE:** 1 tabla (5%) - Sin uso significativo

---

## ✅ CATEGORÍA 1: KEEP (3 tablas)

Tablas con alto uso en código que deben mantenerse para funcionalidad futura.

### 1.1 `tickets` 🎫
- **Estado:** KEEP - Alto uso en código (363 menciones)
- **Filas actuales:** 0
- **Columnas:** 10 (incluye tenant_id ✅)
- **Uso en código:**
  - 2 INSERTs
  - 11 SELECTs
  - 35 archivos Python
  - 2 archivos de modelos
  - 6 servicios
- **Prioridad:** 🔴 ALTA
- **Decisión:** **MANTENER** - Sistema de tickets está implementado pero sin datos reales
- **Acción recomendada:** Implementar funcionalidad de tickets en Sprint 3

**Archivos clave:**
- `core/ticket_analyzer.py`
- `modules/invoicing_agent/ticket_processor.py`
- `modules/invoicing_agent/models.py`

---

### 1.2 `workers` 👷
- **Estado:** KEEP - Alto uso en código (87 menciones)
- **Filas actuales:** 0
- **Columnas:** 13 (incluye tenant_id ✅)
- **Uso en código:**
  - 0 INSERTs (⚠️ no se está poblando)
  - 0 SELECTs directos
  - 8 archivos Python
  - 1 servicio
- **Prioridad:** 🟡 MEDIA
- **Decisión:** **MANTENER** - Sistema de workers/queue está definido
- **Acción recomendada:** Implementar sistema de workers en Sprint 4 o deprecar referencias

**Archivos clave:**
- `core/worker_system.py`
- `core/batch_performance_optimizer.py`
- `core/idempotent_workers.py`

**Nota:** Alto uso en código pero 0 queries sugiere código dead code o funcionalidad no implementada.

---

### 1.3 `expense_invoices` 💰
- **Estado:** KEEP - Uso moderado con queries activas
- **Filas actuales:** 0
- **Columnas:** 36 (incluye tenant_id ✅)
- **Uso en código:**
  - 4 INSERTs ✅
  - 7 SELECTs ✅
  - 3 archivos Python
- **Prioridad:** 🔴 ALTA
- **Decisión:** **MANTENER** - Tabla activa con queries pero sin datos aún
- **Acción recomendada:** Verificar por qué no se están guardando facturas

**Archivos clave:**
- `core/unified_db_adapter.py`
- `core/internal_db.py`

**⚠️ ALERTA:** Esta tabla tiene queries activas pero 0 registros. Posible bug en el flujo de inserción.

---

## ⚠️ CATEGORÍA 2: EVALUATE (14 tablas)

Tablas con bajo uso que requieren decisión caso por caso.

### 2.1 `automation_screenshots` 📸
- **Filas:** 0
- **Columnas:** 7 (incluye tenant_id ✅)
- **Uso:** 17 menciones, 1 INSERT, 3 SELECTs
- **Archivos:** 10 archivos Python (automation engines)
- **Decisión recomendada:** **MANTENER** - Funcionalidad útil para debugging RPA
- **Acción:** Verificar si automation engines están guardando screenshots

**Archivos clave:**
- `core/playwright_executor.py`
- `modules/invoicing_agent/robust_automation_engine.py`
- `modules/invoicing_agent/automation_persistence.py`

**Nota:** Screenshots visibles en `/static/automation_screenshots/` sugieren que se guardan en disco pero no en DB.

---

### 2.2 `automation_sessions` 🔄
- **Filas:** 0
- **Columnas:** 10 (incluye tenant_id ✅)
- **Uso:** 20 menciones, 0 INSERTs, 0 SELECTs
- **Archivos:** 5 archivos Python
- **Decisión recomendada:** **MANTENER** - Sesiones de automation para recovery
- **Acción:** Implementar persistencia de sesiones en automation engines

**Archivos clave:**
- `core/rpa_automation_engine_system.py`
- `core/robust_automation_engine_system.py`

---

### 2.3 `system_health` 🏥
- **Filas:** 0
- **Columnas:** 8 (NO tiene tenant_id ❌)
- **Uso:** 29 menciones, 0 INSERTs, 0 SELECTs
- **Archivos:** 7 archivos Python
- **Decisión recomendada:** **MANTENER** - Monitoreo de salud del sistema
- **Acción:** Implementar endpoint `/health` que popule esta tabla

**Archivos clave:**
- `api/robust_automation_engine_api.py`
- `modules/invoicing_agent/services/orchestrator.py`

**⚠️ FALTA:** Agregar `tenant_id` si se decide implementar (aunque salud del sistema es global)

---

### 2.4 `bank_reconciliation_feedback` 🏦
- **Filas:** 0
- **Columnas:** 11 (incluye tenant_id ✅)
- **Uso:** 1 mención, 1 INSERT, 0 SELECTs
- **Archivos:** 1 archivo (`core/unified_db_adapter.py`)
- **Decisión recomendada:** **EVALUAR EN SPRINT 3** - Machine learning feedback loop
- **Acción:** Decidir si implementar o eliminar

---

### 2.5 `duplicate_detection` & `duplicate_detections` 🔁
- **Filas:** 0 (ambas)
- **Columnas:** 9 y 14 respectivamente
- **tenant_id:** NO en `duplicate_detection`, SÍ en `duplicate_detections`
- **Uso:** Muy bajo (7 y 3 menciones)
- **Archivos:** Solo `core/unified_db_adapter.py`
- **Decisión recomendada:** **CONSOLIDAR** - Dos tablas para lo mismo
- **Acción:** Eliminar `duplicate_detection`, mantener `duplicate_detections`

**Nota:** Existe tabla `optimized_duplicate_detector` que probablemente reemplaza estas.

---

### 2.6 Tablas de Category Learning (3 tablas)

#### `category_learning`
- **Uso:** 7 menciones, 1 INSERT, 4 SELECTs
- **tenant_id:** NO ❌
- **Archivos:** `core/category_learning_system.py`

#### `category_learning_metrics`
- **Uso:** 6 menciones, 1 INSERT, 4 SELECTs
- **tenant_id:** SÍ ✅
- **Archivos:** `core/category_learning_system.py`

#### `category_prediction_history`
- **Uso:** 4 menciones, 1 INSERT, 2 SELECTs
- **tenant_id:** SÍ ✅
- **Archivos:** `core/unified_db_adapter.py`

**Decisión recomendada:** **MANTENER** las 3 tablas pero:
1. Agregar `tenant_id` a `category_learning`
2. Implementar funcionalidad ML de categorización
3. Sprint 3: Activar sistema de aprendizaje

---

### 2.7 `expense_ml_features` 🤖
- **Filas:** 0
- **Columnas:** 9 (incluye tenant_id ✅)
- **Uso:** 4 menciones, 0 INSERTs, 1 SELECT
- **Archivos:** `core/unified_db_adapter.py`
- **Decisión recomendada:** **MANTENER** - Feature extraction para ML
- **Acción:** Implementar extracción de features en Sprint 4

---

### 2.8 `expense_tag_relations` 🏷️
- **Filas:** 0
- **Columnas:** 4 (incluye tenant_id ✅)
- **Uso:** 11 menciones, 1 INSERT, 8 SELECTs
- **Archivos:** `core/unified_db_adapter.py`, `core/internal_db.py`
- **Decisión recomendada:** **MANTENER** - Relación many-to-many expenses-tags
- **Acción:** Verificar por qué no se está poblando (existe `expense_tags` con 8 filas)

**⚠️ ALERTA:** 8 SELECTs pero 0 filas sugiere bug en inserción.

---

### 2.9 `gpt_usage_events` 📊
- **Filas:** 0
- **Columnas:** 13 (incluye tenant_id ✅)
- **Uso:** 7 menciones, 2 INSERTs, 3 SELECTs
- **Archivos:** `core/unified_db_adapter.py`, `core/cost_analytics.py`
- **Decisión recomendada:** **MANTENER** - Analytics de costos LLM
- **Acción:** Activar logging de usage en `cost_analytics.py`

---

### 2.10 `user_preferences` ⚙️
- **Filas:** 0
- **Columnas:** 11 (incluye tenant_id ✅)
- **Uso:** 17 menciones, 0 INSERTs, 0 SELECTs
- **Archivos:** 5 archivos Python
- **Decisión recomendada:** **MANTENER** - Preferencias de usuario
- **Acción:** Implementar funcionalidad en Sprint 3

**Archivos clave:**
- `core/category_learning_system.py`
- `core/expense_completion_system.py`
- `api/expense_completion_api.py`

---

### 2.11 `user_sessions` 🔐
- **Filas:** 0
- **Columnas:** 10 (incluye tenant_id ✅)
- **Uso:** 3 menciones, 1 INSERT, 1 SELECT
- **Archivos:** `core/auth_jwt.py`, `api/auth_jwt_api.py`
- **Decisión recomendada:** **EVALUAR** - ¿Necesario si ya existe `refresh_tokens`?
- **Acción:** Decidir si consolidar con `refresh_tokens` o implementar

---

## 🗑️ CATEGORÍA 3: DELETE (1 tabla)

### 3.1 `expense_attachments` 📎
- **Estado:** DELETE - Sin schema y sin uso
- **Filas:** 0
- **Columnas:** 9 (NO tiene tenant_id ❌)
- **Uso:** 1 mención (solo en `core/api_models.py`)
- **INSERTs/SELECTs:** 0
- **Prioridad:** 🟢 BAJA
- **Decisión:** **ELIMINAR** - Funcionalidad no implementada
- **Justificación:**
  - Solo 1 mención en código (modelo Pydantic)
  - 0 queries reales
  - No tiene tenant_id
  - Probablemente reemplazada por `expense_invoices`

**Acción inmediata:**
```sql
DROP TABLE expense_attachments;
```

---

## 📋 PLAN DE ACCIÓN - SPRINT 2

### Fase 1: Limpieza Inmediata (1 día)

#### ✅ Acción 1.1: Eliminar tabla obsoleta
```sql
-- Migration 024_cleanup_unused_tables.sql
DROP TABLE IF EXISTS expense_attachments;
```

#### ✅ Acción 1.2: Consolidar tablas duplicadas
```sql
-- Eliminar duplicate_detection (mantener duplicate_detections)
DROP TABLE IF EXISTS duplicate_detection;
```

**Resultado esperado:** -2 tablas (-4%)

---

### Fase 2: Correcciones de Schema (1 día)

#### ✅ Acción 2.1: Agregar tenant_id faltantes
```sql
-- Migration 025_add_missing_tenant_id.sql

-- category_learning
ALTER TABLE category_learning ADD COLUMN tenant_id INTEGER;
CREATE INDEX idx_category_learning_tenant ON category_learning(tenant_id);

-- system_health (opcional, evaluar si es global o por tenant)
-- ALTER TABLE system_health ADD COLUMN tenant_id INTEGER;
```

#### ✅ Acción 2.2: Poblar tenant_id en registros existentes
```sql
-- Aunque estas tablas tienen 0 filas, el código de migración
-- debe estar listo para cuando se inserten datos
```

---

### Fase 3: Activar Funcionalidades (2-3 días)

#### 🔴 Alta Prioridad

1. **expense_invoices** - Investigar por qué no se guardan facturas
   - Revisar flujo en `core/unified_db_adapter.py`
   - Verificar que automation engines llamen a INSERT
   - Testing: Procesar 1 factura y verificar inserción

2. **expense_tag_relations** - Activar relación expenses-tags
   - Revisar flujo en `core/internal_db.py`
   - Verificar que al crear expense con tags se inserte relación
   - Testing: Crear expense con 2 tags y verificar tabla

3. **automation_screenshots** - Persistir screenshots en DB
   - Modificar `core/playwright_executor.py`
   - Guardar ruta del screenshot en DB además de disco
   - Testing: Ejecutar automation y verificar inserción

#### 🟡 Media Prioridad

4. **gpt_usage_events** - Activar analytics de costos
   - Modificar `core/cost_analytics.py`
   - Insertar evento cada vez que se llame a LLM
   - Testing: Ejecutar 10 llamadas LLM y verificar 10 registros

5. **user_preferences** - Implementar preferencias de usuario
   - Crear endpoint POST `/api/user/preferences`
   - Guardar preferencias al actualizar
   - Testing: Actualizar preferencias y verificar inserción

---

### Fase 4: Decisiones Pendientes (Sprint 3)

Tablas que requieren decisión de producto/negocio:

1. **tickets** - ¿Implementar sistema de tickets en Q1 2025?
2. **workers** - ¿Implementar queue system o usar Celery/Redis?
3. **automation_sessions** - ¿Implementar recovery de sesiones?
4. **system_health** - ¿Implementar dashboard de salud?
5. **user_sessions** - ¿Consolidar con refresh_tokens o implementar separado?

---

## 📊 MÉTRICAS ESPERADAS POST-SPRINT 2

### Antes
- **Tablas totales:** 46
- **Tablas DEFINED_NO_DATA:** 18 (39%)
- **Tablas sin tenant_id:** 5
- **Tablas con queries activas pero 0 filas:** 11

### Después (Fase 1-2)
- **Tablas totales:** 44 (-2 tablas eliminadas)
- **Tablas DEFINED_NO_DATA:** 16 (-2)
- **Tablas sin tenant_id:** 3 (-2, agregado a category_learning y system_health)
- **Tablas con queries activas pero 0 filas:** 11 (sin cambio aún)

### Después (Fase 3)
- **Tablas con queries activas pero 0 filas:** 6 (-5 activadas)
- **Tablas con datos reales:** +5 tablas pobladas
- **Coverage funcional:** +15% (funcionalidades activadas)

---

## 🎯 PRÓXIMOS PASOS INMEDIATOS

### Sprint 2A: Limpieza (Esta semana)
1. ✅ Ejecutar Migration 024 (eliminar expense_attachments, duplicate_detection)
2. ✅ Ejecutar Migration 025 (agregar tenant_id faltantes)
3. ✅ Verificar 0 breaking changes en código
4. ✅ Actualizar código para eliminar referencias a tablas eliminadas

### Sprint 2B: Activación (Próxima semana)
5. 🔴 Investigar bug en expense_invoices (queries activas, 0 filas)
6. 🔴 Activar expense_tag_relations
7. 🟡 Activar automation_screenshots
8. 🟡 Activar gpt_usage_events

### Sprint 3: Roadmap Features
9. 📅 Decidir roadmap para tickets, workers, automation_sessions
10. 📅 Implementar funcionalidades según decisión de producto

---

## 📝 ARCHIVOS GENERADOS

- ✅ `defined_no_data_analysis.json` - Análisis completo en JSON
- ✅ `SPRINT_2_DEFINED_NO_DATA_REPORT.md` - Este reporte
- 🔄 `migrations/024_cleanup_unused_tables.sql` - Por crear
- 🔄 `migrations/025_add_missing_tenant_id.sql` - Por crear

---

## ⚠️ ALERTAS Y WARNINGS

### 🔴 CRÍTICO
1. **expense_invoices** tiene 4 INSERTs y 7 SELECTs pero 0 filas
   - Posible bug en flujo de inserción
   - Requiere investigación inmediata

2. **expense_tag_relations** tiene 8 SELECTs pero 0 filas
   - Existe tabla `expense_tags` con 8 registros
   - Relación many-to-many no se está creando

### 🟡 ADVERTENCIA
3. **workers** tiene 87 menciones pero 0 queries
   - Posible dead code o funcionalidad no implementada
   - Evaluar deprecar o implementar

4. **automation_screenshots** guarda en disco (`/static/automation_screenshots/`) pero no en DB
   - Inconsistencia entre persistencia en disco y DB

---

**Sprint 2: EN PROGRESO** 🔄

**Esfuerzo Estimado Total:** 4-5 días
- Fase 1 (Limpieza): 1 día
- Fase 2 (Schema): 1 día
- Fase 3 (Activación): 2-3 días

**Complejidad:** Media-Alta
**Riesgo:** Bajo-Medio (requiere testing exhaustivo)
**Impacto:** Alto (activación de funcionalidades + limpieza)
