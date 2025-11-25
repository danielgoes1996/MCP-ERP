# Invoice Classification Architecture Diagram

## End-to-End Flow

```
USER UPLOADS INVOICE
        ↓
    [API] /universal-invoice/sessions/upload/
        ↓
    CreateSession(company_id, file_path, filename)
        ↓
    [BACKGROUND] POST /universal-invoice/sessions/{session_id}/process
        ↓
┌───────────────────────────────────────────────┐
│   UNIVERSAL INVOICE ENGINE (universal_invoice_engine_system.py)
├───────────────────────────────────────────────┤
│                                               │
│  1. process_invoice(session_id)               │
│     ↓                                         │
│  2. _select_best_parser(file_path)            │
│     • Detect format (PDF/XML/Image)           │
│     • Choose parser: PDF, XML, Image, Hybrid  │
│     ↓                                         │
│  3. parser.parse(file_path)                   │
│     • PDF parser → OCR extraction             │
│     • XML parser → Deterministic CFDI parsing │
│     • Image parser → OCR + Layout analysis    │
│     ↓                                         │
│  4. template_engine.find_best_template()      │
│     • Match patterns                          │
│     • Score field mappings                    │
│     ↓                                         │
│  5. validation_engine.validate_extraction()   │
│     • Apply business rules                    │
│     • Check compliance                        │
│     ↓                                         │
│  6. _calculate_overall_quality()              │
│     • Combine scores (extraction + template   │
│       + validation)                           │
│     ↓                                         │
│  7. _save_processing_result()                 │
│     • Save to sat_invoices      │
│     • Save parsed_data (full CFDI)            │
│                                               │
└───────────────────────────────────────────────┘
        ↓
    [AUTO-TRIGGER] if status == "completed"
        ↓
┌───────────────────────────────────────────────┐
│   CLASSIFICATION SERVICE (classification_service.py)
│   (Only if beta tenant + tipo_comprobante=I/E)
├───────────────────────────────────────────────┤
│                                               │
│  1. classify_invoice_session()                │
│     ↓                                         │
│  2. _build_expense_snapshot()                 │
│     • Extract: description, provider, amount  │
│     ↓                                         │
│  3. _build_embeddings_payload()               │
│     • Add semantic hints                      │
│     • Add SAT product code mapping            │
│     ↓                                         │
│  4. retrieve_relevant_accounts()              │
│     [EMBEDDINGS SEARCH - Zero Cost]           │
│     • Filter by family_filter                 │
│     • Return top_k=10 candidates              │
│     ↓                                         │
│  5. _transform_candidates()                   │
│     • Format for LLM                          │
│     ↓                                         │
│  6. ExpenseLLMClassifier.classify()           │
│     [LLM REFINEMENT - Claude Sonnet 4.5]      │
│     • Takes candidates + company context      │
│     • Returns final SAT code                  │
│                                               │
└───────────────────────────────────────────────┘
        ↓
    [DUAL-WRITE] Save classification to both:
        ├─ expense_invoices.accounting_classification
        │  (Primary: Single source of truth)
        │
        └─ sat_invoices.accounting_classification
           (Secondary: Audit trail)
        ↓
    Status: "pending_confirmation"
        ↓
    [DASHBOARD] Shows pending classifications for accountant review


ACCOUNTANT REVIEW
        ↓
    ┌─────────────────────────────┐
    │ Either CONFIRM or CORRECT   │
    └─────────────────────────────┘
        ↓
        ├─ CONFIRM (Accountant accepts)
        │      ↓
        │   [API] /invoice-classification/confirm/{session_id}
        │      ↓
        │   Status → "confirmed"
        │   confirmed_at = now()
        │   confirmed_by = user_id
        │
        └─ CORRECT (Accountant overrides)
               ↓
            [API] /invoice-classification/correct/{session_id}
               ↓
            Status → "corrected"
            corrected_sat_code = new_code
            corrected_by = user_id
            correction_notes = reason
               ↓
            [LEARNING] Save to ai_correction_memory
            (provider_rfc + original_description → corrected_code)
```

