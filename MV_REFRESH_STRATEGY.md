## 🔄 Estrategia Híbrida de Refresco de Materialized Views

**Problema**: "Cliente paga en cpg_pos → ¿Cuándo aparece en dashboard del CEO?"

**Solución**: Sistema híbrido de 3 niveles con monitoreo completo

---

## 📊 Análisis de Opciones

| Estrategia | Latencia | Performance | Complejidad | Costo | Recomendado |
|------------|----------|-------------|-------------|-------|-------------|
| **CRON nocturno** | 24 horas | ✅ Alta | ✅ Baja | ✅ $0 | ❌ Muy lento |
| **Trigger AFTER INSERT** | <1 segundo | ❌ Baja | ❌ Alta | ❌ $$ | ❌ No escala |
| **On-Demand** | Variable | ✅ Alta | ✅ Media | ✅ $ | ⚠️ Solo para reportes |
| **HÍBRIDA** ⭐ | 5-60 min | ✅ Alta | ✅ Media | ✅ $ | ✅ **GANADOR** |

---

## 🎯 Estrategia Implementada: Híbrida de 3 Niveles

```
┌─────────────────────────────────────────────────────────────┐
│  NIVEL 1: CRON Base (Cada hora)                            │
│  ├─ Garantiza que MV nunca esté >60 min desactualizada     │
│  ├─ Corre incluso si no hay actividad                      │
│  └─ Costo: $0 (built-in PostgreSQL)                        │
└─────────────────────────────────────────────────────────────┘
                            ↓ +
┌─────────────────────────────────────────────────────────────┐
│  NIVEL 2: Eventos de Alto Impacto (Cada 5 min)            │
│  ├─ Trigger en transacciones >$10k MXN                     │
│  ├─ Worker procesa cola cada 5 minutos                     │
│  └─ Latencia: 5-10 minutos típico                          │
└─────────────────────────────────────────────────────────────┘
                            ↓ +
┌─────────────────────────────────────────────────────────────┐
│  NIVEL 3: On-Demand (Manual)                               │
│  ├─ API endpoint: POST /api/v1/mv/refresh                 │
│  ├─ Para reportes urgentes del CEO                         │
│  └─ Latencia: <5 segundos                                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔧 Componentes Implementados

### 1. Tracking de Actualización
**Tabla**: `mv_refresh_log`

Registra cada refresh con:
- Tiempo de ejecución
- Trigger type (cron/event/manual)
- Quién lo disparó
- Filas afectadas
- Errores si los hubo

```sql
SELECT * FROM mv_refresh_log ORDER BY created_at DESC LIMIT 5;

 id | view_name                  | duration_ms | status    | trigger_type
----+----------------------------+-------------+-----------+--------------
 42 | universal_transactions_mv  | 1234        | completed | cron
 41 | universal_transactions_mv  | 987         | completed | event
 40 | universal_transactions_mv  | 2345        | completed | manual
```

### 2. Función de Refresco con Logging
**Función**: `refresh_universal_transactions_logged(trigger_type, triggered_by)`

```sql
-- Manual refresh
SELECT * FROM refresh_universal_transactions_logged('manual', 'ceo@company.com');

-- Resultado:
-- refresh_id | duration_ms | rows_affected | status
-- 43         | 1456        | 12543         | completed
```

### 3. Health Check
**Función**: `mv_health_check()`

Verifica frescura de la vista:
```sql
SELECT * FROM mv_health_check();

-- view_name                  | last_refresh        | age_minutes | needs_refresh
-- universal_transactions_mv  | 2025-01-04 10:30:00 | 25          | false
```

### 4. Sistema de Eventos
**Tabla**: `mv_refresh_triggers`

Para transacciones grandes:
```sql
-- Automático cuando monto_total >= $10,000 MXN
INSERT INTO cpg_consignment (monto_total, ...) VALUES (50000, ...);

-- Trigger automático registra:
INSERT INTO mv_refresh_triggers (priority = 'critical', refresh_requested = TRUE);

-- Worker procesa cada 5 min:
SELECT process_pending_mv_refreshes();
```

### 5. API On-Demand
**Endpoint**: `POST /api/v1/mv/refresh/universal-transactions`

```bash
# CEO va a presentar reporte en 5 minutos
curl -X POST "http://localhost:8001/api/v1/mv/refresh/universal-transactions?force=true" \
  -H "Authorization: Bearer CEO_TOKEN"

