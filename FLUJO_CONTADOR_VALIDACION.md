# 👨‍💼 Guía: Flujo del Contador para Validación de Facturas

**Fecha**: 2025-11-25
**Caso de Uso**: Gastos sin RFC que necesitan validación manual

---

## 📋 CASO REAL: Gasolina Sin RFC en el Ticket

### **Escenario Típico**

```
Lunes 20 Nov:
├─ Colaborador va a gasolinera
├─ Compra $500 de gasolina
├─ Le dan ticket físico (sin RFC, solo "Pemex" o "G500")
└─ Captura en el sistema ese mismo día

Jueves 25 Nov:
├─ Llega factura electrónica (XML)
├─ Fecha de factura: 25 Nov (≠ 20 Nov)
├─ Monto: $500
├─ RFC: PRE850101ABC
└─ Sistema necesita emparejar con gasto del 20 Nov
```

---

## ✅ SOLUCIÓN IMPLEMENTADA

### **Sistema de Matching Flexible**

El sistema ahora busca por **DOS criterios**:

| Criterio | Score | Acción |
|----------|-------|--------|
| **RFC exacto + monto + fecha** | 100 | ✅ Auto-match (sin revisión) |
| **Nombre comercial + monto + fecha** | 80 | ⚠️ A cola de revisión |

---

## 🔄 FLUJO COMPLETO: Gasolina Sin RFC

### **Paso 1: Colaborador Captura Gasto (20 Nov)**

```bash
POST /expenses
{
  "descripcion": "Gasolina auto empresa",
  "monto_total": 500,
  "fecha_gasto": "2025-11-20",
  "categoria": "combustible_gasolina",
  "proveedor": {
    "nombre": "Pemex"  // ← Sin RFC (no viene en ticket)
  },
  "company_id": "2"
}
```

**Estado en DB**:
```sql
manual_expenses:
  id: 123
  description: "Gasolina auto empresa"
  amount: 500
  expense_date: 2025-11-20
  provider_name: "Pemex"
  provider_rfc: NULL  ← Sin RFC
  invoice_uuid: NULL
  status: "pending"
```

---

### **Paso 2: Sistema Descarga Factura (25 Nov)**

```
SAT Auto-Download:
├─ Descarga XML de factura
├─ Extrae datos:
│  ├─ UUID: ABC123...
│  ├─ RFC emisor: PRE850101ABC
│  ├─ Nombre fiscal: "Pemex Refinación S.A. de C.V."
│  ├─ Fecha: 2025-11-25
│  └─ Total: $500
└─ IA clasifica contablemente
```

---

### **Paso 3: Sistema Busca Match**

```bash
POST /invoice-matching/match-invoice/{invoice_uuid}

# Query ejecutado:
SELECT * FROM manual_expenses
WHERE company_id = '2'
  AND (
      provider_rfc = 'PRE850101ABC'  -- ❌ No match (NULL en DB)
      OR provider_name ILIKE '%Pemex%'  -- ✅ MATCH!
  )
  AND ABS(amount - 500) < 5.0  -- ✅ Match ($500 = $500)
  AND expense_date BETWEEN '2025-11-10' AND '2025-12-10'  -- ✅ Match (±15 días)
  AND invoice_uuid IS NULL  -- ✅ Match (sin factura aún)

# Resultado: 1 gasto encontrado
# Match Score: 80 (nombre comercial, no RFC)
```

---

### **Paso 4: Sistema Crea Asignación Pendiente**

Porque `match_score = 80` (no 100), el sistema **NO auto-match**. En su lugar:

```bash
# Respuesta del API:
{
  "status": "success",
  "action": "pending_manual_review",
  "case": "1b",
  "assignment_id": 42,
  "possible_matches": [
    {
      "expense_id": 123,
      "description": "Gasolina auto empresa",
      "amount": 500.00,
      "date": "2025-11-20",
      "provider_name": "Pemex",
      "match_score": 80
    }
  ],
  "match_confidence": "medium",
  "reason": "Match by name only - RFC not available in expense. Please confirm."
}
```

**Estado en DB**:
```sql
invoice_expense_pending_assignments:
  id: 42
  invoice_id: "ABC123..."
  possible_expense_ids: [123]
  status: "needs_manual_assignment"
  created_at: 2025-11-25 10:00:00
```

---

### **Paso 5: Contador Revisa y Confirma** ⭐

#### **5.1 Contador ve cola de revisión**

```bash
GET /invoice-matching/pending-assignments?company_id=2

# Respuesta:
{
  "count": 5,
  "pending_assignments": [
    {
      "assignment_id": 42,
      "invoice_uuid": "ABC123...",
      "invoice_total": 500,
      "invoice_date": "2025-11-25",
      "emisor_nombre": "Pemex Refinación S.A. de C.V.",
      "possible_expense_ids": [123],
      "created_at": "2025-11-25T10:00:00"
    },
    // ... otros 4 casos pendientes
  ]
}
```