## Classification System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    CLASSIFICATION PIPELINE                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  STAGE 1: EMBEDDINGS SEARCH (Zero Cost - pgvector)             │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Input:                                                   │  │
│  │  - Invoice description                                   │  │
│  │  - Provider name                                         │  │
│  │  - SAT product/service code                              │  │
│  │  - Amount                                                │  │
│  │  - Family filter (e.g., [601, 602, 603, ...])            │  │
│  │                                                          │  │
│  │ Process:                                                 │  │
│  │  1. Build rich embeddings payload with semantic hints    │  │
│  │  2. Query pgvector for similar SAT accounts             │  │
│  │  3. Filter to only applicable families                   │  │
│  │  4. Return top-K candidates with similarity scores       │  │
│  │                                                          │  │
│  │ Output: Top 10 SAT account candidates                    │  │
│  │  [{                                                      │  │
│  │    "code": "613.01",                                     │  │
│  │    "name": "Servicios de consultoría",                   │  │
│  │    "family_hint": "613",                                 │  │
│  │    "score": 0.92,                                        │  │
│  │    "description": "..."                                  │  │
│  │  }, ...]                                                 │  │
│  └──────────────────────────────────────────────────────────┘  │
│                          ↓                                      │
│  STAGE 2: LLM REFINEMENT (Claude Sonnet 4.5)                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Input:                                                   │  │
│  │  - Candidates from embeddings search                     │  │
│  │  - Company context (industry, business model, etc.)      │  │
│  │  - Full invoice data                                     │  │
│  │                                                          │  │
│  │ Process:                                                 │  │
│  │  1. Build prompt with candidates + company context      │  │
│  │  2. Ask Claude: "Which is the best SAT code?"            │  │
│  │  3. Parse response → SAT code + family code              │  │
│  │  4. Calculate confidence scores                          │  │
│  │                                                          │  │
│  │ Output: Classification Result                            │  │
│  │  {                                                       │  │
│  │    "sat_account_code": "613.01",                         │  │
│  │    "family_code": "613",                                 │  │
│  │    "confidence_sat": 0.92,                               │  │
│  │    "confidence_family": 0.95,                            │  │
│  │    "explanation_short": "...",                           │  │
│  │    "model_version": "claude-sonnet-4-5-20250929",       │  │
│  │    "alternative_candidates": [...]                       │  │
│  │  }                                                       │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Database Storage Model

```
┌──────────────────────────────────────────────────────┐
│          SINGLE SOURCE OF TRUTH MODEL                │
├──────────────────────────────────────────────────────┤
│                                                      │
│  PRIMARY:  expense_invoices                         │
│  ├─ id                                              │
│  ├─ uuid (CFDI UUID)                               │
│  ├─ tenant_id                                       │
│  ├─ company_id                                      │
│  ├─ accounting_classification JSONB                │
│  │  ├─ sat_account_code                            │
│  │  ├─ family_code                                 │
│  │  ├─ confidence_sat                              │
│  │  ├─ confidence_family                           │
│  │  ├─ status (pending/confirmed/corrected)        │
│  │  ├─ explanation_short                           │
│  │  ├─ classified_at                               │
│  │  ├─ confirmed_at                                │
│  │  ├─ confirmed_by                                │
│  │  ├─ corrected_at                                │
│  │  ├─ corrected_sat_code                          │
│  │  ├─ correction_notes                            │
│  │  └─ alternative_candidates                      │
│  ├─ session_id (FK to sat_invoices)  │
│  └─ [Other invoice fields...]                      │
│                                                      │
│  SECONDARY: sat_invoices (Audit Log) │
│  ├─ id                                              │
│  ├─ company_id                                      │
│  ├─ original_filename                              │
│  ├─ extracted_data JSONB (full CFDI)              │
│  ├─ accounting_classification JSONB                │
│  │  (Same structure as expense_invoices)           │
│  ├─ processing_metrics JSONB                       │
│  │  ├─ classification_duration_ms                  │
│  │  ├─ num_candidates                              │
│  │  └─ [Other metrics...]                          │
│  └─ [Other processing fields...]                   │
│                                                      │
│  LEARNING:  ai_correction_memory                   │
│  ├─ company_id                                      │
│  ├─ original_description                           │
│  ├─ provider_name                                  │
│  ├─ provider_rfc                                   │
│  ├─ original_sat_code                              │
│  ├─ corrected_sat_code                             │
│  ├─ corrected_by_user_id                           │
│  ├─ corrected_at                                   │
│  └─ confidence_before                              │
│                                                      │
└──────────────────────────────────────────────────────┘

MERGE LOGIC:
  corrected > confirmed > pending_confirmation
  (Respects human decisions with highest priority)
```

## Family Classifier (Hierarchical Phase 1)

