# 📊 Dashboard de Métodos y Formas de Pago - Guía de Uso

## 🎯 Descripción

Dashboard completo para analizar la clasificación de facturas por:
- **Método de Pago** (PUE/PPD/PIP) - ¿Cuándo se paga?
- **Forma de Pago** (01-99) - ¿Cómo se paga?

Genera reportes visuales con métricas de negocio, flujo de efectivo y alertas.

---

## 📁 Ubicación

```
scripts/analysis/payment_methods_dashboard.py
```

---

## 🚀 Uso Básico

### 1. Dashboard Completo (Todas las Facturas)

```bash
python3 scripts/analysis/payment_methods_dashboard.py --company-id 2
```

### 2. Últimos 30 Días

```bash
python3 scripts/analysis/payment_methods_dashboard.py \
  --company-id 2 \
  --ultimos-30-dias
```

### 3. Mes Actual

```bash
python3 scripts/analysis/payment_methods_dashboard.py \
  --company-id 2 \
  --mes-actual
```

### 4. Rango de Fechas Personalizado

```bash
python3 scripts/analysis/payment_methods_dashboard.py \
  --company-id 2 \
  --fecha-inicio 2025-01-01 \
  --fecha-fin 2025-12-31
```

### 5. Exportar a JSON

```bash
python3 scripts/analysis/payment_methods_dashboard.py \
  --company-id 2 \
  --ultimos-30-dias \
  --export-json reporte_pago.json
```

---

## 📊 Métricas Incluidas

### 1. Resumen General
- Total de facturas
- Monto total
- Promedio por factura
- Total de proveedores

### 2. Análisis de Flujo de Efectivo
- **Flujo Real (PUE)**: Dinero ya pagado/cobrado
- **Flujo Proyectado (PPD)**: Por pagar/cobrar
- **Flujo Mixto (PIP)**: Pago inicial + parcialidades

### 3. Distribución por Método de Pago
Para cada método (PUE/PPD/PIP):
- Cantidad de facturas
- Monto total
- Monto promedio
- Porcentaje del total

### 4. Distribución por Forma de Pago
Para cada forma (Efectivo, Transferencia, etc.):
- Cantidad de facturas
- Monto total
- Monto promedio
- Porcentaje del total

### 5. Facturas PPD Pendientes
Listado de cuentas por cobrar/pagar:
- Fecha de emisión
- Proveedor
- Monto
- Días desde emisión

### 6. Top Proveedores con PPD
Los 10 proveedores con mayor monto en PPD

### 7. Tendencias Mensuales
Últimos 6 meses:
- Total facturas por mes
- Monto PUE vs PPD
- Evolución temporal

### 8. Distribución Combinada
Cruza Método + Forma de Pago:
- Ejemplo: "PUE + Transferencia"
- Top 15 combinaciones

### 9. Alertas y Recomendaciones
Sistema inteligente que detecta:
- ⚠️ Alto porcentaje de PPD
- 🚨 Facturas PPD antiguas (>90 días)
- ℹ️ Facturas sin clasificación

---

## 📈 Ejemplo de Salida

