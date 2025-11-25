# Invoice Storage Architecture Analysis
## SQLite to PostgreSQL Migration Report

Generated: 2025-11-15

---

## EXECUTIVE SUMMARY

Your application currently uses **MIXED DATABASE STORAGE** for invoices:
- **Primary**: PostgreSQL (via psycopg2) for universal invoice sessions
- **Legacy**: SQLite (via sqlite3) for some invoice management functions

**Critical Finding**: The `expense_invoices` table (main invoice storage) exists in **PostgreSQL only**, but some code still references SQLite.

---

## KEY FILES RESPONSIBLE FOR INVOICE STORAGE

### 1. MAIN INVOICE ENGINE (PRIMARY - POSTGRESQL)
**File**: `/Users/danielgoes96/Desktop/mcp-server/core/expenses/invoices/universal_invoice_engine_system.py`

**Database**: PostgreSQL (PSYCOPG2)
**Connection**: Lines 17-19
```python
import psycopg2
from psycopg2.extras import RealDictCursor
from core.shared.db_config import POSTGRES_CONFIG
```

**Key Methods for Storing Invoices**:
- `create_processing_session()` (line 893-916) - Creates session in `sat_invoices` table
- `_save_processing_result()` (line 1123-1189) - Saves extraction results
  - Updates `sat_invoices` with extracted data
  - Inserts into `universal_invoice_templates` 
  - Inserts into `universal_invoice_validations`
  - **CRITICAL**: `_save_classification_to_invoice()` (line 1446-1566) saves to `expense_invoices` table

**Database Tables Used**:
- `sat_invoices` - Processing metadata
- `universal_invoice_templates` - Template matching results
- `universal_invoice_validations` - Validation rules
- `expense_invoices` - SINGLE SOURCE OF TRUTH (line 1495-1552)

---

### 2. INVOICE MANAGER (LEGACY - SQLITE)
**File**: `/Users/danielgoes96/Desktop/mcp-server/core/expenses/invoices/invoice_manager.py`

**Database**: SQLite (SQLITE3)
**Connection**: Line 76
```python
conn = sqlite3.connect(self.db_path)  # ./data/mcp_internal.db
```

**Key Methods for Storing Invoices**:
- `update_invoice_status()` (line 65-107) - Updates ticket invoice status
- `attach_invoice_file()` (line 109-180) - Stores file attachment
  - **INSERT** into `invoice_attachments` table (line 144-156)
  - **UPDATE** `tickets` table with paths (line 162-163)

**Database Tables Used**:
- `invoice_attachments` - File storage metadata
- `tickets` - Invoice status tracking

**Status**: ⚠️ LEGACY - Should be migrated away from

---

### 3. UNIVERSAL INVOICE ENGINE API (ENDPOINTS)
**File**: `/Users/danielgoes96/Desktop/mcp-server/api/universal_invoice_engine_api.py`

**Database**: PostgreSQL (via unified_invoice_engine_system)

**Key Endpoints That Store Invoices**:
- `POST /sessions/upload/` (line 627-691) - Creates session
- `POST /sessions/batch-upload/` (line 114-250) - Batch processing
  - Duplicate detection using UUID (line 176-182)
  - Creates sessions for each unique invoice
- `POST /sessions/{session_id}/process` (line 693-758) - Processes invoice
  - Calls `universal_invoice_engine_system.process_invoice()`
  - Stores in PostgreSQL

**Database Operations**:
- Reads: `sat_invoices` to check for duplicates
- Writes: Delegates to `universal_invoice_engine_system`

---

### 4. BULK INVOICE PROCESSOR
**File**: `/Users/danielgoes96/Desktop/mcp-server/core/expenses/invoices/bulk_invoice_processor.py`

**Database**: Uses `get_db_adapter()` (abstracted)
**Location**: Lines 19-23

**Key Methods**:
- `create_batch()` - Creates batch record
- `process_batch()` - Processes multiple invoices
- Results are stored via `get_db_adapter()` abstraction

**Note**: Uses abstracted database adapter for flexibility

---

### 5. BULK INVOICE API
**File**: `/Users/danielgoes96/Desktop/mcp-server/api/bulk_invoice_api.py`

**Database**: PostgreSQL (via unified_db_adapter)