# Response:
{
  "success": true,
  "refreshed": true,
  "duration_ms": 1234,
  "rows_affected": 12543,
  "message": "View refreshed successfully in 1234ms"
}
```

---

## 📅 Configuración de CRON Jobs

### Opción 1: pg_cron (Recomendado)

```sql
-- Instalar extensión
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- Job cada hora (base)
SELECT cron.schedule(
    'refresh-universal-transactions-hourly',
    '0 * * * *',
    $$SELECT refresh_universal_transactions_logged('cron', 'hourly_job')$$
);

-- Job más frecuente en horario laboral
SELECT cron.schedule(
    'refresh-universal-transactions-frequent',
    '*/15 9-18 * * 1-5',  -- Cada 15min, 9am-6pm, Lun-Vie
    $$SELECT refresh_universal_transactions_logged('cron', 'frequent_job')$$
);

-- Worker de eventos (cada 5 min)
SELECT cron.schedule(
    'process-mv-refresh-events',
    '*/5 * * * *',
    $$SELECT process_pending_mv_refreshes()$$
);
```

### Opción 2: Sistema Cron del OS

```bash
# En crontab
0 * * * * psql -U mcp_user -d mcp_system -c "SELECT refresh_universal_transactions_logged('cron', 'system_cron')"
```

### Opción 3: Python APScheduler

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

async def refresh_mv():
    execute_query("SELECT refresh_universal_transactions_logged('cron', 'python_scheduler')")

scheduler.add_job(refresh_mv, 'interval', hours=1)
scheduler.start()
```

---

## 📈 Métricas y Monitoreo

### Vista de Métricas
```sql
SELECT * FROM mv_refresh_metrics;

 hour                | total_refreshes | successful | failed | avg_duration_ms
---------------------+-----------------+------------+--------+-----------------
 2025-01-04 10:00:00 | 12              | 12         | 0      | 1234
 2025-01-04 09:00:00 | 15              | 14         | 1      | 2345
```

### Dashboard de Freshness

```bash
# Health check
GET /api/v1/mv/health/universal-transactions

# Response:
{
  "view_name": "universal_transactions_mv",
  "last_refresh": "2025-01-04T10:30:00",
  "age_minutes": 25,
  "freshness": "fresh",  # fresh | stale | very_stale
  "rows_count": 12543,
  "needs_refresh": false,
  "recommendation": "View is fresh. No action needed."
}
```

### Historial de Refreshes

```bash
# Últimas 24 horas
GET /api/v1/mv/metrics/refresh-history?hours=24

# Response:
{
  "stats": {
    "total_refreshes": 25,
    "successful": 24,
    "failed": 1,
    "success_rate": 96.0,
    "avg_duration_ms": 1456,
    "max_duration_ms": 3456
  },
  "history": [...]
}
```

---

## 🎯 Casos de Uso

### Caso 1: Operación Normal (CRON)
```
09:00 - CRON ejecuta refresh → MV actualizada
10:00 - CRON ejecuta refresh → MV actualizada
11:00 - CRON ejecuta refresh → MV actualizada
...
CEO abre dashboard a las 11:30 → Datos con max 30 min de antigüedad ✅
```

### Caso 2: Transacción Grande (Evento)
```
10:15 - Cliente paga $50,000 MXN en consignación
10:15 - Trigger registra evento en mv_refresh_triggers (priority='critical')
10:20 - Worker ejecuta process_pending_mv_refreshes()
10:20 - MV refrescada automáticamente
10:25 - CEO ve la transacción en dashboard ✅ (Latencia: 10 minutos)
```

### Caso 3: Reporte Urgente (On-Demand)
```
14:55 - CEO va a presentar a inversionistas en 5 minutos
14:55 - CFO dispara: POST /api/v1/mv/refresh?force=true
14:56 - MV refrescada (1 segundo de ejecución)
15:00 - Presentación con datos actualizados ✅
```

---

## ⚠️ Consideraciones Importantes

### Performance

**Tiempo de ejecución típico**:
- 10,000 transacciones: ~1 segundo
- 100,000 transacciones: ~5 segundos
- 1,000,000 transacciones: ~30 segundos

**Impacto en DB**:
- `REFRESH MATERIALIZED VIEW CONCURRENTLY` no bloquea lecturas
- Lock exclusivo solo al final (swap de índices)
- Compatible con operaciones en producción

### Costos

**CRON cada hora**:
- 24 refreshes/día x 30 días = 720 refreshes/mes
- Tiempo total: 720 x 1.5 seg = 18 minutos CPU/mes
- Costo: Negligible

**Eventos**:
- ~50 transacciones grandes/día = 1,500/mes
- Procesadas en batches de 5 min
- Refreshes reales: ~100/mes (batching eficiente)
- Costo adicional: Mínimo

### Escalabilidad

**¿Qué pasa cuando crecemos?**