```
================================================================================
💳 DASHBOARD DE MÉTODOS Y FORMAS DE PAGO
================================================================================

📅 Periodo: 2025-01-01 → 2025-12-31
🏢 Company ID: 2

────────────────────────────────────────────────────────────────────────────────
📊 RESUMEN GENERAL
────────────────────────────────────────────────────────────────────────────────
  Total Facturas:     1,247
  Monto Total:        $12,450,789.50
  Promedio/Factura:   $9,984.23
  Total Proveedores:  87

────────────────────────────────────────────────────────────────────────────────
💰 ANÁLISIS DE FLUJO DE EFECTIVO
────────────────────────────────────────────────────────────────────────────────

  ✅ FLUJO REAL (PUE - Ya pagado/cobrado)
     Monto:     $8,950,234.00
     Facturas:  892

  ⏳ FLUJO PROYECTADO (PPD - Por pagar/cobrar)
     Monto:     $3,500,555.50
     Facturas:  355

────────────────────────────────────────────────────────────────────────────────
🎯 DISTRIBUCIÓN POR MÉTODO DE PAGO (¿CUÁNDO?)
────────────────────────────────────────────────────────────────────────────────

  Método  Descripción                          Facturas       Monto %
  ──────────────────────────────────────────────────────────────────────────────
  PUE     Pago en Una Exhibición                    892  $8,950,234.00 71.9%
  PPD     Pago en Parcialidades o Diferido          355  $3,500,555.50 28.1%

────────────────────────────────────────────────────────────────────────────────
💵 DISTRIBUCIÓN POR FORMA DE PAGO (¿CÓMO?)
────────────────────────────────────────────────────────────────────────────────

  Forma Descripción                     Facturas          Monto %
  ──────────────────────────────────────────────────────────────────
  03    Transferencia electrónica            756  $9,234,567.00 74.2%
  04    Tarjeta de crédito                   312  $2,145,890.00 17.2%
  28    Tarjeta de débito                    134    $892,345.50  7.2%
  01    Efectivo                              45    $177,987.00  1.4%

────────────────────────────────────────────────────────────────────────────────
📋 FACTURAS PPD PENDIENTES (Top 10)
────────────────────────────────────────────────────────────────────────────────

  Fecha        Emisor                           Monto   Días
  ──────────────────────────────────────────────────────────
  2025-10-15   PROVEEDOR ABC SA DE CV      $125,000.00     24
  2025-09-30   SERVICIOS XYZ               $89,500.00      39
  2025-08-20   COMERCIALIZADORA DEL SUR    $67,890.00      80

────────────────────────────────────────────────────────────────────────────────
🏪 TOP PROVEEDORES CON PPD
────────────────────────────────────────────────────────────────────────────────

  Proveedor                                  Facturas          Monto
  ──────────────────────────────────────────────────────────────────
  PROVEEDOR ABC SA DE CV                           45    $567,890.00
  SERVICIOS XYZ                                    32    $445,600.00
  COMERCIALIZADORA DEL SUR                         28    $389,450.00

────────────────────────────────────────────────────────────────────────────────
📈 TENDENCIAS MENSUALES (Últimos 6 meses)
────────────────────────────────────────────────────────────────────────────────

  Mes           Total    PUE Monto      PPD Monto
  ──────────────────────────────────────────────────
  2025-11         234  $1,567,890.00    $456,789.00
  2025-10         198  $1,234,567.00    $389,456.00
  2025-09         167    $987,654.00    $345,678.00

────────────────────────────────────────────────────────────────────────────────
⚠️  ALERTAS Y RECOMENDACIONES
────────────────────────────────────────────────────────────────────────────────

  ⚠️ Alto porcentaje de PPD
     28.1% del monto total está en PPD (por cobrar/pagar)
     💡 Revisar antigüedad de saldos pendientes

  🚨 Facturas PPD antiguas
     12 facturas PPD con más de 90 días
     💡 Gestionar cobro/pago de facturas vencidas

================================================================================
✅ Dashboard generado: 2025-11-08T14:30:45.123456
================================================================================
```

---

## 💼 Casos de Uso

### 1. Análisis de Flujo de Efectivo

**Pregunta:** ¿Cuánto dinero tengo realmente vs cuánto está pendiente?

```bash
python3 scripts/analysis/payment_methods_dashboard.py \
  --company-id 2 \
  --mes-actual
```

**Resultado:** Ver sección "ANÁLISIS DE FLUJO DE EFECTIVO"

---

### 2. Seguimiento de Cuentas por Cobrar/Pagar

**Pregunta:** ¿Qué facturas están pendientes de pago?

```bash
python3 scripts/analysis/payment_methods_dashboard.py \
  --company-id 2 \
  --ultimos-30-dias
```

**Resultado:** Ver sección "FACTURAS PPD PENDIENTES"

---

### 3. Análisis de Proveedores con Crédito

**Pregunta:** ¿Qué proveedores nos dan más crédito (PPD)?

```bash
python3 scripts/analysis/payment_methods_dashboard.py \
  --company-id 2
```