**Endpoint**: `POST /api/bulk-invoice/process-batch` (line 30-79)
- Validates batch data
- Calls `bulk_invoice_processor.create_batch()`
- Uses `get_db_adapter()` for storage

---

### 6. LEGACY INTERNAL_DB (PARTIAL)
**File**: `/Users/danielgoes96/Desktop/mcp-server/core/internal_db.py`

**Database**: MIXED - SQLite (line 1703) and PostgreSQL
**Connection**: Lines 1702-1703
```python
with sqlite3.connect(_get_db_path()) as connection:
```

**Key Methods**:
- `register_expense_invoice()` (line 1013-1039) - **INSERT** into `expense_invoices`
- `mark_expense_invoiced()` (line 1041-1051) - **UPDATE** `expense_records`

**Status**: ⚠️ LEGACY CODE - Uses SQLite but should use PostgreSQL

---

## DATABASE CONFIGURATION

**File**: `/Users/danielgoes96/Desktop/mcp-server/core/shared/db_config.py`

**PostgreSQL Configuration** (lines 12-19):
```python
POSTGRES_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "127.0.0.1"),
    "port": int(os.getenv("POSTGRES_PORT", 5433)),
    "database": os.getenv("POSTGRES_DB", "mcp_system"),
    "user": os.getenv("POSTGRES_USER", "mcp_user"),
    "password": os.getenv("POSTGRES_PASSWORD", "changeme")
}
```

**expense_invoices Table Schema** (lines 23-49):
```python
"id": "integer",
"tenant_id": "integer",
"company_id": "integer",
"filename": "varchar(500)",
"uuid": "varchar(36)",
"rfc_emisor": "varchar(13)",
"nombre_emisor": "varchar(500)",
"rfc_receptor": "varchar(13)",
"nombre_receptor": "varchar(500)",
"fecha_emision": "timestamp",
"subtotal": "double precision",
"iva_amount": "double precision",
"total": "double precision",
"currency": "varchar(10)",
"tipo_comprobante": "varchar(10)",
"linked_expense_id": "integer",
"match_confidence": "double precision",
"raw_xml": "text"
```

---

## CURRENT DATABASE USAGE SUMMARY

### PostgreSQL (ACTIVE)
Tables that store invoice data:
1. `sat_invoices` - Invoice processing metadata
2. `universal_invoice_templates` - Template matching results
3. `universal_invoice_validations` - Validation audit trail
4. `expense_invoices` - **MAIN INVOICE DATA** (SINGLE SOURCE OF TRUTH)

### SQLite (LEGACY)
Tables that store invoice data:
1. `invoice_attachments` - File attachments (deprecated)
2. `tickets` - Invoice status (deprecated)
3. `expense_records` - Expense tracking (partially used)

---

## INSERT/UPDATE OPERATIONS FOUND

### PostgreSQL Operations (MODERN - PRIMARY)

#### INSERT Operations:
1. **Line 905-912** (universal_invoice_engine_system.py): 
   - `INSERT INTO sat_invoices`
   
2. **Line 1152-1166** (universal_invoice_engine_system.py):
   - `INSERT INTO universal_invoice_templates`
   
3. **Line 1171-1187** (universal_invoice_engine_system.py):
   - `INSERT INTO universal_invoice_validations`
   
4. **Line 1022** (unified_db_adapter.py):
   - `INSERT INTO expense_invoices` (new invoices)
   
5. **Line 1467** (unified_db_adapter.py):
   - `INSERT INTO expense_invoices` (alternative path)

#### UPDATE Operations:
1. **Line 1131-1148** (universal_invoice_engine_system.py):
   - `UPDATE sat_invoices` (sets extracted data, template match, validation rules)
   
2. **Line 1542-1552** (universal_invoice_engine_system.py):
   - `UPDATE expense_invoices` (saves classification and session_id)
   
3. **Line 1583** (unified_db_adapter.py):
   - `UPDATE expense_invoices` (general updates)

### SQLite Operations (LEGACY - TO BE DEPRECATED)

#### INSERT Operations:
1. **Line 1712-1719** (internal_db.py):
   - `INSERT INTO expense_invoices` (CONFLICTS with PostgreSQL!)
   
2. **Line 144-156** (invoice_manager.py):
   - `INSERT INTO invoice_attachments`

