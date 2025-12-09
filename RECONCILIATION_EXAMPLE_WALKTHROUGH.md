# Sistema de Reconciliación - Ejemplo Práctico con Datos Ficticios
**Fecha:** 2025-12-08
**Escenario:** Carreta Verde - Semana del 15-22 Nov 2025

---

## 📊 PARTE 1: DATOS DE ENTRADA (Estado Inicial)

### A) Manual Expenses (Gastos Capturados por Usuario)

```json
{
  "manual_expenses": [
    {
      "id": 101,
      "tenant_id": 2,
      "description": "Gasolina Pemex Cuautla",
      "amount": 1250.50,
      "expense_date": "2025-11-18",
      "provider_name": "PEMEX",
      "provider_rfc": "PMI950421123",
      "category": "combustible",
      "payment_method": "tarjeta",
      "invoice_required": true,
      "sat_invoice_id": null,
      "bank_transaction_id": null,
      "reconciliation_status": "unmatched",
      "reconciliation_confidence": null,
      "reconciliation_layer": null,
      "created_by": 9,
      "created_at": "2025-11-18T14:30:00Z"
    },
    {
      "id": 102,
      "tenant_id": 2,
      "description": "Recarga PASE peajes",
      "amount": 500.00,
      "expense_date": "2025-11-19",
      "provider_name": "PASE",
      "provider_rfc": "ISD950921HE5",
      "category": "viaticos",
      "payment_method": "transferencia",
      "invoice_required": true,
      "sat_invoice_id": null,
      "bank_transaction_id": null,
      "reconciliation_status": "unmatched",
      "reconciliation_confidence": null,
      "reconciliation_layer": null,
      "created_by": 9,
      "created_at": "2025-11-19T10:15:00Z"
    },
    {
      "id": 103,
      "tenant_id": 2,
      "description": "Mantenimiento Scania Monterrey",
      "amount": 15600.00,
      "expense_date": "2025-11-20",
      "provider_name": "Scania",
      "provider_rfc": null,
      "category": "mantenimiento",
      "payment_method": "efectivo",
      "invoice_required": false,
      "sat_invoice_id": null,
      "bank_transaction_id": null,
      "reconciliation_status": "unmatched",
      "reconciliation_confidence": null,
      "reconciliation_layer": null,
      "created_by": 9,
      "created_at": "2025-11-20T16:45:00Z"
    }
  ]
}
```

**❗ FLAW #1 Detectado:**
- `manual_expenses[2]` NO tiene `provider_rfc` → Layer 0 (SQL exact match) fallará
- Necesitaremos Layer 2 (vectorial) o Layer 3 (LLM) para matchear

---

### B) Bank Transactions (Movimientos Bancarios del Estado de Cuenta)

