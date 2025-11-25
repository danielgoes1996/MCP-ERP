# 🐘 PostgreSQL Migration Plan
## Eliminación del SPOF Crítico - SQLite → PostgreSQL

---

## 🚨 Análisis del SPOF Actual

### **Problema Crítico Identificado**
- **Afecta**: 22/23 funcionalidades (96% del sistema)
- **Tiempo de Recovery**: 4-8 horas
- **Riesgo**: Máximo
- **Estado**: Base de datos SQLite como archivo único

### **Limitaciones de SQLite en Producción**
```sql
-- Problemas identificados:
-- 1. Un solo archivo = SPOF total
-- 2. Bloqueo global en escrituras
-- 3. Sin replicación nativa
-- 4. Sin clustering
-- 5. Sin backup en caliente
-- 6. Performance limitada en concurrencia
```

---

## 🎯 PLAN DE MIGRACIÓN PostgreSQL

### **Fase 1: Preparación y Setup (1 semana)**

#### 1.1 Instalación y Configuración PostgreSQL
```bash
# Installation (Ubuntu/Debian)
sudo apt update
sudo apt install postgresql postgresql-contrib

# Configuration
sudo -u postgres psql
CREATE DATABASE mcp_production;
CREATE DATABASE mcp_staging;
CREATE DATABASE mcp_development;

# Create application user
CREATE USER mcp_user WITH ENCRYPTED PASSWORD 'secure_password_here';
GRANT ALL PRIVILEGES ON DATABASE mcp_production TO mcp_user;
GRANT ALL PRIVILEGES ON DATABASE mcp_staging TO mcp_user;
GRANT ALL PRIVILEGES ON DATABASE mcp_development TO mcp_user;
```

#### 1.2 PostgreSQL Configuration Optimization
```sql
-- postgresql.conf optimizations
max_connections = 200
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 4MB
maintenance_work_mem = 64MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100

-- Enable connection pooling
listen_addresses = '*'
port = 5432

-- Security settings
ssl = on
password_encryption = scram-sha-256
```

#### 1.3 Create Database Adapter
```python
# core/postgresql_adapter.py
import asyncpg
import asyncio
from typing import Dict, Any, List, Optional
import json
from datetime import datetime
import logging

class PostgreSQLAdapter:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self._pool: Optional[asyncpg.Pool] = None
        self._logger = logging.getLogger(__name__)

    async def initialize(self):
        """Initialize connection pool"""
        self._pool = await asyncpg.create_pool(
            self.database_url,
            min_size=5,
            max_size=20,
            command_timeout=60,
            server_settings={
                'jit': 'off'  # Disable JIT for better predictability
            }
        )
        self._logger.info("PostgreSQL connection pool initialized")

    async def close(self):
        """Close connection pool"""
        if self._pool:
            await self._pool.close()

    async def fetch_one(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """Fetch single row"""
        async with self._pool.acquire() as connection:
            row = await connection.fetchrow(query, *args)
            return dict(row) if row else None

    async def fetch_all(self, query: str, *args) -> List[Dict[str, Any]]:
        """Fetch multiple rows"""
        async with self._pool.acquire() as connection:
            rows = await connection.fetch(query, *args)
            return [dict(row) for row in rows]

    async def execute(self, query: str, *args) -> str:
        """Execute query and return status"""
        async with self._pool.acquire() as connection:
            return await connection.execute(query, *args)

    async def transaction(self):
        """Get transaction context"""
        return self._pool.acquire()

    async def health_check(self) -> bool:
        """Check database connectivity"""
        try:
            async with self._pool.acquire() as connection:
                await connection.fetchval("SELECT 1")
                return True
        except Exception as e:
            self._logger.error(f"Database health check failed: {e}")
            return False

# Singleton instance
pg_adapter = PostgreSQLAdapter(
    "postgresql://mcp_user:secure_password_here@localhost:5432/mcp_production"
)
```

### **Fase 2: Schema Migration (1 semana)**

