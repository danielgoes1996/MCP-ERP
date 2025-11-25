# 📋 GUÍA DE MIGRACIÓN: Renombrado de Tablas

**Fecha**: 2025-11-15
**Versión**: v1.5.0
**Autor**: Claude Code + Daniel Goes

---

## 🎯 Objetivo

Renombrar tablas para reflejar claramente su propósito:

```
sat_invoices  →  sat_invoices      (Facturas SAT/CFDIs)
expenses                   →  manual_expenses    (Gastos manuales voz/foto/texto)
expense_invoices           →  DEPRECADA          (Legacy sin uso)
```

---

## 📊 Estado Actual

| Tabla Actual | Registros | Estado | Nueva Tabla |
|--------------|-----------|--------|-------------|
| `sat_invoices` | 482 | ✅ Activa | `sat_invoices` |
| `expenses` | 0 | ⚠️ Pendiente activar | `manual_expenses` |
| `expense_invoices` | 0 | ❌ Legacy deprecada | [ELIMINAR] |

---

## 🚀 Pasos de Migración

### **Paso 1: Backup de Base de Datos**

```bash
# Crear backup completo de PostgreSQL
pg_dump -h 127.0.0.1 -p 5433 -U mcp_user -d mcp_system > backup_pre_rename_$(date +%Y%m%d_%H%M%S).sql
```

### **Paso 2: Ejecutar Preview del Script Python**

```bash
# Ver qué archivos serán modificados (DRY RUN)
python3 scripts/migration/update_code_references_table_rename.py --dry-run
```

**Resultado esperado**:
- Archivos procesados: ~1700
- Archivos modificados: ~136
- Total de reemplazos: ~476

### **Paso 3: Aplicar la Migración SQL**

```bash
# Opción A: Usando psql
psql postgresql://mcp_user:changeme@127.0.0.1:5433/mcp_system \
  -f migrations/2025_11_15_rename_tables_sat_invoices_manual_expenses.sql

# Opción B: Usando Docker (si aplica)
docker exec -i mcp-postgres psql -U mcp_user -d mcp_system \
  < migrations/2025_11_15_rename_tables_sat_invoices_manual_expenses.sql
```

**Verificación**:
```sql
-- Verificar que las tablas fueron renombradas
SELECT tablename FROM pg_tables
WHERE schemaname = 'public'
AND tablename IN ('sat_invoices', 'manual_expenses', 'expense_invoices')
ORDER BY tablename;

-- Debe mostrar:
-- expense_invoices (legacy)
-- manual_expenses
-- sat_invoices
```

### **Paso 4: Actualizar Referencias en Código**

```bash
# Aplicar cambios en archivos (EJECUTAR CON CUIDADO)
python3 scripts/migration/update_code_references_table_rename.py --apply
```

**IMPORTANTE**: Este script modificará 136 archivos. Revisar cambios con:
```bash
git diff
```

### **Paso 5: Verificar que Todo Funciona**

```bash
# 1. Reiniciar backend
lsof -ti:8001 | xargs kill -9 2>/dev/null
python3 main.py &

# 2. Verificar health check
curl -s http://localhost:8001/health | python3 -m json.tool

# 3. Probar endpoint de facturas
curl -s "http://localhost:8001/universal-invoice/sessions/company/carreta_verde?limit=5" \
  | python3 -m json.tool
```

### **Paso 6: Tests**

```bash
# Ejecutar tests (si existen)
pytest tests/ -v

# Verificar que las facturas se muestran correctamente
# Acceder a: http://localhost:3000/invoices
```

---

## ✅ Verificación Post-Migración

### **1. Verificar Estructura de Base de Datos**

