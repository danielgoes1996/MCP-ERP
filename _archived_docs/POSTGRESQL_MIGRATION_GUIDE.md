# 🐘 PostgreSQL Migration Guide

## 📋 Índice

1. [Descripción General](#descripción-general)
2. [Pre-requisitos](#pre-requisitos)
3. [Proceso de Migración](#proceso-de-migración)
4. [Validación](#validación)
5. [Actualizar Configuración](#actualizar-configuración)
6. [Rollback](#rollback)
7. [Troubleshooting](#troubleshooting)
8. [FAQ](#faq)

---

## 🎯 Descripción General

Esta guía cubre la migración completa de tu base de datos desde **SQLite** a **PostgreSQL**, incluyendo:

- ✅ Extracción automática del schema
- ✅ Conversión de tipos SQLite → PostgreSQL
- ✅ Migración de todos los datos (51 tablas)
- ✅ Migración de índices (145 índices)
- ✅ Migración de vistas (2 vistas)
- ✅ Validación de integridad
- ✅ Backup automático
- ✅ Procedimiento de rollback

**Tiempo estimado**: 5-10 minutos
**Riesgo**: Bajo (se crea backup automático)

---

## 📦 Pre-requisitos

### 1. Docker Stack Corriendo

```bash
# Iniciar PostgreSQL + API
./docker-start.sh

# Verificar que PostgreSQL está listo
docker-compose ps
# mcp-postgres debe estar "Up (healthy)"
```

### 2. Backup Manual (Opcional pero Recomendado)

```bash
# Crear backup adicional
cp unified_mcp_system.db unified_mcp_system.db.pre_migration_$(date +%Y%m%d)
```

### 3. Dependencias Python

```bash
# Instalar psycopg2 si no está instalado
pip install psycopg2-binary
```

---

## 🚀 Proceso de Migración

### Opción 1: Migración Automática (Recomendado)

```bash
# Ejecutar script maestro
./scripts/migration/run_migration.sh
```

Este script ejecuta automáticamente:
1. ✅ Verificación de conexiones
2. ✅ Backup de SQLite
3. ✅ Extracción de schema
4. ✅ Conversión a PostgreSQL
5. ✅ Creación de schema en PostgreSQL
6. ✅ Migración de datos
7. ✅ Validación de integridad

**Salida Esperada:**

```
============================================
🐘 SQLite → PostgreSQL Migration
============================================

✅ Found SQLite database: unified_mcp_system.db
✅ PostgreSQL connection successful
✅ Backup created: backups/sqlite_backup_20250104_120000.db

============================================
📋 Step 1: Extract SQLite Schema
============================================
📊 Found 51 tables
  ✅ companies: 2 rows, 19 columns
  ✅ users: 2 rows, 31 columns
  ...
✅ Schema saved

============================================
🔄 Step 2: Convert to PostgreSQL Schema
============================================
✅ Converted: 51 tables, 145 indexes, 2 views

============================================
🏗️  Step 3: Create PostgreSQL Schema
============================================
✅ PostgreSQL schema created successfully

============================================
📊 Step 4: Migrate Data
============================================
📦 Migrating table: companies
   ✅ Migrated: 2 rows
...
✅ Migration Complete!
   Tables migrated: 51
   Rows migrated: 1,309

============================================
✔️  Step 5: Validate Migration
============================================
✅ companies              -      2 rows migrated
✅ users                  -      2 rows migrated
...
✅ Validation PASSED!

============================================
✅ Migration Complete!
============================================
```

### Opción 2: Migración Manual (Paso a Paso)

```bash
# 1. Extraer schema de SQLite
python3 scripts/migration/extract_sqlite_schema.py \
    unified_mcp_system.db \
    scripts/migration/sqlite_schema.json

# 2. Convertir a PostgreSQL
python3 scripts/migration/convert_to_postgres.py \
    scripts/migration/sqlite_schema.json \
    scripts/migration/postgres_schema.sql

# 3. Crear schema en PostgreSQL
psql -h localhost -p 5432 -U mcp_user -d mcp_system \
    -f scripts/migration/postgres_schema.sql

# 4. Migrar datos
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_DB=mcp_system
export POSTGRES_USER=mcp_user
export POSTGRES_PASSWORD=changeme

python3 scripts/migration/migrate_data.py

# 5. Validar
python3 scripts/migration/validate_migration.py
```

---

## ✅ Validación

### Validación Automática

El script de migración incluye validación automática. Verifica:

- ✅ Número de tablas migradas
- ✅ Número de filas por tabla
- ✅ Integridad de datos básica

### Validación Manual

```bash
# Contar registros en SQLite
sqlite3 unified_mcp_system.db "SELECT COUNT(*) FROM users"

# Contar registros en PostgreSQL
psql -h localhost -U mcp_user -d mcp_system -c "SELECT COUNT(*) FROM users"
```

### Queries de Verificación

```sql
-- En PostgreSQL

-- Verificar tablas
SELECT table_name,
       (SELECT COUNT(*) FROM information_schema.columns
        WHERE table_name = t.table_name) as column_count
FROM information_schema.tables t
WHERE table_schema = 'public'
ORDER BY table_name;

-- Verificar índices
SELECT tablename, indexname
FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY tablename;

-- Verificar foreign keys
SELECT conname as constraint_name,
       conrelid::regclass as table_name,
       confrelid::regclass as referenced_table
FROM pg_constraint
WHERE contype = 'f';
```

---

## ⚙️ Actualizar Configuración

### 1. Actualizar .env

```bash
# Editar .env
nano .env
```

**Cambiar de:**
```bash
DATABASE_URL=sqlite:///./unified_mcp_system.db
```

**A:**
```bash
DATABASE_URL=postgresql://mcp_user:changeme@localhost:5432/mcp_system
```

### 2. Configuración para Docker

Si usas Docker, la configuración ya está lista en `docker-compose.yml`:

```yaml
environment:
  DATABASE_URL: postgresql://mcp_user:changeme@db:5432/mcp_system
```

### 3. Reiniciar Aplicación

```bash
# Si usas Docker
./docker-stop.sh
./docker-start.sh

# Si corres localmente
# Ctrl+C para detener
uvicorn main:app --reload
```

### 4. Verificar Conexión

```bash
# Probar endpoint
curl http://localhost:8000/health

# Debería retornar:
# {"status": "healthy", "database": "postgresql"}
```

---

## 🔄 Rollback

### Si la Migración Falla

```bash
# 1. Detener aplicación
./docker-stop.sh

# 2. Restaurar backup
cp backups/sqlite_backup_YYYYMMDD_HHMMSS.db unified_mcp_system.db

# 3. Revertir .env a SQLite
# DATABASE_URL=sqlite:///./unified_mcp_system.db

# 4. Reiniciar con SQLite
./docker-start.sh
```

### Limpiar PostgreSQL

```bash
# Conectar a PostgreSQL
psql -h localhost -U mcp_user -d mcp_system

# Borrar todo el schema
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;

# Salir
\q
```

---

## 🔧 Troubleshooting

### Problema: "Cannot connect to PostgreSQL"

**Causa**: PostgreSQL no está corriendo

**Solución:**
```bash
# Verificar estado de Docker
docker-compose ps

# Si no está corriendo
./docker-start.sh

# Verificar logs
./docker-logs.sh db
```

### Problema: "Row count mismatch"

**Causa**: Datos no se migraron completamente

**Solución:**
```bash
# Ver qué tabla falló
python3 scripts/migration/validate_migration.py

# Re-migrar tabla específica
# (crear script custom si es necesario)
```

### Problema: "Foreign key constraint error"

**Causa**: Orden de migración de tablas incorrecto

**Solución:**
El script maneja esto automáticamente deshabilitando FK checks temporalmente. Si aún tienes problemas:

```bash
# Verificar que session_replication_role se restauró
psql -h localhost -U mcp_user -d mcp_system \
     -c "SHOW session_replication_role"
# Debe ser: origin
```

### Problema: "Triggers not migrated"

**Causa**: Triggers de SQLite tienen sintaxis diferente

**Solución:**
Los triggers requieren conversión manual. Revisa:
```bash
# Ver triggers pendientes
grep "TODO: Convert trigger" scripts/migration/postgres_schema.sql
```

La mayoría de triggers son para `updated_at`, que pueden ser reemplazados por:
```sql
-- Ejemplo de trigger en PostgreSQL
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_table_updated_at BEFORE UPDATE ON table_name
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

---

## ❓ FAQ

### ¿Puedo migrar solo algunas tablas?

Sí, edita `run_migration.sh` y especifica las tablas:

```python
# En migrate_data.py
table_order = ['users', 'companies', 'manual_expenses']  # Solo estas
```

### ¿Cómo verifico el tamaño de la base de datos?

```sql
-- SQLite
SELECT page_count * page_size as size
FROM pragma_page_count(), pragma_page_size();

-- PostgreSQL
SELECT pg_size_pretty(pg_database_size('mcp_system'));
```

### ¿Puedo usar ambas bases en paralelo?

Sí, durante la transición:

```python
# En config/config.py
SQLITE_URL = "sqlite:///./unified_mcp_system.db"
POSTGRES_URL = os.getenv("DATABASE_URL")

# Usa POSTGRES_URL para nuevas features
# Mantén SQLITE_URL para fallback
```

### ¿Qué pasa con los datos futuros?

Una vez migrado a PostgreSQL, todos los datos nuevos se guardan allí. SQLite queda como backup histórico.

### ¿Necesito cambiar código de la aplicación?

**No**. SQLAlchemy maneja ambas bases de datos transparentemente. Solo cambia la `DATABASE_URL` en `.env`.

### ¿Cómo hago backup de PostgreSQL?

```bash
# Backup
docker-compose exec db pg_dump -U mcp_user mcp_system > backup.sql

# Restaurar
cat backup.sql | docker-compose exec -T db psql -U mcp_user mcp_system
```

---

## 📊 Diferencias SQLite vs PostgreSQL

| Característica | SQLite | PostgreSQL |
|----------------|--------|------------|
| **Tipo** | File-based | Server-based |
| **Concurrency** | Limitada | Alta |
| **Max DB Size** | ~140 TB teórico | Ilimitado |
| **Connections** | Una escritura | Múltiples |
| **ACID** | ✅ | ✅ |
| **Foreign Keys** | ✅ | ✅ |
| **Triggers** | ✅ | ✅ (sintaxis diferente) |
| **Full-text Search** | Básico | Avanzado |
| **JSON Support** | Básico | Nativo |
| **Replication** | ❌ | ✅ |
| **Partitioning** | ❌ | ✅ |

---

## 🎯 Próximos Pasos

Después de migrar exitosamente:

1. ✅ **Probar la aplicación** completamente
2. ✅ **Ejecutar tests** con PostgreSQL
3. ✅ **Monitorear performance** con queries lentas
4. ✅ **Configurar backups automáticos**
5. ✅ **Documentar cualquier cambio** necesario

---

## 📚 Recursos Adicionales

- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [SQLAlchemy PostgreSQL](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html)
- [Docker PostgreSQL](https://hub.docker.com/_/postgres)
- [pgAdmin Documentation](https://www.pgadmin.org/docs/)

---

**Fecha de Creación**: 2025-11-04
**Fase**: 2.3 - Migración PostgreSQL
**Autor**: MCP Backend Refactor Team
