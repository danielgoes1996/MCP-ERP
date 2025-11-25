# 📊 Base de Datos PostgreSQL - ContaFlow MCP System

> **✅ MIGRACIÓN COMPLETADA** - Sistema 100% en PostgreSQL desde el 9 de noviembre de 2025
>
> Ver [POSTGRESQL_MIGRATION_COMPLETE.md](POSTGRESQL_MIGRATION_COMPLETE.md) para detalles completos

---

## 🎯 Estado Actual

**Motor**: PostgreSQL 16 (Alpine)
**Host**: 127.0.0.1:5433
**Database**: mcp_system
**Container**: mcp-postgres (Docker)
**Estado**: ✅ Running (healthy)

---

## 📋 Estadísticas

```sql
Total de tablas:      43
Usuarios activos:     11
Tenants:              1
Extensiones:          uuid-ossp, pg_trgm, btree_gin
```

---

## 🔗 Conexión

### Docker Compose

```yaml
services:
  db:
    image: postgres:16-alpine
    container_name: mcp-postgres
    ports:
      - "5433:5432"
    environment:
      POSTGRES_DB: mcp_system
      POSTGRES_USER: mcp_user
      POSTGRES_PASSWORD: changeme
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U mcp_user -d mcp_system"]
      interval: 10s
      timeout: 5s
      retries: 5
```

### Variables de Entorno

```bash
USE_POSTGRESQL=true
POSTGRES_DSN=postgresql://mcp_user:changeme@127.0.0.1:5433/mcp_system
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5433
POSTGRES_DB=mcp_system
POSTGRES_USER=mcp_user
POSTGRES_PASSWORD=changeme
```

### Conexión Directa

```bash
# CLI (psql)
docker exec -it mcp-postgres psql -U mcp_user -d mcp_system

# Python (usando adapter)
from core.database import pg_sync_adapter as sqlite3
conn = sqlite3.connect()  # Conecta a PostgreSQL automáticamente

# Python (psycopg2 directo)
import psycopg2
conn = psycopg2.connect(
    host="127.0.0.1",
    port=5433,
    database="mcp_system",
    user="mcp_user",
    password="changeme"
)
```

### PgAdmin Web UI

```
URL:      http://localhost:5050
Email:    admin@mcp.local
Password: admin
```

---

## 📁 Tablas Principales (43 total)

### 🔐 Autenticación y Usuarios

1. **tenants** - Multi-tenancy
2. **users** - Usuarios del sistema
3. **companies** - Empresas/compañías
4. **refresh_tokens** - Tokens de sesión

### 💰 Gastos y Fiscal

5. **expenses** - Gastos principales
6. **expense_invoices** - Facturas de gastos
7. **expense_action_audit** - Auditoría de acciones
8. **expense_action_notifications** - Notificaciones
9. **expense_action_rules** - Reglas de acción
10. **expense_completion_analytics** - Analytics de completado
11. **expense_completion_history** - Historial de completado
12. **expense_completion_patterns** - Patrones de completado
13. **expense_completion_rules** - Reglas de completado
14. **expense_field_changes** - Cambios de campos
15. **expense_field_priorities** - Prioridades de campos
16. **expense_non_reconciliation** - No conciliados

### 🏦 Conciliación Bancaria

17. **bank_statements** - Estados de cuenta
18. **bank_transactions** - Transacciones bancarias
19. **payment_accounts** - Cuentas de pago

### 📄 Procesamiento de Facturas

20. **merchants** - Comerciantes/proveedores
21. **bulk_invoice_batches** - Lotes de facturas
22. **bulk_invoice_batch_items** - Items de lotes
23. **bulk_processing_analytics** - Analytics de procesamiento
24. **bulk_processing_performance** - Performance de procesamiento
25. **bulk_processing_rules** - Reglas de procesamiento

### 🤖 Automatización

26. **automation_templates** - Plantillas de automatización
27. **web_automation_engines** - Motores de automatización web
28. **rpa_portal_templates** - Plantillas de portales RPA

### 🇲🇽 SAT (Sistema de Administración Tributaria)

29. **sat_download_logs** - Logs de descarga SAT
30. **sat_efirma_credentials** - Credenciales e.firma
31. **sat_invoice_mapping** - Mapeo de facturas SAT
32. **sat_packages** - Paquetes SAT
33. **sat_requests** - Solicitudes SAT

### 📊 Analytics y Reportes

34. **non_reconciliation_analytics** - Analytics de no conciliación
35. **non_reconciliation_history** - Historial
36. **non_reconciliation_notifications** - Notificaciones
37. **non_reconciliation_escalation_rules** - Reglas de escalación
38. **non_reconciliation_reason_codes** - Códigos de razón

