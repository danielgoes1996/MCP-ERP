# Invoice Processing & Classification Flow - Complete Analysis

## 1. MAIN INVOICE PROCESSING PIPELINE

### Entry Points (API Endpoints)
1. **File Upload & Session Creation**
   - `/universal-invoice/sessions/upload/` - Single file upload
   - `/universal-invoice/sessions/batch-upload/` - Multiple file batch
   - **Location**: `/Users/danielgoes96/Desktop/mcp-server/api/universal_invoice_engine_api.py:535-599`

2. **Processing Trigger**
   - `/universal-invoice/sessions/{session_id}/process` - Start processing
   - **Location**: `/Users/danielgoes96/Desktop/mcp-server/api/universal_invoice_engine_api.py:601-666`
   - Triggers background processing via FastAPI BackgroundTasks

### Processing Pipeline (Sequential Flow)

```
1. CREATE SESSION
   ↓
2. PARSE INVOICE
   - Detect file format (PDF, XML, Image)
   - Select best parser
   - Extract structured data
   ↓
3. TEMPLATE MATCHING
   - Find best template match
   - Calculate pattern scores
   - Extract field mappings
   ↓
4. VALIDATION RULES
   - Apply business rules
   - Check format compliance
   - Generate validation scores
   ↓
5. QUALITY CALCULATION
   - Combine extraction confidence + template + validation
   - Generate overall quality score (0-100)
   ↓
6. SAVE PROCESSING RESULTS
   - Store in sat_invoices
   - Save parsed_data (full CFDI)
   ↓
7. AUTO-TRIGGER CLASSIFICATION (if completed)
   - Extract company_id + parsed_data
   - Call accounting classification service
   ↓
8. AUTO-TRIGGER SAT VALIDATION (if completed)
   - Validate CFDI against SAT web services
```

**Core Engine**: `UniversalInvoiceEngineSystem` class
- **Location**: `/Users/danielgoes96/Desktop/mcp-server/core/expenses/invoices/universal_invoice_engine_system.py`
- **Key Method**: `process_invoice(session_id)` - Lines 918-1013
- Uses singleton pattern for global instance
- Supports multiple parsers: PDF, XML, Image, Hybrid

## 2. CURRENT CLASSIFICATION SYSTEM

### Classification Flow (Two-Stage)

#### Stage 1: Embeddings Search (Zero Cost)
- **File**: `core/accounting/account_catalog.py`
- **Function**: `retrieve_relevant_accounts(expense_payload, top_k, family_filter)`
- Uses vector embeddings to find SAT account candidates
- Filters by applicable families (family_filter parameter)
- Returns top-K candidates with similarity scores

**Example Call**:
```python
candidates = retrieve_relevant_accounts(
    expense_payload={
        'descripcion': 'Servicios profesionales',
        'metadata': {'amount': 500.00}
    },
    top_k=10,
    family_filter=['601', '602', '603', '604', '605', '606', '607', '608', '609']
)
```

#### Stage 2: LLM Refinement
- **File**: `core/ai_pipeline/classification/expense_llm_classifier.py`
- **Class**: `ExpenseLLMClassifier`
- **Model**: Claude Sonnet 4.5 (claude-sonnet-4-5-20250929)
- Takes candidates + company context → Returns final SAT code + family code + confidence

**Returns**:
```python
ClassificationResult(
    sat_account_code="601.84.01",
    family_code="601", 
    confidence_sat=0.92,
    confidence_family=0.95,
    explanation_short="Servicios de consultoría",
    model_version="claude-sonnet-4-5-20250929"
)
```

### Classification Service Orchestration
- **File**: `core/ai_pipeline/classification/classification_service.py`
- **Function**: `classify_invoice_session(session_id, company_id, parsed_data, top_k)`
- **Location**: Lines 378-441

**Key Logic**:
1. Build expense snapshot from parsed_data
2. Call embeddings search with family_filter (received invoice families)
3. Transform candidates to LLM format
4. Call LLM classifier
5. Return classification dict with all metadata

**Current Family Filter** (Lines 75-109):
Filters to RECEIVED invoice families (what company buys):
- Fixed Assets: 151-158
- Intangible Assets: 118, 183, 184
- Inventory: 115
- Production Costs: 501-505
- Operating Expenses: 601-614

**EXCLUDES** income families (400-499) to prevent misclassification