#### 2.1 Create PostgreSQL Schema
```sql
-- postgresql_schema.sql
-- Enhanced schema with all audit improvements

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For similarity searches
CREATE EXTENSION IF NOT EXISTS "btree_gin"; -- For JSON indexing

-- Core tables
CREATE TABLE companies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    company_id INTEGER REFERENCES companies(id),
    identifier VARCHAR(255),
    full_name VARCHAR(255),
    company_name VARCHAR(255),
    tenant_id INTEGER DEFAULT 1,
    role VARCHAR(50) DEFAULT 'user',
    is_active BOOLEAN DEFAULT TRUE,
    registration_method VARCHAR(50) DEFAULT 'email',
    email_verified BOOLEAN DEFAULT FALSE,
    phone_verified BOOLEAN DEFAULT FALSE,
    onboarding_step INTEGER DEFAULT 0,
    onboarding_completed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP WITH TIME ZONE
);

-- Enhanced expenses table with all audit fields
CREATE TABLE manual_expenses (
    id SERIAL PRIMARY KEY,
    descripcion TEXT NOT NULL,
    monto_total DECIMAL(10,2) NOT NULL CHECK (monto_total > 0),
    fecha_gasto DATE,
    proveedor VARCHAR(255),
    categoria VARCHAR(100),
    metodo_pago VARCHAR(50),
    moneda CHAR(3) DEFAULT 'MXN',

    -- Business fields (from audit)
    deducible BOOLEAN DEFAULT TRUE,
    requiere_factura BOOLEAN DEFAULT TRUE,
    centro_costo VARCHAR(100),
    proyecto VARCHAR(100),

    -- Advanced tracking fields
    rfc_proveedor VARCHAR(20),
    cfdi_uuid VARCHAR(50),
    invoice_status VARCHAR(20) DEFAULT 'pending',
    bank_status VARCHAR(20) DEFAULT 'pending',
    approval_status VARCHAR(20) DEFAULT 'pending',
    approved_by INTEGER,
    approved_at TIMESTAMP WITH TIME ZONE,

    -- Context fields
    company_id VARCHAR(50) DEFAULT 'default',
    user_id VARCHAR(50),
    updated_by INTEGER,

    -- Additional metadata
    notas TEXT,
    ubicacion VARCHAR(255),
    tags JSONB DEFAULT '[]'::jsonb,
    metadata JSONB,

    -- Enhanced fields from audit
    audit_trail JSONB,
    user_context TEXT,
    enhanced_data JSONB,
    completion_status VARCHAR(20) DEFAULT 'draft',
    validation_errors JSONB,
    field_completeness DECIMAL(3,2) DEFAULT 0.0,

    -- ML and analytics fields
    trend_category VARCHAR(50),
    forecast_confidence DECIMAL(3,2),
    seasonality_factor DECIMAL(3,2),
    ml_features JSONB,
    similarity_scores JSONB,
    duplicate_risk_level VARCHAR(20) DEFAULT 'low',
    ml_model_version VARCHAR(20),

    -- Legacy compatibility
    estado VARCHAR(20) DEFAULT 'pendiente',
    factura_generada BOOLEAN DEFAULT FALSE,
    fecha_facturacion DATE,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Enhanced invoices table
CREATE TABLE invoices (
    id SERIAL PRIMARY KEY,
    expense_id INTEGER REFERENCES expenses(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    file_path VARCHAR(500),
    content_type VARCHAR(100) DEFAULT 'application/pdf',
    tenant_id INTEGER DEFAULT 1,

    -- Invoice data fields
    uuid VARCHAR(50),
    rfc_emisor VARCHAR(20),
    nombre_emisor VARCHAR(255),
    subtotal DECIMAL(10,2),
    iva_amount DECIMAL(10,2),
    total DECIMAL(10,2),
    moneda CHAR(3) DEFAULT 'MXN',
    fecha_emision DATE,
    discount DECIMAL(10,2) DEFAULT 0.0,
    retention DECIMAL(10,2) DEFAULT 0.0,

    -- Enhanced processing fields (from audit)
    xml_content TEXT,
    validation_status VARCHAR(20) DEFAULT 'pending',
    processing_metadata JSONB,
    template_match DECIMAL(3,2),
    validation_rules JSONB,
    detected_format VARCHAR(50),
    parser_used VARCHAR(50),
    ocr_confidence DECIMAL(3,2),
    processing_metrics JSONB,
    quality_score DECIMAL(3,2),
    processor_used VARCHAR(50),

    -- Processing status
    processing_status VARCHAR(20) DEFAULT 'pending',
    match_confidence DECIMAL(3,2) DEFAULT 0.0,
    auto_matched BOOLEAN DEFAULT FALSE,
    processed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Enhanced bank movements table
CREATE TABLE bank_movements (
    id SERIAL PRIMARY KEY,
    amount DECIMAL(10,2) NOT NULL,
    description TEXT NOT NULL,
    date DATE NOT NULL,
    account VARCHAR(100) NOT NULL,
    tenant_id INTEGER DEFAULT 1,

    -- Enhanced fields (from audit)
    decision VARCHAR(20),
    bank_metadata JSONB,
    confidence DECIMAL(3,2) DEFAULT 0.0,
    movement_id VARCHAR(100),
    transaction_type VARCHAR(20) DEFAULT 'debit',
    reference VARCHAR(100),
    balance_after DECIMAL(12,2),
    raw_data TEXT,
    processing_status VARCHAR(20) DEFAULT 'pending',
    matched_at TIMESTAMP WITH TIME ZONE,
    matched_by INTEGER,
    auto_matched BOOLEAN DEFAULT FALSE,
    reconciliation_notes TEXT,
    bank_account_id VARCHAR(50),
    category VARCHAR(50),

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- New tables from audit
CREATE TABLE automation_sessions (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(100) UNIQUE NOT NULL,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    state_data JSONB,
    checkpoint_data JSONB,
    recovery_metadata JSONB,
    session_status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE workers (
    id SERIAL PRIMARY KEY,
    task_id VARCHAR(100) UNIQUE NOT NULL,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    task_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    progress DECIMAL(3,2) DEFAULT 0.0,
    worker_metadata JSONB,
    retry_policy JSONB,
    retry_count INTEGER DEFAULT 0,
    result_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE system_health (
    id SERIAL PRIMARY KEY,
    component_name VARCHAR(100) NOT NULL,
    health_status VARCHAR(20) NOT NULL,
    automation_health JSONB,
    performance_metrics JSONB,
    error_count INTEGER DEFAULT 0,
    last_check TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB
);

CREATE TABLE user_preferences (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    company_id INTEGER NOT NULL REFERENCES companies(id),
    preferences JSONB,
    onboarding_step VARCHAR(20) DEFAULT 'start',
    demo_preferences JSONB,
    completion_rules JSONB,
    field_priorities JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Analytics and ML tables
CREATE TABLE analytics_cache (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    cache_key VARCHAR(255) NOT NULL,
    cache_data JSONB,
    cache_type VARCHAR(50) NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE category_learning (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    description_pattern TEXT,
    predicted_category VARCHAR(100),
    confidence DECIMAL(3,2),
    user_feedback VARCHAR(20),
    learning_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE duplicate_detection (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    expense_id_1 INTEGER REFERENCES expenses(id),
    expense_id_2 INTEGER REFERENCES expenses(id),
    similarity_score DECIMAL(3,2),
    detection_method VARCHAR(50),
    status VARCHAR(20) DEFAULT 'pending',
    user_decision VARCHAR(20),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE error_logs (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id),
    user_id INTEGER REFERENCES users(id),
    error_code VARCHAR(50),
    error_message TEXT,
    stack_trace TEXT,
    user_context JSONB,
    request_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Schema migrations tracking
CREATE TABLE schema_migrations (
    id SERIAL PRIMARY KEY,
    version VARCHAR(20) UNIQUE NOT NULL,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);
```