#### **5.2 Contador revisa el gasto**

```bash
GET /expenses/123

# Respuesta:
{
  "id": 123,
  "description": "Gasolina auto empresa",
  "amount": 500,
  "expense_date": "2025-11-20",
  "provider_name": "Pemex",
  "provider_rfc": null,
  "employee_name": "Juan Pérez",
  "category": "combustible_gasolina"
}
```

**Contador valida**:
- ✅ Monto coincide ($500)
- ✅ Proveedor es el mismo (Pemex)
- ✅ Fecha razonable (5 días de diferencia)
- ✅ Categoría correcta (combustible)
- ✅ Empleado autorizado

#### **5.3 Contador confirma asignación**

```bash
POST /invoice-matching/assign/42
{
  "expense_id": 123
}

# Sistema actualiza:
UPDATE manual_expenses
SET
    invoice_uuid = 'ABC123...',
    provider_fiscal_name = 'Pemex Refinación S.A. de C.V.',
    provider_rfc = 'PRE850101ABC',  -- ← Ahora sí tiene RFC
    status = 'invoiced'
WHERE id = 123

UPDATE invoice_expense_pending_assignments
SET
    status = 'resolved',
    resolved_expense_id = 123,
    resolved_by_user_id = 5,  -- ID del contador
    resolved_at = NOW()
WHERE id = 42
```

---

## 📊 CRITERIOS DE MATCHING MEJORADOS

### **Antes (Original)**
```sql
WHERE provider_rfc = :invoice_rfc  -- ❌ Muy estricto
  AND ABS(amount - :total) < 1.0   -- ❌ Solo $1 tolerancia
  AND expense_date BETWEEN -7 AND +7 days  -- ❌ Solo 7 días
```

**Problema**: Gastos sin RFC nunca se emparejaban

### **Ahora (Mejorado)**
```sql
WHERE (
    provider_rfc = :invoice_rfc  -- Opción 1: RFC exacto
    OR provider_name ILIKE '%Pemex%'  -- Opción 2: Nombre comercial
  )
  AND ABS(amount - :total) < 5.0  -- $5 tolerancia (propinas, redondeo)
  AND expense_date BETWEEN -15 AND +15 days  -- 15 días (facturas retrasadas)
```

**Ventajas**:
- ✅ Detecta gastos sin RFC
- ✅ Permite diferencias de fecha (facturas retrasadas)
- ✅ Tolerancia para redondeo/propinas

---

## 🎯 PREGUNTAS FRECUENTES

### **1. ¿El RFC viene en el ticket físico de gasolinera?**

❌ **NO**. Los tickets físicos generalmente solo tienen:
- Nombre comercial ("Pemex", "G500", "BP")
- Monto
- Fecha/hora

El RFC **solo viene en la factura electrónica (XML)**.

---

### **2. ¿Qué pasa si hay múltiples gastos de gasolina sin factura?**

**Ejemplo**:
```sql
-- Gastos sin factura:
ID 120: "Gasolina" | $480 | 2025-11-18 | Pemex
ID 123: "Gasolina auto empresa" | $500 | 2025-11-20 | Pemex
ID 125: "Combustible" | $520 | 2025-11-22 | Pemex

-- Factura llega:
UUID: ABC123 | $500 | 2025-11-25 | Pemex Refinación
```

**Sistema encuentra 3 matches**:
```json
{
  "action": "pending_manual_review",
  "case": 3,
  "possible_matches": [
    {"expense_id": 120, "amount": 480, "match_score": 80},
    {"expense_id": 123, "amount": 500, "match_score": 80},  ← Mejor match
    {"expense_id": 125, "amount": 520, "match_score": 80}
  ]
}
```

**Contador ve los 3 y elige el correcto** (ID 123 porque monto exacto).

---

### **3. ¿El contador tiene que revisar TODO?**

❌ **NO**. Solo casos con `match_score < 100`:

| Caso | Auto/Manual | % Esperado |
|------|-------------|-----------|
| RFC exacto + monto + fecha | ✅ Automático | 60% |
| Nombre comercial + monto + fecha | ⚠️ Revisión | 25% |
| Múltiples matches | ⚠️ Revisión | 10% |
| Sin match (crear nuevo) | ⚠️ Revisar después | 5% |

**Solo ~40% requiere revisión del contador**.

---

### **4. ¿Cómo revisa el contador cada departamento?**

**Dashboard del Contador**:
```bash
# Ver asignaciones pendientes por departamento
GET /invoice-matching/pending-assignments?company_id=2

# Respuesta agrupada:
{
  "total_pending": 15,
  "by_department": {
    "ventas": 5,
    "operaciones": 8,
    "administracion": 2
  },
  "assignments": [...]
}
```