```sql
-- Contar registros
SELECT 'sat_invoices' as tabla, COUNT(*) as total FROM sat_invoices
UNION ALL
SELECT 'manual_expenses' as tabla, COUNT(*) as total FROM manual_expenses
UNION ALL
SELECT 'expense_invoices (legacy)' as tabla, COUNT(*) as total FROM expense_invoices;

-- Verificar índices
SELECT tablename, indexname
FROM pg_indexes
WHERE tablename IN ('sat_invoices', 'manual_expenses')
ORDER BY tablename, indexname;

-- Verificar foreign keys
SELECT
    conname AS constraint_name,
    conrelid::regclass AS table_name,
    confrelid::regclass AS referenced_table
FROM pg_constraint
WHERE contype = 'f'
AND (conrelid::regclass::text IN ('sat_invoices', 'manual_expenses')
     OR confrelid::regclass::text IN ('sat_invoices', 'manual_expenses'))
ORDER BY table_name, constraint_name;
```

### **2. Verificar Vistas de Compatibilidad**

```sql
-- Debe existir vista de compatibilidad temporal
SELECT * FROM sat_invoices LIMIT 1;  -- Debe funcionar (vista)
SELECT * FROM manual_expenses LIMIT 1;  -- Debe funcionar (vista)
```

---

## 🔄 Rollback (Si es necesario)

```bash
# 1. Restaurar backup
psql postgresql://mcp_user:changeme@127.0.0.1:5433/mcp_system < backup_pre_rename_XXXXXXXX_XXXXXX.sql

# 2. Revertir cambios en código
git checkout .

# 3. Reiniciar servidor
python3 main.py &
```

---

## 📝 Cambios Específicos

### **Archivos Críticos Modificados** (ejemplos)

#### **Backend Python**
- `core/expenses/invoices/universal_invoice_engine_system.py`
- `api/universal_invoice_engine_api.py`
- `core/sat/sat_validation_service.py`
- `core/shared/classification_utils.py`

#### **Migraciones SQL**
- `migrations/*.sql` (todas las que referencien las tablas antiguas)

#### **Documentación**
- Todos los `.md` que mencionen `sat_invoices`

---

## ⚠️ Notas Importantes

1. **Vistas de Compatibilidad**: Se crean vistas temporales `sat_invoices` y `expenses` que apuntan a las tablas nuevas. Esto permite compatibilidad con código legacy.

2. **Deprecación de expense_invoices**: La tabla `expense_invoices` NO se elimina, solo se marca como DEPRECADA. Se eliminará en futuras migraciones.

3. **Sin Pérdida de Datos**: Esta migración es 100% segura:
   - Solo renombra tablas
   - Actualiza índices y foreign keys
   - NO elimina ni modifica datos

4. **Tiempo de Ejecución**: ~2-5 minutos total (la mayoría en actualizar archivos de código).

---

## 📊 Resumen de Impacto

```
┌─────────────────────────────────────────────────┐
│  ANTES                                          │
├─────────────────────────────────────────────────┤
│  sat_invoices (482 registros)     │
│  expenses (0 registros)                         │
│  expense_invoices (0 registros, legacy)         │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│  DESPUÉS                                        │
├─────────────────────────────────────────────────┤
│  sat_invoices (482 registros) ✅                │
│  manual_expenses (0 registros) ✅               │
│  expense_invoices (0 registros, DEPRECADA) ⚠️  │
│                                                 │
│  Vistas de compatibilidad:                     │
│  - sat_invoices → sat_invoices   │
│  - expenses → manual_expenses                   │
└─────────────────────────────────────────────────┘
```

---

## 🎉 Beneficios

1. **Nomenclatura Clara**: Los nombres reflejan el propósito real de cada tabla
2. **Facilita Onboarding**: Nuevos desarrolladores entienden inmediatamente qué hace cada tabla
3. **Evita Confusión**: Ya no hay ambigüedad entre "sessions" vs "invoices"
4. **Código más Limpio**: Referencias claras en toda la codebase
5. **Mejor Documentación**: La arquitectura es autoexplicativa

---

## 📞 Soporte

Si encuentras problemas durante la migración:

1. Revisar logs de PostgreSQL: `docker logs mcp-postgres`
2. Verificar errores del backend: `tail -f logs/app.log`
3. Consultar este documento

---

**✅ Migración Completada** 🚀
