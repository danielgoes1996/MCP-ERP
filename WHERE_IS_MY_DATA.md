# ¿Dónde Está Mi Data?

## Base de Datos Principal

**TODO está aquí**: PostgreSQL en Docker

```bash
# Ver tus transacciones bancarias
docker exec mcp-postgres psql -U mcp_user -d mcp_system \
  -c "SELECT COUNT(*) FROM bank_transactions;"

# Ver tus estados de cuenta
docker exec mcp-postgres psql -U mcp_user -d mcp_system \
  -c "SELECT * FROM bank_statements;"
```

## Conexión

- **Host**: Docker container `mcp-postgres`
- **Puerto**: 5432
- **Database**: `mcp_system`
- **Usuario**: `mcp_user`
- **Password**: `changeme`

## Regla Simple

✅ **TODO dato persistente** → PostgreSQL (Docker)
✅ **Cache temporal** → SQLite (`unified_mcp_system.db`)
❌ **NO uses** localhost PostgreSQL (puerto 5432) - usa Docker

## Verificación Rápida

```bash
# ¿Cuántas transacciones tengo?
docker exec mcp-postgres psql -U mcp_user -d mcp_system \
  -c "SELECT
    (SELECT COUNT(*) FROM bank_transactions) as total_transacciones,
    (SELECT COUNT(*) FROM bank_transactions WHERE transaction_class IS NOT NULL) as enriquecidas;"

# ¿Cuántos estados de cuenta?
docker exec mcp-postgres psql -U mcp_user -d mcp_system \
  -c "SELECT id, file_name, transaction_count FROM bank_statements;"
```

## Fin

No busques en otro lado. Todo está en Docker PostgreSQL.
