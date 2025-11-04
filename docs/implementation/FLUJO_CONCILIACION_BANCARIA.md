# Flujo de Conciliación Bancaria - Sistema MCP

## 📋 Resumen
Este documento explica el flujo completo para conciliar gastos del usuario con movimientos bancarios en nuestro sistema.

---

## 🔄 Flujo General

```
┌─────────────────┐
│  1. CREAR GASTO │
│   (Usuario)     │
└────────┬────────┘
         │
         ▼
┌────────────────────────┐
│  2. SUBIR ESTADO DE    │
│     CUENTA BANCARIO    │
└────────┬───────────────┘
         │
         ▼
┌────────────────────────┐
│  3. SUGERENCIAS ML/IA  │
│     (Matching)         │
└────────┬───────────────┘
         │
         ▼
┌────────────────────────┐
│  4. CONCILIACIÓN       │
│     Manual o Auto      │
└────────┬───────────────┘
         │
         ▼
┌────────────────────────┐
│  5. GASTO CONCILIADO   │
│     ✅ Completo        │
└────────────────────────┘
```

---

## 📝 Paso 1: Crear Gasto

### Métodos disponibles:
1. **Por voz** (dictado en `/voice-expenses`)
2. **Por ticket/OCR** (subir foto del ticket)
3. **Manual** (formulario texto)

### Datos del gasto:
```json
{
  "descripcion": "Gasolina Pemex",
  "monto_total": 850.50,
  "fecha_gasto": "2025-01-15",
  "proveedor": {
    "nombre": "Gasolinera Pemex",
    "rfc": "PEM850101ABC"
  },
  "categoria": "combustible",
  "forma_pago": "tarjeta_credito",
  "paid_by": "company_account",
  "will_have_cfdi": true,
  "company_id": "default",
  "metadata": {
    "source": "manual"
  }
}
```

### Almacenamiento:
- **Tabla:** `expense_records`
- **Estado inicial:**
  - `invoice_status`: "pending"
  - `bank_status`: "pending"
  - `status`: "pending"

---

## 🏦 Paso 2: Subir Estado de Cuenta Bancario

### Proceso:

#### 2.1. Subir PDF del banco
```
POST /bank-statements/accounts/{account_id}/upload
Content-Type: multipart/form-data

file: estado_cuenta_julio_2025.pdf
```

#### 2.2. Parser automático
El sistema usa parsers específicos por banco:
- **Inbursa**: `pdfplumber` + `pymupdf`
- **BBVA**: Parser específico
- **Santander**: Parser específico
- etc.

#### 2.3. Extracción de movimientos
Cada movimiento extraído contiene:
```json
{
  "fecha": "2025-07-31",
  "descripcion": "OFFICE DEPOT CITADINA MX",
  "cargo": 4.50,
  "abono": 0,
  "saldo": 38317.76,
  "referencia": "3525403592",
  "tipo": "Gasto"
}
```

#### 2.4. Almacenamiento
- **Tabla:** `bank_movements`
- **Campos clave:**
  - `amount`: Monto (negativo para cargos)
  - `description`: Descripción limpia
  - `description_raw`: Texto original del PDF
  - `date`: Fecha del movimiento
  - `movement_kind`: "Gasto" | "Ingreso"
  - `cargo_amount`: Monto del cargo
  - `abono_amount`: Monto del abono
  - `is_reconciled`: false (inicialmente)
  - `matched_expense_id`: null (inicialmente)

---

## 🤖 Paso 3: Sugerencias de Matching (ML/IA)

### 3.1. Matching Automático con IA

El sistema ofrece **3 niveles** de matching:

#### A. Matching Heurístico (reglas)
**Endpoint:** `POST /bank_reconciliation/suggestions`

**Criterios de scoring:**
1. **Monto** (peso: 40%): Coincidencia exacta o cercana
2. **Fecha** (peso: 30%): Diferencia en días
   - 0 días: score = 1.0
   - 1-3 días: score = 0.9
   - 4-7 días: score = 0.75
   - 8-15 días: score = 0.6
   - 16-30 días: score = 0.4
   - >30 días: score = 0.0
3. **Descripción** (peso: 20%): Similitud de texto
4. **Forma de pago** (peso: 10%): Tarjeta empresa vs cuenta propia

**Ejemplo de respuesta:**
```json
{
  "suggestions": [
    {
      "movement_id": 10235,
      "description": "OFFICE DEPOT CITADINA MX",
      "amount": -4.50,
      "date": "2025-07-31",
      "confidence": 0.92,
      "score_breakdown": {
        "amount_score": 1.0,
        "date_score": 0.9,
        "text_score": 0.85,
        "payment_score": 0.9
      },
      "reasons": [
        "✅ Monto exacto coincide",
        "✅ Fecha muy cercana (1 día)",
        "✅ Descripción similar"
      ]
    }
  ]
}
```