```
┌──────────────────────────────────────────────────────┐
│   HIERARCHICAL CLASSIFICATION (3 PHASES)             │
├──────────────────────────────────────────────────────┤
│                                                      │
│  Phase 1: Family-Level (Currently Implemented)      │
│  ─────────────────────────────────────────────      │
│  Input: Invoice data + Company context              │
│  Process: LLM analyzes invoice → Family (100-800)   │
│  Output: {                                           │
│    "familia_codigo": "600",                          │
│    "familia_nombre": "GASTOS DE OPERACIÓN",         │
│    "confianza": 0.97,                               │
│    "razonamiento_principal": "...",                 │
│    "factores_decision": [...],                      │
│    "uso_cfdi_analisis": "...",                      │
│    "override_uso_cfdi": false,                      │
│    "override_razon": null,                          │
│    "requiere_revision_humana": false,               │
│    "siguiente_fase": "subfamily",                   │
│    "comentarios_adicionales": "..."                 │
│  }                                                   │
│  Confidence Threshold: >= 0.95 auto-approve         │
│                                                      │
│  Phase 2: Subfamily-Level (TODO Phase 2)            │
│  ─────────────────────────────────────────────      │
│  If family confidence >= 0.95:                       │
│    Refine: 600 → 613 (specific subfamily)           │
│  Target Confidence: >= 0.90                         │
│                                                      │
│  Phase 3: Detailed Account (TODO Phase 3)           │
│  ─────────────────────────────────────────────      │
│  If subfamily confidence >= 0.90:                    │
│    Refine: 613 → 613.01 (specific account)          │
│  Target Confidence: >= 0.85                         │
│                                                      │
│  KEY PHILOSOPHY:                                    │
│  • PRIMARY: Invoice concept + Company context       │
│  • SECONDARY: UsoCFDI as validation only            │
│  • Providers often select UsoCFDI incorrectly       │
│  • Economic reality > Formal declaration            │
│                                                      │
│  EXAMPLE: Same "Etiquetas adhesivas"                │
│  • Software company → 600 (Office Supplies)         │
│  • Honey producer → 500 (Packaging Material)         │
│  → Context changes everything                       │
│                                                      │
└──────────────────────────────────────────────────────┘
```

## Classification Status Workflow

```
┌─────────────────────────────────────────────────────┐
│          CLASSIFICATION STATUS LIFECYCLE            │
├─────────────────────────────────────────────────────┤
│                                                     │
│  1. PENDING_CONFIRMATION (Initial)                 │
│     └─ AI auto-classification completed             │
│     └─ Waiting for accountant review                │
│                                                     │
│  2. CONFIRMED (User Acceptance)                    │
│     └─ Accountant clicks "CONFIRM"                  │
│     └─ Classification locked                        │
│     └─ Moves to accounting system                   │
│                                                     │
│  3. CORRECTED (User Override)                      │
│     └─ Accountant clicks "CORRECT"                  │
│     └─ Provides corrected_sat_code                  │
│     └─ Saved to correction_memory for learning      │
│     └─ Classification locked with override          │
│                                                     │
│  4. NOT_CLASSIFIED (AI Failure)                    │
│     └─ No SAT candidates found                      │
│     └─ Requires manual classification               │
│                                                     │
│  TRANSITIONS:
│  pending_confirmation → confirmed  (✓ Accept)
│  pending_confirmation → corrected  (✎ Override)
│  corrected → confirmed             (Later accept)
│  not_classified → (manual review)
│                                                     │
└─────────────────────────────────────────────────────┘
```

## Key Integration Points for Family Classifier

```
OPTION A: Pre-Filter Embeddings
┌──────────────────────────────────┐
│ 1. Family Classifier             │
│    (get family code 100-800)      │
│        ↓                          │
│ 2. If confidence >= 0.95:         │
│    Use family_filter=[family_code]│
│        ↓                          │
│ 3. Embeddings search (filtered)   │
│    Only candidates in that family │
└──────────────────────────────────┘

OPTION B: Validate Final Result
┌──────────────────────────────────┐
│ 1. Embeddings → Top candidates    │
│        ↓                          │
│ 2. LLM → Final SAT code           │
│        ↓                          │
│ 3. Family Classifier              │
│    Check if family matches        │
│        ↓                          │
│ 4. If mismatch & high confidence: │
│    Log warning, prefer family     │
│    classifier result              │
└──────────────────────────────────┘

OPTION C: Multi-Stage Pipeline (Recommended)
┌──────────────────────────────────┐
│ Stage 1: Family (confidence>=0.95)│
│ 100-800 with detailed reasoning   │
│        ↓                          │
│ Stage 2: Subfamily (confidence>=0.9)
│ If family confident, refine further
│        ↓                          │
│ Stage 3: Detailed (confidence>=0.85)
│ Final SAT code with precision     │
│        ↓                          │
│ Accountant Review & Confirmation  │
└──────────────────────────────────┘
```