#### 2.2 Comprehensive Indexing Strategy
```sql
-- indexes.sql - Performance optimization indexes

-- Core business indexes
CREATE INDEX CONCURRENTLY idx_expenses_company_date ON expenses(company_id, fecha_gasto DESC);
CREATE INDEX CONCURRENTLY idx_expenses_provider ON expenses(proveedor) WHERE proveedor IS NOT NULL;
CREATE INDEX CONCURRENTLY idx_expenses_amount_range ON expenses(monto_total, moneda);
CREATE INDEX CONCURRENTLY idx_expenses_status ON expenses(invoice_status, bank_status, approval_status);
CREATE INDEX CONCURRENTLY idx_expenses_deducible ON expenses(deducible) WHERE deducible IS TRUE;
CREATE INDEX CONCURRENTLY idx_expenses_completion ON expenses(completion_status, field_completeness);

-- Enhanced business indexes
CREATE INDEX CONCURRENTLY idx_expenses_centro_costo ON expenses(centro_costo) WHERE centro_costo IS NOT NULL;
CREATE INDEX CONCURRENTLY idx_expenses_proyecto ON expenses(proyecto) WHERE proyecto IS NOT NULL;
CREATE INDEX CONCURRENTLY idx_expenses_duplicate_risk ON expenses(duplicate_risk_level) WHERE duplicate_risk_level != 'low';

-- JSON/JSONB indexes for enhanced fields
CREATE INDEX CONCURRENTLY idx_expenses_tags_gin ON expenses USING gin(tags);
CREATE INDEX CONCURRENTLY idx_expenses_metadata_gin ON expenses USING gin(metadata);
CREATE INDEX CONCURRENTLY idx_expenses_ml_features_gin ON expenses USING gin(ml_features);
CREATE INDEX CONCURRENTLY idx_expenses_audit_trail_gin ON expenses USING gin(audit_trail);

-- Invoice indexes
CREATE INDEX CONCURRENTLY idx_invoices_expense ON invoices(expense_id);
CREATE INDEX CONCURRENTLY idx_invoices_uuid ON invoices(uuid) WHERE uuid IS NOT NULL;
CREATE INDEX CONCURRENTLY idx_invoices_rfc_emisor ON invoices(rfc_emisor) WHERE rfc_emisor IS NOT NULL;
CREATE INDEX CONCURRENTLY idx_invoices_processing_status ON invoices(processing_status, match_confidence);
CREATE INDEX CONCURRENTLY idx_invoices_validation_status ON invoices(validation_status);
CREATE INDEX CONCURRENTLY idx_invoices_quality_score ON invoices(quality_score) WHERE quality_score IS NOT NULL;

-- Bank movement indexes
CREATE INDEX CONCURRENTLY idx_bank_movements_date_amount ON bank_movements(date DESC, amount);
CREATE INDEX CONCURRENTLY idx_bank_movements_account ON bank_movements(account, date DESC);
CREATE INDEX CONCURRENTLY idx_bank_movements_processing ON bank_movements(processing_status, confidence);
CREATE INDEX CONCURRENTLY idx_bank_movements_decision ON bank_movements(decision) WHERE decision IS NOT NULL;

-- Full-text search indexes
CREATE INDEX CONCURRENTLY idx_expenses_description_fts ON expenses USING gin(to_tsvector('spanish', descripcion));
CREATE INDEX CONCURRENTLY idx_expenses_provider_similarity ON expenses USING gin(proveedor gin_trgm_ops) WHERE proveedor IS NOT NULL;
CREATE INDEX CONCURRENTLY idx_bank_movements_description_fts ON bank_movements USING gin(to_tsvector('spanish', description));

-- Automation and system indexes
CREATE INDEX CONCURRENTLY idx_automation_sessions_company ON automation_sessions(company_id, session_status);
CREATE INDEX CONCURRENTLY idx_workers_company_status ON workers(company_id, status, task_type);
CREATE INDEX CONCURRENTLY idx_workers_task_id ON workers(task_id);
CREATE INDEX CONCURRENTLY idx_system_health_component ON system_health(component_name, health_status);

-- Analytics indexes
CREATE INDEX CONCURRENTLY idx_analytics_cache_company_key ON analytics_cache(company_id, cache_key, cache_type);
CREATE INDEX CONCURRENTLY idx_analytics_cache_expires ON analytics_cache(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX CONCURRENTLY idx_category_learning_company ON category_learning(company_id, predicted_category);
CREATE INDEX CONCURRENTLY idx_duplicate_detection_company ON duplicate_detection(company_id, similarity_score DESC);

-- Error tracking indexes
CREATE INDEX CONCURRENTLY idx_error_logs_company_date ON error_logs(company_id, created_at DESC);
CREATE INDEX CONCURRENTLY idx_error_logs_error_code ON error_logs(error_code, created_at DESC);

-- User and preferences indexes
CREATE INDEX CONCURRENTLY idx_user_preferences_user ON user_preferences(user_id);
CREATE INDEX CONCURRENTLY idx_user_preferences_company ON user_preferences(company_id);
CREATE INDEX CONCURRENTLY idx_users_company ON users(company_id, is_active);
CREATE INDEX CONCURRENTLY idx_users_email ON users(email) WHERE is_active = TRUE;
```

