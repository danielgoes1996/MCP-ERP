# 🔍 Análisis: CFDIs Pendientes vs Pagos Bancarios

**Fecha:** 2025-11-09

---

## 📊 Situación Actual

### CFDIs Pendientes (Gastos de la empresa)
- **Total:** 29 CFDIs
- **Monto:** $112,591.46 MXN

### Traspasos SPEI Pendientes (Salidas de dinero)
- **Total:** 1 traspaso
- **Monto:** $11,241.70 MXN

### Depósitos SPEI Pendientes (Entradas de dinero)
- **Total:** 24 depósitos
- **Monto:** ~$120,000 MXN (aproximado)

---

## 🎯 Hallazgo Principal

**DESCUBRIMIENTO IMPORTANTE:**

Los 29 CFDIs pendientes son **gastos/compras** de la empresa, pero la mayoría de los "DEPOSITO SPEI" en el estado de cuenta son **CRÉDITOS** (ingresos/entradas de dinero), **NO débitos**.

Esto significa que esos depósitos son **ventas/cobros**, no pagos a proveedores.

---

## 💰 ¿Cómo se Pagaron los CFDIs Pendientes?

### Análisis por CFDI:

#### 1. HORNO INDUSTRIAL - $59,900 ✅ Parcialmente Identificado

**CFDI-748** - FABRICACIONES Y MAQUILAS DE OCCIDENTE
- Método Pago: **PPD** (Pago en Parcialidades)
- Fecha CFDI: 27 de enero

**Pago Identificado:**
- ✅ **TX-4:** $11,241.70 (2 de enero) - Probable **ANTICIPO** (18.8% del total)
- ❓ **Faltante:** $48,658.30

**Posibles escenarios:**
1. Se pagó el resto con cheque (no aparece en estado de cuenta)
2. Se pagó el resto con transferencia de otra cuenta
3. Se pagó el resto en febrero 2025 (fuera del periodo analizado)
4. Está programado como pago en parcialidades (PPD)

---

#### 2. MIEL - $37,000 (20 facturas) ❌ No Identificado

**20 CFDIs de MIELVIL** - $1,850 c/u
- Método Pago: **PUE** (Pago en Una Exhibición)
- Fecha CFDIs: Todos del 29 de enero

**Análisis:**
- NO hay traspasos SPEI débito del 29 de enero que coincidan
- NO hay traspasos de ~$37,000 en ninguna fecha

**Posibles escenarios:**
1. Se pagó con cheque
2. Se pagó en efectivo
3. Se pagó con transferencia de otra cuenta bancaria
4. Se pagó en febrero (fuera del periodo)
5. **¿Hay una cuenta corriente/crédito con el proveedor?**

---

#### 3. LLANTAS - $4,325 ❓ Pagado con Tarjeta

**CFDI-747** - VENTUS SPORT
- Método Pago: PUE
- **Forma Pago: 04 (Tarjeta de crédito)**
- Fecha: 23 de enero

**Acción:** Revisar estados de cuenta de tarjetas de crédito corporativas

---

#### 4. BOLSAS EMPAQUE - $3,992.67 ❓ Pagado con Tarjeta

**CFDI-767** - CLIFTON PACKAGING
- Método Pago: PUE
- **Forma Pago: 04 (Tarjeta de crédito)**
- Fecha: 30 de enero

**Acción:** Revisar estados de cuenta de tarjetas de crédito corporativas

---

#### 5. NUEZ - $3,600 ❌ No Identificado

**CFDI-735** - CARLOS ANDRES GOMEZ CASTILLO
- Método Pago: PUE
- Fecha: 9 de enero

**Análisis:**
- NO hay traspasos SPEI cerca de esa fecha que coincidan
- Posible pago con cheque o efectivo

---

#### 6. CUBETAS PLÁSTICAS - $1,653 ❌ No Identificado

**CFDI-761** - HAISO PLASTICOS
- Método Pago: PUE
- Fecha: 27 de enero

**Análisis:**
- NO hay traspasos SPEI que coincidan

---

#### 7. SERVICIOS MENORES

**Amazon FBA ($902.69), Reparación impresora ($780), Banco Inbursa ($252.88), Finkok ($185.22)**

- Probablemente pagados con tarjeta o débito automático
- Banco Inbursa: Comisión bancaria (probablemente ya debitada)

---

## 🤔 ¿Por Qué NO Aparecen los Pagos?