**Resultado:** Ver sección "TOP PROVEEDORES CON PPD"

---

### 4. Tendencias de Pago

**Pregunta:** ¿Cómo ha evolucionado el uso de PUE vs PPD?

```bash
python3 scripts/analysis/payment_methods_dashboard.py \
  --company-id 2 \
  --fecha-inicio 2025-01-01
```

**Resultado:** Ver sección "TENDENCIAS MENSUALES"

---

### 5. Métodos de Pago Preferidos

**Pregunta:** ¿Cómo pagamos más? (Transferencia, tarjeta, efectivo)

```bash
python3 scripts/analysis/payment_methods_dashboard.py \
  --company-id 2 \
  --ultimos-30-dias
```

**Resultado:** Ver sección "DISTRIBUCIÓN POR FORMA DE PAGO"

---

### 6. Exportar para Excel/BI

**Pregunta:** Quiero analizar los datos en Excel/Power BI

```bash
python3 scripts/analysis/payment_methods_dashboard.py \
  --company-id 2 \
  --ultimos-30-dias \
  --export-json reporte_noviembre.json
```

**Resultado:** Archivo JSON con todos los datos estructurados

---

## 🔧 Integración con Herramientas

### 1. Cron Job (Reporte Diario)

Generar reporte automático cada día a las 8 AM:

```bash
# Agregar a crontab
0 8 * * * cd /path/to/mcp-server && python3 scripts/analysis/payment_methods_dashboard.py --company-id 2 --mes-actual --export-json /path/to/reportes/$(date +\%Y\%m\%d)_pago.json
```

### 2. Script de Monitoreo

Crear alerta si hay muchas facturas PPD antiguas:

```bash
#!/bin/bash
python3 scripts/analysis/payment_methods_dashboard.py \
  --company-id 2 \
  --export-json /tmp/reporte_pago.json

# Procesar JSON y enviar alerta si hay problemas
python3 -c "
import json
with open('/tmp/reporte_pago.json') as f:
    data = json.load(f)
    alertas = data.get('alertas', [])
    for alerta in alertas:
        if alerta['tipo'] == 'danger':
            print(f\"ALERTA: {alerta['titulo']}\")
            print(f\"        {alerta['mensaje']}\")
"
```

### 3. API Endpoint Personalizado

Agregar endpoint que use el dashboard:

```python
# En api/custom_reports_api.py
from scripts.analysis.payment_methods_dashboard import calculate_payment_stats

@router.get("/custom-dashboard")
async def custom_dashboard(company_id: int):
    stats = calculate_payment_stats(company_id)
    return {"success": True, "data": stats}
```

---

## 📚 Catálogo de Alertas

### ⚠️ Warning (Advertencia)

**Alto porcentaje de PPD**
- **Condición:** Más del 30% del monto total está en PPD
- **Impacto:** Riesgo de liquidez
- **Acción:** Revisar antigüedad de saldos

### 🚨 Danger (Peligro)

**Facturas PPD antiguas**
- **Condición:** Facturas PPD con más de 90 días
- **Impacto:** Posible incobrable o morosidad
- **Acción:** Gestionar cobro/pago urgente

### ℹ️ Info (Información)

**Facturas sin clasificar**
- **Condición:** Facturas sin metodo_pago o forma_pago
- **Impacto:** Reportes incompletos
- **Acción:** Ejecutar `update_payment_methods.py`

---

## 🎨 Personalización

### Agregar Nuevas Alertas

Editar `scripts/analysis/payment_methods_dashboard.py`:

```python
# Línea ~380 - Sección de alertas

# Ejemplo: Alerta por uso excesivo de efectivo
if any(f['forma'] == '01' for f in stats["formas_pago"]):
    efectivo = next(f for f in stats["formas_pago"] if f['forma'] == '01')
    if efectivo['porcentaje_monto'] > 10:  # Más del 10% en efectivo
        alertas.append({
            "tipo": "warning",
            "titulo": "Alto uso de efectivo",
            "mensaje": f"{efectivo['porcentaje_monto']} en efectivo",
            "recomendacion": "Preferir métodos electrónicos"
        })
```

