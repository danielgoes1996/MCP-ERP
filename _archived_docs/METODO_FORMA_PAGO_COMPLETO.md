# 💳 Clasificación por Método y Forma de Pago - Guía Completa

## 📋 Resumen

Sistema completo para clasificar facturas por:
- **Método de Pago** (¿CUÁNDO se paga?)
- **Forma de Pago** (¿CÓMO se paga?)

---

## 🎯 Conceptos Clave

### Método de Pago (MetodoPago)
**¿CUÁNDO se realiza el pago?**

| Código | Descripción | Uso |
|--------|-------------|-----|
| **PUE** | Pago en Una Exhibición | Pago completo al momento |
| **PPD** | Pago en Parcialidades o Diferido | Pago posterior o en partes |
| **PIP** | Pago Inicial y Parcialidades | Enganche + diferido |

### Forma de Pago (FormaPago)
**¿CÓMO se realiza el pago?**

| Código | Descripción |
|--------|-------------|
| 01 | Efectivo |
| 02 | Cheque nominativo |
| 03 | Transferencia electrónica |
| 04 | Tarjeta de crédito |
| 05 | Monedero electrónico |
| 28 | Tarjeta de débito |
| 99 | Por definir (común en PPD) |

---

## ✅ Implementación Completada

### 1. Migración de Base de Datos

**Archivo:** `migrations/add_metodo_forma_pago.sql`

```sql
-- Agregar columnas
ALTER TABLE manual_expenses
ADD COLUMN IF NOT EXISTS metodo_pago VARCHAR(3) CHECK (metodo_pago IN ('PUE', 'PPD', 'PIP')),
ADD COLUMN IF NOT EXISTS forma_pago VARCHAR(2);

-- Crear índices
CREATE INDEX IF NOT EXISTS idx_expenses_metodo_pago ON expenses(metodo_pago);
CREATE INDEX IF NOT EXISTS idx_expenses_forma_pago ON expenses(forma_pago);
```

**Aplicar migración:**
Ver instrucciones en [APPLY_PAYMENT_MIGRATION.md](APPLY_PAYMENT_MIGRATION.md)

---

### 2. Extracción desde XML

**Script:** `scripts/utilities/reprocesar_cfdis_completo.py`

Ya extrae automáticamente:
- Línea 73: `data['forma_pago'] = root.get('FormaPago')`
- Línea 74: `data['metodo_pago'] = root.get('MetodoPago')`

**Nuevas facturas**: Se extraen automáticamente al procesar XMLs

---

### 3. Actualizar Facturas Existentes

**Script:** `scripts/utilities/update_payment_methods.py`

```bash
# Ver qué se haría (simulación)
python3 scripts/utilities/update_payment_methods.py --company-id 2 --dry-run

# Aplicar cambios reales
python3 scripts/utilities/update_payment_methods.py --company-id 2

# Limitar a 10 facturas (para prueba)
python3 scripts/utilities/update_payment_methods.py --company-id 2 --limit 10
```

**Qué hace:**
1. Lee todas las facturas sin metodo_pago/forma_pago
2. Busca sus XMLs
3. Extrae los datos
4. Actualiza la BD
5. Genera reporte con distribución

---

### 4. API Endpoints

**Router:** `api/payment_methods_api.py`

Ya registrado en `main.py` (líneas 327-333)

#### Endpoints Disponibles:

##### 📊 Resumen General
```bash
GET /payment-methods/summary?company_id=2

# Con rango de fechas
GET /payment-methods/summary?company_id=2&fecha_inicio=2025-01-01&fecha_fin=2025-12-31
```