### **Fase 3: Data Migration (1 semana)**

#### 3.1 SQLite to PostgreSQL Migration Script
```python
# migration_script.py
import sqlite3
import asyncpg
import asyncio
import json
from datetime import datetime
from typing import Dict, Any, List
import logging

class SQLiteToPostgreSQLMigrator:
    def __init__(self, sqlite_path: str, postgres_url: str):
        self.sqlite_path = sqlite_path
        self.postgres_url = postgres_url
        self._logger = logging.getLogger(__name__)

    async def migrate(self):
        """Execute complete migration"""
        try:
            # Connect to both databases
            sqlite_conn = sqlite3.connect(self.sqlite_path)
            sqlite_conn.row_factory = sqlite3.Row

            postgres_pool = await asyncpg.create_pool(self.postgres_url)

            # Migration steps
            await self._migrate_companies(sqlite_conn, postgres_pool)
            await self._migrate_users(sqlite_conn, postgres_pool)
            await self._migrate_expenses(sqlite_conn, postgres_pool)
            await self._migrate_invoices(sqlite_conn, postgres_pool)
            await self._migrate_bank_movements(sqlite_conn, postgres_pool)
            await self._migrate_automation_data(sqlite_conn, postgres_pool)

            # Update sequences
            await self._update_sequences(postgres_pool)

            # Verify migration
            await self._verify_migration(sqlite_conn, postgres_pool)

            self._logger.info("Migration completed successfully")

        except Exception as e:
            self._logger.error(f"Migration failed: {e}")
            raise
        finally:
            sqlite_conn.close()
            await postgres_pool.close()

    async def _migrate_expenses(self, sqlite_conn, postgres_pool):
        """Migrate expenses with enhanced fields"""
        cursor = sqlite_conn.execute("SELECT * FROM manual_expenses")
        expenses = cursor.fetchall()

        async with postgres_pool.acquire() as pg_conn:
            async with pg_conn.transaction():
                for expense in expenses:
                    # Map SQLite data to PostgreSQL schema
                    expense_data = dict(expense)

                    # Handle JSON fields
                    if expense_data.get('tags'):
                        try:
                            expense_data['tags'] = json.loads(expense_data['tags'])
                        except:
                            expense_data['tags'] = []

                    if expense_data.get('metadata'):
                        try:
                            expense_data['metadata'] = json.loads(expense_data['metadata'])
                        except:
                            expense_data['metadata'] = {}

                    # Set default values for new fields
                    expense_data.update({
                        'deducible': expense_data.get('deducible', True),
                        'centro_costo': expense_data.get('centro_costo'),
                        'proyecto': expense_data.get('proyecto'),
                        'completion_status': 'complete',  # Existing data is complete
                        'field_completeness': 1.0,
                        'duplicate_risk_level': 'low',
                        'audit_trail': {'migrated_from': 'sqlite', 'migrated_at': datetime.utcnow().isoformat()}
                    })

                    # Insert into PostgreSQL
                    await pg_conn.execute("""
                        INSERT INTO manual_expenses (
                            id, descripcion, monto_total, fecha_gasto, proveedor, categoria,
                            metodo_pago, moneda, deducible, centro_costo, proyecto, tags,
                            metadata, completion_status, field_completeness, duplicate_risk_level,
                            audit_trail, company_id, user_id, created_at, updated_at
                        ) VALUES (
                            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21
                        )
                    """,
                        expense_data['id'], expense_data['descripcion'], expense_data['monto_total'],
                        expense_data.get('fecha_gasto'), expense_data.get('proveedor'), expense_data.get('categoria'),
                        expense_data.get('metodo_pago'), expense_data.get('moneda', 'MXN'),
                        expense_data['deducible'], expense_data['centro_costo'], expense_data['proyecto'],
                        json.dumps(expense_data['tags']), json.dumps(expense_data['metadata']),
                        expense_data['completion_status'], expense_data['field_completeness'],
                        expense_data['duplicate_risk_level'], json.dumps(expense_data['audit_trail']),
                        expense_data.get('company_id', 'default'), expense_data.get('user_id'),
                        expense_data.get('created_at', datetime.utcnow()),
                        expense_data.get('updated_at', datetime.utcnow())
                    )

        self._logger.info(f"Migrated {len(expenses)} expenses")

    async def _update_sequences(self, postgres_pool):
        """Update PostgreSQL sequences to match migrated data"""
        async with postgres_pool.acquire() as conn:
            # Update sequences for all tables
            tables = ['companies', 'users', 'manual_expenses', 'invoices', 'bank_movements',
                     'automation_sessions', 'workers', 'system_health', 'user_preferences']

            for table in tables:
                await conn.execute(f"""
                    SELECT setval('{table}_id_seq', (SELECT COALESCE(MAX(id), 1) FROM {table}));
                """)

    async def _verify_migration(self, sqlite_conn, postgres_pool):
        """Verify migration integrity"""
        # Count records in both databases
        sqlite_counts = {}
        tables = ['manual_expenses', 'invoices', 'bank_movements']

        for table in tables:
            cursor = sqlite_conn.execute(f"SELECT COUNT(*) FROM {table}")
            sqlite_counts[table] = cursor.fetchone()[0]

        async with postgres_pool.acquire() as conn:
            for table in tables:
                pg_count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
                if sqlite_counts[table] != pg_count:
                    raise Exception(f"Migration verification failed for {table}: SQLite={sqlite_counts[table]}, PostgreSQL={pg_count}")

        self._logger.info("Migration verification passed")

# Run migration
async def run_migration():
    migrator = SQLiteToPostgreSQLMigrator(
        sqlite_path="expenses.db",
        postgres_url="postgresql://mcp_user:secure_password_here@localhost:5432/mcp_production"
    )
    await migrator.migrate()

if __name__ == "__main__":
    asyncio.run(run_migration())
```

