# 📘 Guía: Procesar Estados de Cuenta de Nuevos Meses

**Última actualización:** 2025-11-09

Esta guía explica cómo evitar los errores comunes al procesar estados de cuenta de nuevos meses.

---

## 🚫 Errores Comunes Encontrados

### 1. Error de Conexión a Base de Datos
```
❌ psycopg2.OperationalError: role "postgres" does not exist
```

**Causa:** Usar credenciales incorrectas

**Solución:** Siempre importar desde `core.shared.db_config`
```python
from core.shared.db_config import get_connection, POSTGRES_CONFIG
conn = get_connection()
```

---

### 2. Error de Nombre de Columna
```
❌ psycopg2.errors.UndefinedColumn: column "emisor_nombre" does not exist
```

**Causa:** Usar nombres de columna incorrectos

**Solución:** Usar el esquema documentado
```python
# ❌ INCORRECTO
emisor_nombre

# ✅ CORRECTO
nombre_emisor
```

**Consultar columnas disponibles:**
```python
from core.shared.db_config import get_table_columns
columns = get_table_columns('expense_invoices')
print(columns)
```

---

### 3. Error de String Demasiado Largo
```
❌ psycopg2.errors.StringDataRightTruncation: value too long for type character varying(100)
```

**Causa:** Campo `match_method` tiene límite de 100 caracteres

**Solución:** Usar función de truncado automático
```python
from core.shared.db_config import truncate_field

# ❌ INCORRECTO
match_method = "AMEX - TODOLLANTAS SUC CONSTI (VENTUS SPORT) (2025-01-23). Llantas Pirelli..."

# ✅ CORRECTO
match_method = truncate_field("expense_invoices", "match_method", descripcion_larga)
# O manualmente:
match_method = descripcion_larga[:100]
```

---

### 4. Columnas de Reconciliación No Existen
```
❌ column "reconciliation_status" does not exist
❌ column "payment_method" does not exist
```

**Causa:** Intentar usar columnas que no existen en el esquema

**Solución:** Usar solo las columnas que SÍ existen

**Tabla `expense_invoices`:**
- ✅ `linked_expense_id` (integer)
  - `-1` = Pago con tarjeta AMEX
  - `> 0` = ID de transacción bancaria
  - `NULL` = Sin conciliar
- ✅ `match_confidence` (double precision)
- ✅ `match_method` (varchar 100)
- ✅ `match_date` (timestamp)

**Tabla `bank_transactions`:**
- ✅ `reconciled_invoice_id` (integer)
- ✅ `match_confidence` (double precision)
- ✅ `reconciliation_status` (varchar 50)
- ✅ `reconciled_at` (timestamp)

---

## ✅ Proceso Correcto para Nuevos Meses

### Paso 1: Validar Sistema

Antes de procesar CUALQUIER estado de cuenta:

```bash
python3 validar_antes_de_procesar.py
```

Este script verifica:
- ✅ Conexión a BD funciona
- ✅ Todas las columnas existen
- ✅ Datos del mes están cargados
- ✅ Genera checklist de preparación

**Salida esperada:**
```
✅ SISTEMA LISTO PARA PROCESAR NUEVOS ESTADOS DE CUENTA
```

---

### Paso 2: Preparar Datos

#### Opción A: Extraer Transacciones del PDF (Automático)

```bash
# Para banco Inbursa
python3 scripts/extraer_estado_cuenta_gemini.py \
  --archivo "/path/to/estado_febrero.pdf" \
  --mes 2 --año 2025

# Para AMEX
python3 scripts/extraer_amex_gemini.py \
  --archivo "/path/to/amex_febrero.pdf" \
  --mes 2 --año 2025
```

#### Opción B: Usar Transacciones ya Extraídas (JSON)

Si ya tienes las transacciones en JSON:
```json
[
  {
    "fecha": "2025-02-03",
    "descripcion": "TRASPASO SPEI",
    "monto": -11241.70,
    "bank_tx_id": 123
  }
]
```

---

### Paso 3: Procesar y Conciliar

#### Para Estado de Cuenta Bancario:

```bash
python3 procesar_estado_cuenta_generico.py \
  --tipo banco \
  --mes 2 \
  --año 2025 \
  --transacciones transacciones_febrero.json
```

**Qué hace:**
1. Busca CFDIs pendientes de febrero 2025
2. Busca matches automáticos (diferencia < $0.50)
3. Actualiza `bank_transactions.reconciled_invoice_id`
4. Actualiza `expense_invoices.linked_expense_id`
5. Genera reporte de conciliación

---

#### Para Estado de Cuenta AMEX:

```bash
python3 procesar_estado_cuenta_generico.py \
  --tipo amex \
  --mes 2 \
  --año 2025 \
  --transacciones transacciones_amex_febrero.json
```

**Diferencia con banco:**
- NO actualiza `bank_transactions` (AMEX no está en esa tabla)
- Marca `linked_expense_id = -1` (convención para AMEX)
- Guarda detalles en `match_method`

---

### Paso 4: Verificar Resultados

```bash
# Ver resumen de conciliación
python3 -c "
from core.shared.db_config import get_reconciliation_summary
summary = get_reconciliation_summary(2025, 2)
print(f'Conciliados: {summary[\"conciliados\"]}/{summary[\"total_cfdis\"]}')
print(f'Monto: ${summary[\"monto_conciliado\"]:,.2f}')
"
```