**Respuesta:**
```json
{
  "success": true,
  "metodos_pago": [
    {
      "metodo_pago": "PUE",
      "descripcion": "Pago en Una Exhibición",
      "cantidad": 45,
      "total_monto": 125000.50,
      "promedio": 2777.78
    },
    {
      "metodo_pago": "PPD",
      "descripcion": "Pago en Parcialidades o Diferido",
      "cantidad": 12,
      "total_monto": 50000.00,
      "promedio": 4166.67
    }
  ],
  "formas_pago": [
    {
      "forma_pago": "03",
      "descripcion": "Transferencia electrónica",
      "cantidad": 35,
      "total_monto": 98000.00
    }
  ],
  "totales": {
    "facturas": 57,
    "monto_total": 175000.50,
    "pagado_inmediato": {
      "cantidad": 45,
      "monto": 125000.50
    },
    "por_pagar": {
      "cantidad": 12,
      "monto": 50000.00
    }
  }
}
```

##### 💰 Facturas PPD Pendientes
```bash
GET /payment-methods/ppd-pending?company_id=2
```

**Uso:** Ver cuentas por cobrar/pagar

##### 📈 Por Método Específico
```bash
GET /payment-methods/by-method/PUE?company_id=2
GET /payment-methods/by-method/PPD?company_id=2
```

##### 💵 Análisis de Flujo de Efectivo
```bash
GET /payment-methods/cash-flow?company_id=2&fecha_inicio=2025-01-01
```

**Respuesta:**
```json
{
  "flujo_efectivo": {
    "real": {
      "monto": 125000.50,
      "facturas": 45,
      "descripcion": "Dinero ya pagado/cobrado (PUE)"
    },
    "proyectado": {
      "monto": 50000.00,
      "facturas": 12,
      "descripcion": "Dinero por pagar/cobrar (PPD)"
    }
  }
}
```

---

## 📊 Consultas SQL Útiles

### Resumen por Método de Pago
```sql
SELECT
    metodo_pago,
    COUNT(*) as cantidad,
    SUM(total) as monto_total,
    AVG(total) as promedio
FROM manual_expenses
WHERE company_id = 2
GROUP BY metodo_pago
ORDER BY cantidad DESC;
```

### Cuentas por Cobrar (PPD)
```sql
SELECT
    uuid,
    fecha,
    emisor_nombre,
    total,
    forma_pago
FROM manual_expenses
WHERE company_id = 2
  AND metodo_pago = 'PPD'
  AND sat_status = 'vigente'
ORDER BY fecha DESC;
```

### Distribución por Forma de Pago
```sql
SELECT
    forma_pago,
    CASE forma_pago
        WHEN '01' THEN 'Efectivo'
        WHEN '02' THEN 'Cheque'
        WHEN '03' THEN 'Transferencia'
        WHEN '04' THEN 'Tarjeta crédito'
        WHEN '28' THEN 'Tarjeta débito'
        WHEN '99' THEN 'Por definir'
        ELSE forma_pago
    END as descripcion,
    COUNT(*) as cantidad,
    SUM(total) as monto
FROM manual_expenses
WHERE company_id = 2
GROUP BY forma_pago
ORDER BY monto DESC;
```

### Análisis de Flujo de Efectivo
```sql
SELECT
    DATE_TRUNC('month', fecha) as mes,
    SUM(CASE WHEN metodo_pago = 'PUE' THEN total ELSE 0 END) as flujo_real,
    SUM(CASE WHEN metodo_pago = 'PPD' THEN total ELSE 0 END) as flujo_proyectado
FROM manual_expenses
WHERE company_id = 2
  AND fecha >= '2025-01-01'
GROUP BY mes
ORDER BY mes;
```

---

## 🚀 Pasos para Activar

### 1. Aplicar Migración SQL
```bash
# Opción A: Conectar a psql y ejecutar
psql -h localhost -p 5433 -U danielgoes96 -d mcp_server -f migrations/add_metodo_forma_pago.sql

# Opción B: Copiar SQL manualmente
# Ver: APPLY_PAYMENT_MIGRATION.md
```

### 2. Actualizar Facturas Existentes
```bash
# Primero en dry-run
python3 scripts/utilities/update_payment_methods.py --company-id 2 --dry-run

# Luego aplicar
python3 scripts/utilities/update_payment_methods.py --company-id 2
```

