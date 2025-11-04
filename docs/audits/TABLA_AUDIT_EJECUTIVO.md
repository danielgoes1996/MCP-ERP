# 📊 AUDITORÍA DE TABLAS - RESUMEN EJECUTIVO

**Sistema:** MCP Multi-Tenant SaaS
**Fecha:** 2025-10-03
**Total Tablas Analizadas:** 49

---

## 🎯 HALLAZGOS CLAVE

### Clasificación de Tablas

| Estado | Tablas | % | Acción Recomendada |
|--------|--------|---|--------------------|
| **ACTIVE_MULTI_TENANT** | 18 | 37% | ✅ Mantener y monitorear |
| **DEFINED_NO_DATA** | 18 | 37% | ⚠️ Evaluar uso futuro |
| **ACTIVE_NO_TENANT** | 10 | 20% | 🔴 Agregar tenant_id |
| **UNUSED** | 2 | 4% | 🗑️ Eliminar |
| **LEGACY_DATA** | 1 | 2% | 🗑️ Migrar y eliminar |

---

## 📈 TABLAS MÁS ACTIVAS (Top 10)

| Tabla | Filas | Menciones | Queries | Archivos | Multi-Tenant |
|-------|-------|-----------|---------|----------|--------------|
| `missing_transactions_log` | 31,859 | 5 | 3 | 1 | ❌ |
| `automation_logs` | 1,259 | 6 | 3 | 3 | ❌ |
| `validation_issues_log` | 245 | 3 | 1 | 1 | ❌ |
| `bank_movements` | 196 | 104 | 60 | 10 | ✅ |
| `refresh_tokens` | 127 | 3 | 3 | 1 | ❌ |
| `automation_jobs` | 117 | 61 | 26 | 8 | ✅ |
| `pdf_extraction_audit` | 82 | 11 | 6 | 1 | ✅ |
| `bank_movements_backup_20250928` | 75 | 0 | 0 | 0 | ⚠️ LEGACY |
| `error_logs` | 57 | 7 | 5 | 1 | ✅ |
| `banking_institutions` | 30 | 4 | 1 | 2 | ❌ |

---

## 🚨 TABLAS PROBLEMÁTICAS

### 1. UNUSED (0 menciones, 0 datos)

**Acción:** Eliminar de database y migrations

- `analytics_cache` - Nunca usada
- `invoice_match_history` - Nunca usada

**Comando SQL:**
```sql
DROP TABLE analytics_cache;
DROP TABLE invoice_match_history;
```

### 2. LEGACY_DATA (datos sin uso en código)

**Acción:** Backup y eliminar

- `bank_movements_backup_20250928` - 75 registros, tabla de respaldo temporal

**Comando SQL:**
```sql
-- Backup primero
.dump bank_movements_backup_20250928 > backup_20250928.sql

-- Luego eliminar
DROP TABLE bank_movements_backup_20250928;
```

### 3. ACTIVE_NO_TENANT (Usadas pero sin multi-tenancy)

**Acción CRÍTICA:** Agregar `tenant_id` para multi-tenancy seguro

**Tablas que NECESITAN tenant_id:**

| Tabla | Filas | Menciones | Prioridad |
|-------|-------|-----------|-----------|
| `missing_transactions_log` | 31,859 | 5 | 🔴 ALTA |
| `automation_logs` | 1,259 | 6 | 🔴 ALTA |
| `validation_issues_log` | 245 | 3 | 🔴 ALTA |
| `refresh_tokens` | 127 | 3 | 🔴 ALTA |
| `banking_institutions` | 30 | 4 | 🟡 MEDIA |
| `permissions` | 11 | 27 | 🟡 MEDIA |
| `schema_versions` | 9 | 6 | 🟢 BAJA |
| `schema_migrations` | 11 | 2 | 🟢 BAJA |
| `tenants` | 4 | 36 | 🟢 N/A (es la tabla maestra) |
| `access_log` | 3 | 3 | 🟡 MEDIA |

