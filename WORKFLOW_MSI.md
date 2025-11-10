# 🔄 Workflow de Confirmación MSI

Guía para detectar y confirmar facturas pagadas a Meses Sin Intereses (MSI)

---

## 🎯 Problema

Las facturas **PUE + Tarjeta (crédito/débito)** pueden ser:
- ✅ Pago completo inmediato
- ⚠️ Meses Sin Intereses (MSI) - requiere conciliación especial

El CFDI **NO indica** si fue MSI, por lo que se requiere **confirmación manual**.

**Importante:** MSI puede aplicar a **cualquier monto**, no solo compras grandes. Incluso una compra de $500 puede ser a 3 MSI.

---

## 📋 Workflow Mensual

### 1️⃣ Identificar Candidatos (Automático)

```bash
# Detectar facturas sospechosas de MSI
python3 scripts/analysis/detectar_msi.py --company-id 2 --mes 2025-08
```

**Resultado:**
- Lista de facturas PUE + Tarjeta + >$5,000
- Sugerencias de planes MSI (3, 6, 9, 12, 18, 24 meses)

### 2️⃣ Revisar Estado de Cuenta (Manual)

Para cada factura identificada:

1. **Abrir estado de cuenta** de la tarjeta del mes
2. **Buscar cargo** en la fecha de la factura
3. **Comparar montos:**

```
Factura:  $45,017.92
Banco:    $3,751.49  ← MSI detectado (12 meses)
          $45,017.92 ← Pago completo (NO es MSI)
```

### 3️⃣ Confirmar en el Sistema (API/Manual)

#### Opción A: Via API

```bash
# Ver facturas pendientes de confirmación
curl "http://localhost:8000/msi/pending?company_id=2"

# Confirmar como MSI
curl -X POST "http://localhost:8000/msi/confirm/123" \
  -H "Content-Type: application/json" \
  -d '{
    "es_msi": true,
    "meses_msi": 12,
    "pago_mensual_msi": 3751.49,
    "usuario_id": 1
  }'

# Confirmar como pago completo (NO MSI)
curl -X POST "http://localhost:8000/msi/confirm/123" \
  -H "Content-Type: application/json" \
  -d '{
    "es_msi": false,
    "usuario_id": 1
  }'
```

#### Opción B: Via SQL Directo

```sql
-- Confirmar como MSI
UPDATE expense_invoices
SET
    es_msi = TRUE,
    meses_msi = 12,
    pago_mensual_msi = 3751.49,
    msi_confirmado = TRUE,
    msi_confirmado_por = 1,
    msi_confirmado_fecha = NOW()
WHERE id = 123;

-- Confirmar como pago completo
UPDATE expense_invoices
SET
    es_msi = FALSE,
    msi_confirmado = TRUE,
    msi_confirmado_por = 1,
    msi_confirmado_fecha = NOW()
WHERE id = 123;
```

### 4️⃣ Registro Contable (Si es MSI)

Si confirmaste que **SÍ es MSI**, crear asiento contable:

```sql
-- Póliza Inicial (Mes 1)
DEBE:
  Activo Fijo:        $38,808.55
  IVA Acreditable:    $6,209.37
HABER:
  Bancos - Tarjeta:   $3,751.49
  Acreedores MSI:     $41,266.43

-- Pólizas Mensuales (Meses 2-12)
DEBE:
  Acreedores MSI:     $3,751.49
HABER:
  Bancos - Tarjeta:   $3,751.49
```

---

## 📊 Consultas Útiles

### Ver Facturas Pendientes de Confirmación

```bash
curl "http://localhost:8000/msi/pending?company_id=2"
```

### Ver Estadísticas MSI

```bash
curl "http://localhost:8000/msi/stats?company_id=2"
```

**Respuesta:**
```json
{
  "resumen": {
    "total_facturas_msi": 5,
    "monto_total_msi": 125000.50,
    "promedio_meses": 9.6,
    "pendientes_confirmacion": 2
  },
  "distribucion_por_meses": [
    {"meses": 6, "cantidad": 2, "monto": 45000},
    {"meses": 12, "cantidad": 3, "monto": 80000.50}
  ]
}
```

### Listar Todas las Facturas MSI

```bash
# Solo facturas confirmadas como MSI
curl "http://localhost:8000/msi/list?company_id=2&solo_msi=true"

# Todas las facturas confirmadas (MSI y no MSI)
curl "http://localhost:8000/msi/list?company_id=2"
```

### SQL: Facturas MSI Activas