### Modificar Formato de Salida

```python
# Cambiar número de facturas PPD mostradas
for factura in stats["ppd_pendientes"][:20]:  # Cambiar de 10 a 20

# Cambiar número de top proveedores
for proveedor in stats["top_proveedores_ppd"][:10]:  # Cambiar de 5 a 10
```

---

## 📊 Estructura del JSON Exportado

```json
{
  "company_id": 2,
  "periodo": {
    "inicio": "2025-01-01",
    "fin": "2025-12-31"
  },
  "resumen_general": {
    "total_facturas": 1247,
    "monto_total": 12450789.50,
    "promedio_factura": 9984.23,
    "total_proveedores": 87
  },
  "metodos_pago": [
    {
      "metodo": "PUE",
      "descripcion": "Pago en Una Exhibición",
      "cantidad": 892,
      "monto": 8950234.00,
      "promedio": 10034.92,
      "porcentaje_cantidad": "71.5%",
      "porcentaje_monto": "71.9%"
    }
  ],
  "formas_pago": [...],
  "flujo_efectivo": {
    "real": {
      "monto": 8950234.00,
      "facturas": 892,
      "descripcion": "Ya pagado/cobrado (PUE)"
    },
    "proyectado": {
      "monto": 3500555.50,
      "facturas": 355,
      "descripcion": "Por pagar/cobrar (PPD)"
    }
  },
  "ppd_pendientes": [...],
  "tendencias_mensuales": [...],
  "top_proveedores_ppd": [...],
  "distribucion_combinada": [...],
  "alertas": [...],
  "metadata": {
    "generado_en": "2025-11-08T14:30:45.123456",
    "version": "1.0"
  }
}
```

---

## ✅ Checklist de Uso

Antes de usar el dashboard:

- [ ] Aplicar migración SQL (`migrations/add_metodo_forma_pago.sql`)
- [ ] Ejecutar script de actualización (`update_payment_methods.py`)
- [ ] Verificar que existen datos clasificados
- [ ] Probar con `--company-id` correcto

Para usar el dashboard:

- [ ] Elegir rango de fechas apropiado
- [ ] Revisar sección de alertas
- [ ] Exportar a JSON si necesitas análisis adicional
- [ ] Documentar hallazgos importantes

---

## 🔍 Troubleshooting

### Error: "No module named 'core.shared.unified_db_adapter'"

**Solución:** Ejecutar desde directorio raíz del proyecto:

```bash
cd /Users/danielgoes96/Desktop/mcp-server
python3 scripts/analysis/payment_methods_dashboard.py --company-id 2
```

### Error: "column 'metodo_pago' does not exist"

**Solución:** Aplicar migración SQL:

```bash
psql -h localhost -p 5433 -U danielgoes96 -d mcp_server \
  -f migrations/add_metodo_forma_pago.sql
```

### Todos los valores en 0

**Solución:** Ejecutar script de actualización:

```bash
python3 scripts/utilities/update_payment_methods.py --company-id 2
```

### Error de conexión a base de datos

**Solución:** Verificar que PostgreSQL está corriendo:

```bash
docker ps | grep postgres
```

---

## 📖 Referencias

- **Migración SQL:** [migrations/add_metodo_forma_pago.sql](migrations/add_metodo_forma_pago.sql)
- **Script de Actualización:** [scripts/utilities/update_payment_methods.py](scripts/utilities/update_payment_methods.py)
- **API Endpoints:** [api/payment_methods_api.py](api/payment_methods_api.py)
- **Documentación Completa:** [METODO_FORMA_PAGO_COMPLETO.md](METODO_FORMA_PAGO_COMPLETO.md)

---

## 🎯 Próximos Pasos

1. **Aplicar migración** si aún no lo has hecho
2. **Actualizar facturas existentes** con el script
3. **Ejecutar dashboard** para ver resultados
4. **Configurar cron job** para reportes automáticos
5. **Integrar con herramientas BI** si es necesario

---

**Última actualización:** 2025-11-08
**Versión:** 1.0
**Status:** ✅ Listo para uso