### **Fase 4: High Availability Setup (1 semana)**

#### 4.1 Master-Slave Replication
```bash
# Setup streaming replication
# On master server (postgresql.conf)
wal_level = replica
max_wal_senders = 3
wal_keep_segments = 64
archive_mode = on
archive_command = 'cp %p /var/lib/postgresql/archive/%f'

# On master (pg_hba.conf)
host replication repl_user 192.168.1.101/32 md5

# Setup slave server
pg_basebackup -h master_ip -D /var/lib/postgresql/12/slave -U repl_user -P -W

# Configure slave (recovery.conf)
standby_mode = 'on'
primary_conninfo = 'host=master_ip port=5432 user=repl_user password=repl_password'
```

#### 4.2 Connection Pooling with PgBouncer
```ini
# pgbouncer.ini
[databases]
mcp_production = host=localhost port=5432 dbname=mcp_production
mcp_staging = host=localhost port=5432 dbname=mcp_staging

[pgbouncer]
listen_port = 6432
listen_addr = *
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt
pool_mode = transaction
max_client_conn = 1000
default_pool_size = 100
reserve_pool_size = 25
```

#### 4.3 Monitoring and Alerting
```sql
-- Database monitoring queries
-- Connection monitoring
SELECT count(*) FROM pg_stat_activity WHERE state = 'active';

-- Lock monitoring
SELECT blocked_locks.pid AS blocked_pid,
       blocked_activity.usename AS blocked_user,
       blocking_locks.pid AS blocking_pid,
       blocking_activity.usename AS blocking_user,
       blocked_activity.query AS blocked_statement,
       blocking_activity.query AS current_statement_in_blocking_process
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks blocking_locks ON blocking_locks.locktype = blocked_locks.locktype
    AND blocking_locks.database IS NOT DISTINCT FROM blocked_locks.database
    AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
    AND blocking_locks.page IS NOT DISTINCT FROM blocked_locks.page
    AND blocking_locks.tuple IS NOT DISTINCT FROM blocked_locks.tuple
    AND blocking_locks.virtualxid IS NOT DISTINCT FROM blocked_locks.virtualxid
    AND blocking_locks.transactionid IS NOT DISTINCT FROM blocked_locks.transactionid
    AND blocking_locks.classid IS NOT DISTINCT FROM blocked_locks.classid
    AND blocking_locks.objid IS NOT DISTINCT FROM blocked_locks.objid
    AND blocking_locks.objsubid IS NOT DISTINCT FROM blocked_locks.objsubid
    AND blocking_locks.pid != blocked_locks.pid
JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.granted;

-- Performance monitoring
SELECT schemaname,tablename,attname,n_distinct,correlation
FROM pg_stats
WHERE tablename IN ('manual_expenses', 'invoices', 'bank_movements')
ORDER BY schemaname, tablename, attname;
```