```json
{
  "bank_transactions": [
    {
      "id": 501,
      "tenant_id": 2,
      "account_number": "1234567890",
      "transaction_date": "2025-11-18",
      "description": "CARGO PEMEX CUAUTLA MOR",
      "amount": -1250.50,
      "balance_after": 45230.75,
      "transaction_type": "cargo",
      "transaction_class": "gasto",
      "category": null,
      "vendor_normalized": null,
      "likely_vendor_rfc": "PMI950421123",
      "vendor_rfc": "PMI950421123",
      "vendor_rfc_source": "extracted",
      "vendor_rfc_confidence": 0.85,
      "sat_invoice_id": null,
      "manual_expense_id": null,
      "reconciliation_status": "unmatched",
      "reconciliation_confidence": null,
      "reconciliation_layer": null,
      "created_at": "2025-11-22T08:00:00Z"
    },
    {
      "id": 502,
      "tenant_id": 2,
      "account_number": "1234567890",
      "transaction_date": "2025-11-19",
      "description": "SPEI PASE SERVICIOS",
      "amount": -502.35,
      "balance_after": 44728.40,
      "transaction_type": "spei_salida",
      "transaction_class": "gasto",
      "category": null,
      "vendor_normalized": null,
      "likely_vendor_rfc": null,
      "vendor_rfc": null,
      "vendor_rfc_source": null,
      "vendor_rfc_confidence": null,
      "sat_invoice_id": null,
      "manual_expense_id": null,
      "reconciliation_status": "unmatched",
      "reconciliation_confidence": null,
      "reconciliation_layer": null,
      "created_at": "2025-11-22T08:00:00Z"
    },
    {
      "id": 503,
      "tenant_id": 2,
      "account_number": "1234567890",
      "transaction_date": "2025-11-20",
      "description": "RETIRO ATM BANAMEX",
      "amount": -16000.00,
      "balance_after": 28728.40,
      "transaction_type": "retiro_efectivo",
      "transaction_class": "gasto",
      "category": null,
      "vendor_normalized": null,
      "likely_vendor_rfc": null,
      "vendor_rfc": null,
      "vendor_rfc_source": null,
      "vendor_rfc_confidence": null,
      "sat_invoice_id": null,
      "manual_expense_id": null,
      "reconciliation_status": "unmatched",
      "reconciliation_confidence": null,
      "reconciliation_layer": null,
      "created_at": "2025-11-22T08:00:00Z"
    },
    {
      "id": 504,
      "tenant_id": 2,
      "account_number": "1234567890",
      "transaction_date": "2025-11-21",
      "description": "DEPOSITO CLIENTE ABC SA",
      "amount": 35000.00,
      "balance_after": 63728.40,
      "transaction_type": "deposito",
      "transaction_class": "ingreso",
      "category": null,
      "vendor_normalized": null,
      "likely_vendor_rfc": null,
      "vendor_rfc": null,
      "vendor_rfc_source": null,
      "vendor_rfc_confidence": null,
      "sat_invoice_id": null,
      "manual_expense_id": null,
      "reconciliation_status": "unmatched",
      "reconciliation_confidence": null,
      "reconciliation_layer": null,
      "created_at": "2025-11-22T08:00:00Z"
    }
  ]
}
```

**❗ FLAW #2 Detectado:**
- `bank_transactions[1]` (PASE) NO tiene `vendor_rfc` extraído
- `bank_transactions[2]` (retiro ATM) NO tiene `vendor_rfc` - es un retiro de efectivo
- `bank_transactions[3]` es un INGRESO, no un gasto - ¿debería estar en reconciliación?

**❗ FLAW #3 Detectado:**
- Monto diferente: Manual $500 vs Banco $502.35 (diferencia de $2.35 = comisión)
- Layer 0 (exact match) fallará, necesitamos Layer 1 (mathematical tolerance)

---

### C) SAT Invoices (Facturas Fiscales del SAT)

