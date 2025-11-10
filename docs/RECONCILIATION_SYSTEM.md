# 🔄 Sistema de Conciliación Automática

## Descripción

El sistema de conciliación automática permite emparejar transacciones bancarias con facturas (CFDIs) de manera inteligente, detectando automáticamente matches basados en:

- **Monto**: Diferencia ≤ $2.00 MXN
- **Fecha**: Diferencia ≤ 2 días
- **Company/Tenant**: Mismo contexto empresarial

## 📊 Arquitectura

### Esquema de Base de Datos

#### Nuevas Columnas en `bank_transactions`

```sql
-- Identificación única para detectar duplicados
source_hash VARCHAR(64) UNIQUE

-- Enlace con factura conciliada
reconciled_invoice_id INT (FK → expense_invoices.id)

-- Confianza de la conciliación (0.0 - 1.0)
match_confidence NUMERIC(5,4) DEFAULT 0.0

-- Estado: pending, matched, manual, reviewed
reconciliation_status VARCHAR(20) DEFAULT 'pending'

-- Usuario que confirmó manualmente
reconciled_by INT

-- Timestamp de conciliación
reconciled_at TIMESTAMP
```

### Trigger Automático: Hash SHA-256

Cada transacción obtiene automáticamente un hash único para detectar duplicados:

```sql
CREATE FUNCTION fn_generate_source_hash() RETURNS TRIGGER AS $$
BEGIN
  NEW.source_hash := encode(
    digest(
      concat_ws('|',
        transaction_date,
        description,
        amount,
        balance,
        reference,
        account_id
      ),
      'sha256'
    ),
    'hex'
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

### Vistas SQL

#### 1. `vw_reconciliation_ready`

Vista principal que une `bank_transactions` con `expense_invoices`.

**Campos clave:**

- `transaction_*`: Datos de la transacción bancaria
- `invoice_*`: Datos de la factura
- `amount_difference`: Diferencia absoluta de montos
- `days_difference`: Diferencia en días
- `match_status`: Estado calculado (REVIEWED, MANUAL_MATCH, MATCHED, AUTO_MATCH, PENDING)

**Lógica de matching:**

```sql
-- Join condition
ON ABS(ABS(bt.amount) - ei.total) <= 2
AND bt.transaction_date BETWEEN (ei.fecha_emision::DATE - INTERVAL '2 days')
                            AND (ei.fecha_emision::DATE + INTERVAL '2 days')
AND bt.company_id = ei.company_id
AND bt.tenant_id = ei.tenant_id

-- Match status
CASE
  WHEN reconciled_invoice_id IS NOT NULL AND reconciliation_status = 'reviewed'
    THEN 'REVIEWED'
  WHEN reconciled_invoice_id IS NOT NULL AND reconciliation_status = 'manual'
    THEN 'MANUAL_MATCH'
  WHEN reconciled_invoice_id IS NOT NULL
    THEN 'MATCHED'
  WHEN ABS(ABS(bt.amount) - ei.total) <= 2
       AND ABS(bt.transaction_date - ei.fecha_emision::DATE) <= 2
    THEN 'AUTO_MATCH'
  ELSE 'PENDING'
END AS match_status
```

#### 2. `vw_pending_reconciliation`

Filtra solo transacciones pendientes de conciliar.

```sql
SELECT * FROM vw_reconciliation_ready
WHERE match_status IN ('PENDING', 'AUTO_MATCH')
  AND reconciled_invoice_id IS NULL
ORDER BY transaction_date DESC;
```

#### 3. `vw_auto_match_suggestions`

Sugerencias de alta confianza para conciliación automática.

```sql
SELECT * FROM vw_reconciliation_ready
WHERE match_status = 'AUTO_MATCH'
  AND reconciled_invoice_id IS NULL
  AND invoice_id IS NOT NULL