**Migration Recomendada:**
```sql
-- 023_add_tenant_to_logs.sql
ALTER TABLE missing_transactions_log ADD COLUMN tenant_id INTEGER;
ALTER TABLE automation_logs ADD COLUMN tenant_id INTEGER;
ALTER TABLE validation_issues_log ADD COLUMN tenant_id INTEGER;
ALTER TABLE refresh_tokens ADD COLUMN tenant_id INTEGER;
ALTER TABLE banking_institutions ADD COLUMN tenant_id INTEGER;
ALTER TABLE permissions ADD COLUMN tenant_id INTEGER;
ALTER TABLE access_log ADD COLUMN tenant_id INTEGER;

-- Indexes
CREATE INDEX idx_missing_transactions_tenant ON missing_transactions_log(tenant_id);
CREATE INDEX idx_automation_logs_tenant ON automation_logs(tenant_id);
CREATE INDEX idx_validation_issues_tenant ON validation_issues_log(tenant_id);
CREATE INDEX idx_refresh_tokens_tenant ON refresh_tokens(tenant_id);
CREATE INDEX idx_banking_institutions_tenant ON banking_institutions(tenant_id);
CREATE INDEX idx_permissions_tenant ON permissions(tenant_id);
CREATE INDEX idx_access_log_tenant ON access_log(tenant_id);
```

### 4. DEFINED_NO_DATA (18 tablas sin datos)

**Acción:** Evaluar si son necesarias o eliminar

**Tablas con código activo (mantener):**
- `tickets` - 223 menciones, usado en automatización
- `workers` - 87 menciones, sistema de workers
- `automation_screenshots` - 17 menciones, capturas de pantalla
- `automation_sessions` - 20 menciones, sesiones de automatización
- `expense_invoices` - 25 menciones, facturas de gastos
- `system_health` - 29 menciones, monitoreo de salud

**Tablas con poco uso (evaluar eliminar):**
- `bank_reconciliation_feedback` - 1 mención
- `duplicate_detection` - 7 menciones
- `duplicate_detections` - 3 menciones
- `category_learning` - 7 menciones
- `category_learning_metrics` - 6 menciones
- `category_prediction_history` - 4 menciones
- `expense_attachments` - 1 mención
- `expense_ml_features` - 4 menciones
- `expense_tag_relations` - 11 menciones
- `gpt_usage_events` - 7 menciones (pero importante para analytics)
- `user_preferences` - 17 menciones
- `user_sessions` - 3 menciones

---

## 💡 RECOMENDACIONES PRIORITARIAS

### 🔴 CRÍTICO (Sprint 1)

1. **Agregar tenant_id a logs activos**
   - `missing_transactions_log`, `automation_logs`, `validation_issues_log`
   - **Riesgo:** Cross-tenant data leaks en logs
   - **Esfuerzo:** 1-2 días
   - **Impacto:** Alto

2. **Eliminar tablas UNUSED**
   - `analytics_cache`, `invoice_match_history`
   - **Riesgo:** Ninguno
   - **Esfuerzo:** 30 minutos
   - **Impacto:** Limpieza

3. **Backup y eliminar LEGACY**
   - `bank_movements_backup_20250928`
   - **Riesgo:** Bajo (es backup temporal)
   - **Esfuerzo:** 30 minutos
   - **Impacto:** Limpieza

### 🟡 IMPORTANTE (Sprint 2)

4. **Agregar tenant_id a refresh_tokens**
   - Necesario para seguridad multi-tenant
   - **Esfuerzo:** 1 día
   - **Impacto:** Alto

5. **Evaluar tablas DEFINED_NO_DATA**
   - Decidir cuáles mantener vs eliminar
   - **Esfuerzo:** 2-3 días (análisis + decisión)
   - **Impacto:** Medio

6. **Agregar tenant_id a banking_institutions**
   - Permitir configuraciones por tenant
   - **Esfuerzo:** 1 día
   - **Impacto:** Medio

### 🟢 MEJORA CONTINUA (Sprint 3+)