### Storage: Single Source of Truth Model
- **Primary Table**: `expense_invoices` (domain model)
  - Column: `accounting_classification JSONB`
  - Index: `idx_expense_invoices_classification_status` for queries
  - **Location**: `migrations/2025_11_13_add_accounting_classification_to_invoices.sql`

- **Secondary Table**: `sat_invoices` (audit trail)
  - Column: `accounting_classification JSONB`
  - Indexes: SAT code, status, company queries
  - **Location**: `migrations/2025_11_12_add_accounting_classification.sql`

## 3. HIERARCHICAL FAMILY CLASSIFIER INTEGRATION

### Phase 1: Family-Level Classification (IMPLEMENTED)
- **File**: `core/ai_pipeline/classification/family_classifier.py`
- **Class**: `FamilyClassifier`
- **Purpose**: Classify invoice to family level (100-800) with >95% confidence
- **Input**: invoice_data dict + optional company_context
- **Output**: FamilyClassificationResult with detailed reasoning

**Families**:
```
100 - ACTIVO (Assets)
200 - PASIVO (Liabilities)
300 - CAPITAL (Equity)
400 - INGRESOS (Income)
500 - COSTO DE VENTAS (Cost of Sales)
600 - GASTOS DE OPERACIÓN (Operating Expenses)
700 - GASTOS FINANCIEROS (Financial Expenses)
800 - OTROS INGRESOS/GASTOS (Other Income/Expenses)
```

**Key Philosophy** (Lines 53-62):
- PRIMARY signal: Invoice concept (description) + company context
- SECONDARY signal: UsoCFDI as validation only
- Overrides UsoCFDI when semantic analysis contradicts it
- Provider reliability varies (often select UsoCFDI incorrectly)

**Integration Points**:
1. Currently standalone, not yet integrated with main classification flow
2. Could be used to pre-filter candidates in embeddings search
3. Would improve confidence by family validation

### Phase 2: Subfamily-Level (NOT YET IMPLEMENTED)
- Refine family (600) → subfamily (613) with >90% confidence
- Target implementation: Next iteration

### Phase 3: Detailed Account (NOT YET IMPLEMENTED)
- Refine subfamily (613) → detailed (613.01) with >85% confidence
- Target implementation: Later iteration

## 4. API ENDPOINTS FOR CLASSIFICATION

### Classification Management Endpoints
- **File**: `api/invoice_classification_api.py`

| Endpoint | Method | Purpose | Location |
|----------|--------|---------|----------|
| `/invoice-classification/confirm/{session_id}` | POST | Mark classification as correct | Lines 35-117 |
| `/invoice-classification/correct/{session_id}` | POST | Override classification + save correction | Lines 120-294 |
| `/invoice-classification/pending` | GET | List pending classifications for review | Lines 297-397 |
| `/invoice-classification/stats/{company_id}` | GET | Classification performance metrics | Lines 400-468 |
| `/invoice-classification/detail/{session_id}` | GET | Full classification details | Lines 471-539 |

### Processing Pipeline Endpoints
- **File**: `api/universal_invoice_engine_api.py`

| Endpoint | Purpose | Location |
|----------|---------|----------|
| `/universal-invoice/sessions/upload/` | Single file upload + session creation | Lines 535-599 |
| `/universal-invoice/sessions/batch-upload/` | Batch upload with background processing | Lines 83-158 |
| `/universal-invoice/sessions/{session_id}/process` | Trigger/continue processing | Lines 601-666 |
| `/universal-invoice/sessions/{session_id}/status` | Get processing status | Lines 922-958 |
| `/universal-invoice/sessions/{session_id}/extracted-data` | Get parsed invoice data | Lines 1041-1083 |
| `/universal-invoice/sessions/viewer-pro/{tenant_id}` | Optimized data for CFDI viewer | Lines 305-532 |

## 5. DATABASE SCHEMA FOR CLASSIFICATION RESULTS

### sat_invoices Table
**Columns for Classification**:
```sql
accounting_classification JSONB  -- AI classification result
processing_metrics JSONB         -- Includes classification_duration_ms
```

