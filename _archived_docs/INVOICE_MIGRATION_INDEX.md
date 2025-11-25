# Invoice Storage Migration - Complete Documentation Index

## Overview
This directory contains comprehensive documentation for migrating invoice storage from SQLite to PostgreSQL. All analysis was completed on 2025-11-15.

---

## Generated Documents

### 1. MIGRATION_SUMMARY.txt (START HERE)
**File Size**: 11 KB | **Format**: Plain text
**Best For**: Quick overview and executive summary

**Contains**:
- Key findings and current state
- Critical files and line numbers
- Migration checklist (5 phases)
- 10 key SQL operations to verify
- Database schema information
- Configuration requirements
- Next steps

**Read This First** - It's the quickest way to understand what needs to be done.

---

### 2. INVOICE_STORAGE_MIGRATION.md
**File Size**: 11 KB | **Format**: Markdown
**Best For**: Detailed architecture and migration strategy

**Contains**:
- Executive summary
- 6 key files responsible for invoice storage
- Database configuration details
- Complete INSERT/UPDATE operations breakdown
- Migration priority levels (HIGH/MEDIUM/LOW)
- 5 recommended migration steps
- Key insights for migration
- Testing checklist

**Read This** - For understanding the complete architecture and migration approach.

---

### 3. INVOICE_INSERT_UPDATE_LOCATIONS.md
**File Size**: 14 KB | **Format**: Markdown
**Best For**: Code snippets and exact locations

**Contains**:
- 7 PostgreSQL operations with full code snippets
- 4 SQLite operations with code snippets
- Summary table of all locations
- Migration action items
- Database statistics

**Read This** - When you need to see exact code and line numbers.

---

### 4. INVOICE_CLASSIFICATION_COMPLETE_GUIDE.md
**File Size**: 16 KB | **Format**: Markdown
**Best For**: Understanding the classification system

**Contains**:
- Invoice classification architecture
- LLM integration details
- Classification status tracking
- Database tables used
- Example workflows

**Read This** - If you need to understand how classification integrates with storage.

---

## Quick Navigation

### For Project Managers
1. Start with `MIGRATION_SUMMARY.txt`
2. Review the 5-phase checklist
3. Understand HIGH PRIORITY items

### For Backend Developers
1. Read `INVOICE_STORAGE_MIGRATION.md` for architecture
2. Use `INVOICE_INSERT_UPDATE_LOCATIONS.md` for code locations
3. Refer back to specific line numbers as needed

### For DevOps/Database Administrators
1. Check "Database Configuration" section in `MIGRATION_SUMMARY.txt`
2. Review schema details in `INVOICE_STORAGE_MIGRATION.md`
3. Plan infrastructure for PostgreSQL connection

### For QA/Testing Engineers
1. Review "Testing Checklist" in `INVOICE_STORAGE_MIGRATION.md`
2. Plan test cases for each operation
3. Prepare test data

---

## Key Facts at a Glance

**Current Status**:
- 64% PostgreSQL (7 operations) - ACTIVE
- 36% SQLite (4 operations) - LEGACY/DEPRECATED

**Critical Files to Know**:
- `/core/expenses/invoices/universal_invoice_engine_system.py` - PRIMARY storage logic
- `/core/expenses/invoices/invoice_manager.py` - DEPRECATED SQLite code
- `/core/internal_db.py` - CONFLICTS with PostgreSQL
- `/core/shared/db_config.py` - Database configuration

**Main Invoice Table**:
- `expense_invoices` in PostgreSQL
- Unique identifier: `uuid` (CFDI XML)
- Single source of truth: Yes

**Database Configuration**:
- Host: 127.0.0.1 (env: POSTGRES_HOST)
- Port: 5433 (env: POSTGRES_PORT)
- Database: mcp_system (env: POSTGRES_DB)
- User: mcp_user (env: POSTGRES_USER)

---

## 5-Phase Migration Checklist

### Phase 1: Audit & Documentation (COMPLETED)
- [x] Identified all INSERT/UPDATE operations
- [x] Mapped database conflicts
- [x] Created architecture documentation
- [x] Generated code location references

### Phase 2: Immediate Fixes (HIGH PRIORITY - DO FIRST)
- [ ] Stop using invoice_manager.py SQLite code
- [ ] Stop using internal_db.py SQLite INSERT
- [ ] Redirect all calls to unified_db_adapter.py (PostgreSQL)
- [ ] Add deprecation warnings to SQLite methods

### Phase 3: Refactoring (MEDIUM PRIORITY)
- [ ] Review all invoice upload endpoints
- [ ] Ensure bulk_invoice_processor uses PostgreSQL
- [ ] Create unified invoice storage interface
- [ ] Add transaction support for multi-step operations

### Phase 4: Migration (LOW PRIORITY - If SQLite data exists)
- [ ] Backup SQLite invoice data
- [ ] Create migration script (UUID-based deduplication)
- [ ] Validate data integrity
- [ ] Migrate SQLite → PostgreSQL
- [ ] Verify no data loss