#### UPDATE Operations:
1. **Line 84-97** (invoice_manager.py):
   - `UPDATE tickets` (status tracking)
   
2. **Line 425-429** (invoice_manager.py):
   - `UPDATE tickets` (file paths)
   
3. **Line 1720-1732** (internal_db.py):
   - `UPDATE expense_records` (marks as invoiced)

---

## MIGRATION PRIORITY

### 🔴 HIGH PRIORITY - CONFLICTS
1. **invoice_manager.py** - REMOVE entirely, use universal_invoice_engine_system
2. **internal_db.py** - Migrate `register_expense_invoice()` to PostgreSQL
3. Invoice attachment handling - Move to file_manager or unified_db_adapter

### 🟡 MEDIUM PRIORITY - REFACTOR
1. **bulk_invoice_processor.py** - Ensure all paths use PostgreSQL
2. Update all SQLite references to use PostgreSQL connection
3. Add database adapter abstraction for flexibility

### 🟢 LOW PRIORITY - COMPLETE
1. **universal_invoice_engine_system.py** - Already using PostgreSQL ✓
2. **universal_invoice_engine_api.py** - Already using PostgreSQL ✓
3. Database configuration - Already set to PostgreSQL ✓

---

## RECOMMENDED MIGRATION STEPS

1. **Create Database Adapter Interface**
   - Single unified way to insert/update invoices
   - Located: `core/shared/unified_db_adapter.py` (PARTIALLY DONE)

2. **Remove Legacy SQLite Code**
   - Delete `invoice_manager.py` methods that use SQLite
   - Replace with calls to PostgreSQL via unified_db_adapter
   - Delete SQLite-only code from `internal_db.py`

3. **Update All INSERT/UPDATE Statements**
   - Change sqlite3 connections to psycopg2
   - Use parameterized queries (already done in most places)
   - Add proper error handling for constraint violations

4. **Create Migration Script**
   - Copy data from SQLite to PostgreSQL
   - Handle duplicates (UUID-based deduplication)
   - Validate data integrity

5. **Testing**
   - Test invoice upload flow end-to-end
   - Test batch processing with large datasets
   - Verify no data loss in migration

---

## KEY INSIGHTS FOR MIGRATION

### Database Connection Patterns
- **PostgreSQL**: Uses `psycopg2` with connection pooling support
- **SQLite**: Uses sqlite3 with thread locks (`_DB_LOCK`)
- Both use parameterized queries (safe from SQL injection)

### Important Fields to Preserve
- `uuid` - Unique invoice identifier (critical for deduplication)
- `tenant_id` - Multi-tenant support
- `accounting_classification` - LLM classification results
- `session_id` - Audit trail linking to sat_invoices
- `raw_xml` - Original CFDI XML for compliance

### Constraints to Implement
- UUID uniqueness constraint
- Foreign keys (expense_id, tenant_id)
- NOT NULL for required fields (uuid, tenant_id, total)
- Check constraints for amounts > 0

---

## FILES TO MODIFY FOR MIGRATION

### Remove/Deprecate:
- `/Users/danielgoes96/Desktop/mcp-server/core/expenses/invoices/invoice_manager.py`
- SQLite sections in `core/internal_db.py`

### Update:
- `core/shared/unified_db_adapter.py` - Ensure all invoice operations use PostgreSQL
- `core/expenses/invoices/bulk_invoice_processor.py` - Verify PostgreSQL usage
- `core/expenses/invoices/universal_invoice_engine_system.py` - Already done ✓
- `api/universal_invoice_engine_api.py` - Already done ✓
- `api/bulk_invoice_api.py` - Already done ✓

### Verify:
- `core/shared/db_config.py` - PostgreSQL configuration is correct ✓
- All connection strings use `POSTGRES_CONFIG`
- All table names match PostgreSQL schema

---

## TESTING CHECKLIST

- [ ] PostgreSQL connection works with POSTGRES_CONFIG
- [ ] All INSERT statements execute successfully
- [ ] All UPDATE statements execute successfully
- [ ] UUID uniqueness constraint prevents duplicates
- [ ] Foreign key constraints work correctly
- [ ] Rollback on error doesn't leave partial records
- [ ] Large batch processing (1000+ invoices) works
- [ ] Error messages are informative
- [ ] Data integrity checks pass
- [ ] Performance meets SLAs