```json
{
  "sat_invoices": [
    {
      "id": "A1B2C3D4-E5F6-7890-ABCD-1234567890AB",
      "tenant_id": 2,
      "batch_id": "batch_20251122_001",
      "invoice_type": "ingreso",
      "cfdi_version": "4.0",
      "status": "vigente",
      "cancellation_status": null,
      "parsed_data": {
        "uuid": "A1B2C3D4-E5F6-7890-ABCD-1234567890AB",
        "serie": "A",
        "folio": "12345",
        "fecha_emision": "2025-11-18",
        "rfc_emisor": "PMI950421123",
        "nombre_emisor": "PEMEX ESTACION CUAUTLA",
        "rfc_receptor": "CVE210315ABC",
        "nombre_receptor": "CARRETA VERDE SA DE CV",
        "total": 1250.50,
        "subtotal": 1078.88,
        "moneda": "MXN",
        "tipo_cambio": 1.0,
        "metodo_pago": "PUE",
        "forma_pago": "04",
        "uso_cfdi": "G03",
        "conceptos": [
          {
            "cantidad": 75.5,
            "unidad": "litro",
            "descripcion": "GASOLINA MAGNA",
            "importe": 1078.88,
            "clave_prod_serv": "15101514"
          }
        ],
        "impuestos": {
          "iva": 171.62,
          "otros": 0,
          "detalle": [
            {
              "code": "002",
              "kind": "traslado",
              "rate": 0.16,
              "type": "IVA",
              "amount": 171.62,
              "factor": "Tasa"
            }
          ]
        }
      },
      "bank_transaction_id": null,
      "manual_expense_id": null,
      "reconciliation_status": "unmatched",
      "reconciliation_confidence": null,
      "reconciliation_layer": null,
      "downloaded_at": "2025-11-22T09:00:00Z"
    },
    {
      "id": "B2C3D4E5-F6G7-8901-BCDE-2345678901BC",
      "tenant_id": 2,
      "batch_id": "batch_20251122_001",
      "invoice_type": "ingreso",
      "cfdi_version": "4.0",
      "status": "vigente",
      "cancellation_status": null,
      "parsed_data": {
        "uuid": "B2C3D4E5-F6G7-8901-BCDE-2345678901BC",
        "serie": "B",
        "folio": "67890",
        "fecha_emision": "2025-11-19",
        "rfc_emisor": "ISD950921HE5",
        "nombre_emisor": "PASE SERVICIOS ELECTRONICOS",
        "rfc_receptor": "CVE210315ABC",
        "nombre_receptor": "CARRETA VERDE SA DE CV",
        "total": 502.35,
        "subtotal": 433.24,
        "moneda": "MXN",
        "tipo_cambio": 1.0,
        "metodo_pago": "PUE",
        "forma_pago": "03",
        "uso_cfdi": "G03",
        "conceptos": [
          {
            "cantidad": 1,
            "unidad": "servicio",
            "descripcion": "RECARGA SALDO IAVE",
            "importe": 425.00,
            "clave_prod_serv": "95111615"
          },
          {
            "cantidad": 1,
            "unidad": "servicio",
            "descripcion": "COMISION RECARGA",
            "importe": 8.24,
            "clave_prod_serv": "80141628"
          }
        ],
        "impuestos": {
          "iva": 69.11,
          "otros": 0,
          "detalle": [
            {
              "code": "002",
              "kind": "traslado",
              "rate": 0.16,
              "type": "IVA",
              "amount": 69.11,
              "factor": "Tasa"
            }
          ]
        }
      },
      "bank_transaction_id": null,
      "manual_expense_id": null,
      "reconciliation_status": "unmatched",
      "reconciliation_confidence": null,
      "reconciliation_layer": null,
      "downloaded_at": "2025-11-22T09:00:00Z"
    }
  ]
}
```

**❗ FLAW #4 Detectado:**
- Solo hay 2 facturas SAT, pero 3 gastos manuales
- `manual_expenses[2]` (Mantenimiento Scania $15,600) NO tiene factura SAT
  - Usuario marcó `invoice_required: false` - ¿Es válido? ¿Cómo lo reconciliamos?

---

## 🔄 PARTE 2: PROCESO DE RECONCILIACIÓN (4 Capas)

### LAYER 0: Deterministic SQL Matching (Exact Match)

**Query ejecutado:**
```sql
SELECT
    me.id as manual_id,
    bt.id as bank_id,
    si.id as sat_id
FROM manual_expenses me
LEFT JOIN sat_invoices si ON
    si.parsed_data->>'rfc_emisor' = me.provider_rfc
    AND si.parsed_data->>'fecha_emision' = me.expense_date::TEXT
    AND (si.parsed_data->>'total')::NUMERIC = me.amount
LEFT JOIN bank_transactions bt ON
    bt.vendor_rfc = me.provider_rfc
    AND bt.transaction_date = me.expense_date
    AND ABS(bt.amount) = me.amount
WHERE me.tenant_id = 2
  AND me.reconciliation_status = 'unmatched';
```

**Resultados Layer 0:**
```json
{
  "layer0_matches": [
    {
      "manual_expense_id": 101,
      "sat_invoice_id": "A1B2C3D4-E5F6-7890-ABCD-1234567890AB",
      "bank_transaction_id": 501,
      "match_type": "perfect_3way",
      "confidence": 1.00,
      "explanation": "RFC, fecha y monto coinciden exactamente en las 3 fuentes",
      "matched_fields": {
        "rfc": "PMI950421123",
        "date": "2025-11-18",
        "amount": 1250.50
      }
    }
  ],
  "unmatched": [
    {
      "manual_expense_id": 102,
      "reason": "Amount mismatch: manual=$500.00, sat=$502.35, bank=$502.35"
    },
    {
      "manual_expense_id": 103,
      "reason": "Missing provider_rfc in manual_expense, no SAT invoice found"
    }
  ]
}
```