ORDER BY match_confidence DESC, amount_difference ASC;
```

#### 4. `vw_reconciliation_stats`

Estadísticas globales de conciliación.

```sql
SELECT
  COUNT(*) AS total_transactions,
  COUNT(CASE WHEN reconciliation_status = 'matched' THEN 1 END) AS matched,
  COUNT(CASE WHEN reconciliation_status = 'manual' THEN 1 END) AS manual_matched,
  COUNT(CASE WHEN reconciliation_status = 'reviewed' THEN 1 END) AS reviewed,
  COUNT(CASE WHEN reconciliation_status = 'pending' THEN 1 END) AS pending,
  ROUND(AVG(match_confidence), 4) AS avg_confidence,
  SUM(CASE WHEN reconciliation_status != 'pending' THEN 1 ELSE 0 END)::FLOAT /
    NULLIF(COUNT(*), 0) * 100 AS reconciliation_rate
FROM bank_transactions
WHERE transaction_type = 'debit';
```

## 🚀 Instalación

### 1. Habilitar extensión pgcrypto

```bash
docker exec mcp-postgres psql -U mcp_user -d mcp_system -c "CREATE EXTENSION IF NOT EXISTS pgcrypto;"
```

### 2. Aplicar schema de conciliación

```bash
docker cp scripts/migration/add_reconciliation_schema.sql mcp-postgres:/tmp/
docker exec mcp-postgres psql -U mcp_user -d mcp_system -f /tmp/add_reconciliation_schema.sql
```

### 3. Crear vistas

```bash
docker cp scripts/migration/add_reconciliation_view.sql mcp-postgres:/tmp/
docker exec mcp-postgres psql -U mcp_user -d mcp_system -f /tmp/add_reconciliation_view.sql
```

## 📖 Uso

### Opción 1: Script Python Automático

```bash
python reconcile_auto_matches.py
```

Este script:
1. Consulta `vw_auto_match_suggestions`
2. Muestra los matches encontrados
3. Pide confirmación
4. Aplica conciliaciones automáticamente
5. Muestra estadísticas antes/después

### Opción 2: SQL Manual

#### Ver sugerencias de auto-match

```sql
SELECT
    transaction_id,
    transaction_date,
    transaction_description,
    transaction_amount,
    invoice_uuid,
    invoice_total,
    amount_difference,
    days_difference
FROM vw_auto_match_suggestions
ORDER BY amount_difference ASC
LIMIT 10;
```

#### Conciliar manualmente

```sql
UPDATE bank_transactions
SET
    reconciled_invoice_id = 123,  -- ID de la factura
    match_confidence = 1.0,
    reconciliation_status = 'manual',
    reconciled_by = 1,  -- ID del usuario
    reconciled_at = CURRENT_TIMESTAMP
WHERE id = 456;  -- ID de la transacción
```

#### Ver estadísticas

```sql
SELECT * FROM vw_reconciliation_stats;
```

### Opción 3: API Endpoints (Futuro)

```python
# En tu API FastAPI
@router.get("/api/reconciliation/suggestions")
async def get_suggestions(db: Session):
    """Obtener sugerencias de auto-match"""
    return db.execute(
        "SELECT * FROM vw_auto_match_suggestions"
    ).fetchall()

@router.post("/api/reconciliation/auto-match")
async def apply_auto_matches(db: Session):
    """Aplicar todas las sugerencias de auto-match"""
    suggestions = db.execute(
        "SELECT transaction_id, invoice_id FROM vw_auto_match_suggestions"
    ).fetchall()

    for match in suggestions:
        db.execute("""
            UPDATE bank_transactions
            SET reconciled_invoice_id = :invoice_id,
                match_confidence = 1.0,
                reconciliation_status = 'matched',
                reconciled_at = CURRENT_TIMESTAMP
            WHERE id = :transaction_id
        """, match)

    db.commit()
    return {"reconciled": len(suggestions)}

@router.get("/api/reconciliation/stats")
async def get_stats(db: Session):
    """Obtener estadísticas de conciliación"""
    return db.execute(
        "SELECT * FROM vw_reconciliation_stats"
    ).fetchone()
```

## 🔍 Queries Útiles

### Transacciones conciliadas hoy

```sql
SELECT * FROM vw_reconciliation_ready
WHERE reconciled_at::DATE = CURRENT_DATE
  AND reconciliation_status IN ('matched', 'manual', 'reviewed');
```

### Transacciones sin match

```sql
SELECT * FROM vw_reconciliation_ready
WHERE match_status = 'PENDING'
  AND invoice_id IS NULL
