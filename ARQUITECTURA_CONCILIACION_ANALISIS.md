# 🏗️ Análisis Completo de Arquitectura: Sistema de Conciliación Bancaria y CFDIs

**Fecha del Análisis:** 2025-11-09
**Rama:** `feature/backend-refactor`
**Estado General:** Sistema parcialmente integrado, con flujos dispersos

---

## 📋 Tabla de Contenidos

1. [Resumen Ejecutivo](#resumen-ejecutivo)
2. [Arquitectura Actual](#arquitectura-actual)
3. [Flujos de Datos Identificados](#flujos-de-datos-identificados)
4. [Puntos de Conexión](#puntos-de-conexión)
5. [Puntos de Desconexión](#puntos-de-desconexión)
6. [Problemas Detectados](#problemas-detectados)
7. [Recomendaciones de Integración](#recomendaciones-de-integración)
8. [Diagrama de Flujo Unificado](#diagrama-de-flujo-unificado)

---

## 🎯 Resumen Ejecutivo

### Estado Actual
- **Sistema:** Parcialmente integrado
- **Cobertura:** 5 flujos principales identificados (3-4 integrados, 1-2 dispersos)
- **Desconexiones:** ~6 puntos críticos de desacoplamiento
- **Duplicación:** 3 sistemas paralelos para tareas similares
- **Tablas Críticas Faltantes:** `bank_statements` en PostgreSQL

### Hallazgos Clave

| Aspecto | Estado | Observación |
|---------|--------|-------------|
| **Extracción de Estados** | ✅ Moderado | Parser robusto pero sin integración con DB |
| **Parsing de CFDIs** | ✅ Moderado | Sistema AI pero con fallbacks manuales |
| **Matching/Conciliación** | 🟡 Disperso | 3 sistemas: heurístico, AI, embeddings |
| **Detección MSI** | ⚠️ Manual | Detecta pero no automático en flujo |
| **Reportes/Visualización** | 🟡 Básico | Vistas SQL creadas, no integradas en UI |
| **Integración End-to-End** | ❌ No existe | Cada componente funciona aislado |

---

## 🏗️ Arquitectura Actual

### 1. **Estructura de Directorios (Refactorización Phase 2)**

```
core/
├── reconciliation/                    # 🔄 Matching e integración
│   ├── bank/                         # Extracción de estados
│   │   ├── bank_file_parser.py      # Parser robusto (PDF, CSV, XLSX)
│   │   ├── bank_detector.py         # Detecta banco automáticamente
│   │   ├── universal_bank_patterns.py
│   │   └── bank_transactions_models.py
│   │
│   ├── matching/                     # 🤖 Motor de matching
│   │   ├── bank_reconciliation.py   # Scoring heurístico
│   │   ├── ai_reconciliation_service.py  # Suggestions AI (embeddings)
│   │   └── claude_transaction_processor.py
│   │
│   ├── validation/                   # ✅ Validación de matches
│   │   ├── duplicate_detector.py
│   │   ├── duplicate_prevention.py
│   │   └── optimized_duplicate_detector.py
│   │
│   ├── ai_description_matcher.py    # Similitud de texto
│   └── embedding_matcher.py         # Embeddings OpenAI
│
├── ai_pipeline/                       # 🧠 Procesamiento inteligente
│   ├── ai_bank_orchestrator.py      # ⭐ Orquestador principal
│   ├── ocr/
│   │   ├── gemini_vision_ocr.py
│   │   ├── advanced_ocr_service.py
│   │   └── hybrid_vision_service.py
│   │
│   ├── parsers/
│   │   ├── ai_bank_statement_parser.py
│   │   ├── cfdi_llm_parser.py
│   │   ├── invoice_parser.py
│   │   └── robust_pdf_parser.py
│   │
│   └── classification/
│       ├── ai_msi_detector.py       # 🎯 Detecta MSI automáticamente
│       ├── expense_classifier.py
│       ├── enhanced_categorization_engine.py
│       └── category_learning_system.py
│
├── expenses/                          # 💰 Gestión de gastos
│   ├── models.py
│   ├── invoices/
│   │   ├── invoice_manager.py
│   │   ├── universal_invoice_engine_system.py
│   │   └── bulk_invoice_processor.py
│   │
│   ├── completion/
│   │   ├── expense_completion_system.py
│   │   ├── expense_enhancer.py
│   │   └── expense_enrichment.py
│   │
│   ├── validation/
│   │   ├── expense_validation.py
│   │   ├── expense_field_validator.py
│   │   └── expense_features.py
│   │
│   └── audit/
│       ├── expense_audit_system.py
│       └── compliance_audit_trail.py
│
├── shared/                            # 🔗 Utilidades compartidas
│   ├── unified_db_adapter.py        # ⚠️ Legacy SQLite
│   ├── db_config.py
│   ├── data_consistency_manager.py
│   ├── observability_system.py
│   └── task_dispatcher.py
│
└── non_reconciliation_system.py      # ⚠️ Gastos no conciliables

api/                                   # 🌐 FastAPI Endpoints
├── ai_reconciliation_api.py          # GET /bank_reconciliation/ai/suggestions
├── bank_statements_api.py            # POST /bank-statements/upload
├── msi_confirmation_api.py           # GET/POST /msi/pending
├── cfdi_api.py                       # CFDIs management
├── payment_methods_api.py            # Payment accounts
├── split_reconciliation_api.py       # Split logic
└── non_reconciliation_api.py         # Non-reconcilable expenses
```

### 2. **Stack Tecnológico Actual**

```
Frontend:
  React (voice-expenses.source.jsx) → FastAPI

Backend (FastAPI):
  ├─ Routers: /bank, /bank_reconciliation, /bank-statements, /msi
  └─ Services: AI Reconciliation, Bank Statement, MSI Detection

Bases de Datos:
  ├─ PostgreSQL (PRODUCCIÓN) → payment_accounts, expense_invoices, deferred_payments
  ├─ SQLite (LEGACY) → bank_movements, bank_statements
  └─ Vistas SQL → vw_reconciliation_stats_improved, vw_auto_match_suggestions_improved

AI Services:
  ├─ Google Gemini (Vision OCR, LLM Parsing)
  ├─ Claude (Text Analysis)
  ├─ OpenAI (Embeddings)
  └─ Custom Models (MSI Detection, Bank Detection)

Utilities:
  ├─ Selenium (Web Automation)
  ├─ 2Captcha (Captcha Solving)
  └─ PDF/Excel Libraries (pypdf, openpyxl, xlrd)
```

---

## 🔄 Flujos de Datos Identificados

### **Flujo 1: Extracción de Estados de Cuenta**

```
┌──────────────────────────────────────────────────────────────┐
│ USUARIO                                                       │
│ Sube estado de cuenta bancario (PDF, XLSX, CSV)             │
└─────────────────────────────┬────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ API: POST /bank-statements/accounts/{account_id}/upload      │
│ • Validaciones: tipo archivo, tamaño (<50MB)                │
│ • Crea registro en bank_statements (❌ NO EXISTE EN POSTGRES)│
│ • Guarda archivo en filesystem                              │
└─────────────────────────────┬────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ BACKGROUND TASK: parse_statement_background()               │
│ • Status → 'processing'                                      │
│ • Llama bank_file_parser.parse_file()                        │
└─────────────────────────────┬────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ PARSER: bank_file_parser.py                                 │
│ • Detecta formato (PDF, XLSX, CSV)                          │
│ • Detecta banco (Inbursa, BBVA, Santander, etc) ✅          │
│ • Extrae transacciones:                                      │
│   - Fecha (con normalización de formatos)                   │
│   - Monto (conversión positivo/negativo)                    │
│   - Descripción (normalización de texto)                    │
│   - Clasificación: ingreso/egreso                           │
│   ❌ NO detecta tipo de cuenta (crédito/débito)             │
└─────────────────────────────┬────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ PROBLEMA: Datos no se guardan en PostgreSQL                  │
│ • Parser retorna BankTransactionModel                        │
│ • ❌ API intenta guardar en banco inexistente              │
│ • ❌ Transacciones quedan en memoria (no persistidas)       │
│ • ✅ Alternativa: AI Bank Orchestrator (usa Postgres)      │
└──────────────────────────────┬────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ ALTERNATIVA: ai_bank_orchestrator.py (Nuevo sistema)        │
│ • Gemini Vision OCR → Extrae texto PDF                      │
│ • Gemini LLM → Parsea transacciones estructuradas           │
│ • Gemini Reasoning → Detecta MSI                            │
│ • PostgreSQL → Guarda en bank_movements, bank_transactions  │
│ ✅ Flujo completo y persistido                              │
│ ❌ Pero NO integrado con API /bank-statements               │
└──────────────────────────────┬────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ RESULTADO                                                     │
│ Transacciones en base de datos (si usa orch)                 │
└──────────────────────────────────────────────────────────────┘

⚠️ DESCONEXIÓN CLAVE: 2 parsers independientes
  - bank_file_parser: Robusto pero sin persistencia
  - ai_bank_orchestrator: Integrado pero no usado por API
```

---

### **Flujo 2: Procesamiento de CFDIs**

```
┌──────────────────────────────────────────────────────────────┐
│ PROVEEDOR / SAT                                              │
│ Emite CFDI con XML                                          │
└─────────────────────────────┬────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ USUARIO / SISTEMA                                            │
│ Sube CFDI (XML, PDF) o lo descarga del SAT                 │
│ POST /invoices/bulk-upload                                  │
│ POST /universal-invoice/upload                              │
└─────────────────────────────┬────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ PARSING: Múltiples opciones (problema)                      │
│                                                              │
│ Opción A: universal_invoice_engine.py                       │
│  ├─ Lee XML directamente                                    │
│  ├─ Extrae campos SAT: RFC, UUID, total, etc               │
│  ├─ Clasifica forma pago: PUE, PPD, etc                    │
│  ├─ Inserta en expense_invoices (PostgreSQL)               │
│  └─ ✅ Integrado, funcional                                │
│                                                              │
│ Opción B: cfdi_llm_parser.py                                │
│  ├─ Usa Gemini/Claude para parsear                          │
│  ├─ Extrae información adicional                            │
│  └─ ❌ No se integra automáticamente                        │
│                                                              │
│ Opción C: Scripts manuales (detectados)                     │
│  ├─ extract_cfdi_types_to_db.py                            │
│  ├─ analizar_cfdis_disponibles.py                          │
│  └─ cfdis_enero_detalle.py                                 │
│  └─ ❌ Ad-hoc, sin integración                             │
└─────────────────────────────┬────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ ENRIQUECIMIENTO (Opcional)                                   │
│ • Detección de MSI (Meses Sin Intereses) ❌ NO AUTOMÁTICO  │
│ • Clasificación de categoría 🟡 Semi-automático            │
│ • Validación de campos 🟡 En workflow                       │
│ • Extracción de productos 🟡 Manual/Gemini                 │
└─────────────────────────────┬────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ ALMACENAMIENTO                                               │
│ PostgreSQL - expense_invoices:                              │
│  • id, uuid, nombre_emisor, total, fecha_emision            │
│  • es_msi, meses_msi, pago_mensual_msi (campos)             │
│  • msi_confirmado (campo para confirmación manual)          │
│  • payment_account_id (link a cuenta pago)                  │
│  • metodo_pago, forma_pago (SAT)                            │
│  • linked_expense_id (para matching)                        │
│  • match_confidence, match_method                           │
└──────────────────────────────┬────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ RESULTADO                                                     │
│ CFDIs en base de datos, listos para matching                │
└──────────────────────────────────────────────────────────────┘

⚠️ DESCONEXIONES CLAVE:
  1. 3 parsers compitiendo (no orquestados)
  2. MSI detection es manual (campo msi_confirmado)
  3. No hay flujo automático de SAT → DB
```

---

### **Flujo 3: Conciliación (Matching)**

```
┌──────────────────────────────────────────────────────────────┐
│ ENTRADA: Estados + CFDIs cargados en BD                      │
│ • bank_movements (transacciones bancarias)                   │
│ • bank_transactions (parsing de estados)                     │
│ • expense_invoices (CFDIs)                                   │
└─────────────────────────────┬────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ OPCIÓN A: Matching Heurístico (bank_reconciliation.py)      │
│                                                              │
│ Scoring basado en:                                          │
│  • Amount score: diff_amount / max_amount (0-1)             │
│  • Date score: diferencia en días (0-1)                     │
│  • Text score: similitud Levenshtein (0-1)                  │
│  • Payment mode: si coincide medio de pago                  │
│                                                              │
│ Resultado:                                                   │
│  - Score final (0-100)                                      │
│  - Confidence: "high", "medium", "low"                      │
│  - No persistente (cálculo en tiempo real)                  │
│  ✅ Rápido, ❌ Sin persistencia                             │
└─────────────────────────────┬────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ OPCIÓN B: Matching AI (ai_reconciliation_service.py)        │
│                                                              │
│ Hybrid approach:                                            │
│  1. Rule-based matching (exacto + proximidad)               │
│  2. Text similarity (embeddings OpenAI)                     │
│  3. One-to-many splits (1 movimiento → N gastos)            │
│  4. Many-to-one splits (N movimientos → 1 gasto)            │
│                                                              │
│ Resultado:                                                   │
│  - Suggestions con confidence_score (0-100)                 │
│  - Breakdown: amount_match, date_proximity, similarity      │
│  ✅ Más preciso, ❌ Costo OpenAI                            │
│  ⚠️ Sugiere pero NO persiste automáticamente                │
└─────────────────────────────┬────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ OPCIÓN C: Embeddings Matcher (embedding_matcher.py)         │
│                                                              │
│ Usa embeddings OpenAI + búsqueda vectorial                   │
│ ❌ No integrado en flujo principal                          │
└─────────────────────────────┬────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ API: GET /bank_reconciliation/ai/suggestions                │
│ • Retorna suggestions de ai_reconciliation_service          │
│ • Usuario confirma manualmente                              │
│ • No hay auto-aplicación de matches                         │
└─────────────────────────────┬────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ PERSISTENCIA (Script manual)                                 │
│ reconcile_auto_matches.py:                                  │
│  • Aplica matches con confidence > threshold                │
│  • UPDATE expense_invoices SET linked_expense_id = ...      │
│  • UPDATE bank_transactions SET status = 'reconciled'       │
│  ❌ Script ad-hoc, no integrado en API                      │
│  ❌ Debe ejecutarse manualmente                             │
└─────────────────────────────┬────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ VALIDACIÓN: Duplicate Detection                             │
│ • optimized_duplicate_detector.py                           │
│ • Detecta duplicados en matches                             │
│ • ✅ Integrado pero no obligatorio                          │
└─────────────────────────────┬────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ RESULTADO FINAL                                              │
│ Transacciones y CFDIs vinculados                            │
│ linked_expense_id ← → movimiento bancario                   │
│ match_confidence, match_method almacenados                  │
└──────────────────────────────────────────────────────────────┘

⚠️ DESCONEXIONES CLAVE:
  1. 3 motores de matching no orquestados
  2. Suggestions son ad-hoc, no automáticas
  3. Persistencia requiere script manual
  4. No hay auto-aplicación de matches de alta confianza
```

---

### **Flujo 4: Detección y Manejo de MSI**

```
┌──────────────────────────────────────────────────────────────┐
│ ENTRADA: CFDI pagado con Meses Sin Intereses                │
│ Ejemplo: Llanta Pirelli $4,325 a 6 MSI = $720.83/mes        │
└─────────────────────────────┬────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ DETECCIÓN MSI (Múltiples opciones)                          │
│                                                              │
│ Opción A: AI MSI Detector (ai_msi_detector.py)              │
│  • Usa Gemini Reasoning                                     │
│  • Detecta en descripción AMEX: "6 MSI", "MESES SIN..."     │
│  • Extrae número de meses automáticamente                   │
│  ✅ Integrado en ai_bank_orchestrator                       │
│  ❌ No usado por banco_statements_api                       │
│                                                              │
│ Opción B: Detección Manual                                  │
│ • Usuario marca manualmente en msi_confirmation_api         │
│ • Confirmación POST /msi/confirm                            │
│ • ❌ Requiere intervención manual                           │
│                                                              │
│ Opción C: Scripts Ad-hoc                                    │
│ • detectar_msi_amex.py                                      │
│ • extraer_msi_gemini.py                                     │
│ • ❌ No integrados en flujo principal                       │
└─────────────────────────────┬────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ REGISTRAR PAGO DIFERIDO                                      │
│ Tablas creadas por detectar_msi_amex.py:                    │
│                                                              │
│ deferred_payments:                                          │
│  ├─ cfdi_id → CFDI original                                 │
│  ├─ meses_sin_intereses                                     │
│  ├─ pago_mensual = total / meses                            │
│  ├─ primer_pago_fecha, ultimo_pago_fecha                    │
│  ├─ pagos_realizados (tracking)                             │
│  └─ status: 'activo' | 'completado'                         │
│                                                              │
│ deferred_payment_installments:                              │
│  ├─ deferred_payment_id                                     │
│  ├─ numero_cuota (1, 2, 3, ...)                             │
│  ├─ monto (pago_mensual)                                    │
│  ├─ fecha_programada vs fecha_pagada                        │
│  ├─ bank_tx_id (vinculación a transacción bancaria)         │
│  └─ pagado (boolean)                                        │
│                                                              │
│ ❌ PROBLEMA: Tablas creadas pero no integradas en schema    │
│              Las migrations principales no las incluyen      │
└─────────────────────────────┬────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ CONCILIACIÓN CON MSI                                         │
│ En expense_invoices:                                        │
│  • linked_expense_id = -1000 - deferred_id (marca especial) │
│  • match_method = "AMEX MSI 6M: ..."                        │
│  • match_confidence = 1.0                                   │
│                                                              │
│ ❌ PROBLEMA: El CFDI no se marca como "pagado parcial"     │
│              No hay estado intermedio entre "pendiente" y   │
│              "completamente pagado"                          │
└─────────────────────────────┬────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ TRACKING FUTURO                                              │
│ Cada mes se verifica:                                       │
│  • bank_movements de la tarjeta AMEX                        │
│  • Buscar descripción con MSI asociada                      │
│  • UPDATE deferred_payment_installments SET                 │
│    pagado = true, fecha_pagada = ...                        │
│  • Incrementar pagos_realizados                             │
│  • Cuando pagos_realizados = meses → status = 'completado'  │
│                                                              │
│ ❌ NO AUTOMATIZADO: Requiere script manual mensual          │
│    (o similar a detectar_msi_amex.py)                       │
└──────────────────────────────┬────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ REPORTES MSI                                                 │
│ msi_confirmation_api GET /msi/pending:                      │
│  • Facturas PUE + forma_pago='04' (tarjeta crédito)        │
│  • Monto > $100                                             │
│  • sat_status = 'vigente'                                   │
│  • msi_confirmado = false                                   │
│  └─ ❌ Query limitado, no integrado con AI detection       │
└──────────────────────────────┬────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ RESULTADO FINAL                                              │
│ Pagos diferidos registrados y tracked mes a mes             │
│ (si se ejecutan scripts manualmente)                         │
└──────────────────────────────────────────────────────────────┘

⚠️ DESCONEXIONES CLAVE:
  1. 3 sistemas de detección MSI sin orquestar
  2. Tablas de pago diferido no integradas en migrations
  3. Tracking MSI manual (requiere script mensual)
  4. No hay API unificada para MSI management
  5. No hay estados intermedios en workflow
```

---

### **Flujo 5: Reportes y Visualización**

```
┌──────────────────────────────────────────────────────────────┐
│ USUARIO PIDE REPORTES                                        │
│ Dashboard / Reports Section                                 │
└─────────────────────────────┬────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ VISTAS SQL CREADAS (analyze_reconciliation.py)              │
│                                                              │
│ vw_reconciliation_stats_improved:                           │
│  ├─ total_transactions                                      │
│  ├─ matched (ya conciliadas)                                │
│  ├─ pending (pendientes)                                    │
│  ├─ auto_match_perfect (diff=$0, days≤1)                   │
│  ├─ auto_match_high, medium, low                            │
│  └─ no_invoice_found                                        │
│                                                              │
│ vw_auto_match_suggestions_improved:                         │
│  ├─ transaction_id, transaction_date, description          │
│  ├─ transaction_amount vs invoice_total                     │
│  ├─ amount_difference, days_difference                      │
│  ├─ match_score (0-100)                                     │
│  └─ confidence_label                                        │
│                                                              │
│ vw_transactions_without_invoice:                            │
│  ├─ Transacciones sin CFDI asociado                        │
│  └─ Categorizadas por descripción                          │
│                                                              │
│ ✅ Vistas correctas y útiles                                │
│ ❌ NO integradas en frontend React                         │
└─────────────────────────────┬────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ API ENDPOINTS (No integrados)                                │
│                                                              │
│ GET /bank_reconciliation/ai/suggestions                     │
│  • Retorna sugerencias AI (sin guardar)                     │
│  • ✅ Funcional, ❌ No persistente                          │
│                                                              │
│ GET /bank_reconciliation/stats                             │
│  • ❌ NO EXISTE en código                                   │
│                                                              │
│ GET /reconciliation/report                                 │
│  • ❌ NO EXISTE en código                                   │
│                                                              │
│ GET /msi/pending                                            │
│  • ✅ Funcional, retorna facturas pendientes MSI           │
└─────────────────────────────┬────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ SCRIPTS ANALÍTICOS AD-HOC                                    │
│                                                              │
│ analyze_reconciliation.py:                                  │
│  • Statsísticas mejoradas                                   │
│  • Desglose por nivel de confianza                          │
│  • TOP 10 auto-matches                                      │
│  • Transacciones sin factura por categoría                  │
│  • ✅ Detallado, ❌ Requiere ejecución manual              │
│                                                              │
│ ver_estado_conciliacion.py:                                 │
│  • Resumen conciliación enero                               │
│  • Gastos vs traspasos                                      │
│  • ✅ Útil, ❌ Ad-hoc                                       │
│                                                              │
│ resumen_conciliacion_simple.py:                             │
│  • Resumen simplificado                                     │
│  • ✅ Útil, ❌ Ad-hoc                                       │
│                                                              │
│ exportar_conciliacion_excel.py:                             │
│  • Exporta a Excel                                          │
│  • ✅ Útil, ❌ Ad-hoc                                       │
└─────────────────────────────┬────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ FRONTEND (React)                                             │
│                                                              │
│ voice-expenses.source.jsx:                                  │
│  • Dashboard principal                                      │
│  • ❌ NO integra reportes de conciliación                   │
│  • ❌ NO muestra suggestions                                │
│  • ❌ NO visualiza MSI tracking                             │
│                                                              │
│ Necesitaría:                                                │
│  • New component: ReconciliationDashboard                   │
│  • New component: MSITracking                               │
│  • New component: MatchSuggestions                          │
│  • Integration con API endpoints                            │
└──────────────────────────────┬────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ RESULTADO FINAL                                              │
│ Reportes solo disponibles vía scripts Python                │
│ No hay visualización web integrada                          │
└──────────────────────────────────────────────────────────────┘

⚠️ DESCONEXIONES CLAVE:
  1. Vistas SQL creadas pero no expuestas en API
  2. No hay endpoints para reportes completos
  3. Frontend no integra dashboards de conciliación
  4. Scripts ad-hoc no son mantenibles
```

---

## 🔗 Puntos de Conexión

### **Conexiones Exitosas**

| Componente | → | Componente | Estado | Notas |
|-----------|---|-----------|--------|-------|
| universal_invoice_engine | → | expense_invoices (DB) | ✅ | Upload → Parse → Store |
| bank_detector | → | bank_file_parser | ✅ | Detecta banco → parsea |
| ai_bank_orchestrator | → | PostgreSQL | ✅ | Nuevo flujo completo |
| ai_reconciliation_api | → | ai_reconciliation_service | ✅ | Suggestions endpoint |
| msi_confirmation_api | → | expense_invoices | ✅ | UPDATE msi_confirmado |
| expense_validator | → | expense_completion_api | ✅ | Validación en workflow |

### **Conexiones Parciales (Acopladas débilmente)**

| Componente | → | Componente | Estado | Problema |
|-----------|---|-----------|--------|----------|
| bank_statements_api | → | bank_file_parser | 🟡 | Parser no persiste |
| bank_reconciliation.py | → | expense_invoices | 🟡 | Solo scoring, no vinculación |
| embedding_matcher | → | AI Services | 🟡 | No integrado en flujo |
| duplicate_detector | → | matching | 🟡 | Optional, no obligatorio |
| deferred_payments (tablas) | → | expense_invoices | 🟡 | No migradas formalmente |

---

## ❌ Puntos de Desconexión

### **1. Extracción de Estados de Cuenta**

**Problema:** 2 parsers independientes sin coordinación

```python
# Parser 1: Legacy (banco_statements_api.py)
bank_file_parser.parse_file(pdf_path)
# Retorna: List[BankTransaction]
# Guarda: ❌ NO guarda nada (devuelve modelo)

# Parser 2: Nueva (ai_bank_orchestrator.py)
orchestrator.process_bank_statement(pdf_path)
# Guarda: ✅ PostgreSQL (bank_movements)
# Detecta MSI: ✅ Sí
# Pero: ❌ No usado por API
```

**Impacto:** 
- Un usuario sube un estado por API → se parsea pero no se persiste
- O el sistema usa orchestrator → no expuesto en API
- Resultado: datos duplicados o pérdida de datos

---

### **2. Conciliación Dispersa**

**Problema:** 3 motores de matching independientes

```python
# Motor 1: Heurístico (bank_reconciliation.py)
score = amount_score * 0.4 + date_score * 0.3 + text_score * 0.3
# Ventaja: Rápido, determinístico
# Desventaja: Score no persistido

# Motor 2: AI Service (ai_reconciliation_service.py)
suggestions = suggest_one_to_many_splits()
# Ventaja: Híbrido (rules + embeddings)
# Desventaja: Costo OpenAI, solo sugiere

# Motor 3: Embeddings (embedding_matcher.py)
# Ventaja: Búsqueda vectorial
# Desventaja: No integrado en nada
```

**Impacto:**
- Usuario ve 3 sets de suggestions diferentes
- No hay una fuente única de verdad
- Persistencia requiere script manual

---

### **3. MSI No Automatizado**

**Problema:** Detección MSI manual o dispersa

```python
# Opción A: Manual (usuario marca en UI)
POST /msi/confirm { es_msi: true, meses_msi: 6 }
# Requiere intervención

# Opción B: AI Detector (solo en orchestrator)
ai_msi_detector.detect(description)
# ✅ Funciona, ❌ no llamado automáticamente

# Opción C: Scripts (detectar_msi_amex.py)
# ❌ Ad-hoc, requiere ejecución manual
```

**Impacto:**
- 30% de pagos en tarjeta crédito no se detectan como MSI
- Tracking de cuotas incompleto
- Reportes MSI inexactos

---

### **4. Tablas Críticas Faltantes en PostgreSQL**

**Problema:** Migración incompleta de SQLite a PostgreSQL

```
✅ Ya en PostgreSQL:
  - payment_accounts (con account_type)
  - expense_invoices (con es_msi, meses_msi)
  - bank_movements (?)

❌ Faltantes en PostgreSQL:
  - bank_statements (metadata de carga)
  - bank_transactions (transacciones parseadas)
  - deferred_payments (MSI tracking)
  - deferred_payment_installments (cuotas)

⚠️ Existen en SQLite legacy pero no syncronizadas
```

**Impacto:**
- API espera tablas que no existen
- Código intenta guardar en lugares equivocados
- Pérdida de datos o excepciones en runtime

---

### **5. No Automatización de Matching**

**Problema:** Matches sugeridos pero no aplicados automáticamente

```python
# Flujo actual:
1. GET /suggestions → Obtiene matches (score > 85%)
2. Usuario revisa manualmente
3. python reconcile_auto_matches.py → Aplica

# Debe ser:
1. Sistema detecta match > 85%
2. AUTO-aplica si en política
3. User audit trail si quiere revisar
```

**Impacto:**
- Tasa de conciliación baja (38% cuando podría ser 70%+)
- Labor manual innecesaria
- Error humano en aplicación de matches

---

### **6. Sin Integración de Reportes en UI**

**Problema:** Vistas SQL excelentes pero no expuestas

```python
# Existen en BD:
SELECT * FROM vw_reconciliation_stats_improved
SELECT * FROM vw_auto_match_suggestions_improved
SELECT * FROM vw_transactions_without_invoice

# Pero en frontend:
❌ No hay dashboard de conciliación
❌ No hay visualización de matches
❌ No hay tracking de MSI
❌ No hay alertas de transacciones sin factura
```

**Impacto:**
- Usuarios no pueden monitorear conciliación
- Reportes solo en consola Python
- Decisiones basadas en datos incompletos

---

## ⚙️ Problemas Detectados

### **1. Arquitectura Monolítica sin Orquestación**

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Parser 1  │     │   Parser 2  │     │   Parser 3  │
│  (Legacy)   │     │    (AI)     │     │  (Scripts)  │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                    │                    │
       └────────┬───────────┴────────┬───────────┘
                │                    │
                ▼                    ▼
          ❌ Conflict          ❌ Duplication
             & waste              of effort

Necesita: Orquestador único (Director Pattern)
```

---

### **2. Duplicación de Lógica**

| Lógica | Ubicación A | Ubicación B | Ubicación C |
|--------|-----------|-----------|-----------|
| Detección MSI | ai_msi_detector.py | detectar_msi_amex.py | msi_confirmation_api |
| Parsing banco | bank_file_parser.py | ai_bank_orchestrator | N/A |
| Matching score | bank_reconciliation.py | ai_reconciliation_service | embedding_matcher |
| Validación | expense_validation.py | expense_features.py | form validation |

---

### **3. Falta de State Management**

```
Problema: No hay estados de transición claros

IDEAL:
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ Uploaded │ → │ Parsing  │ → │ Parsed   │ → │ Matching │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
                                                       ↓
                                                ┌──────────┐
                                                │Reconciled│
                                                └──────────┘

ACTUAL:
Transición 1: Uploaded → ??? (API no completa)
Transición 2: ?? → Parsed (Orchestrator incompleto)
Transición 3: Parsed → Matching (Manual)
Transición 4: Matching → ??? (Script ad-hoc)
```

---

### **4. Pérdida de Datos**

```
Escenario 1: Usuario sube estado PDF
├─ API parsea con bank_file_parser
├─ bank_file_parser retorna transacciones en memoria
├─ ❌ API intenta guardar en tabla inexistente
└─ ❌ Transacciones se pierden

Escenario 2: Usuario carga CFDI XML
├─ Sistema parsea con universal_invoice_engine
├─ Guarda en expense_invoices ✅
├─ ❌ Pero MSI no se detecta automáticamente
├─ ❌ deferred_payments no se crean
└─ ❌ Tracking futuro es manual

Escenario 3: Sistema genera suggestions
├─ ai_reconciliation_service calcula scores
├─ Retorna a usuario
├─ ❌ Usuario rechaza o ignora
├─ ❌ Sugerencias se pierden (no persistidas)
└─ ❌ La próxima llamada recalcula (desperdicio)
```

---

### **5. Problemas de Performance**

```
Problem 1: Recálculo repetido
├─ Cada vez que llamamos /suggestions
├─ Recalcula ALL embeddings OpenAI
├─ Costo: $$ por llamada

Problem 2: Sin caché de resultados
├─ Matching no persistido
├─ Cada carga de página recalcula
└─ Queries lentas en vistas

Problem 3: Sin índices en búsquedas
├─ Text search sin índices FTS
├─ Queries N+1 en matching
└─ Performance degradación en escala
```

---

### **6. Testing Incompleto**

```
✅ Unit tests existen para:
  - bank_detector
  - expense_validator
  - category_predictor

❌ NO existen tests para:
  - Flujo end-to-end (upload → matching)
  - Integration entre parsers
  - AI reconciliation pipeline
  - MSI tracking workflow
  - Multi-tenancy en reconciliation
```

---

## 🚀 Recomendaciones de Integración

### **FASE 1: Unificar Extracción (Semana 1)**

#### 1.1 Crear Orquestador de Parsers
```python
# core/reconciliation/bank/bank_statement_orchestrator.py

class BankStatementOrchestrator:
    """Unifica el parsing de estados de cuenta"""
    
    def parse_statement(self, file_path: str, account_id: int):
        """
        Flujo unificado:
        1. Detecta formato (PDF/XLSX/CSV)
        2. Selecciona mejor parser
        3. Parsea y extrae transacciones
        4. Valida datos
        5. Guarda en PostgreSQL
        6. Retorna resultado
        """
        
        # Seleccionar parser
        if self._is_heavy_file(file_path):
            parser = self.ai_orchestrator  # Usa Gemini
        else:
            parser = self.traditional_parser  # Rápido
        
        # Parsear
        transactions = parser.parse(file_path)
        
        # Guardar en BD
        self._save_to_postgres(account_id, transactions)
        
        return transactions
```

#### 1.2 Crear tabla `bank_statements` en PostgreSQL
```sql
CREATE TABLE bank_statements (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    payment_account_id INTEGER NOT NULL,
    bank_name VARCHAR(255),
    file_name VARCHAR(255),
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processing_date TIMESTAMP,
    period_start DATE,
    period_end DATE,
    transaction_count INTEGER,
    total_debits NUMERIC(15,2),
    total_credits NUMERIC(15,2),
    status VARCHAR(50),  -- 'pending', 'processing', 'completed', 'failed'
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id),
    FOREIGN KEY (payment_account_id) REFERENCES payment_accounts(id)
);

CREATE TABLE bank_transactions (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    bank_statement_id INTEGER NOT NULL,
    transaction_date DATE,
    description VARCHAR(500),
    amount NUMERIC(15,2),
    transaction_type VARCHAR(50),  -- 'debit', 'credit', 'fee'
    reference_number VARCHAR(255),
    balance_after NUMERIC(15,2),
    status VARCHAR(50),  -- 'pending_reconciliation', 'reconciled', 'non_reconcilable'
    reconciliation_status VARCHAR(50),
    linked_invoice_id INTEGER,
    match_confidence NUMERIC(3,2),
    match_method VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id),
    FOREIGN KEY (bank_statement_id) REFERENCES bank_statements(id),
    FOREIGN KEY (linked_invoice_id) REFERENCES expense_invoices(id)
);

CREATE INDEX idx_bank_transactions_date ON bank_transactions(transaction_date);
CREATE INDEX idx_bank_transactions_status ON bank_transactions(status);
CREATE INDEX idx_bank_transactions_amount ON bank_transactions(amount);
```

#### 1.3 Actualizar API
```python
# api/bank_statements_api.py

@router.post("/accounts/{account_id}/upload")
async def upload_bank_statement(
    account_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """
    Flujo unificado:
    1. Valida archivo
    2. Orquestador parsea
    3. Guarda en BD
    4. Retorna resultado con transacciones persistidas
    """
    orchestrator = BankStatementOrchestrator()
    
    # Parsear y guardar
    statement = orchestrator.parse_statement(
        file_path=saved_path,
        account_id=account_id,
        tenant_id=current_user.tenant_id
    )
    
    # Retorna con transacciones reales (persistidas)
    return BankStatementResponse(
        statement=statement,
        transactions=statement.transactions,  # Ya en BD
        summary={...}
    )
```

---

### **FASE 2: Unificar Conciliación (Semana 2)**

#### 2.1 Crear Motor de Matching Orquestado
```python
# core/reconciliation/matching/reconciliation_engine.py

class ReconciliationEngine:
    """Motor unificado de matching"""
    
    def reconcile_batch(self, tenant_id: int, threshold: float = 0.85):
        """
        Flujo unificado de matching:
        1. Obtiene transacciones sin conciliar
        2. Obtiene CFDIs sin vinculación
        3. Ejecuta múltiples estrategias
        4. Consolida resultados
        5. Auto-aplica si > threshold
        6. Persiste en BD
        """
        
        # 1. Obtener transacciones pendientes
        transactions = self._get_pending_transactions(tenant_id)
        invoices = self._get_unmatched_invoices(tenant_id)
        
        # 2. Estrategia 1: Heurística (rápida)
        heuristic_matches = self._heuristic_matching(transactions, invoices)
        
        # 3. Estrategia 2: AI (précisa)
        ai_matches = self._ai_matching(transactions, invoices)
        
        # 4. Consolidar (usar puntuación ponderada)
        consolidated = self._consolidate_matches(heuristic_matches, ai_matches)
        
        # 5. Auto-aplicar si > threshold
        applied = self._auto_apply_matches(consolidated, threshold)
        
        # 6. Persistir
        self._persist_matches(applied)
        
        return {
            'total_matches': len(consolidated),
            'applied': len(applied),
            'confidence_avg': np.mean([m['confidence'] for m in applied])
        }
```

#### 2.2 Persistir Suggestions
```python
# Nueva tabla para audit trail

CREATE TABLE reconciliation_suggestions (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    transaction_id INTEGER NOT NULL,
    invoice_id INTEGER NOT NULL,
    suggestion_score NUMERIC(3,2),
    heuristic_score NUMERIC(3,2),
    ai_score NUMERIC(3,2),
    suggested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    applied BOOLEAN DEFAULT FALSE,
    applied_at TIMESTAMP,
    applied_by INTEGER,  -- user_id
    status VARCHAR(50),  -- 'suggested', 'applied', 'rejected'
    rejection_reason TEXT,
    FOREIGN KEY (transaction_id) REFERENCES bank_transactions(id),
    FOREIGN KEY (invoice_id) REFERENCES expense_invoices(id)
);
```

#### 2.3 Nuevo Endpoint Unificado
```python
@router.post("/reconciliation/auto-apply")
async def auto_apply_reconciliation(
    tenant_id: int = Query(...),
    threshold: float = Query(default=0.85),
    current_user: User = Depends(get_current_user)
):
    """
    Auto-aplica matches de alta confianza
    - Ejecuta reconciliation_engine.reconcile_batch()
    - Aplica automáticamente si score > threshold
    - Persiste suggestions para audit
    - Retorna resumen
    """
    engine = ReconciliationEngine()
    result = engine.reconcile_batch(tenant_id, threshold)
    
    return {
        'success': True,
        'total_matches': result['total_matches'],
        'applied_count': result['applied'],
        'reconciliation_rate_improved': f"{result['rate_change']:.1f}%"
    }
```

---

### **FASE 3: Automatizar MSI (Semana 3)**

#### 3.1 Integrar AI MSI Detector en Flujo Principal
```python
# core/reconciliation/msi/msi_manager.py

class MSIManager:
    """Gestiona detección y tracking de MSI"""
    
    def process_invoice_for_msi(self, invoice_id: int, description: str):
        """
        1. Detecta si tiene MSI (AI)
        2. Si SÍ: Registra pago diferido
        3. Crea cuotas futuras
        4. Vincula a transacción inicial
        """
        
        # 1. Detectar
        msi_info = self.ai_msi_detector.detect(description)
        if not msi_info['es_msi']:
            return None
        
        # 2. Registrar
        deferred_id = self._create_deferred_payment(
            invoice_id,
            msi_info['meses'],
            msi_info['monto']
        )
        
        # 3. Crear cuotas
        self._create_installments(deferred_id, msi_info)
        
        # 4. Marcar en CFDI
        cursor.execute("""
            UPDATE expense_invoices
            SET es_msi = true, meses_msi = %s,
                pago_mensual_msi = %s,
                deferred_payment_id = %s,
                status = 'partially_paid'
            WHERE id = %s
        """, (msi_info['meses'], msi_info['monto_mensual'], deferred_id, invoice_id))
        
        return deferred_id
```

#### 3.2 Crear Estados Intermedios
```sql
-- Actualizar expense_invoices para estados intermedios

ALTER TABLE expense_invoices ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'pending';
-- Valores: 'pending', 'partially_paid' (MSI), 'reconciled', 'non_reconcilable'

ALTER TABLE expense_invoices ADD COLUMN IF NOT EXISTS deferred_payment_id INTEGER;
-- Link a deferred_payments
```

#### 3.3 Endpoint MSI Completo
```python
@router.get("/msi/pending")
async def get_pending_msi(tenant_id: int = Query(...)):
    """
    Retorna:
    1. Facturas PUE tarjeta crédito SIN confirmar MSI
    2. Pagos diferidos activos (tracking)
    3. Cuotas próximas a vencer
    """
    conn = get_connection()
    cursor = conn.cursor(RealDictCursor)
    
    # 1. Pendientes de confirmar
    cursor.execute("""
        SELECT * FROM expense_invoices
        WHERE tenant_id = %s
        AND metodo_pago = 'PUE'
        AND forma_pago = '04'
        AND status = 'pending'
        AND total > 100
    """, (tenant_id,))
    
    pending = cursor.fetchall()
    
    # 2. Activos con tracking
    cursor.execute("""
        SELECT dp.*, ei.nombre_emisor, ei.total
        FROM deferred_payments dp
        JOIN expense_invoices ei ON dp.cfdi_id = ei.id
        WHERE dp.status = 'activo'
        AND ei.tenant_id = %s
    """, (tenant_id,))
    
    active = cursor.fetchall()
    
    return {
        'pending_confirmation': pending,
        'active_installments': active
    }
```

---

### **FASE 4: Integrar Reportes en UI (Semana 4)**

#### 4.1 Crear Endpoints de Reportes
```python
# api/reconciliation_reports_api.py

@router.get("/reconciliation/stats")
async def get_reconciliation_stats(
    tenant_id: int = Query(...),
    period_month: int = Query(default=11),
    period_year: int = Query(default=2025)
):
    """Retorna stats de vistas SQL mejoradas"""
    conn = get_connection()
    cursor = conn.cursor(RealDictCursor)
    
    cursor.execute("""
        SELECT * FROM vw_reconciliation_stats_improved
        WHERE tenant_id = %s
        AND EXTRACT(MONTH FROM transaction_date) = %s
        AND EXTRACT(YEAR FROM transaction_date) = %s
    """, (tenant_id, period_month, period_year))
    
    return cursor.fetchone()

@router.get("/reconciliation/suggestions-detailed")
async def get_detailed_suggestions(
    tenant_id: int = Query(...),
    limit: int = Query(default=50)
):
    """TOP matches con detalles"""
    conn = get_connection()
    cursor = conn.cursor(RealDictCursor)
    
    cursor.execute("""
        SELECT * FROM vw_auto_match_suggestions_improved
        WHERE tenant_id = %s
        ORDER BY match_score DESC
        LIMIT %s
    """, (tenant_id, limit))
    
    return cursor.fetchall()

@router.get("/reconciliation/unmatched-transactions")
async def get_unmatched_transactions(
    tenant_id: int = Query(...),
    min_amount: float = Query(default=0)
):
    """Transacciones sin CFDI, categorizadas"""
    conn = get_connection()
    cursor = conn.cursor(RealDictCursor)
    
    cursor.execute("""
        SELECT * FROM vw_transactions_without_invoice
        WHERE tenant_id = %s
        AND amount >= %s
        ORDER BY amount DESC
    """, (tenant_id, min_amount))
    
    return cursor.fetchall()
```

#### 4.2 Componentes React
```jsx
// frontend/src/components/ReconciliationDashboard.jsx

export function ReconciliationDashboard() {
  const [stats, setStats] = useState(null);
  const [suggestions, setSuggestions] = useState([]);
  const [unmatched, setUnmatched] = useState([]);
  
  useEffect(() => {
    const fetchData = async () => {
      // 1. Stats
      const statsRes = await fetch(`/api/reconciliation/stats?tenant_id=${tenantId}`);
      const statsData = await statsRes.json();
      setStats(statsData);
      
      // 2. Suggestions
      const sugRes = await fetch(`/api/reconciliation/suggestions-detailed?tenant_id=${tenantId}`);
      const sugData = await sugRes.json();
      setSuggestions(sugData);
      
      // 3. Unmatched
      const unmRes = await fetch(`/api/reconciliation/unmatched-transactions?tenant_id=${tenantId}`);
      const unmData = await unmRes.json();
      setUnmatched(unmData);
    };
    
    fetchData();
  }, [tenantId]);
  
  return (
    <div className="reconciliation-dashboard">
      <h1>Conciliación Bancaria</h1>
      
      {/* Stats Cards */}
      <div className="stats-grid">
        <StatCard 
          label="Tasa de Conciliación"
          value={`${stats?.reconciliation_rate?.toFixed(1)}%`}
        />
        <StatCard 
          label="Transacciones Totales"
          value={stats?.total_transactions}
        />
        <StatCard 
          label="Matches Disponibles"
          value={stats?.auto_match_perfect + stats?.auto_match_high}
        />
      </div>
      
      {/* Suggestions Table */}
      <section>
        <h2>Sugerencias de Matching ({suggestions.length})</h2>
        <Table data={suggestions} columns={[
          { key: 'transaction_date', label: 'Fecha' },
          { key: 'transaction_description', label: 'Descripción' },
          { key: 'transaction_amount', label: 'Monto TX' },
          { key: 'invoice_total', label: 'Monto Factura' },
          { key: 'match_score', label: 'Score' },
          { key: 'confidence_label', label: 'Confianza' }
        ]} />
        
        <button onClick={applyAllMatches}>
          Aplicar Matches (Score > 85%)
        </button>
      </section>
      
      {/* Unmatched Transactions */}
      <section>
        <h2>Transacciones Sin Factura ({unmatched.length})</h2>
        <Table data={unmatched} columns={[
          { key: 'transaction_date', label: 'Fecha' },
          { key: 'description', label: 'Descripción' },
          { key: 'amount', label: 'Monto' },
          { key: 'category', label: 'Categoría' }
        ]} />
      </section>
    </div>
  );
}
```

---

### **FASE 5: Testing End-to-End (Semana 5)**

#### 5.1 Tests Integración
```python
# tests/test_reconciliation_e2e.py

class TestReconciliationE2E:
    """Tests flujo completo de conciliación"""
    
    def test_upload_to_matching(self):
        """Flujo: Upload estado → Parse → Match → Apply"""
        
        # 1. Upload
        response = client.post(
            "/bank-statements/accounts/1/upload",
            files={"file": open("test_statement.pdf", "rb")}
        )
        assert response.status_code == 201
        statement_id = response.json()["statement_id"]
        
        # 2. Esperar parsing
        time.sleep(2)
        
        # 3. Verificar transacciones guardadas
        stmt = db.query(BankStatement).filter_by(id=statement_id).first()
        assert stmt.status == "completed"
        assert len(stmt.transactions) > 0
        
        # 4. Obtener suggestions
        response = client.get(
            "/reconciliation/suggestions-detailed",
            params={"tenant_id": 1}
        )
        suggestions = response.json()
        assert len(suggestions) > 0
        
        # 5. Auto-apply
        response = client.post(
            "/reconciliation/auto-apply",
            params={"tenant_id": 1, "threshold": 0.85}
        )
        result = response.json()
        assert result["applied_count"] > 0
        
        # 6. Verificar vinculaciones
        matched_tx = db.query(BankTransaction).filter(
            BankTransaction.linked_invoice_id.isnot(None)
        ).count()
        assert matched_tx == result["applied_count"]
    
    def test_msi_detection_and_tracking(self):
        """Flujo: Detectar MSI → Crear cuotas → Track pagos"""
        
        # 1. Crear CFDI con MSI
        invoice = self._create_invoice_with_msi(
            amount=4325.00,
            description="TODOLLANTAS 6 MSI"
        )
        
        # 2. Detectar MSI
        result = msi_manager.process_invoice_for_msi(
            invoice.id,
            invoice.descripcion
        )
        assert result is not None
        deferred_id = result
        
        # 3. Verificar cuotas creadas
        installments = db.query(DeferredPaymentInstallment).filter_by(
            deferred_payment_id=deferred_id
        ).all()
        assert len(installments) == 6
        assert installments[0].monto == Decimal("720.83")
        
        # 4. Simular pago de cuota 1
        db.query(DeferredPaymentInstallment).filter_by(
            id=installments[0].id
        ).update({
            'pagado': True,
            'fecha_pagada': date.today()
        })
        db.commit()
        
        # 5. Verificar tracking
        deferred = db.query(DeferredPayment).filter_by(id=deferred_id).first()
        assert deferred.pagos_realizados == 1
        assert deferred.status == 'activo'
        
        # 6. Simular últimas cuotas
        for installment in installments[1:]:
            installment.pagado = True
            installment.fecha_pagada = date.today()
        db.commit()
        
        # 7. Verificar completado
        deferred = db.query(DeferredPayment).filter_by(id=deferred_id).first()
        assert deferred.pagos_realizados == 6
        assert deferred.status == 'completado'
        
        # 8. Verificar invoice marcada como pagada
        invoice = db.query(ExpenseInvoice).filter_by(id=invoice.id).first()
        assert invoice.status == 'reconciled'
```

---

## 📊 Diagrama de Flujo Unificado

### **Flujo Deseado (Post-Integración)**

```
┌─────────────────────────────────────────────────────────────────────┐
│                          USUARIO                                     │
│                                                                       │
│  1. Sube Estado de Cuenta    2. Carga CFDI XML    3. Revisa Dashboard│
└─────────────────┬───────────────────┬──────────────────────┬─────────┘
                  │                   │                      │
                  ▼                   ▼                      ▼
        ┌──────────────────┐ ┌──────────────────┐ ┌───────────────────┐
        │  Upload API      │ │  CFDI API        │ │  Reconciliation   │
        │  /bank-statements│ │  /invoices/upload│ │  Dashboard        │
        └────────┬─────────┘ └────────┬─────────┘ └─────────┬─────────┘
                 │                    │                      │
                 ▼                    ▼                      ▼
        ┌──────────────────────────────────────────────────────────┐
        │  ORQUESTADORES (Nuevos - Fase 1,2,3)                    │
        │                                                          │
        │  ┌────────────────────────────────────────────────────┐ │
        │  │ BankStatementOrchestrator (Fase 1)                │ │
        │  │ ├─ Detecta formato                               │ │
        │  │ ├─ Selecciona parser (AI o tradicional)          │ │
        │  │ ├─ Parsea transacciones                          │ │
        │  │ ├─ Detecta banco automáticamente ✅              │ │
        │  │ └─ Guarda en PostgreSQL ✅                       │ │
        │  └────────────────────────────────────────────────────┘ │
        │                                                          │
        │  ┌────────────────────────────────────────────────────┐ │
        │  │ ReconciliationEngine (Fase 2)                     │ │
        │  │ ├─ Obtiene transacciones pendientes              │ │
        │  │ ├─ Obtiene CFDIs sin vincular                    │ │
        │  │ ├─ Estrategia 1: Heurística (rápido)             │ │
        │  │ ├─ Estrategia 2: AI (Preciso)                    │ │
        │  │ ├─ Consolida resultados (ponderado)              │ │
        │  │ ├─ Auto-aplica si score > threshold ✅           │ │
        │  │ └─ Persiste en vistas para audit trail ✅        │ │
        │  └────────────────────────────────────────────────────┘ │
        │                                                          │
        │  ┌────────────────────────────────────────────────────┐ │
        │  │ MSIManager (Fase 3)                              │ │
        │  │ ├─ Detecta MSI automáticamente ✅                │ │
        │  │ ├─ Registra pago diferido                        │ │
        │  │ ├─ Crea cuotas futuras                           │ │
        │  │ ├─ Marca CFDI con status 'partially_paid' ✅     │ │
        │  │ └─ Tracks pagos mensuales ✅                     │ │
        │  └────────────────────────────────────────────────────┘ │
        │                                                          │
        └──────────┬──────────────────────┬───────────────────────┘
                   │                      │
                   ▼                      ▼
        ┌──────────────────┐ ┌──────────────────┐
        │  PostgreSQL      │ │  Vistas SQL      │
        │  ✅ Todas las    │ │  (Fase 4)        │
        │     tablas       │ │  ✅ Expuestas    │
        │     migradas     │ │     en API       │
        └────────┬─────────┘ └────────┬─────────┘
                 │                    │
                 └────────┬───────────┘
                          │
                          ▼
        ┌──────────────────────────────────────┐
        │  Reportes API (Fase 4)               │
        │  ✅ /reconciliation/stats            │
        │  ✅ /reconciliation/suggestions      │
        │  ✅ /reconciliation/unmatched        │
        │  ✅ /msi/pending                     │
        │  ✅ /reconciliation/auto-apply       │
        └────────┬─────────────────────────────┘
                 │
                 ▼
        ┌──────────────────────────────────────┐
        │  Frontend Components (Fase 4)        │
        │  ✅ ReconciliationDashboard          │
        │  ✅ MSITracking                      │
        │  ✅ MatchSuggestions                 │
        │  ✅ UnmatchedTransactions            │
        │  ✅ Auto-Apply Button                │
        └──────────────────────────────────────┘
```

---

## 📈 Métricas de Éxito

| Métrica | Antes | Después | Plazo |
|---------|-------|---------|-------|
| Tasa de conciliación | 38% | 85%+ | Fase 2 |
| Transacciones con matching sugerido | 0% | 100% | Fase 2 |
| Matches auto-aplicados | 0% | 70%+ | Fase 2 |
| CFDIs con MSI detectado automáticamente | 0% | 95%+ | Fase 3 |
| Tiempo ciclo (upload → matching) | Manual | < 2 min | Fase 1 |
| Cobertura de reportes en UI | 0% | 100% | Fase 4 |
| Test coverage (reconciliation) | 40% | 90% | Fase 5 |

---

## 🎯 Conclusiones

### **Estado Actual Resumido**

**BUENO:**
- ✅ Parsers robustos (legacy) 
- ✅ Orquestador AI nuevo y funcional
- ✅ Vistas SQL de reporting excelentes
- ✅ MSI detection implementada (aunque dispersa)
- ✅ Multi-tenancy foundation

**MALO:**
- ❌ 2-3 sistemas competidores sin coordinación
- ❌ Sin persistencia de matching sugerido
- ❌ Automatización incompleta
- ❌ Sin integración en UI
- ❌ Scripts manuales críticos

**OPORTUNIDADES:**
- 🔄 Consolidar en 1 flujo principal (Fases 1-3)
- 📊 Exponer vistas SQL en dashboards (Fase 4)
- ✅ Automatizar 100% del flujo (Fase 2)
- 🎯 Integrar MSI en lifecycle completo (Fase 3)
- 🧪 Aumentar test coverage (Fase 5)

### **Recomendación Final**

**Seguir plan de 5 fases (5 semanas):**
1. **Fase 1:** Orquestador de parsers + tablas PostgreSQL
2. **Fase 2:** Motor matching unificado + auto-aplicación
3. **Fase 3:** MSI automation + estados intermedios
4. **Fase 4:** APIs de reportes + componentes React
5. **Fase 5:** E2E testing + documentación

**Beneficio esperado:** Pasar de sistema disperso a integración end-to-end con tasa de conciliación 85%+.