### **Fase 5: Application Integration (1 semana)**

#### 5.1 Database Configuration Management
```python
# config/database.py
import os
from typing import Dict, Any

class DatabaseConfig:
    """Database configuration management"""

    def __init__(self):
        self.environment = os.getenv("ENVIRONMENT", "development")
        self._configs = self._load_configs()

    def _load_configs(self) -> Dict[str, Dict[str, Any]]:
        return {
            "development": {
                "url": "postgresql://mcp_user:password@localhost:5432/mcp_development",
                "pool_size": 5,
                "max_overflow": 10,
                "pool_timeout": 30,
                "pool_recycle": 3600
            },
            "staging": {
                "url": "postgresql://mcp_user:password@staging-db:5432/mcp_staging",
                "pool_size": 10,
                "max_overflow": 20,
                "pool_timeout": 30,
                "pool_recycle": 3600
            },
            "production": {
                "url": "postgresql://mcp_user:password@prod-db:5432/mcp_production",
                "pool_size": 20,
                "max_overflow": 50,
                "pool_timeout": 30,
                "pool_recycle": 1800,
                "read_replica_url": "postgresql://mcp_user:password@prod-replica:5432/mcp_production"
            }
        }

    def get_config(self) -> Dict[str, Any]:
        return self._configs.get(self.environment, self._configs["development"])

    def get_database_url(self) -> str:
        return self.get_config()["url"]

    def get_read_replica_url(self) -> str:
        config = self.get_config()
        return config.get("read_replica_url", config["url"])

# Usage in application
db_config = DatabaseConfig()
```