```sql
SELECT
    fecha_emision,
    nombre_emisor,
    total,
    meses_msi,
    pago_mensual_msi,
    (total - pago_mensual_msi) as saldo_pendiente
FROM expense_invoices
WHERE company_id = 2
AND es_msi = TRUE
AND sat_status = 'vigente'
ORDER BY fecha_emision DESC;
```

---

## 🔧 Setup Inicial

### 1. Aplicar Migración

```bash
# Opción A: psql
psql -h localhost -p 5433 -U mcp_user -d mcp_system \
  -f migrations/add_msi_fields.sql

# Opción B: Docker
docker exec -i mcp-postgres psql -U mcp_user -d mcp_system \
  < migrations/add_msi_fields.sql
```

### 2. Registrar Router en main.py

```python
from api.msi_confirmation_api import router as msi_router

app.include_router(
    msi_router,
    prefix="/api",
    tags=["MSI"]
)
```

### 3. Verificar Endpoints

```bash
# Listar endpoints disponibles
curl "http://localhost:8000/docs"
```

Buscar sección "MSI Confirmation"

---

## 📅 Rutina Mensual Recomendada

### Día 1-5 del mes (Cierre mensual)

1. ✅ Ejecutar detector MSI del mes anterior
2. ✅ Revisar estados de cuenta
3. ✅ Confirmar todas las facturas pendientes
4. ✅ Crear pólizas contables para MSI nuevos
5. ✅ Generar reporte MSI para contadora

### Script Automatizado

```bash
#!/bin/bash
# Rutina mensual MSI

COMPANY_ID=2
MES=$(date -d "last month" +%Y-%m)

echo "🔍 Detectando MSI del mes: $MES"
python3 scripts/analysis/detectar_msi.py --company-id $COMPANY_ID --mes $MES

echo ""
echo "📋 Facturas pendientes de confirmación:"
curl "http://localhost:8000/msi/pending?company_id=$COMPANY_ID"

echo ""
echo "📊 Estadísticas MSI:"
curl "http://localhost:8000/msi/stats?company_id=$COMPANY_ID"
```

---

## ⚠️ Casos Especiales

### Caso 1: MSI con Primer Pago Diferente

Algunas tiendas cobran un monto distinto en el primer mes:

```
Factura:  $45,017.92
Mes 1:    $3,850.00  ← Primer pago mayor
Mes 2-12: $3,742.54  ← Pagos regulares
```

**Solución:** Registrar el `pago_mensual_msi` como el promedio o el pago regular.

### Caso 2: MSI + Intereses Bancarios

Si el banco cobra intereses adicionales:

```
Factura:  $45,017.92
Pago:     $3,850.00  ← Incluye intereses
```

**Solución:**
- Registrar como MSI el monto original
- Los intereses bancarios van a "Gastos Financieros"

### Caso 3: Cancelación de MSI

Si cancelas el MSI antes de completarlo:

```sql
-- Marcar como cancelado
UPDATE expense_invoices
SET es_msi = FALSE,
    observaciones = 'MSI cancelado - liquidado anticipadamente'
WHERE id = 123;
```

---

## 📈 Reportes para Contabilidad

### Reporte Mensual MSI

```sql
SELECT
    DATE_TRUNC('month', fecha_emision) as mes,
    COUNT(*) as facturas_msi,
    SUM(total) as monto_total,
    SUM(pago_mensual_msi) as pago_mensual_total
FROM expense_invoices
WHERE company_id = 2
AND es_msi = TRUE
GROUP BY mes
ORDER BY mes DESC;
```

### Cuentas por Pagar MSI

```sql
SELECT
    nombre_emisor,
    total,
    pago_mensual_msi,
    meses_msi,
    fecha_emision,
    -- Calcular meses transcurridos
    EXTRACT(MONTH FROM AGE(CURRENT_DATE, fecha_emision::date)) as meses_transcurridos,
    -- Calcular saldo pendiente
    total - (pago_mensual_msi * EXTRACT(MONTH FROM AGE(CURRENT_DATE, fecha_emision::date))) as saldo_pendiente
FROM expense_invoices
WHERE company_id = 2
AND es_msi = TRUE
AND sat_status = 'vigente'
ORDER BY saldo_pendiente DESC;
```

---

## ✅ Checklist

- [ ] Aplicar migración `add_msi_fields.sql`
- [ ] Registrar API router en `main.py`
- [ ] Probar endpoints `/msi/pending` y `/msi/stats`
- [ ] Ejecutar detector MSI primer vez
- [ ] Confirmar facturas históricas MSI
- [ ] Documentar workflow con contadora
- [ ] Establecer rutina mensual

---

**Última actualización:** 2025-11-09
**Versión:** 1.0
