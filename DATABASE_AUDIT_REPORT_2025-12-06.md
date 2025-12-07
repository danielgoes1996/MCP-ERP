# Auditoría de Bases de Datos - MCP Server
**Fecha**: 2025-12-06
**Objetivo**: Evitar confusiones sobre bases de datos y migraciones

---

## Resumen Ejecutivo

✅ **Estado**: Sistema operando correctamente con PostgreSQL
⚠️  **Problema detectado**: Migración 046 creada innecesariamente
📊 **Total de tablas**: 98 en PostgreSQL, 1 en SQLite activo

---

## 1. Infraestructura de Bases de Datos

### 1.1 Base de Datos Principal: PostgreSQL (Docker)

**Contenedor**: `mcp-postgres`
**Puerto**: 5432
**Database**: `mcp_system`
**Usuario**: `mcp_user`
**Total de tablas**: 98

#### Tablas Bancarias (4 tablas):
- `bank_statements` ✅
- `bank_transactions` ✅
- `bank_reconciliation_splits` ✅
- `banking_institutions` ✅

#### Esquema de `bank_transactions`:
```sql
-- CONFIRMA: Usa esquema de Migration 036
✅ transaction_class VARCHAR
✅ category VARCHAR
✅ subcategory VARCHAR
✅ vendor_normalized VARCHAR
✅ enrichment_confidence NUMERIC
✅ description_clean VARCHAR
```

**Estado de datos**:
- 166 transacciones totales
- 85 transacciones enriquecidas con IA
- 2 bank statements procesados

---

### 1.2 SQLite Activo (Mínimo)

**Ubicación**: `/Users/danielgoes96/Desktop/mcp-server/unified_mcp_system.db`
**Tamaño**: 16KB
**Tablas**: 1 sola tabla

```
ai_correction_memory  ← Solo memoria de correcciones de IA
```

**Estado**: ✅ Correcto (solo para cache/memoria temporal)

---

### 1.3 SQLite Vacío (No usado)

**Ubicación**: `/Users/danielgoes96/Desktop/mcp-server/mcp_database.db`
**Tamaño**: 0 bytes
**Tablas**: Ninguna
**Estado**: ⚠️  Archivo vacío sin uso

---

## 2. Análisis de Migraciones

### Migration 036 ✅ APLICADA (Noviembre 9, 2025)

**Archivo**: `migrations/036_create_bank_statements_postgres.sql`
**Tamaño**: 10KB
**Estado**: ✅ Ejecutada correctamente

**Creó**:
- `bank_statements` (con account_id, tenant_id, company_id)
- `bank_transactions` (con TODOS los campos de enrichment)
- Foreign keys a `payment_accounts`, `tenants`, `companies`
- Índices de performance
- Triggers para `updated_at`
- Vista `bank_statements_summary`

---

### Migration 046 ❌ INNECESARIA (Diciembre 6, 2025)

**Archivo**: `migrations/046_create_bank_statements_simple.sql`
**Tamaño**: 6.9KB
**Estado**: ❌ NUNCA ejecutada (tablas ya existen)

**Problema**:
- Intenta crear las mismas tablas que migration 036
- Simplifica el esquema (quita foreign keys complejos)
- **NO se ejecutó** porque PostgreSQL reporta error: "table already exists"

**Conclusión**: **ELIMINAR migration 046** - es redundante

---

## 3. Uso de Bases de Datos por Módulo

### 3.1 Módulos que SOLO usan PostgreSQL ✅

```python
✅ api/bank_statements_api.py          → PostgreSQL
✅ core/reconciliation/bank/bank_statements_models.py  → PostgreSQL (psycopg2)
✅ api/auth_jwt_api.py                 → PostgreSQL
✅ api/reconciliation_api.py           → PostgreSQL
✅ main.py                             → PostgreSQL
```

### 3.2 Módulos con SQLite LEGACY (backups) ⚠️

```python
⚠️  core/reconciliation/bank/bank_statements_models_sqlite_backup.py  ← BACKUP
⚠️  migrations/test_035_migration.py  ← TEST
⚠️  migrations/apply_035_migration.py  ← MIGRACIÓN LEGACY
```

**Nota**: Estos archivos son backups y NO se usan en producción.

### 3.3 Módulos usando SQLite para Cache/Memoria ✅

```python
✅ core/accounting/account_catalog.py  → SQLite (ai_correction_memory)
✅ core/reconciliation/matching/ai_reconciliation_service.py  → SQLite (cache)
```

**Nota**: Uso correcto de SQLite para datos temporales.

---

## 4. Docker Compose Configuration ✅

```yaml
✅ db:
    image: pgvector/pgvector:pg16
    container_name: mcp-postgres
    environment:
      POSTGRES_DB: mcp_system
      POSTGRES_USER: mcp_user
      POSTGRES_PASSWORD: changeme
    ports:
      - "5432:5432"

✅ api:
    environment:
      USE_POSTGRESQL: "true"
      DATABASE_URL: postgresql://mcp_user:changeme@db:5432/mcp_system
      POSTGRES_DSN: postgresql://mcp_user:changeme@db:5432/mcp_system
```

**Estado**: Configuración correcta ✅