### 3. Verificar API
```bash
# Reiniciar servidor (si está corriendo)
# Se auto-recarga con --reload

# Probar endpoint
curl "http://localhost:8000/payment-methods/summary?company_id=2"
```

### 4. Procesar Nuevas Facturas
Las nuevas facturas se procesarán automáticamente con los campos:

```bash
python3 scripts/utilities/reprocesar_cfdis_completo.py --company-id 2
```

### 5. Generar Dashboard Visual
```bash
# Dashboard completo
python3 scripts/analysis/payment_methods_dashboard.py --company-id 2

# Últimos 30 días
python3 scripts/analysis/payment_methods_dashboard.py --company-id 2 --ultimos-30-dias

# Mes actual
python3 scripts/analysis/payment_methods_dashboard.py --company-id 2 --mes-actual

# Exportar a JSON
python3 scripts/analysis/payment_methods_dashboard.py --company-id 2 --export-json reporte.json
```

Ver guía completa en: [DASHBOARD_METODOS_PAGO.md](DASHBOARD_METODOS_PAGO.md)

---

## 📈 Casos de Uso

### 1. Dashboard de Cuentas por Cobrar
```bash
curl "http://localhost:8000/payment-methods/ppd-pending?company_id=2"
```

### 2. Análisis de Flujo de Efectivo Mensual
```sql
SELECT
    TO_CHAR(fecha, 'YYYY-MM') as mes,
    COUNT(*) as total_facturas,
    SUM(CASE WHEN metodo_pago = 'PUE' THEN total END) as cobrado,
    SUM(CASE WHEN metodo_pago = 'PPD' THEN total END) as por_cobrar
FROM manual_expenses
WHERE company_id = 2
GROUP BY mes
ORDER BY mes DESC
LIMIT 12;
```

### 3. Reporte de Métodos de Pago por Proveedor
```sql
SELECT
    emisor_nombre,
    metodo_pago,
    COUNT(*) as facturas,
    SUM(total) as monto
FROM manual_expenses
WHERE company_id = 2
GROUP BY emisor_nombre, metodo_pago
ORDER BY monto DESC;
```

---

## ✅ Checklist de Implementación

- [ ] Aplicar migración SQL (agregar columnas)
- [ ] Ejecutar script de actualización para facturas existentes
- [ ] Verificar que API funciona
- [ ] Probar con nuevas facturas
- [x] Dashboard visual de análisis (scripts/analysis/payment_methods_dashboard.py)

---

## 📚 Catálogos Completos SAT

### Métodos de Pago (c_MetodoPago)
- **PUE**: Pago en Una Exhibición
- **PPD**: Pago en Parcialidades o Diferido
- **PIP**: Pago Inicial y Parcialidades

### Formas de Pago (c_FormaPago)
```
01 - Efectivo
02 - Cheque nominativo
03 - Transferencia electrónica de fondos
04 - Tarjeta de crédito
05 - Monedero electrónico
06 - Dinero electrónico
08 - Vales de despensa
12 - Dación en pago
13 - Pago por subrogación
14 - Pago por consignación
15 - Condonación
17 - Compensación
23 - Novación
24 - Confusión
25 - Remisión de deuda
26 - Prescripción o caducidad
27 - A satisfacción del acreedor
28 - Tarjeta de débito
29 - Tarjeta de servicios
30 - Aplicación de anticipos
31 - Intermediario pagos
99 - Por definir
```

---

## 🎯 Beneficios

### Para Finanzas:
- ✅ Visibilidad de flujo de efectivo real vs proyectado
- ✅ Seguimiento de cuentas por cobrar/pagar
- ✅ Análisis de antigüedad de saldos

### Para Contabilidad:
- ✅ Clasificación automática de movimientos
- ✅ Distinción entre caja y cuentas por cobrar
- ✅ Reportes más precisos

### Para Operaciones:
- ✅ Dashboard de facturas pendientes
- ✅ Análisis de métodos de pago preferidos
- ✅ Optimización de flujo de efectivo

---

**Última actualización:** 2025-11-08
**Status:** ✅ Implementación completa