### ⚙️ Sistema

39. **audit_trail** - Trazabilidad de cambios
40. **schema_versions** - Control de versiones de schema
41. **table_comments** - Comentarios de tablas
42. **llm_model_configs** - Configuración de modelos LLM
43. **user_completion_preferences** - Preferencias de usuario

---

## 🔧 Extensiones Instaladas

```sql
-- UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Text search (trigram matching)
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- GIN indexes optimization
CREATE EXTENSION IF NOT EXISTS "btree_gin";
```

---

## 🚀 Queries Comunes

### Usuarios

```sql
-- Listar todos los usuarios
SELECT id, email, full_name, role, created_at
FROM users
WHERE is_active = true
ORDER BY created_at DESC;

-- Buscar usuarios por email (con índice trigram)
SELECT * FROM users
WHERE email ILIKE '%john%';
```

### Gastos

```sql
-- Gastos recientes
SELECT e.id, e.description, e.amount, e.created_at,
       u.email as created_by
FROM manual_expenses e
LEFT JOIN users u ON e.user_id = u.id
WHERE e.created_at >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY e.created_at DESC
LIMIT 100;

-- Gastos por estado
SELECT status, COUNT(*) as count, SUM(amount) as total
FROM manual_expenses
GROUP BY status;
```

### Facturas SAT

```sql
-- Facturas recientes del SAT
SELECT uuid, rfc_emisor, total, fecha_emision
FROM sat_invoice_mapping
WHERE fecha_emision >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY fecha_emision DESC;
```

---

## 📈 Optimizaciones

### Índices Recomendados

```sql
-- Full-text search en descripciones de gastos
CREATE INDEX idx_expenses_description_gin
ON expenses USING gin(to_tsvector('spanish', description));

-- Búsqueda por rango de fechas
CREATE INDEX idx_expenses_created_at_brin
ON expenses USING brin(created_at);

-- Búsqueda por usuario y estado
CREATE INDEX idx_expenses_user_status
ON expenses(user_id, status)
WHERE is_active = true;
```

### Mantenimiento

```sql
-- Vacuum y analyze
VACUUM ANALYZE expenses;

-- Reindex
REINDEX TABLE manual_expenses;

-- Estadísticas de tabla
SELECT
    schemaname,
    tablename,
    n_live_tup AS rows,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_stat_user_tables
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

---

## 🔒 Seguridad

### Cambiar Contraseñas

```sql
-- PostgreSQL
ALTER USER mcp_user WITH PASSWORD 'nueva_contraseña_segura';
```

### Backup

```bash
# Backup completo
docker exec mcp-postgres pg_dump -U mcp_user -d mcp_system -F c -f /backups/mcp_system_$(date +%Y%m%d).dump

# Restore
docker exec -i mcp-postgres pg_restore -U mcp_user -d mcp_system /backups/mcp_system_20251109.dump
```

---

## 🐛 Troubleshooting

### Verificar Estado

```bash
# Docker container status
docker ps | grep mcp-postgres

# Logs
docker logs mcp-postgres --tail 50

# Healthcheck
docker exec mcp-postgres pg_isready -U mcp_user -d mcp_system
```

### Conexión

```bash
# Test connection
docker exec mcp-postgres psql -U mcp_user -d mcp_system -c "SELECT version();"

# Check active connections
docker exec mcp-postgres psql -U mcp_user -d mcp_system -c "
SELECT count(*), state
FROM pg_stat_activity
WHERE datname = 'mcp_system'
GROUP BY state;
"
```

---

## 📚 Referencias

- [PostgreSQL Documentation](https://www.postgresql.org/docs/16/)
- [Docker PostgreSQL](https://hub.docker.com/_/postgres)
- [PgAdmin Documentation](https://www.pgadmin.org/docs/)
- [psycopg2 Documentation](https://www.psycopg.org/docs/)

---

## 📝 Documentos Relacionados

- [POSTGRESQL_MIGRATION_COMPLETE.md](POSTGRESQL_MIGRATION_COMPLETE.md) - Reporte de migración completo
- [ESTRUCTURA_BASE_DATOS.md](ESTRUCTURA_BASE_DATOS.md) - Documentación detallada del schema (legacy SQLite)
- [docker-compose.yml](docker-compose.yml) - Configuración Docker
- [.env](.env) - Variables de entorno

---

*Última actualización: 9 de noviembre de 2025*
*Documentado por: Claude Code (Anthropic)*
