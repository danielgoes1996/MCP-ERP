#!/usr/bin/env python3
"""
Migración de SQLite a PostgreSQL
Prepara el sistema para escalabilidad empresarial
"""

import sqlite3
import logging
from pathlib import Path
from datetime import datetime

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PostgreSQLMigrationPreparer:
    """Prepara la migración a PostgreSQL"""

    def __init__(self, sqlite_db_path="/Users/danielgoes96/Desktop/mcp-server/unified_mcp_system.db"):
        self.sqlite_db_path = Path(sqlite_db_path)
        self.output_dir = self.sqlite_db_path.parent / "postgresql_migration"
        self.output_dir.mkdir(exist_ok=True)

    def generate_postgresql_schema(self):
        """Genera esquema PostgreSQL equivalente"""
        schema_sql = """
-- POSTGRESQL SCHEMA FOR MCP SYSTEM
-- Migración desde SQLite unificado

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. TENANTS
CREATE TABLE tenants (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    api_key VARCHAR(500),
    config JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. USERS
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(320) UNIQUE NOT NULL,
    tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE,
    role VARCHAR(50) DEFAULT 'user',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. EXPENSE RECORDS
CREATE TABLE expense_records (
    id SERIAL PRIMARY KEY,
    amount DECIMAL(15,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'MXN',
    description TEXT,
    category VARCHAR(100),
    merchant_name VARCHAR(255),
    merchant_category VARCHAR(100),
    date TIMESTAMP WITH TIME ZONE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. BANK MOVEMENTS
CREATE TABLE bank_movements (
    id SERIAL PRIMARY KEY,
    amount DECIMAL(15,2) NOT NULL,
    description TEXT,
    date TIMESTAMP WITH TIME ZONE,
    account VARCHAR(100),
    tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE,
    matched_expense_id INTEGER REFERENCES expense_records(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 5. EXPENSE INVOICES
CREATE TABLE expense_invoices (
    id SERIAL PRIMARY KEY,
    expense_id INTEGER REFERENCES expense_records(id) ON DELETE CASCADE,
    filename VARCHAR(500),
    file_path VARCHAR(1000),
    content_type VARCHAR(100),
    parsed_data JSONB,
    tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 6. TICKETS
CREATE TABLE tickets (
    id SERIAL PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    status VARCHAR(50) DEFAULT 'open',
    priority VARCHAR(20) DEFAULT 'medium',
    assignee VARCHAR(255),
    tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 7. AUTOMATION JOBS
CREATE TABLE automation_jobs (
    id SERIAL PRIMARY KEY,
    job_type VARCHAR(100) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    config JSONB,
    tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 8. AUTOMATION LOGS
CREATE TABLE automation_logs (
    id SERIAL PRIMARY KEY,
    job_id INTEGER REFERENCES automation_jobs(id) ON DELETE CASCADE,
    level VARCHAR(20) DEFAULT 'info',
    message TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 9. AUTOMATION SCREENSHOTS
CREATE TABLE automation_screenshots (
    id SERIAL PRIMARY KEY,
    job_id INTEGER REFERENCES automation_jobs(id) ON DELETE CASCADE,
    filename VARCHAR(500),
    file_path VARCHAR(1000),
    step_name VARCHAR(255),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 10. GPT USAGE EVENTS
CREATE TABLE gpt_usage_events (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    field_name VARCHAR(100) NOT NULL,
    reason TEXT NOT NULL,
    tokens_estimated INTEGER NOT NULL,
    cost_estimated_usd DECIMAL(10,4) NOT NULL,
    confidence_before DECIMAL(5,4) NOT NULL,
    confidence_after DECIMAL(5,4) NOT NULL,
    success BOOLEAN NOT NULL,
    merchant_type VARCHAR(100),
    ticket_id VARCHAR(50),
    error_message TEXT,
    tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE
);

-- 11. SCHEMA VERSIONS
CREATE TABLE schema_versions (
    id SERIAL PRIMARY KEY,
    version VARCHAR(50) NOT NULL,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    description TEXT
);

-- PERFORMANCE INDEXES
CREATE INDEX idx_expense_tenant_status ON expense_records(tenant_id, status);
CREATE INDEX idx_expense_user_date ON expense_records(user_id, date DESC);
CREATE INDEX idx_expense_category ON expense_records(category);
CREATE INDEX idx_expense_amount ON expense_records(amount DESC);
CREATE INDEX idx_expense_created ON expense_records(created_at DESC);

CREATE INDEX idx_bank_tenant_date ON bank_movements(tenant_id, date DESC);
CREATE INDEX idx_bank_matched ON bank_movements(matched_expense_id);
CREATE INDEX idx_bank_amount ON bank_movements(amount);

CREATE INDEX idx_automation_tenant_status ON automation_jobs(tenant_id, status);
CREATE INDEX idx_automation_type ON automation_jobs(job_type);
CREATE INDEX idx_automation_created ON automation_jobs(created_at DESC);

CREATE INDEX idx_logs_job_timestamp ON automation_logs(job_id, timestamp DESC);
CREATE INDEX idx_logs_level ON automation_logs(level);

CREATE INDEX idx_tickets_tenant_status ON tickets(tenant_id, status);
CREATE INDEX idx_tickets_user ON tickets(user_id);
CREATE INDEX idx_tickets_priority ON tickets(priority);
CREATE INDEX idx_tickets_created ON tickets(created_at DESC);

CREATE INDEX idx_invoices_expense ON expense_invoices(expense_id);
CREATE INDEX idx_invoices_tenant ON expense_invoices(tenant_id);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_tenant ON users(tenant_id);

CREATE INDEX idx_gpt_tenant_timestamp ON gpt_usage_events(tenant_id, timestamp DESC);
CREATE INDEX idx_gpt_field_name ON gpt_usage_events(field_name);
CREATE INDEX idx_gpt_success ON gpt_usage_events(success);

-- Compound indexes for complex queries
CREATE INDEX idx_expense_tenant_user_date ON expense_records(tenant_id, user_id, date DESC);
CREATE INDEX idx_bank_tenant_amount_date ON bank_movements(tenant_id, amount DESC, date DESC);

-- UPDATE triggers for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_tenants_updated_at BEFORE UPDATE ON tenants FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_expense_records_updated_at BEFORE UPDATE ON expense_records FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_bank_movements_updated_at BEFORE UPDATE ON bank_movements FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_expense_invoices_updated_at BEFORE UPDATE ON expense_invoices FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_tickets_updated_at BEFORE UPDATE ON tickets FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_automation_jobs_updated_at BEFORE UPDATE ON automation_jobs FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Insert initial schema version
INSERT INTO schema_versions (version, description)
VALUES ('2.0.0', 'PostgreSQL Migration - Production Schema');
"""

        schema_file = self.output_dir / "postgresql_schema.sql"
        with open(schema_file, 'w') as f:
            f.write(schema_sql)

        logger.info(f"✅ PostgreSQL schema generado: {schema_file}")
        return schema_file

    def generate_data_export_script(self):
        """Genera script para exportar datos de SQLite"""
        export_script = '''#!/usr/bin/env python3
"""
Exportador de datos SQLite -> PostgreSQL
"""

import sqlite3
import json
import csv
from pathlib import Path
from datetime import datetime

def export_table_to_csv(db_path, table_name, output_dir):
    """Exporta una tabla SQLite a CSV"""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()

        if not rows:
            print(f"⚠️  Tabla {table_name} vacía")
            return

        csv_file = output_dir / f"{table_name}.csv"

        with open(csv_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=rows[0].keys())
            writer.writeheader()

            for row in rows:
                # Convertir Row a dict
                row_dict = dict(row)
                writer.writerow(row_dict)

        print(f"✅ {table_name}: {len(rows)} filas -> {csv_file}")

def main():
    sqlite_db = "unified_mcp_system.db"
    output_dir = Path("postgresql_migration/data_export")
    output_dir.mkdir(parents=True, exist_ok=True)

    tables = [
        'tenants', 'users', 'expense_records', 'bank_movements',
        'expense_invoices', 'tickets', 'automation_jobs',
        'automation_logs', 'automation_screenshots', 'gpt_usage_events',
        'schema_versions'
    ]

    print(f"🔄 Exportando datos desde {sqlite_db}")

    for table in tables:
        try:
            export_table_to_csv(sqlite_db, table, output_dir)
        except Exception as e:
            print(f"❌ Error exportando {table}: {e}")

    print("🎉 Exportación completada!")

if __name__ == "__main__":
    main()
'''

        export_file = self.output_dir / "export_data.py"
        with open(export_file, 'w') as f:
            f.write(export_script)

        export_file.chmod(0o755)
        logger.info(f"✅ Script de exportación generado: {export_file}")
        return export_file

    def generate_import_script(self):
        """Genera script para importar datos a PostgreSQL"""
        import_script = '''#!/usr/bin/env python3
"""
Importador PostgreSQL
Requiere: pip install psycopg2-binary
"""

import psycopg2
import csv
from pathlib import Path
import os

def import_csv_to_postgresql(csv_file, table_name, connection):
    """Importa CSV a PostgreSQL"""
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            cursor = connection.cursor()

            # Leer header
            reader = csv.DictReader(f)
            rows = list(reader)

            if not rows:
                print(f"⚠️  {csv_file} vacío")
                return

            # Construir INSERT
            columns = list(rows[0].keys())
            placeholders = ', '.join(['%s'] * len(columns))
            sql = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})"

            # Insertar datos
            for row in rows:
                values = [row[col] if row[col] != '' else None for col in columns]
                cursor.execute(sql, values)

            connection.commit()
            print(f"✅ {table_name}: {len(rows)} filas importadas")

    except Exception as e:
        print(f"❌ Error importando {table_name}: {e}")

def main():
    # Configuración PostgreSQL
    DB_CONFIG = {
        'host': os.getenv('PG_HOST', 'localhost'),
        'database': os.getenv('PG_DATABASE', 'mcp_production'),
        'user': os.getenv('PG_USER', 'mcp_user'),
        'password': os.getenv('PG_PASSWORD', 'your_password'),
        'port': os.getenv('PG_PORT', '5432')
    }

    data_dir = Path("postgresql_migration/data_export")

    if not data_dir.exists():
        print("❌ Directorio de datos no encontrado. Ejecuta export_data.py primero")
        return

    try:
        # Conectar a PostgreSQL
        conn = psycopg2.connect(**DB_CONFIG)
        print("✅ Conectado a PostgreSQL")

        # Orden de importación (respetando foreign keys)
        import_order = [
            'schema_versions',
            'tenants',
            'users',
            'expense_records',
            'bank_movements',
            'expense_invoices',
            'tickets',
            'automation_jobs',
            'automation_logs',
            'automation_screenshots',
            'gpt_usage_events'
        ]

        for table in import_order:
            csv_file = data_dir / f"{table}.csv"
            if csv_file.exists():
                import_csv_to_postgresql(csv_file, table, conn)
            else:
                print(f"⚠️  {csv_file} no encontrado")

        conn.close()
        print("🎉 Importación completada!")

    except Exception as e:
        print(f"❌ Error de conexión PostgreSQL: {e}")

if __name__ == "__main__":
    main()
'''

        import_file = self.output_dir / "import_to_postgresql.py"
        with open(import_file, 'w') as f:
            f.write(import_script)

        import_file.chmod(0o755)
        logger.info(f"✅ Script de importación generado: {import_file}")
        return import_file

    def generate_docker_compose(self):
        """Genera docker-compose para PostgreSQL local"""
        docker_compose = '''version: '3.8'

services:
  postgres:
    image: postgres:15
    container_name: mcp_postgres
    environment:
      POSTGRES_DB: mcp_production
      POSTGRES_USER: mcp_user
      POSTGRES_PASSWORD: mcp_secure_password_2024
      POSTGRES_INITDB_ARGS: "--encoding=UTF8 --locale=C"
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./postgresql_schema.sql:/docker-entrypoint-initdb.d/01_schema.sql
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U mcp_user -d mcp_production"]
      interval: 30s
      timeout: 10s
      retries: 5

  pgadmin:
    image: dpage/pgadmin4
    container_name: mcp_pgadmin
    environment:
      PGADMIN_DEFAULT_EMAIL: admin@mcp.local
      PGADMIN_DEFAULT_PASSWORD: admin123
    ports:
      - "5050:80"
    depends_on:
      - postgres
    restart: unless-stopped

volumes:
  postgres_data:
    driver: local

# Para iniciar: docker-compose up -d
# Para detener: docker-compose down
# Logs: docker-compose logs postgres
'''

        docker_file = self.output_dir / "docker-compose.yml"
        with open(docker_file, 'w') as f:
            f.write(docker_compose)

        logger.info(f"✅ Docker Compose generado: {docker_file}")
        return docker_file

    def generate_migration_readme(self):
        """Genera documentación de migración"""
        readme = '''# 🚀 MIGRACIÓN A POSTGRESQL

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
```python
# En config/config.py, cambiar:
USE_UNIFIED_DB = False
USE_POSTGRESQL = True
DATABASE_URL = "postgresql://mcp_user:password@localhost:5432/mcp_production"
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
'''

        readme_file = self.output_dir / "README.md"
        with open(readme_file, 'w') as f:
            f.write(readme)

        logger.info(f"✅ Documentación generada: {readme_file}")
        return readme_file

    def prepare_full_migration(self):
        """Prepara todo lo necesario para la migración"""
        logger.info("🚀 Preparando migración completa a PostgreSQL")

        files_created = []
        files_created.append(self.generate_postgresql_schema())
        files_created.append(self.generate_data_export_script())
        files_created.append(self.generate_import_script())
        files_created.append(self.generate_docker_compose())
        files_created.append(self.generate_migration_readme())

        logger.info("🎉 Migración a PostgreSQL preparada!")
        logger.info(f"📁 Archivos en: {self.output_dir}")

        return files_created

if __name__ == "__main__":
    migrator = PostgreSQLMigrationPreparer()
    files = migrator.prepare_full_migration()

    print("📋 ARCHIVOS GENERADOS:")
    for file in files:
        print(f"  ✅ {file}")

    print("\n🚀 PRÓXIMOS PASOS:")
    print("  1. Revisar postgresql_migration/README.md")
    print("  2. Ejecutar docker-compose up -d")
    print("  3. Ejecutar python3 export_data.py")
    print("  4. Ejecutar python3 import_to_postgresql.py")
    print("\n⚠️  La migración está PREPARADA pero NO ejecutada")
    print("   El sistema sigue usando SQLite hasta que la actives")