7. **Implementar uso de tablas sin datos**
   - `tickets`, `workers`, `automation_screenshots`
   - Estas están definidas pero nunca pobladas
   - **Esfuerzo:** Variable según módulo
   - **Impacto:** Completitud del sistema

8. **Optimizar índices en tablas grandes**
   - `missing_transactions_log` (31K rows)
   - `automation_logs` (1.2K rows)
   - **Esfuerzo:** 1 día
   - **Impacto:** Performance

---

## 📊 ANÁLISIS DE DATOS REALES

### Distribución por Tenant (Tablas con datos)

**Tenant 1:** 244 registros en 10 tablas
**Tenant 3:** 183 registros en 7 tablas
**Tenant 4:** 107 registros en 4 tablas
**NULL/Sin tenant:** 34,423 registros en 10 tablas ⚠️

**Problema:** 34K registros sin tenant_id asignado (principalmente logs)

### Rangos de Fechas

**Tablas más antiguas:**
- `automation_jobs`: 2025-09-25
- `companies`: 2025-09-25
- `users`: 2025-09-25

**Tablas más recientes:**
- `employee_advances`: 2025-10-03
- `bank_reconciliation_splits`: 2025-10-03
- `users`: 2025-10-03 (última modificación)

**Observación:** Sistema activamente usado (datos de últimas 2 semanas)

---

## 🎯 IMPACTO ESTIMADO

### Si se implementan todas las recomendaciones:

**Beneficios:**
- ✅ 100% de tablas activas con multi-tenancy
- ✅ 3 tablas legacy eliminadas (-6% database)
- ✅ 34K+ registros migrados a tenants correctos
- ✅ Mejor performance (índices en logs)
- ✅ Seguridad mejorada (tenant isolation completo)

**Esfuerzo Total:** 5-7 días desarrollo

**Riesgo:** Bajo (principalmente adiciones, no modificaciones)

---

## 📝 PLAN DE ACCIÓN

### Semana 1
- [ ] Eliminar `analytics_cache` y `invoice_match_history`
- [ ] Backup y eliminar `bank_movements_backup_20250928`
- [ ] Crear migration 023 para tenant_id en logs
- [ ] Ejecutar migration y poblar tenant_id

### Semana 2
- [ ] Agregar tenant_id a `refresh_tokens` y `banking_institutions`
- [ ] Revisar y decidir sobre 18 tablas DEFINED_NO_DATA
- [ ] Crear migrations para tablas aprobadas

### Semana 3+
- [ ] Implementar funcionalidad para tablas sin datos (tickets, workers)
- [ ] Optimizar índices en tablas grandes
- [ ] Documentar decisiones en README

---

## 🔍 CONSULTAS SQL ÚTILES

### Ver distribución de datos por tenant
```sql
SELECT
  'expense_records' as tabla,
  tenant_id,
  COUNT(*) as registros
FROM expense_records
GROUP BY tenant_id
UNION ALL
SELECT
  'bank_movements',
  tenant_id,
  COUNT(*)
FROM bank_movements
GROUP BY tenant_id;
```

### Encontrar registros sin tenant
```sql
SELECT
  'automation_logs' as tabla,
  COUNT(*) as sin_tenant
FROM automation_logs
WHERE tenant_id IS NULL
UNION ALL
SELECT
  'error_logs',
  COUNT(*)
FROM error_logs
WHERE tenant_id IS NULL;
```

### Ver tablas ordenadas por tamaño
```sql
SELECT
  name as tabla,
  (SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=m.name) as filas
FROM sqlite_master m
WHERE type='table' AND name NOT LIKE 'sqlite_%'
ORDER BY filas DESC;
```

---

**Conclusión:** Sistema bien estructurado con **37% de tablas multi-tenant activas**. Principales oportunidades: completar multi-tenancy en logs (20% de tablas) y limpiar legacy/unused (6% de tablas).

**Próximo paso:** Implementar migration 023 para tenant_id en logs críticos.