**Classification JSON Structure**:
```json
{
  "sat_account_code": "613.01",
  "family_code": "613",
  "confidence_sat": 0.92,
  "confidence_family": 0.95,
  "status": "pending_confirmation|confirmed|corrected|not_classified",
  "classified_at": "2025-11-12T10:30:00Z",
  "confirmed_at": null,
  "confirmed_by": null,
  "corrected_at": null,
  "corrected_sat_code": null,
  "correction_notes": null,
  "explanation_short": "Brief explanation",
  "model_version": "claude-sonnet-4-5-20250929",
  "alternative_candidates": [...],
  "metadata": {
    "session_id": "uis_...",
    "company_id": "carreta_verde",
    "candidates_count": 10
  }
}
```

**Indexes**:
- `idx_universal_invoice_sessions_accounting_code` - Filter by SAT code
- `idx_universal_invoice_sessions_accounting_status` - Filter by status (pending_confirmation)
- `idx_universal_invoice_sessions_company_accounting` - Composite query (company + status)

### expense_invoices Table
**Columns for Classification** (New as of Nov 13):
```sql
accounting_classification JSONB  -- Same structure as sessions
session_id TEXT                  -- Reference to sat_invoices for audit
```

**Indexes**:
- `idx_expense_invoices_classification_gin` - JSONB full-text search
- `idx_expense_invoices_classification_status` - Filter by status
- `idx_expense_invoices_sat_code` - Filter by SAT code
- `idx_expense_invoices_session_id` - Link to session for audit trail

## 6. KEY FILES SUMMARY

### Configuration & Setup
| File | Purpose |
|------|---------|
| `core/expenses/invoices/universal_invoice_engine_system.py` | Main engine (1654 lines) |
| `api/universal_invoice_engine_api.py` | Processing API endpoints (1499 lines) |
| `api/invoice_classification_api.py` | Classification confirmation API (540 lines) |

### Classification Core
| File | Purpose |
|------|---------|
| `core/ai_pipeline/classification/classification_service.py` | Orchestration service (442 lines) |
| `core/ai_pipeline/classification/expense_llm_classifier.py` | LLM refinement (uses Claude) |
| `core/ai_pipeline/classification/family_classifier.py` | Family-level classifier (336 lines) |
| `core/ai_pipeline/classification/prompts/family_classifier_prompt.py` | Prompt building (383 lines) |

### Supporting Services
| File | Purpose |
|------|---------|
| `core/accounting/account_catalog.py` | Embeddings search for SAT accounts |
| `core/shared/company_context.py` | Load company classification context |
| `core/shared/classification_utils.py` | Merge classifications (respects priority) |
| `core/ai_pipeline/parsers/invoice_parser.py` | Deterministic XML parsing for CFDI |

### Database
| File | Purpose |
|------|---------|
| `migrations/2025_11_12_add_accounting_classification.sql` | Add accounting_classification to sessions |
| `migrations/2025_11_13_add_accounting_classification_to_invoices.sql` | Add accounting_classification to invoices |

## 7. AUTO-CLASSIFICATION FLOW (Auto-Trigger on Processing Complete)

**When**: After invoice parsing completes successfully
**How**: Automatic background call (no user action required)
**Location**: `universal_invoice_engine_system.py` Lines 1246-1323

**Detailed Steps**:
1. Check if invoice has parsed_data (not extracted_data)
2. Filter by tipo_comprobante (only I=Income, E=Egreso)
3. Extract first concept (v1 simplification, handles multiple in Phase 2)
4. Build expense snapshot
5. Search SAT candidates via embeddings (top_k=10)
6. Call LLM classifier (ExpenseLLMClassifier)
7. Calculate duration metrics
8. Save classification to both tables:
   - `sat_invoices.accounting_classification` (audit trail)
   - `expense_invoices.accounting_classification` (single source of truth)

**Beta Tenants Only** (v1):
- carreta_verde
- pollenbeemx
- contaflow

## 8. CORRECTION/CONFIRMATION WORKFLOW

### Confirmation Flow (Lines 35-117 of invoice_classification_api.py)
```
Invoice with status: pending_confirmation
↓
Accountant clicks "CONFIRM"
↓
1. Mark status = "confirmed"
2. Set confirmed_at = now()
3. Set confirmed_by = user_id
4. Dual-write: Update both sat_invoices AND expense_invoices
5. Return confirmation receipt
```