**✅ Match Exitoso:** Gasto #101 (Gasolina) matcheó perfectamente las 3 fuentes
**❌ Sin Match:** Gastos #102 y #103 pasan a Layer 1

---

### LAYER 1: Mathematical Matching (Tolerance-based)

**Reglas aplicadas:**
- Tolerancia de ±5% en monto
- Ventana de ±3 días en fecha
- RFC debe coincidir (si existe)

**Query ejecutado:**
```sql
SELECT
    me.id as manual_id,
    si.id as sat_id,
    bt.id as bank_id,
    ABS(me.amount - (si.parsed_data->>'total')::NUMERIC) as amount_diff,
    ABS(EXTRACT(DAYS FROM (me.expense_date - (si.parsed_data->>'fecha_emision')::DATE))) as date_diff
FROM manual_expenses me
LEFT JOIN sat_invoices si ON
    si.parsed_data->>'rfc_emisor' = me.provider_rfc
    AND ABS(EXTRACT(DAYS FROM (me.expense_date - (si.parsed_data->>'fecha_emision')::DATE))) <= 3
    AND ABS(me.amount - (si.parsed_data->>'total')::NUMERIC) / me.amount <= 0.05
LEFT JOIN bank_transactions bt ON
    bt.vendor_rfc = me.provider_rfc
    AND ABS(EXTRACT(DAYS FROM (bt.transaction_date - me.expense_date))) <= 3
    AND ABS(ABS(bt.amount) - me.amount) / me.amount <= 0.05
WHERE me.tenant_id = 2
  AND me.id IN (102, 103)
  AND me.reconciliation_status = 'unmatched';
```

**Resultados Layer 1:**
```json
{
  "layer1_matches": [
    {
      "manual_expense_id": 102,
      "sat_invoice_id": "B2C3D4E5-F6G7-8901-BCDE-2345678901BC",
      "bank_transaction_id": 502,
      "match_type": "mathematical_tolerance",
      "confidence": 0.95,
      "explanation": "RFC coincide, diferencia de $2.35 (0.47%) dentro de tolerancia del 5%",
      "matched_fields": {
        "rfc": "ISD950921HE5",
        "date": "2025-11-19",
        "amount_manual": 500.00,
        "amount_sat": 502.35,
        "amount_bank": 502.35,
        "amount_diff": 2.35,
        "amount_diff_pct": 0.47
      },
      "requires_review": true,
      "review_reason": "Discrepancia de monto: posible comisión no registrada"
    }
  ],
  "unmatched": [
    {
      "manual_expense_id": 103,
      "reason": "Missing provider_rfc, cannot match with SAT invoice. Missing SAT invoice entirely."
    }
  ]
}
```

**✅ Match con Tolerancia:** Gasto #102 (PASE) matcheó con 5% de diferencia
**⚠️ Requiere Revisión Humana:** Diferencia de $2.35 debe ser explicada
**❌ Sin Match:** Gasto #103 pasa a Layer 2

---

### LAYER 2: Vector Similarity Matching (Embeddings)

**Proceso:**
1. Crear embedding del gasto manual #103:
   ```json
   {
     "text_to_embed": "Mantenimiento Scania Monterrey, monto: $15600.00, fecha: 2025-11-20, categoría: mantenimiento"
   }
   ```

2. Buscar vectorialmente en:
   - `sat_invoices.parsed_data` (descripción de conceptos)
   - `bank_transactions.description`