---

## 5. Hallazgos y Problemas

### ❌ Problema 1: Migration 046 Redundante

**Descripción**: Se creó migration 046 pensando que las tablas no existían, pero migration 036 ya las había creado.

**Impacto**: Ninguno (no se ejecutó)

**Solución**: Eliminar `migrations/046_create_bank_statements_simple.sql`

---

### ⚠️  Problema 2: Confusión sobre Ubicación de Datos

**Descripción**: No quedaba claro dónde estaban los 85 registros procesados con IA.

**Causa**: Múltiples bases de datos (PostgreSQL local vs Docker, SQLite legacy)

**Solución**:
- Documentar claramente que TODO está en Docker PostgreSQL
- Eliminar archivos SQLite vacíos o legacy

---

### ✅ Problema 3: Archivos SQLite Vacíos

**Descripción**: `mcp_database.db` existe pero está vacío (0 bytes)

**Solución**: Eliminar archivo

---

## 6. Recomendaciones

### 6.1 Limpieza Inmediata ⚡

```bash
# 1. Eliminar migration redundante
rm migrations/046_create_bank_statements_simple.sql

# 2. Eliminar SQLite vacío
rm mcp_database.db

# 3. Mover backups SQLite a carpeta legacy
mkdir -p _archived_db/legacy_sqlite_backups
mv core/reconciliation/bank/bank_statements_models_sqlite_backup.py \
   _archived_db/legacy_sqlite_backups/
```

### 6.2 Documentación 📝

**Crear**: `DATABASE_ARCHITECTURE.md`

```markdown
# Arquitectura de Bases de Datos

## Base de Datos Principal
- **Tipo**: PostgreSQL 16 con pgvector
- **Ubicación**: Docker container `mcp-postgres`
- **Puerto**: 5432
- **Database**: mcp_system

## Base de Datos Secundaria (Cache)
- **Tipo**: SQLite
- **Ubicación**: unified_mcp_system.db
- **Uso**: Solo para ai_correction_memory (cache temporal)
- **Tamaño**: ~16KB

## Regla General
✅ TODO dato persistente → PostgreSQL
✅ Cache temporal → SQLite (unified_mcp_system.db)
❌ NUNCA crear nuevas conexiones SQLite para datos persistentes
```

### 6.3 Política de Migraciones 📋

**Antes de crear una migración**:

1. ✅ Verificar que la tabla NO existe: `\dt tablename` en psql
2. ✅ Verificar migraciones anteriores: `ls migrations/`
3. ✅ Verificar en Docker PostgreSQL, NO en localhost PostgreSQL
4. ✅ Probar en ambiente de desarrollo antes de aplicar

**Comando de verificación**:
```bash
# Verificar si tabla existe ANTES de crear migración
docker exec mcp-postgres psql -U mcp_user -d mcp_system \
  -c "\dt bank_statements"
```

---

## 7. Estado Final Verificado ✅

### PostgreSQL (Docker)
```
✅ 98 tablas totales
✅ 4 tablas bancarias (bank_statements, bank_transactions, etc.)
✅ 166 transacciones (85 enriquecidas con IA)
✅ 2 bank statements procesados
✅ Esquema completo de migration 036 activo
```

### SQLite
```
✅ unified_mcp_system.db: 1 tabla (ai_correction_memory)
⚠️  mcp_database.db: VACÍO (eliminar)
```

### Código
```
✅ Todos los módulos activos usan PostgreSQL
✅ Solo cache usa SQLite
⚠️  Archivos legacy presentes pero no usados
```

---

## 8. Checklist de Prevención

**Antes de hacer cambios de base de datos**:

- [ ] ¿Verificaste en Docker PostgreSQL (`mcp-postgres`)?
- [ ] ¿Consultaste migraciones existentes?
- [ ] ¿Verificaste que la tabla NO existe ya?
- [ ] ¿Leíste `DATABASE_ARCHITECTURE.md`?
- [ ] ¿Probaste en desarrollo antes de producción?

---

## 9. Comandos Útiles de Auditoría

```bash
# Ver TODAS las tablas en PostgreSQL
docker exec mcp-postgres psql -U mcp_user -d mcp_system \
  -c "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename;"

# Contar registros en una tabla
docker exec mcp-postgres psql -U mcp_user -d mcp_system \
  -c "SELECT COUNT(*) FROM bank_transactions;"

# Ver esquema de una tabla
docker exec mcp-postgres psql -U mcp_user -d mcp_system \
  -c "\d+ bank_transactions"

# Verificar conexiones activas
docker exec mcp-postgres psql -U mcp_user -d mcp_system \
  -c "SELECT datname, usename, application_name FROM pg_stat_activity;"
```

---

## Conclusión

El sistema está operando correctamente con **PostgreSQL como única base de datos principal**. La migración 046 fue innecesaria y puede eliminarse. No hay mezcla de bases de datos en producción, solo confusión por archivos legacy y SQLite vacío.

**Acción inmediata**: Eliminar migration 046 y archivos SQLite vacíos.

---

**Auditor**: Claude Code
**Fecha de auditoría**: 2025-12-06 23:00 CST
**Próxima auditoría recomendada**: Trimestral