#### 5.2 Gradual Migration Strategy
```python
# core/hybrid_database.py
from typing import Dict, Any, Optional
import asyncio

class HybridDatabaseAdapter:
    """Hybrid adapter for gradual migration"""

    def __init__(self, sqlite_adapter, postgresql_adapter):
        self.sqlite = sqlite_adapter
        self.postgresql = postgresql_adapter
        self.migration_mode = True
        self._migration_tables = set()

    def enable_table_migration(self, table_name: str):
        """Enable PostgreSQL for specific table"""
        self._migration_tables.add(table_name)

    async def query(self, table: str, query: str, *args) -> Any:
        """Route queries based on migration status"""
        if self.migration_mode and table in self._migration_tables:
            return await self.postgresql.query(query, *args)
        else:
            return await self.sqlite.query(query, *args)

    async def dual_write(self, table: str, operation: str, *args) -> bool:
        """Write to both databases during migration"""
        if table in self._migration_tables:
            try:
                # Write to both
                sqlite_result = await self.sqlite.execute(operation, *args)
                postgres_result = await self.postgresql.execute(operation, *args)

                # Verify consistency
                if sqlite_result != postgres_result:
                    logging.warning(f"Dual write inconsistency detected for {table}")

                return bool(postgres_result)
            except Exception as e:
                logging.error(f"Dual write failed for {table}: {e}")
                return False
        else:
            return await self.sqlite.execute(operation, *args)
```

### **Fase 6: Testing and Validation (1 semana)**

#### 6.1 Data Integrity Tests
```python
# tests/test_migration_integrity.py
import pytest
import asyncio
from core.postgresql_adapter import pg_adapter

class TestMigrationIntegrity:

    @pytest.mark.asyncio
    async def test_expense_count_integrity(self):
        """Test expense count matches between systems"""
        count = await pg_adapter.fetch_one(
            "SELECT COUNT(*) as count FROM manual_expenses"
        )
        assert count["count"] > 0

    @pytest.mark.asyncio
    async def test_data_consistency(self):
        """Test data consistency across tables"""
        # Test foreign key relationships
        orphaned_invoices = await pg_adapter.fetch_one("""
            SELECT COUNT(*) as count FROM invoices i
            LEFT JOIN manual_expenses e ON i.expense_id = e.id
            WHERE e.id IS NULL
        """)
        assert orphaned_invoices["count"] == 0

    @pytest.mark.asyncio
    async def test_json_fields(self):
        """Test JSON field integrity"""
        expenses_with_tags = await pg_adapter.fetch_all("""
            SELECT id, tags FROM manual_expenses
            WHERE tags IS NOT NULL AND jsonb_array_length(tags) > 0
            LIMIT 10
        """)

        for expense in expenses_with_tags:
            assert isinstance(expense["tags"], (list, str))

    @pytest.mark.asyncio
    async def test_performance(self):
        """Test query performance"""
        import time

        start_time = time.time()
        results = await pg_adapter.fetch_all("""
            SELECT * FROM manual_expenses
            WHERE company_id = $1
            ORDER BY created_at DESC
            LIMIT 100
        """, "default")
        end_time = time.time()

        query_time = end_time - start_time
        assert query_time < 1.0  # Should be under 1 second
        assert len(results) > 0
```