ORDER BY transaction_amount DESC;
```

### Matches imperfectos (diferencia > 0)

```sql
SELECT * FROM vw_reconciliation_ready
WHERE match_status = 'AUTO_MATCH'
  AND amount_difference > 0
ORDER BY amount_difference DESC;
```

### Facturas sin conciliar

```sql
SELECT
    ei.id,
    ei.uuid,
    ei.total,
    ei.fecha_emision,
    ei.rfc_emisor,
    COUNT(vr.transaction_id) as potential_matches
FROM expense_invoices ei
LEFT JOIN vw_reconciliation_ready vr ON vr.invoice_id = ei.id
WHERE NOT EXISTS (
    SELECT 1 FROM bank_transactions bt
    WHERE bt.reconciled_invoice_id = ei.id
)
GROUP BY ei.id, ei.uuid, ei.total, ei.fecha_emision, ei.rfc_emisor
ORDER BY ei.fecha_emision DESC;
```

### Auditoría de conciliaciones

```sql
SELECT
    bt.id,
    bt.transaction_date,
    bt.description,
    bt.amount,
    bt.reconciliation_status,
    bt.match_confidence,
    bt.reconciled_at,
    ei.uuid as invoice_uuid,
    ei.total as invoice_total,
    CASE
        WHEN bt.reconciled_by IS NOT NULL THEN 'Manual'
        ELSE 'Automático'
    END as reconciliation_type
FROM bank_transactions bt
LEFT JOIN expense_invoices ei ON bt.reconciled_invoice_id = ei.id
WHERE bt.reconciliation_status != 'pending'
ORDER BY bt.reconciled_at DESC;
```

## 🎯 Casos de Uso

### 1. Conciliación Diaria Automática

```bash
# Cron job diario a las 9 AM
0 9 * * * cd /path/to/project && python reconcile_auto_matches.py --auto-confirm
```

### 2. Dashboard de Conciliación

```python
# Obtener KPIs para dashboard
stats = db.execute("SELECT * FROM vw_reconciliation_stats").fetchone()

dashboard_data = {
    "total_transactions": stats['total_transactions'],
    "reconciliation_rate": stats['reconciliation_rate'],
    "pending_count": stats['pending'],
    "auto_match_available": db.execute(
        "SELECT COUNT(*) FROM vw_auto_match_suggestions"
    ).scalar()
}
```

### 3. Alertas de Transacciones sin Match

```python
# Alertar si hay transacciones > $10,000 sin conciliar por más de 7 días
unmatched = db.execute("""
    SELECT * FROM vw_reconciliation_ready
    WHERE match_status = 'PENDING'
      AND invoice_id IS NULL
      AND ABS(transaction_amount) > 10000
      AND transaction_date < CURRENT_DATE - INTERVAL '7 days'
""").fetchall()

if unmatched:
    send_alert(f"{len(unmatched)} transacciones grandes sin conciliar")
```

## 📊 Métricas y KPIs

- **Tasa de conciliación**: `reconciliation_rate` (%)
- **Confianza promedio**: `avg_confidence` (0.0 - 1.0)
- **Tiempo promedio de conciliación**: `AVG(reconciled_at - created_at)`
- **Matches automáticos vs manuales**: `matched` vs `manual_matched`

## 🔒 Seguridad

- **Unique hash**: Previene duplicados con `source_hash`
- **Audit trail**: Campos `reconciled_by` y `reconciled_at`
- **Foreign keys**: Integridad referencial con expense_invoices
- **Status tracking**: `reconciliation_status` para workflow

## 🚧 Próximas Mejoras

1. **AI-driven matching**: Usar Gemini para matches más inteligentes
2. **Fuzzy matching**: Comparar descripciones con similitud de texto
3. **Batch reconciliation**: Procesar lotes de transacciones
4. **Undo/Redo**: Deshacer conciliaciones erróneas
5. **Multi-invoice split**: Una transacción → múltiples facturas
6. **Partial matching**: Pagos parciales de facturas

## 📚 Referencias

- [PostgreSQL pgcrypto](https://www.postgresql.org/docs/current/pgcrypto.html)
- [Views en PostgreSQL](https://www.postgresql.org/docs/current/sql-createview.html)
- [Triggers en PostgreSQL](https://www.postgresql.org/docs/current/sql-createtrigger.html)
