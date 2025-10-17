# Database & Data Model Audit (backend-stable-3.9)

## 1. Models Overview

| Model family | File & line | Fields & validators | Router / Domain |
|--------------|-------------|---------------------|-----------------|
| ✅ `MCPRequest`, `MCPResponse` | core/api_models.py:14–29 | `method:str`, `params:dict` (⚠️ mutable default); response fields `success`, `data`, `error`, `result`. | `main.py::mcp_endpoint` |
| ✅ Catalog models (`AccountingCategoryResponse`, etc.) | core/api_models.py:35–120 | Catalog metadata fields; no validators. | Config/catalog endpoints (`config_router_v2`) |
| ✅ `ExpenseCreate` | core/api_models.py:83–233 | Full expense payload; amount/date/currency validators. | Expense POST (`main.py`), duplicate detection. |
| ✅ `ExpenseResponse` & derivatives | core/api_models.py:244–444 | Comprehensive expense response (tax info, metadata, events). | `/expenses`, invoicing automation. |
| ✅ `ExpenseTag*`, `ExpenseAttachmentResponse` | core/api_models.py:369–444 | Tag CRUD with lowercase validators; attachment metadata. | Tag management (planned). |
| ⚠️ `ExpenseInvoicePayload`, `ExpenseActionRequest` | core/api_models.py:1097–1117 | Action payloads; no validators; overlap with router logic. | Invoice registration, mark invoiced. |
| ✅ `DuplicateCheckRequest/Response` | core/api_models.py:1028–1076 | Wraps `ExpenseCreate`; threshold validator. | `/expenses/check-duplicates`. |
| ✅ `CategoryPredictionRequestV2/Response` | core/api_models.py:1079–1094 | Description length validator; response includes alternatives. | `/expenses/predict-category`. |
| ⚠️ Onboarding models (`OnboardingRequest`, etc.) | core/api_models.py:1197–1418 | Basic string trimming; duplicates definitions in `core/unified_auth`. | `/onboarding` router. |
| ✅ `BulkInvoiceMatch*` | core/api_models.py:560–730 | Request ensures thresholds, response w/ metrics. | `/invoices/bulk-match`. |
| ✅ `BankSuggestion*`, `BankReconciliation*` | core/api_models.py:730–1013 | Movement metadata; enum validators. | Bank reconciliation endpoints. |
| ✅ Voice expense/transcript models | core/api_models.py:2224–2480 | Audio base64 + metadata. | `voice_mcp`. |
| ✅ Split reconciliation models | core/split_reconciliation_models.py:33–210 | Amount validators; ConfigDict `use_enum_values=True`. | Split reconciliation service. |
| ✅ Bank statement/transaction models | core/bank_statements_models.py:185–320 | Validators to ignore zero rows; ConfigDict `use_enum_values=True`. | Bank ingestion & APIs. |
| ✅ `UserPaymentAccount`, responses | core/payment_accounts_models.py:32–180 | Validators for card numbers, credit limits; derived state. | Finance router (`/payment-accounts`). |
| ✅ Employee advances models | core/employee_advances_models.py:34–134 | Positive amount validators; ConfigDict `from_attributes=True`. | Employee advances APIs. |
| ✅ Automation models (`AutomationJob*`, etc.) | core/automation_models.py:22–208 | DTOs for automation configs; no validators. | Automation engine/routers. |
| ✅ Auth models (`User`, `TokenData`, `AuthResponse`, etc.) | core/auth_system.py:41–118 | Auth payloads; password validation in service. | Legacy auth endpoints (`api/auth_api.py`). |
| ✅ JWT models (`User`, `Token`, etc.) | core/auth_jwt.py:32–93 | ConfigDict `from_attributes=True`. | JWT helpers. |
| ✅ Unified auth models (`UserBase`, `User`, etc.) | core/unified_auth.py:64–193 | ConfigDict `from_attributes=True`; email/tenant validation. | Unified auth service & routers. |
| ✅ Invoicing agent models (`TicketCreate`, `Merchant*`, `InvoicingJob*`, etc.) | modules/invoicing_agent/models.py:26–143 | `TicketCreate` uses `model_validator`; others mirror DB columns. | `modules/invoicing_agent` API. |
| ✅ Inline request models (Finance, automation routers) | app/routers/finance_router.py, api/automation_v2.py, etc. | Query/response wrappers; minimal validation. | Finance/automation endpoints. |
| ✅ SQLAlchemy models (`AccountingBase`, bank transactions) | core/accounting_models.py, core/bank_transactions_models.py | Declarative ORM mapping to SQLite tables. | Internal DB operations. |

## 2. Relationships and Dependencies