**Query vectorial ejecutado:**
```python
# Pseudo-código
manual_embedding = get_embedding("Mantenimiento Scania Monterrey 15600.00 mantenimiento")

# Buscar en SAT invoices
sat_results = search_similar_sat_invoices(
    embedding=manual_embedding,
    tenant_id=2,
    date_range=("2025-11-17", "2025-11-23"),  # ±3 días
    amount_range=(14820, 16380),  # ±5%
    top_k=5
)

# Buscar en Bank transactions
bank_results = search_similar_bank_transactions(
    embedding=manual_embedding,
    tenant_id=2,
    date_range=("2025-11-17", "2025-11-23"),
    amount_range=(14820, 16380),
    top_k=5
)
```

**Resultados Layer 2:**
```json
{
  "layer2_matches": [
    {
      "manual_expense_id": 103,
      "sat_invoice_id": null,
      "bank_transaction_id": 503,
      "match_type": "partial_bank_only",
      "confidence": 0.65,
      "explanation": "Posible match: retiro ATM $16,000 vs gasto manual $15,600. Diferencia $400 podría ser efectivo retenido.",
      "similarity_scores": {
        "bank_description_similarity": 0.45,
        "amount_proximity": 0.975,
        "date_proximity": 1.0
      },
      "requires_review": true,
      "review_reason": "Solo match bancario (retiro efectivo), sin factura SAT. Usuario marcó 'invoice_required: false'."
    }
  ],
  "unmatched_sat": [
    {
      "manual_expense_id": 103,
      "reason": "No SAT invoice found. This is a cash expense without invoice."
    }
  ]
}
```

**⚠️ Match Parcial:** Solo banco, sin factura SAT
**❗ FLAW #5 Detectado:** ¿Cómo manejamos gastos en efectivo sin factura?

---

### LAYER 3: LLM Reasoning (AI-Powered)

**Prompt enviado al LLM:**
```json
{
  "prompt": "Analyze this expense reconciliation case:\n\nManual Expense:\n- Description: 'Mantenimiento Scania Monterrey'\n- Amount: $15,600.00\n- Date: 2025-11-20\n- Provider: Scania (RFC: unknown)\n- Category: mantenimiento\n- Invoice required: NO\n\nBank Transaction (potential match):\n- Description: 'RETIRO ATM BANAMEX'\n- Amount: $16,000.00\n- Date: 2025-11-20\n- Type: cash withdrawal\n\nSAT Invoice:\n- NOT FOUND\n\nQuestion: Should we match these? Explain your reasoning.",
  "context": {
    "business": "Logistics company with truck fleet",
    "policy": "Cash expenses under $20,000 MXN allowed without invoice for urgent maintenance"
  }
}
```

**Respuesta del LLM:**
```json
{
  "llm_recommendation": {
    "should_match": true,
    "confidence": 0.75,
    "reasoning": "This appears to be a legitimate cash expense for truck maintenance. The $400 difference ($16,000 withdrawal vs $15,600 expense) is reasonable - likely the driver kept $400 as petty cash or for tolls. The timing (same day), category (maintenance), and company policy (allows cash expenses for urgent maintenance) support this match.",
    "suggested_action": "CREATE_MATCH_WITH_REVIEW",
    "flags": [
      "CASH_EXPENSE_NO_INVOICE",
      "AMOUNT_DISCREPANCY_400_MXN",
      "REQUIRES_RECEIPT_UPLOAD"
    ],
    "next_steps": [
      "Request maintenance receipt/evidence from driver",
      "Verify Scania provider with purchase order",
      "Confirm $400 petty cash reconciliation"
    ]
  }
}
```

**✅ Match con IA:** LLM recomienda matchear con revisión humana

---

## 📝 PARTE 3: CREACIÓN DE MATCHES EN reconciliation_matches

