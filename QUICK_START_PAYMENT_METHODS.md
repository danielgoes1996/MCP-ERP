# 🚀 Quick Start - Métodos y Formas de Pago

Guía rápida para empezar a usar la clasificación de facturas por método y forma de pago.

---

## ⚡ Pasos Rápidos

### 1️⃣ Aplicar Migración (Solo una vez)

```bash
# Opción A: Desde psql
psql -h localhost -p 5433 -U danielgoes96 -d mcp_server \
  -f migrations/add_metodo_forma_pago.sql

# Opción B: Copiar y pegar SQL manualmente
# Ver: migrations/add_metodo_forma_pago.sql
```

### 2️⃣ Actualizar Facturas Existentes

```bash
# Primero: Ver qué haría (dry-run)
python3 scripts/utilities/update_payment_methods.py --company-id 2 --dry-run

# Luego: Aplicar cambios
python3 scripts/utilities/update_payment_methods.py --company-id 2
```

### 3️⃣ Ver Dashboard

```bash
# Dashboard completo
python3 scripts/analysis/payment_methods_dashboard.py --company-id 2

# Mes actual
python3 scripts/analysis/payment_methods_dashboard.py --company-id 2 --mes-actual
```

### 4️⃣ Usar API

```bash
# Resumen general
curl "http://localhost:8000/payment-methods/summary?company_id=2"

# Facturas PPD pendientes
curl "http://localhost:8000/payment-methods/ppd-pending?company_id=2"

# Análisis de flujo
curl "http://localhost:8000/payment-methods/cash-flow?company_id=2"
```

---

## 📊 Qué Puedo Consultar

### Flujo de Efectivo
**Pregunta:** ¿Cuánto dinero tengo realmente vs cuánto está pendiente?

```bash
python3 scripts/analysis/payment_methods_dashboard.py --company-id 2 --mes-actual
```

Verás:
- ✅ **Flujo Real (PUE)**: Dinero ya pagado/cobrado
- ⏳ **Flujo Proyectado (PPD)**: Por pagar/cobrar

### Cuentas por Cobrar/Pagar
**Pregunta:** ¿Qué facturas están pendientes de pago?

```bash
curl "http://localhost:8000/payment-methods/ppd-pending?company_id=2"
```

### Métodos de Pago Más Usados
**Pregunta:** ¿Pagamos más en efectivo, transferencia o tarjeta?

```bash
python3 scripts/analysis/payment_methods_dashboard.py --company-id 2 --ultimos-30-dias
```

---

## 🎯 Conceptos Básicos

### Método de Pago (¿CUÁNDO se paga?)
- **PUE**: Pago inmediato (al momento)
- **PPD**: Pago diferido (crédito, a futuro)
- **PIP**: Enganche + parcialidades

### Forma de Pago (¿CÓMO se paga?)
- **01**: Efectivo
- **03**: Transferencia
- **04**: Tarjeta de crédito
- **28**: Tarjeta de débito
- **99**: Por definir

---

## 🔧 Comandos Útiles

### Dashboard

```bash
# Todo el historial
python3 scripts/analysis/payment_methods_dashboard.py --company-id 2

# Últimos 30 días
python3 scripts/analysis/payment_methods_dashboard.py --company-id 2 --ultimos-30-dias

# Mes actual
python3 scripts/analysis/payment_methods_dashboard.py --company-id 2 --mes-actual

# Rango personalizado
python3 scripts/analysis/payment_methods_dashboard.py \
  --company-id 2 \
  --fecha-inicio 2025-01-01 \
  --fecha-fin 2025-12-31

# Exportar a JSON
python3 scripts/analysis/payment_methods_dashboard.py \
  --company-id 2 \
  --export-json reporte.json
```

### API Endpoints

```bash
# Resumen con todas las métricas
curl "http://localhost:8000/payment-methods/summary?company_id=2"

# Solo facturas PPD pendientes
curl "http://localhost:8000/payment-methods/ppd-pending?company_id=2"

# Facturas PUE
curl "http://localhost:8000/payment-methods/by-method/PUE?company_id=2"

# Facturas PPD
curl "http://localhost:8000/payment-methods/by-method/PPD?company_id=2"

# Análisis de flujo de efectivo
curl "http://localhost:8000/payment-methods/cash-flow?company_id=2"

# Con rango de fechas
curl "http://localhost:8000/payment-methods/summary?company_id=2&fecha_inicio=2025-01-01&fecha_fin=2025-12-31"
```

### Consultas SQL Directas

```sql
-- Resumen por método
SELECT
    metodo_pago,
    COUNT(*) as cantidad,
    SUM(total) as monto
FROM expenses
WHERE company_id = 2
GROUP BY metodo_pago;

-- Facturas PPD pendientes
SELECT
    fecha,
    emisor_nombre,
    total
FROM expenses
WHERE company_id = 2
  AND metodo_pago = 'PPD'
  AND sat_status = 'vigente'
ORDER BY fecha DESC;

-- Flujo de efectivo mensual
SELECT
    TO_CHAR(fecha, 'YYYY-MM') as mes,
    SUM(CASE WHEN metodo_pago = 'PUE' THEN total END) as pue,
    SUM(CASE WHEN metodo_pago = 'PPD' THEN total END) as ppd
FROM expenses
WHERE company_id = 2
GROUP BY mes
ORDER BY mes DESC;
```

---

## 📁 Archivos Importantes

### Scripts
- `scripts/utilities/update_payment_methods.py` - Actualizar facturas existentes
- `scripts/analysis/payment_methods_dashboard.py` - Dashboard visual

### API
- `api/payment_methods_api.py` - Endpoints REST

### Migración
- `migrations/add_metodo_forma_pago.sql` - Agregar columnas a BD

### Documentación
- `METODO_FORMA_PAGO_COMPLETO.md` - Guía completa
- `DASHBOARD_METODOS_PAGO.md` - Guía del dashboard
- `QUICK_START_PAYMENT_METHODS.md` - Esta guía

---

## ⚠️ Troubleshooting

### "column 'metodo_pago' does not exist"
→ Aplicar migración SQL (paso 1)

### "No se encontraron facturas para actualizar"
→ Verificar que hay XMLs en las carpetas correctas

### Todos los valores en 0
→ Ejecutar script de actualización (paso 2)

### Error de conexión a BD
→ Verificar que PostgreSQL está corriendo:
```bash
docker ps | grep postgres
```

---

## 📚 Documentación Completa

Para información detallada, ver:
- [METODO_FORMA_PAGO_COMPLETO.md](METODO_FORMA_PAGO_COMPLETO.md) - Implementación completa
- [DASHBOARD_METODOS_PAGO.md](DASHBOARD_METODOS_PAGO.md) - Guía del dashboard
- [APPLY_PAYMENT_MIGRATION.md](APPLY_PAYMENT_MIGRATION.md) - Aplicar migración

---

## ✅ Checklist de Primera Vez

- [ ] 1. Aplicar migración SQL
- [ ] 2. Ejecutar update_payment_methods.py con --dry-run
- [ ] 3. Ejecutar update_payment_methods.py sin dry-run
- [ ] 4. Verificar con dashboard: `--mes-actual`
- [ ] 5. Probar API: `/payment-methods/summary`
- [ ] 6. Listo para usar

---

**Última actualización:** 2025-11-08
**Versión:** 1.0