#### 6.2 Load Testing
```python
# tests/load_test.py
import asyncio
import aiohttp
import time
from concurrent.futures import ThreadPoolExecutor

async def load_test_endpoints():
    """Load test critical endpoints"""

    endpoints = [
        "/api/expenses",
        "/api/invoices",
        "/api/bank-movements",
        "/api/analytics"
    ]

    async with aiohttp.ClientSession() as session:
        tasks = []
        for _ in range(100):  # 100 concurrent requests
            for endpoint in endpoints:
                task = session.get(f"http://localhost:8000{endpoint}")
                tasks.append(task)

        start_time = time.time()
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()

        success_count = sum(1 for r in responses if hasattr(r, 'status') and r.status == 200)
        total_time = end_time - start_time

        print(f"Load test results:")
        print(f"- Total requests: {len(tasks)}")
        print(f"- Successful: {success_count}")
        print(f"- Total time: {total_time:.2f}s")
        print(f"- Requests per second: {len(tasks)/total_time:.2f}")

if __name__ == "__main__":
    asyncio.run(load_test_endpoints())
```

---

## 📊 Migration Timeline and Checklist

### **Semana 1: Preparación**
- [ ] Instalar PostgreSQL en servidores
- [ ] Configurar usuarios y permisos
- [ ] Crear adaptador PostgreSQL
- [ ] Configurar entornos (dev/staging/prod)
- [ ] Setup monitoring básico

### **Semana 2: Schema y Migración**
- [ ] Crear schema PostgreSQL completo
- [ ] Crear todos los índices
- [ ] Desarrollar script de migración
- [ ] Probar migración en desarrollo
- [ ] Validar integridad de datos

### **Semana 3: High Availability**
- [ ] Configurar replicación master-slave
- [ ] Setup connection pooling
- [ ] Configurar backups automáticos
- [ ] Implementar monitoring avanzado
- [ ] Probar failover scenarios

### **Semana 4: Integración de Aplicación**
- [ ] Integrar PostgreSQL adapter
- [ ] Implementar dual-write strategy
- [ ] Migrar tabla por tabla (gradual)
- [ ] Actualizar queries para PostgreSQL
- [ ] Probar compatibilidad

### **Semana 5: Testing y Optimización**
- [ ] Tests de integridad completos
- [ ] Load testing
- [ ] Performance tuning
- [ ] Optimización de queries
- [ ] Stress testing

### **Semana 6: Go-Live y Monitoreo**
- [ ] Migración final producción
- [ ] Cutover a PostgreSQL
- [ ] Monitoreo 24/7 primera semana
- [ ] Backup verification
- [ ] Performance monitoring

---

## 🎯 Expected Benefits Post-Migration

### **Eliminación del SPOF**
- ✅ **Alta Disponibilidad**: 99.9% uptime
- ✅ **Replicación**: Master-slave setup
- ✅ **Backup**: Hot backups continuos
- ✅ **Recovery**: RTO < 5 minutos

### **Performance Improvements**
- ✅ **Concurrency**: 100x más conexiones simultáneas
- ✅ **Scaling**: Horizontal scaling con read replicas
- ✅ **Indexing**: Advanced indexing strategies
- ✅ **Query Performance**: 5-10x faster complex queries

### **Advanced Features**
- ✅ **Full-text Search**: Built-in search capabilities
- ✅ **JSON Support**: Native JSONB with indexing
- ✅ **Extensions**: PostGIS, pg_trgm, etc.
- ✅ **Analytics**: Better aggregation performance

### **Operational Excellence**
- ✅ **Monitoring**: Comprehensive metrics
- ✅ **Alerting**: Proactive problem detection
- ✅ **Maintenance**: Automated routine tasks
- ✅ **Compliance**: Better audit trails

---

## 🚨 Risk Mitigation

### **Migration Risks**
1. **Data Loss**: Mitigated by dual-write strategy and verification
2. **Downtime**: Mitigated by gradual migration approach
3. **Performance Issues**: Mitigated by extensive testing
4. **Compatibility**: Mitigated by hybrid adapter

### **Rollback Plan**
- Keep SQLite database as backup during first month
- Ability to switch back to SQLite within 15 minutes
- Data synchronization tools ready
- Complete rollback procedures documented

---

**📅 Total Timeline**: 6 semanas
**💰 Investment**: Eliminación del 96% SPOF risk
**🎯 Success Metrics**: Zero data loss, <1 hour total downtime, 5x performance improvement
**📋 Next Phase**: Microservices architecture preparation