```json
{
  "reconciliation_matches": [
    {
      "id": 1001,
      "manual_expense_id": 101,
      "sat_invoice_id": "A1B2C3D4-E5F6-7890-ABCD-1234567890AB",
      "bank_transaction_id": 501,
      "match_layer": "layer0_sql",
      "confidence": 1.00,
      "explanation": "Perfect 3-way match: RFC, date, and amount match exactly across all sources",
      "manual_amount_allocated": 1250.50,
      "sat_amount_allocated": 1250.50,
      "bank_amount_allocated": 1250.50,
      "status": "accepted",
      "requires_review": false,
      "created_at": "2025-12-08T10:00:00Z",
      "created_by": null,
      "reviewed_by": null,
      "reviewed_at": null,
      "review_notes": null,
      "tenant_id": 2
    },
    {
      "id": 1002,
      "manual_expense_id": 102,
      "sat_invoice_id": "B2C3D4E5-F6G7-8901-BCDE-2345678901BC",
      "bank_transaction_id": 502,
      "match_layer": "layer1_math",
      "confidence": 0.95,
      "explanation": "Mathematical match with 0.47% tolerance. Difference of $2.35 likely due to bank fee or commission not recorded in manual expense.",
      "manual_amount_allocated": 500.00,
      "sat_amount_allocated": 502.35,
      "bank_amount_allocated": 502.35,
      "status": "pending",
      "requires_review": true,
      "created_at": "2025-12-08T10:00:00Z",
      "created_by": null,
      "reviewed_by": null,
      "reviewed_at": null,
      "review_notes": null,
      "tenant_id": 2
    },
    {
      "id": 1003,
      "manual_expense_id": 103,
      "sat_invoice_id": null,
      "bank_transaction_id": 503,
      "match_layer": "layer3_llm",
      "confidence": 0.75,
      "explanation": "LLM-assisted match: Cash expense for truck maintenance. $400 discrepancy explained as driver petty cash. No SAT invoice (allowed for cash maintenance under $20k).",
      "manual_amount_allocated": 15600.00,
      "sat_amount_allocated": null,
      "bank_amount_allocated": 16000.00,
      "status": "pending",
      "requires_review": true,
      "created_at": "2025-12-08T10:00:00Z",
      "created_by": null,
      "reviewed_by": null,
      "reviewed_at": null,
      "review_notes": null,
      "tenant_id": 2
    }
  ]
}
```

---

## 🚨 PARTE 4: FLAWS Y CAMPOS FALTANTES IDENTIFICADOS

### FLAW #1: Gastos en Efectivo Sin Factura
**Problema:**
- `manual_expenses[2]` es un gasto en efectivo sin factura SAT
- `reconciliation_matches[2]` solo tiene `bank_transaction_id`, no `sat_invoice_id`

**¿Necesitamos agregar?**
```json
{
  "manual_expenses": {
    "cash_receipt_required": "BOOLEAN",
    "cash_receipt_url": "TEXT",
    "cash_receipt_uploaded_at": "TIMESTAMPTZ",
    "expense_justification": "TEXT"
  }
}
```

### FLAW #2: Discrepancias de Monto (Comisiones/Fees)
**Problema:**
- Manual: $500.00 vs SAT/Banco: $502.35 (diferencia de $2.35)
- No tenemos forma de registrar esta diferencia

**¿Necesitamos agregar?**
```json
{
  "reconciliation_matches": {
    "amount_discrepancy": "NUMERIC(15,2)",
    "discrepancy_reason": "VARCHAR(50)",
    "discrepancy_explanation": "TEXT"
  }
}
```

Valores posibles para `discrepancy_reason`:
- `bank_fee`
- `commission`
- `exchange_rate`
- `rounding`
- `petty_cash`
- `other`

### FLAW #3: Ingresos en Reconciliación
**Problema:**
- `bank_transactions[3]` es un INGRESO ($35,000 depósito)
- Actualmente tratamos todo como gastos

**¿Necesitamos?**
- Tabla separada `income_reconciliation_matches`?
- Columna `reconciliation_type` en `reconciliation_matches`?

```json
{
  "reconciliation_matches": {
    "reconciliation_type": "VARCHAR(20)"
  }
}
```

Valores: `expense`, `income`, `transfer`

### FLAW #4: Vendor RFC Extraction Failed
**Problema:**
- `bank_transactions[1]` (PASE) no tiene `vendor_rfc` extraído
- Descripción: "SPEI PASE SERVICIOS" - no detectó el RFC