### Correction Flow (Lines 120-294 of invoice_classification_api.py)
```
Invoice with status: pending_confirmation | corrected
↓
Accountant clicks "CORRECT" with corrected_sat_code
↓
1. Store original classification (for learning)
2. Update status = "corrected"
3. Set corrected_sat_code = new code
4. Set correction_notes = reason (optional)
5. Save to ai_correction_memory table:
   - original_description, provider_name, provider_rfc
   - original_sat_code, corrected_sat_code
   - corrected_by_user_id, corrected_at
   - confidence_before
6. Dual-write: Update both tables
7. Return correction receipt
```

**Correction Memory**:
- Stores human corrections for future learning
- Indexed by: company_id, provider_rfc, original_description
- Can be used to auto-apply patterns in future versions

## 9. KEY DESIGN DECISIONS

### Single Source of Truth
- **Primary**: `expense_invoices.accounting_classification` (domain model)
- **Secondary**: `sat_invoices.accounting_classification` (audit trail)
- Merge logic: Respects priority (corrected > confirmed > pending)

### Family Filter Strategy
- Only applicable families for RECEIVED invoices (what company buys)
- EXCLUDES income families (400-499) to prevent misclassification
- Currently 13 families filtered (151-158, 118, 183, 184, 115, 501-505, 601-614)

### Confidence Thresholds
- SAT code: Default threshold varies per use case
- Family: >95% for auto-approval, <95% for human review
- Alternative candidates: Provided in response for manual override

### Company Context Integration
- Loads industry, business_model, typical_expenses, provider_treatments
- Provided to LLM classifier for contextual reasoning
- Can override embeddings candidates if context suggests differently

### Hierarchical Design (Future-Ready)
- Phase 1: Family-level (100-800)
- Phase 2: Subfamily (e.g., 600 → 613)
- Phase 3: Detailed account (e.g., 613 → 613.01)
- Each phase adds refinement, allows human review between phases

## 10. INTEGRATION POINTS FOR HIERARCHICAL FAMILY CLASSIFIER

To integrate the new family classifier:

### Option A: Pre-Filter Embeddings Search
```python
# In classification_service.py
family_result = family_classifier.classify(invoice_data, company_id)
if family_result.confianza >= 0.95:
    # Filter embeddings search to only this family
    candidates = retrieve_relevant_accounts(
        expense_payload=expense_payload,
        top_k=top_k,
        family_filter=[family_result.familia_codigo]  # Pre-filter to single family
    )
```

### Option B: Validate Final Classification
```python
# After LLM classifier
family_code_from_sat = classification_result.family_code
family_result = family_classifier.classify(invoice_data, company_id)

if family_result.familia_codigo != family_code_from_sat:
    # Log warning and use family result if confidence higher
    if family_result.confianza > 0.95:
        use_family_override = True
```

### Option C: Multi-Stage Pipeline
```python
# Full hierarchical flow
1. Family-level classification (Phase 1) - high confidence threshold
2. Subfamily refinement (Phase 2) - if family confidence >= 0.95
3. Detailed account (Phase 3) - if subfamily confidence >= 0.90
```

## 11. BETA FEATURES & LIMITATIONS

### Current Limitations (v1)
- Only classifies tipo_comprobante I (Ingreso) and E (Egreso)
- Only uses first concept if multiple exist
- Only enabled for beta tenants
- No classification_trace field yet (v2)
- No multi-concept support yet (v2)

### What's Not Yet Integrated
- Family classifier is standalone, not called in main flow
- No Phase 2 (subfamily) refinement
- No Phase 3 (detailed account) refinement
- No classification_trace for audit/debugging
- No auto-apply from correction_memory (v2)

## 12. TESTING ENDPOINTS

### Quick Test
```bash
# Upload invoice
curl -X POST http://localhost:8000/universal-invoice/sessions/upload/ \
  -F "file=@invoice.xml" \
  -F "company_id=carreta_verde"

# Get processing status (will auto-trigger classification)
curl http://localhost:8000/universal-invoice/sessions/{session_id}/status

# Get pending classifications for review
curl "http://localhost:8000/invoice-classification/pending?company_id=carreta_verde"

# Confirm classification
curl -X POST http://localhost:8000/invoice-classification/confirm/{session_id}?user_id=accountant1

# Correct classification
curl -X POST http://localhost:8000/invoice-classification/correct/{session_id} \
  -d "corrected_sat_code=613.01&user_id=accountant1&correction_notes=Actually a professional service"
```