- `ExpenseCreate` is embedded in `DuplicateCheckRequest`; `ExpenseResponse` is referenced by invoice matching, bank reconciliation, and automation responses.
- `BulkInvoiceMatchResponse.results[]` contain `InvoiceMatchResult` objects that embed `ExpenseResponse`, linking invoicing and expenses domains.
- Bank reconciliation models (`BankSuggestion`, `BankReconciliationFeedback`) tie bank movements to expense IDs (implied 1:N mapping).
- Employee advances reference `expense_id` and employee metadata, bridging HR and expenses.
- Invoicing agent models (tickets, merchants, jobs) form a pipeline from WhatsApp ingestion → merchant detection → automation job creation.
- Auth models exist in three layers: legacy (`core/auth_system`), unified (`core/unified_auth`), and JWT (`core/auth_jwt`); routers still import a mix of them.
- SQLAlchemy tables (`core/accounting_models.py`, `core/bank_transactions_models.py`) underpin Pydantic responses but some are loosely referenced in code.

## 3. Potential Issues ⚠️

- ⚠️ **Mutable defaults** in request/response models (`params: {}`, `metadata: {}`) risk shared state.
- ⚠️ **Testing stub misalignment**: `/expenses` stub returns a simplified dict lacking `id`. Downstream tests expecting `ExpenseResponse` fields fail in clean environments.
- ⚠️ **Duplicated models**: Onboarding and auth DTOs reappear across modules (`core/unified_auth`, `api/auth_api`, `core/api_models`).
- ⚠️ **Naming inconsistencies**: Mixed English/Spanish fields (`estado_factura` vs `invoice_status`, `movement_id` vs `id`).
- ⚠️ **Enum serialization**: Many models rely on string enums but lack `model_config = ConfigDict(use_enum_values=True)`, causing inconsistent JSON.
- ⚠️ **SecurityVault** (not a Pydantic model) creates asyncio tasks at import → tests error “no running event loop”.
- ⚠️ **Legacy SQLAlchemy tables** (bank/accounting) are not clearly wired to current APIs; possible drift.
- ⚠️ **Monolithic `core/api_models.py`** mixes domains (voice, onboarding, expenses, bank). Hard to maintain.

## 4. Alignment with API

| Endpoint / Function | Expected payload | Pydantic model | Status |
|---------------------|------------------|----------------|--------|
| `POST /expenses` (`create_expense`) | Should return `ExpenseResponse` with assigned `id`, statuses | `ExpenseResponse` | ⚠️ Testing stub returns `{success: True, expense_id: 1}` (missing fields). |
| `GET /expenses` | List[ExpenseResponse], filtered | `ExpenseResponse` | ⚠️ Stub returns single hard-coded expense, many fields omitted. |
| `POST /expenses/check-duplicates` | `DuplicateCheckRequest` → `DuplicateCheckResponse` | Matching models | ✅ |
| `POST /expenses/predict-category` | `CategoryPredictionRequestV2` | With simple validators | ✅ |
| `POST /invoices/bulk-match` | `BulkInvoiceMatchRequest`/`Response` linking expenses | Model matches router | ✅ |
| `POST /invoices/parse` | Multipart file → `InvoiceParseResponse` | Model matches | ✅ |
| `GET /bank_reconciliation/movements` | Should return movements/suggestions | `BankTransaction` etc. | ⚠️ Router constructs dicts manually; partial coverage. |
| `POST /automation/jobs` | `AutomationJobCreate` etc. | Model aligned | ✅ |
| `POST /voice_mcp` | `VoiceExpenseRequest` | Model aligned | ✅ |
| `/onboarding/register` | `OnboardingRequest/Response` | Mixed definitions across modules | ⚠️ Risk of divergence. |
| Auth (`/auth/token`, `/auth/jwt`) | `LoginRequest`, `Token` | Legacy + unified models co-exist | ⚠️ Duplicated fields. |

## 5. Recommended Actions ✅

1. **Refactor `core/api_models.py` by domain** (expenses, bank, automation, onboarding) and apply `ConfigDict` per group (e.g., `use_enum_values`, `from_attributes`).
2. **Fix mutable defaults** using `Field(default_factory=dict/list)` to avoid shared state (e.g., `MCPRequest.params`, metadata fields).
3. **Align testing stubs** with `ExpenseResponse`: ensure `/expenses` stubs return objects with `id`, statuses, and key metadata so extended tests can pass.
4. **Unify auth/onboarding models** around `core/unified_auth`; deprecate duplicates in `core/auth_system` and `api/auth_api.py` or ensure explicit mapping.
5. **Standardize naming**: adopt consistent English field names for APIs (`invoice_status` instead of `estado_factura`) or document bilingual mapping; provide enums for status fields.
6. **Update SecurityVault initialization** to avoid `asyncio.create_task` at import; expose async factory or lazy init to unblock security tests.
7. **Review SQLAlchemy models** for actual usage; remove or archive unused tables or generate Pydantic models from ORM to guarantee alignment.
8. **Introduce monetary `Decimal` types** in expense/bank models to avoid floating precision issues.
9. **Document relationships** (UML or markdown) linking expenses ↔ invoices ↔ bank movements; helps future schema migrations.
10. **Expand CI** with lint rule catching mutable defaults and run `make test-smoke` (already documented) on every PR.

---

This audit covers Pydantic/BaseModel definitions across `core/`, `modules/`, and API routers, outlines hierarchical dependencies, flags schema issues, and lists practical steps toward a clean, maintainable data model for MCP Server.