### Hipótesis Principales:

1. **Pagos con Cheque**
   - Los cheques no aparecen como "TRASPASO SPEI" en el estado de cuenta
   - Aparecerían como "CHEQUE #XXXX" o similar
   - **Acción:** Buscar en el estado de cuenta transacciones tipo "CHEQUE"

2. **Pagos desde Otra Cuenta Bancaria**
   - La empresa puede tener otras cuentas
   - Los pagos se hicieron desde esas cuentas
   - **Acción:** Revisar otras cuentas bancarias

3. **Pagos con Tarjeta de Crédito**
   - VENTUS SPORT y CLIFTON PACKAGING indican forma de pago 04 (tarjeta)
   - **Acción:** Revisar estados de cuenta de tarjetas corporativas

4. **Pagos en Efectivo**
   - Especialmente para proveedores pequeños (nuez, cubetas)
   - No dejan rastro en el estado de cuenta

5. **Pagos en Febrero**
   - Algunos CFDIs se emitieron al final de enero
   - Pudieron pagarse en febrero
   - **Acción:** Analizar estado de cuenta de febrero 2025

6. **Cuenta Corriente con Proveedores**
   - Especialmente MIELVIL (20 facturas del mismo día)
   - Puede haber un acuerdo de pago diferido
   - **Acción:** Verificar con cuentas por pagar

---

## 📌 DEPÓSITOS SPEI (Ingresos) - NO Son Pagos

Los 24 "DEPOSITO SPEI" pendientes son **INGRESOS** de la empresa, probablemente:

- Ventas de productos (miel, granola, etc.)
- Cobros de clientes
- Ventas por Amazon (transferencias de Amazon)

**Estos NO concilian con los CFDIs de gastos.**

---

## ✅ Acciones Inmediatas Recomendadas

### 1. Revisar Movimientos de Cheques
```bash
python3 buscar_cheques_enero.py
```
Buscar en el estado de cuenta transacciones con "CHEQUE"

### 2. Revisar Estados de Cuenta de Tarjetas
- Tarjeta corporativa
- Buscar cargos de:
  - VENTUS SPORT (~$4,325) - 23 enero
  - CLIFTON PACKAGING (~$3,992) - 30 enero

### 3. Revisar Estado de Cuenta de Febrero
- Buscar pagos de facturas de enero que se pagaron en febrero
- Especialmente: MIEL ($37,000), HORNO ($48,658 restante)

### 4. Consultar con Cuentas por Pagar
- ¿Cómo se pagó la MIEL (20 facturas)?
- ¿El HORNO se pagó completo o hay parcialidades pendientes?
- ¿Hay acuerdos de crédito con MIELVIL?

### 5. Revisar Otras Cuentas Bancarias
- ¿La empresa tiene otras cuentas?
- ¿Se usaron para pagar estos gastos?

---

## 📊 Resumen de Conciliación Posible

| CFDI | Monto | Posible Match | Acción |
|------|-------|---------------|--------|
| HORNO | $59,900 | TX-4 ($11,241.70) anticipo | ✅ Conciliar como pago parcial<br>❓ Buscar resto |
| MIEL (20) | $37,000 | ❌ No encontrado | Revisar cheques/feb |
| LLANTAS | $4,325 | ❓ Tarjeta crédito | Revisar tarjetas |
| BOLSAS | $3,993 | ❓ Tarjeta crédito | Revisar tarjetas |
| NUEZ | $3,600 | ❌ No encontrado | Revisar cheques/feb |
| CUBETAS | $1,653 | ❌ No encontrado | Revisar cheques/feb |
| SERVICIOS | $2,121 | ❓ Varios | Revisar tarjetas/débitos |

---

## 🎯 Próximos Pasos

1. **Inmediato:** Buscar transacciones tipo "CHEQUE" en el estado de cuenta
2. **Corto plazo:** Conseguir estados de cuenta de:
   - Tarjetas de crédito corporativas (enero)
   - Febrero 2025 (banco)
   - Otras cuentas bancarias si existen
3. **Coordinación:** Reunión con cuentas por pagar para entender forma de pago de proveedores grandes (MIELVIL, HORNO)

---

**Conclusión:** Los CFDIs existen y son legítimos, pero los pagos probablemente se hicieron por medios que **NO son traspasos SPEI débito** (cheques, tarjetas, otras cuentas, o en febrero).