**Solución:**
- Mejorar extractor de RFC en `bank_transactions`
- Agregar campo `vendor_rfc_extraction_attempted`:

```json
{
  "bank_transactions": {
    "vendor_rfc_extraction_attempted": "BOOLEAN DEFAULT FALSE",
    "vendor_rfc_extraction_date": "TIMESTAMPTZ",
    "vendor_rfc_extraction_method": "VARCHAR(50)"
  }
}
```

### FLAW #5: Splits (Un Pago → Múltiples Gastos)
**Problema:** ¿Qué pasa si un retiro ATM de $16,000 se usó para:
- $15,600 mantenimiento
- $400 gasolina

**Solución actual:** Ya existe `manual_amount_allocated`, `sat_amount_allocated`, `bank_amount_allocated`

**Pero falta:**
```json
{
  "reconciliation_matches": {
    "is_split": "BOOLEAN DEFAULT FALSE",
    "split_group_id": "UUID",
    "split_sequence": "INTEGER"
  }
}
```

### FLAW #6: Auditoría de Cambios
**Problema:** Si un match se rechaza y se vuelve a crear, no hay historial

**¿Necesitamos?**
```json
{
  "reconciliation_match_history": {
    "id": "SERIAL PRIMARY KEY",
    "match_id": "INTEGER REFERENCES reconciliation_matches(id)",
    "old_status": "VARCHAR(20)",
    "new_status": "VARCHAR(20)",
    "changed_by": "INTEGER REFERENCES users(id)",
    "changed_at": "TIMESTAMPTZ DEFAULT NOW()",
    "change_reason": "TEXT"
  }
}
```

---

## ✅ PARTE 5: ESTADO FINAL DESPUÉS DE RECONCILIACIÓN

### Updates en las tablas principales:

**manual_expenses actualizado:**
```json
{
  "id": 101,
  "sat_invoice_id": "A1B2C3D4-E5F6-7890-ABCD-1234567890AB",
  "bank_transaction_id": 501,
  "reconciliation_status": "matched",
  "reconciliation_confidence": 1.00,
  "reconciliation_layer": "layer0_sql",
  "reconciliation_date": "2025-12-08T10:00:00Z"
}
```

**bank_transactions actualizado:**
```json
{
  "id": 501,
  "sat_invoice_id": "A1B2C3D4-E5F6-7890-ABCD-1234567890AB",
  "manual_expense_id": 101,
  "reconciliation_status": "matched",
  "reconciliation_confidence": 1.00,
  "reconciliation_layer": "layer0_sql",
  "reconciliation_date": "2025-12-08T10:00:00Z"
}
```

**sat_invoices actualizado:**
```json
{
  "id": "A1B2C3D4-E5F6-7890-ABCD-1234567890AB",
  "bank_transaction_id": 501,
  "manual_expense_id": 101,
  "reconciliation_status": "matched",
  "reconciliation_confidence": 1.00,
  "reconciliation_layer": "layer0_sql",
  "reconciliation_date": "2025-12-08T10:00:00Z"
}
```

---

## 🎯 RESUMEN DE CAMPOS QUE FALTAN

### Alta Prioridad (Critical):
1. **Manejo de discrepancias de monto:**
   - `reconciliation_matches.amount_discrepancy`
   - `reconciliation_matches.discrepancy_reason`
   - `reconciliation_matches.discrepancy_explanation`

2. **Gastos en efectivo:**
   - `manual_expenses.cash_receipt_url`
   - `manual_expenses.cash_receipt_uploaded_at`

3. **Splits:**
   - `reconciliation_matches.is_split`
   - `reconciliation_matches.split_group_id`

### Media Prioridad:
4. **Tipo de reconciliación:**
   - `reconciliation_matches.reconciliation_type` (expense/income/transfer)

5. **RFC extraction tracking:**
   - `bank_transactions.vendor_rfc_extraction_attempted`
   - `bank_transactions.vendor_rfc_extraction_date`

### Baja Prioridad:
6. **Historial de auditoría:**
   - Tabla `reconciliation_match_history`