#### B. Matching con ML (Machine Learning)
**Endpoint:** `POST /bank_reconciliation/ml-suggestions`

Usa embeddings semánticos y features ML:
- Vectores de descripción
- Patrones históricos
- Categorías predichas
- Proveedores conocidos

#### C. Auto-Matching (Automático)
**Endpoint:** `POST /bank_reconciliation/auto-reconcile`

Parámetros:
- `threshold`: 0.85 (por defecto) - Solo auto-concilia si confianza > 85%
- `limit`: 100 (máximo de movimientos a procesar)

**Proceso:**
1. Obtiene todos los movimientos sin conciliar
2. Para cada movimiento, busca el mejor match
3. Si `confidence >= threshold`, auto-concilia
4. Registra feedback automático

---

## ✅ Paso 4: Conciliación (Manual o Automática)

### 4.1. Interfaz de Conciliación

**URL:** `http://localhost:8004/bank-reconciliation`

**Vista principal:**
- Lista de gastos pendientes de conciliar
- Para cada gasto, muestra sugerencias de movimientos bancarios
- Indicador visual de confianza (verde/amarillo/rojo)

### 4.2. Conciliación Manual

#### Flujo UI:
1. Usuario ve gasto: "Gasolina Pemex - $850.50"
2. Sistema muestra sugerencias ordenadas por confianza
3. Usuario selecciona el movimiento correcto
4. Click en "Conciliar" o "Aceptar sugerencia"

#### API Call:
```javascript
// 1. Registrar la conciliación
POST /bank_reconciliation/feedback
{
  "expense_id": 10244,
  "movement_id": 10235,
  "confidence": 0.92,
  "decision": "accepted"
}

// 2. Actualizar el gasto
PUT /expenses/10244
{
  "estado_conciliacion": "conciliado_banco",
  "movimientos_bancarios": {
    "movement_id": 10235,
    "matched_at": "2025-01-15T10:30:00Z",
    "confidence": 0.92
  }
}
```

#### Backend:
1. Actualiza `expense_records.bank_status` = "reconciled"
2. Actualiza `bank_movements.matched_expense_id` = expense_id
3. Actualiza `bank_movements.is_reconciled` = true
4. Registra feedback en `bank_reconciliation_feedback`

### 4.3. Conciliación Automática

```javascript
POST /bank_reconciliation/auto-reconcile?threshold=0.85&limit=100

// Respuesta:
{
  "success": true,
  "matched": 15,
  "reviewed": 100,
  "results": [
    {
      "expense_id": 10244,
      "movement_id": 10235,
      "confidence": 0.92,
      "action": "matched"
    }
  ]
}
```

---

## 🗄️ Estructura de Datos

### Tabla: `expense_records`
```sql
- id: 10244
- description: "Gasolina Pemex"
- amount: 850.50
- date: "2025-01-15"
- invoice_status: "pending" | "facturado" | "no_cfdi"
- bank_status: "pending" | "reconciled" | "non_reconcilable"
- metadata: JSON con info adicional
```

### Tabla: `bank_movements`
```sql
- id: 10235
- description: "GASOLINERA PEMEX"
- amount: -850.50
- date: "2025-01-15"
- cargo_amount: 850.50
- abono_amount: 0
- is_reconciled: true
- matched_expense_id: 10244
- matched_at: "2025-01-15T10:30:00Z"
- reconciliation_confidence: 0.92
```

### Tabla: `bank_reconciliation_feedback`
```sql
- id: 1
- expense_id: 10244
- movement_id: 10235
- confidence: 0.92
- decision: "accepted"
- created_at: "2025-01-15T10:30:00Z"
```

---

## 📊 Estados del Gasto

### Lifecycle del gasto:

```
┌──────────────┐
│   CREADO     │ invoice_status: pending
│   (Draft)    │ bank_status: pending
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  FACTURADO   │ invoice_status: facturado
│              │ bank_status: pending
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ CONCILIADO   │ invoice_status: facturado
│   ✅ LISTO   │ bank_status: reconciled
└──────────────┘
```

### Estados posibles de `bank_status`:
- `pending`: Sin conciliar
- `reconciled`: Conciliado con movimiento bancario
- `non_reconcilable`: No se puede conciliar (marcado manual)

---

## 🎯 Criterios de Matching