**Workflow sugerido**:
1. Entrar al sistema cada mañana
2. Ver dashboard de asignaciones pendientes
3. Revisar solo los casos ambiguos (15-20 por día)
4. Confirmar o rechazar
5. Listo en 10-15 minutos

---

## 🔐 SEGURIDAD Y AUDITORÍA

### **Trazabilidad Completa**

Cada asignación manual queda registrada:

```sql
SELECT
  iepa.id,
  iepa.invoice_id,
  iepa.resolved_expense_id,
  u.name as contador_name,
  iepa.resolved_at
FROM invoice_expense_pending_assignments iepa
JOIN users u ON iepa.resolved_by_user_id = u.id
WHERE iepa.status = 'resolved'
  AND iepa.resolved_at >= '2025-11-01'

# Resultado:
assignment_id | invoice_id | expense_id | contador_name | resolved_at
42            | ABC123     | 123        | María López   | 2025-11-25 11:30
43            | DEF456     | 127        | María López   | 2025-11-25 11:35
```

**Auditoría**:
- ✅ Quién asignó cada factura
- ✅ Cuándo se asignó
- ✅ Qué gasto se seleccionó
- ✅ Rastreable para SAT

---

## 📱 INTERFAZ DE USUARIO (UI Sugerida)

### **Dashboard del Contador**

```
┌─────────────────────────────────────────────────────┐
│ 📋 Facturas Pendientes de Asignación               │
├─────────────────────────────────────────────────────┤
│                                                     │
│ 🔴 15 asignaciones pendientes                       │
│                                                     │
│ Por Departamento:                                   │
│   Ventas: 5                                         │
│   Operaciones: 8                                    │
│   Administración: 2                                 │
│                                                     │
│ ┌─────────────────────────────────────────────┐   │
│ │ Factura: Pemex Refinación S.A. de C.V.     │   │
│ │ RFC: PRE850101ABC                           │   │
│ │ Monto: $500.00                              │   │
│ │ Fecha: 25 Nov 2025                          │   │
│ │                                             │   │
│ │ Posibles gastos:                            │   │
│ │ ○ ID 123: Gasolina auto | $500 | 20 Nov    │   │
│ │   Empleado: Juan Pérez                      │   │
│ │   Match: 80 (nombre comercial)              │   │
│ │                                             │   │
│ │ [✅ Confirmar]  [❌ Rechazar]  [👁️ Detalles] │   │
│ └─────────────────────────────────────────────┘   │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## 🚀 ENDPOINTS PARA EL CONTADOR

### **1. Ver Cola de Revisión**
```bash
GET /invoice-matching/pending-assignments?company_id=2
```

### **2. Ver Detalles de un Gasto**
```bash
GET /expenses/{expense_id}
```

### **3. Ver Detalles de una Factura**
```bash
GET /invoices/{invoice_id}
```

### **4. Confirmar Asignación**
```bash
POST /invoice-matching/assign/{assignment_id}
{
  "expense_id": 123
}
```

### **5. Rechazar Asignación** (Crear gasto nuevo)
```bash
POST /invoice-matching/reject/{assignment_id}
{
  "reason": "No corresponde a ningún gasto existente"
}
# → Sistema crea gasto nuevo automáticamente
```

---

## 📈 MÉTRICAS ESPERADAS

| Métrica | Valor | Explicación |
|---------|-------|-------------|
| **Auto-match (score 100)** | 60% | RFC exacto → sin revisión |
| **Revisión media confianza** | 25% | Nombre comercial → revisar |
| **Revisión múltiples matches** | 10% | Varios posibles → elegir |
| **Gastos nuevos creados** | 5% | Sin gasto previo |
| **Tiempo de revisión/caso** | 30 segundos | Ver, validar, confirmar |
| **Casos por día (100 facturas)** | ~40 para revisar | 60 automáticos + 40 manuales |

**Total por día**: ~20 minutos de trabajo del contador para 100 facturas

---

## ✅ RESUMEN

### **Tu Pregunta Original**
> "¿El RFC viene en el ticket? ¿Cómo hacerle para que se adjunte correctamente? El contador va a meterse a validar, ¿no?"

### **Respuesta Completa**

1. **❌ RFC NO viene en ticket físico** → Solo en factura electrónica
2. **✅ Sistema busca por nombre comercial** → Detecta "Pemex" aunque no haya RFC
3. **✅ Permite diferencia de fechas** → ±15 días (facturas retrasadas)
4. **✅ Contador SÍ valida casos ambiguos** → Solo ~40% requiere revisión
5. **✅ Trazabilidad completa** → Auditable para SAT

---

**Preparado por**: Claude Code
**Documento**: Flujo del Contador - Validación de Facturas
**Estado**: ✅ Sistema flexible implementado