### Phase 5: Testing & Cleanup (ONGOING)
- [ ] Test invoice upload flow
- [ ] Test batch processing
- [ ] Test duplicate detection (UUID)
- [ ] Test error handling
- [ ] Remove deprecated SQLite code
- [ ] Performance testing (1000+ invoices)

---

## Top 10 Operations to Track

| # | Location | Table | Operation | DB | Status |
|---|----------|-------|-----------|----|----|
| 1 | universal_invoice_engine_system.py:905 | sat_invoices | INSERT | PostgreSQL | ACTIVE |
| 2 | universal_invoice_engine_system.py:1131 | sat_invoices | UPDATE | PostgreSQL | ACTIVE |
| 3 | universal_invoice_engine_system.py:1152 | universal_invoice_templates | INSERT | PostgreSQL | ACTIVE |
| 4 | universal_invoice_engine_system.py:1171 | universal_invoice_validations | INSERT | PostgreSQL | ACTIVE |
| 5 | universal_invoice_engine_system.py:1542 | expense_invoices | UPDATE | PostgreSQL | CRITICAL |
| 6 | unified_db_adapter.py:1022 | expense_invoices | INSERT | PostgreSQL | ACTIVE |
| 7 | unified_db_adapter.py:1583 | expense_invoices | UPDATE | PostgreSQL | ACTIVE |
| 8 | invoice_manager.py:144 | invoice_attachments | INSERT | SQLite | DEPRECATED |
| 9 | invoice_manager.py:84 | tickets | UPDATE | SQLite | DEPRECATED |
| 10 | internal_db.py:1712 | expense_invoices | INSERT | SQLite | CONFLICT |

---

## Common Questions

**Q: Which database should I use for new invoice code?**
A: PostgreSQL only. Use `unified_db_adapter.py` or `universal_invoice_engine_system.py`.

**Q: What about existing SQLite data?**
A: If it exists, migrate it to PostgreSQL using UUID-based deduplication. See Phase 4.

**Q: How do I know if I'm using the right database?**
A: Check if you're using `psycopg2` (PostgreSQL) or `sqlite3` (SQLite). PostgreSQL is correct.

**Q: What's the single source of truth for invoices?**
A: The `expense_invoices` table in PostgreSQL, updated via `_save_classification_to_invoice()`.

**Q: How is duplicate detection implemented?**
A: Using UUID extracted from CFDI XML files. Checked during session creation.

**Q: What happens to the sat_invoices table?**
A: It's metadata/audit trail. Links to expense_invoices via session_id.

**Q: Do I need to worry about the raw_xml column?**
A: Yes - it stores the original CFDI XML for compliance and validation.

**Q: How are classifications stored?**
A: As JSON in the `accounting_classification` column of expense_invoices.

---

## Performance Considerations

- PostgreSQL can handle 1000+ invoices efficiently
- UUID indexing is important for duplicate detection
- Connection pooling recommended for high-volume processing
- Batch operations should use transactions for atomicity
- Archive old sat_invoices records periodically

---

## Related Files

**Other Important Files**:
- `/api/universal_invoice_engine_api.py` - API endpoints
- `/api/bulk_invoice_api.py` - Bulk processing endpoints
- `/core/expenses/invoices/bulk_invoice_processor.py` - Batch processing logic
- `/core/shared/unified_db_adapter.py` - Database adapter interface
- `/core/shared/db_config.py` - Configuration

**Supporting Documentation**:
- Check git history for when PostgreSQL migration started
- Review PR comments on feature/backend-refactor branch
- Check POSTGRES_CONFIG environment variables

---

## Contact & Support

For detailed information about any section:
1. Check the corresponding document listed above
2. Look at the line numbers referenced
3. Review the code snippets provided
4. Consult team members familiar with invoice processing

---

## Version Information

- **Analysis Date**: 2025-11-15
- **Branch**: feature/backend-refactor
- **Database**: PostgreSQL 5433 (mcp_system)
- **Python Version**: 3.8+ (psycopg2 required)
- **Status**: Documentation Complete, Ready for Implementation

---

## Document Map

```
mcp-server/
├── INVOICE_MIGRATION_INDEX.md .................... This file
├── MIGRATION_SUMMARY.txt ......................... Executive summary (start here)
├── INVOICE_STORAGE_MIGRATION.md ................. Detailed architecture
├── INVOICE_INSERT_UPDATE_LOCATIONS.md ........... Code snippets
└── INVOICE_CLASSIFICATION_COMPLETE_GUIDE.md .... Classification system

core/
├── expenses/invoices/
│   ├── universal_invoice_engine_system.py ....... PRIMARY (PostgreSQL)
│   ├── invoice_manager.py ........................ DEPRECATED (SQLite)
│   └── bulk_invoice_processor.py ................ Batch processing
├── shared/
│   ├── db_config.py ............................. Configuration
│   └── unified_db_adapter.py .................... Database adapter
└── internal_db.py ............................... CONFLICT (SQLite/PostgreSQL mix)

api/
├── universal_invoice_engine_api.py .............. API endpoints
└── bulk_invoice_api.py .......................... Bulk endpoints
```

---

**Last Updated**: 2025-11-15
**Analysis Tool**: Claude Code
**Status**: Ready for Implementation
