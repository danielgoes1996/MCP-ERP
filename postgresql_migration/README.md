# 🚀 MIGRACIÓN A POSTGRESQL

## Pasos para migrar de SQLite a PostgreSQL

### 1. Preparar PostgreSQL

#### Opción A: Docker (Recomendado)
```bash
# Iniciar PostgreSQL con Docker
docker-compose up -d

# Verificar que funciona
docker-compose logs postgres
```

#### Opción B: Instalación Local
```bash
# macOS
brew install postgresql
brew services start postgresql

# Ubuntu/Debian
sudo apt update
sudo apt install postgresql postgresql-contrib

# Crear base de datos
sudo -u postgres createdb mcp_production
sudo -u postgres createuser mcp_user
```

### 2. Crear esquema
```bash
# Con Docker
docker exec -i mcp_postgres psql -U mcp_user -d mcp_production < postgresql_schema.sql

# Local
psql -U mcp_user -d mcp_production < postgresql_schema.sql
```

### 3. Exportar datos de SQLite
```bash
python3 export_data.py
```

### 4. Importar datos a PostgreSQL
```bash
# Configurar variables de entorno
export PG_HOST=localhost
export PG_DATABASE=mcp_production
export PG_USER=mcp_user
export PG_PASSWORD=mcp_secure_password_2024

# Instalar dependencias
pip install psycopg2-binary

# Importar datos
python3 import_to_postgresql.py
```

### 5. Actualizar configuración del sistema
Configura las variables de entorno (por ejemplo en `.env`):
```bash
USE_UNIFIED_DB=true
USE_POSTGRESQL=true
POSTGRES_DSN="postgresql://mcp_user:mcp_secure_password_2024@localhost:5432/mcp_production"
```

### 6. Verificar migración
```bash
# Conectar y verificar datos
docker exec -it mcp_postgres psql -U mcp_user -d mcp_production

# Contar registros
SELECT 'expenses' as table_name, COUNT(*) FROM expense_records
UNION ALL
SELECT 'jobs', COUNT(*) FROM automation_jobs
UNION ALL
SELECT 'users', COUNT(*) FROM users;
```

## Ventajas de PostgreSQL

✅ **Escalabilidad**: Miles de usuarios concurrentes
✅ **Backup automático**: Point-in-time recovery
✅ **Alta disponibilidad**: Replicación master-slave
✅ **ACID completo**: Transacciones robustas
✅ **Tipos de datos avanzados**: JSON, Arrays, etc.
✅ **Full-text search**: Búsqueda de texto integrada
✅ **Extensiones**: PostGIS, TimescaleDB, etc.

## Performance esperado

| Métrica | SQLite | PostgreSQL |
|---------|--------|------------|
| Concurrent users | 1-10 | 100-10,000+ |
| Write throughput | 1K ops/sec | 10K-100K ops/sec |
| Database size | < 1GB | Unlimited |
| Backup time | Minutes | Seconds (incremental) |

## Rollback plan

Si algo falla, el sistema puede volver a SQLite:
```bash
# En .env
USE_UNIFIED_DB=true
USE_POSTGRESQL=false
```

La DB SQLite original se mantiene intacta.