### Scoring ponderado:
```javascript
finalScore = (
  amount_score * 0.40 +
  date_score * 0.30 +
  text_score * 0.20 +
  payment_score * 0.10
)
```

### Clasificación por confianza:
- **Alta (>0.85)**: Verde - Auto-conciliable
- **Media (0.60-0.85)**: Amarillo - Revisar manual
- **Baja (<0.60)**: Rojo - Probablemente no coincide

---

## 🔧 Endpoints Principales

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/expenses` | POST | Crear gasto |
| `/expenses` | GET | Listar gastos |
| `/expenses/{id}` | PUT | Actualizar gasto |
| `/bank-statements/accounts/{id}/upload` | POST | Subir PDF bancario |
| `/bank_reconciliation/movements` | GET | Listar movimientos |
| `/bank_reconciliation/suggestions` | POST | Sugerencias de matching |
| `/bank_reconciliation/ml-suggestions` | POST | Sugerencias ML |
| `/bank_reconciliation/auto-reconcile` | POST | Auto-conciliación |
| `/bank_reconciliation/feedback` | POST | Registrar decisión |

---

## 💡 Casos de Uso

### Caso 1: Conciliación exitosa automática
```
1. Usuario crea gasto: Gasolina $850.50 (15-ene)
2. Usuario sube estado de cuenta con movimiento: PEMEX $850.50 (15-ene)
3. Sistema calcula confidence: 0.95 (muy alta)
4. Auto-matching concilia automáticamente
5. Estado: ✅ Conciliado
```

### Caso 2: Conciliación manual (fechas diferentes)
```
1. Usuario crea gasto: Comida $1,250 (14-ene)
2. Movimiento bancario: RESTAURANTE $1,250 (17-ene)
3. Sistema calcula confidence: 0.75 (media - 3 días de diferencia)
4. Usuario revisa sugerencia y acepta manual
5. Estado: ✅ Conciliado
```

### Caso 3: No conciliable
```
1. Usuario crea gasto: Papelería efectivo $450
2. No hay movimiento bancario (fue en efectivo)
3. Usuario marca como "No conciliable"
4. Registra motivo: "Pago en efectivo"
5. Estado: ⚠️ No conciliable (normal)
```

---

## 🚀 Mejoras Futuras

1. **Matching multi-factura**: Un movimiento bancario que cubre múltiples gastos
2. **Matching parcial**: Gastos pagados en múltiples movimientos
3. **Aprendizaje continuo**: El ML mejora con cada feedback del usuario
4. **Reglas personalizadas**: El usuario puede crear sus propias reglas de matching
5. **Integración directa bancaria**: Importar movimientos vía API (no PDF)

---

## ✨ Flujo Ideal (End-to-End)

```
📱 Usuario registra gasto por voz
   "Gasté 850 pesos en gasolina Pemex hoy"

   ↓

💾 Sistema guarda en expense_records
   - descripcion: "Gasolina Pemex"
   - monto_total: 850
   - fecha_gasto: 2025-01-15
   - bank_status: pending

   ↓

📄 Usuario sube estado de cuenta PDF
   (al final del mes)

   ↓

🤖 Parser extrae movimientos → bank_movements
   - description: "GASOLINERA PEMEX"
   - amount: -850
   - date: 2025-01-15

   ↓

🧠 Sistema ML calcula matching
   confidence: 0.95 (muy alta)

   ↓

✅ Auto-conciliación
   expense.bank_status → "reconciled"
   movement.matched_expense_id → 10244

   ↓

🎉 Gasto completamente procesado
   - ✅ Registrado
   - ✅ Conciliado en banco
   - 📄 Esperando factura (siguiente paso)
```

---

## 📌 Notas Importantes

1. **Separación de tablas**:
   - `expense_records` = Gastos del usuario
   - `bank_movements` = Movimientos del banco
   - NUNCA mezclar

2. **Metadata es clave**:
   - Usa `metadata.source` para distinguir origen
   - `source: "manual"` = Usuario
   - `source: "bank_parser"` = PDF bancario

3. **Confianza del matching**:
   - Siempre guarda el `confidence score`
   - Permite auditoría y mejora continua

4. **Feedback loop**:
   - Cada decisión del usuario entrena el sistema
   - El ML mejora con el tiempo

---

## 🔗 Referencias

- Parser Inbursa: `core/bank_file_parser.py`
- Matching Logic: `core/bank_reconciliation.py`
- API Endpoints: `main.py` (líneas 1849-2200)
- UI: `static/bank-reconciliation.html`
- Modelos: `core/bank_statements_models.py`