---

## 🔧 Funciones Seguras de Conciliación

### Actualizar Conciliación de CFDI (Función Safe)

```python
from core.shared.db_config import safe_update_invoice_reconciliation

# Para banco
safe_update_invoice_reconciliation(
    cursor,
    cfdi_id=747,
    linked_expense_id=123,  # ID de bank_transactions
    match_method="Banco 2025-02-03: TRASPASO SPEI HORNO",
    match_confidence=1.0
)

# Para AMEX
safe_update_invoice_reconciliation(
    cursor,
    cfdi_id=747,
    linked_expense_id=-1,  # -1 indica AMEX
    match_method="AMEX 2025-02-03: TODOLLANTAS",
    match_confidence=1.0
)
```

**Ventajas:**
- ✅ Trunca automáticamente `match_method` a 100 chars
- ✅ Valida que el CFDI no esté ya conciliado
- ✅ Usa NOW() para `match_date`
- ✅ Retorna True/False

---

### Actualizar Conciliación Bancaria (Función Safe)

```python
from core.shared.db_config import safe_update_bank_reconciliation

safe_update_bank_reconciliation(
    cursor,
    bank_tx_id=123,
    cfdi_id=747,
    match_confidence=0.95,
    reconciliation_status='auto'  # o 'manual'
)
```

---

## 📋 Checklist Pre-Procesamiento

Antes de procesar un nuevo mes, verificar:

- [ ] ✅ `validar_antes_de_procesar.py` corre sin errores
- [ ] ✅ CFDIs del mes ya están cargados en `expense_invoices`
- [ ] ✅ Archivo PDF del estado de cuenta disponible
- [ ] ✅ Saber el mes/año correcto
- [ ] ✅ Decidir tipo: `banco` o `amex`
- [ ] ✅ (Opcional) Backup de BD: `pg_dump mcp_system > backup_antes_feb.sql`

---

## 🎯 Flujo Completo - Ejemplo Febrero 2025

### Escenario: Tienes estado de cuenta Inbursa y AMEX de febrero 2025

```bash
# 1. Validar sistema
python3 validar_antes_de_procesar.py

# 2. Extraer transacciones Inbursa (si no están ya en bank_transactions)
python3 scripts/extraer_estado_cuenta_gemini.py \
  --archivo ~/Downloads/inbursa_febrero_2025.pdf \
  --mes 2 --año 2025

# 3. Procesar estado Inbursa
python3 procesar_estado_cuenta_generico.py \
  --tipo banco --mes 2 --año 2025 \
  --transacciones transacciones_inbursa_feb.json

# 4. Extraer transacciones AMEX
python3 scripts/extraer_amex_gemini.py \
  --archivo ~/Downloads/amex_febrero_2025.pdf \
  --mes 2 --año 2025

# 5. Procesar estado AMEX
python3 procesar_estado_cuenta_generico.py \
  --tipo amex --mes 2 --año 2025 \
  --transacciones transacciones_amex_feb.json

# 6. Ver resumen final
python3 ver_estado_conciliacion.py
```

---

## 🆘 Solución Rápida de Errores

### Si aparece error de conexión:
```bash
# Verificar que PostgreSQL está corriendo
docker ps | grep postgres

# Si no está corriendo:
docker-compose up -d postgres
```

### Si aparece error de columna:
```python
# Ver columnas disponibles
from core.shared.db_config import get_table_columns
print(get_table_columns('expense_invoices'))
```

### Si aparece error de string largo:
```python
# Siempre truncar
from core.shared.db_config import truncate_field
safe_string = truncate_field("expense_invoices", "match_method", long_string)
```

---

## 📊 Monitoreo Continuo

Después de procesar cada mes:

1. **Verificar tasa de conciliación**
   ```bash
   python3 ver_estado_conciliacion.py
   ```

2. **Ver CFDIs pendientes más grandes**
   ```sql
   SELECT id, nombre_emisor, total
   FROM expense_invoices
   WHERE EXTRACT(YEAR FROM fecha_emision) = 2025
   AND EXTRACT(MONTH FROM fecha_emision) = 2
   AND linked_expense_id IS NULL
   ORDER BY total DESC
   LIMIT 10;
   ```

3. **Exportar reporte para contabilidad**
   ```bash
   python3 exportar_conciliacion_excel.py --mes 2 --año 2025
   ```

---

## 🚀 Próximos Pasos Recomendados

1. **Automatizar extracción de PDFs**
   - Implementar extracción Gemini Vision en `procesar_estado_cuenta_generico.py`
   - Actualmente solo tiene placeholders

2. **Dashboard de conciliación**
   - Ver estado en tiempo real
   - Alertas de CFDIs grandes sin conciliar

3. **Integración con email**
   - Automáticamente solicitar CFDIs faltantes
   - Templates ya creados en `cfdi_requests/`

---

**¿Dudas?** Revisa los scripts en:
- [core/shared/db_config.py](core/shared/db_config.py) - Configuración centralizada
- [procesar_estado_cuenta_generico.py](procesar_estado_cuenta_generico.py) - Template genérico
- [validar_antes_de_procesar.py](validar_antes_de_procesar.py) - Validación pre-procesamiento