| Escenario | Transacciones | Refresh Time | Frecuencia CRON | Latencia Max |
|-----------|---------------|--------------|-----------------|--------------|
| Startup (actual) | 10k | 1 seg | 1 hora | 60 min |
| Growth (6 meses) | 100k | 5 seg | 30 min | 30 min |
| Scale (1 año) | 500k | 15 seg | 15 min | 15 min |
| Enterprise (2 años) | 2M | 45 seg | 5 min | 5 min |

**Optimizaciones futuras**:
- Partitioning de MV por fecha
- Incremental refresh (solo últimas 24h)
- Caching de queries frecuentes

---

## 🔒 Seguridad y Permisos

### Quién Puede Disparar Refreshes

```python
# En API endpoint
@router.post("/mv/refresh")
async def refresh(user_info: dict = Depends(get_current_user_info)):
    # Solo admins o CFO
    if user_info.get('role') not in ['admin', 'cfo']:
        raise HTTPException(403, "Insufficient permissions")

    # Proceder con refresh...
```

### Rate Limiting

```python
# Máximo 10 refreshes manuales por hora
from slowapi import Limiter

limiter = Limiter(key_func=get_remote_address)

@limiter.limit("10/hour")
@router.post("/mv/refresh")
async def refresh(...):
    ...
```

---

## 📊 SLA (Service Level Agreement)

### Freshness Guarantee

| Tipo de Dato | Freshness SLA | Método |
|--------------|---------------|--------|
| **Transacciones normales** | <60 minutos | CRON cada hora |
| **Transacciones >$10k** | <10 minutos | Eventos |
| **Reportes críticos** | <5 segundos | On-demand |

### Availability

- **Target**: 99.9% uptime para MV
- **Monitoring**: Alertas si refresh falla 2 veces consecutivas
- **Fallback**: Si MV falla, queries directas a tablas fuente

---

## 🧪 Testing de la Estrategia

```bash
# 1. Test CRON
psql -c "SELECT refresh_universal_transactions_logged('test', 'manual_test')"

# 2. Test Evento
psql -c "
    INSERT INTO cpg_consignment (monto_total, ...) VALUES (50000, ...);
    SELECT process_pending_mv_refreshes();
"

# 3. Test On-Demand
curl -X POST "http://localhost:8001/api/v1/mv/refresh?force=true"

# 4. Verificar health
curl "http://localhost:8001/api/v1/mv/health/universal-transactions"
```

---

## 📈 Roadmap de Mejoras

### Q1 2025 (Actual)
- [x] Estrategia híbrida implementada
- [x] Logging completo
- [x] API on-demand
- [ ] Monitoreo en Grafana

### Q2 2025
- [ ] Incremental refresh (solo delta)
- [ ] Partitioning por fecha
- [ ] Cache de queries comunes

### Q3 2025
- [ ] Machine Learning para predecir cuándo refrescar
- [ ] Auto-scaling de frecuencia según carga
- [ ] Real-time streaming (alternativa a batch)

---

## ✅ Checklist de Deployment

Antes de ir a producción:

- [ ] Migración 064 aplicada
- [ ] pg_cron instalado y configurado
- [ ] Jobs de CRON programados
- [ ] Worker de eventos corriendo
- [ ] API on-demand testeada
- [ ] Monitoring configurado (logs, métricas)
- [ ] Alertas configuradas (failures, slowness)
- [ ] Documentación compartida con equipo
- [ ] Runbook para troubleshooting

---

## 🚨 Troubleshooting

### Problema: MV no se actualiza

**Diagnóstico**:
```sql
-- Ver últimos refreshes
SELECT * FROM mv_refresh_log ORDER BY created_at DESC LIMIT 10;

-- Ver errores
SELECT * FROM mv_refresh_log WHERE status = 'failed';

-- Ver jobs de cron
SELECT * FROM cron.job;
```

**Solución**:
```sql
-- Refresh manual inmediato
SELECT refresh_universal_transactions_logged('manual', 'troubleshoot');
```

### Problema: Refresh muy lento

**Diagnóstico**:
```sql
-- Ver tiempos de ejecución
SELECT
    AVG(refresh_duration_ms),
    MAX(refresh_duration_ms),
    COUNT(*)
FROM mv_refresh_log
WHERE status = 'completed'
  AND refresh_started_at >= NOW() - INTERVAL '24 hours';
```

**Solución**:
- Verificar índices en tablas fuente
- Considerar partitioning
- Limitar scope de vista (ej: solo últimos 90 días)

---

**Resultado**: CEO nunca ve datos viejos. Sistema escalable y monitoreado. ✅
