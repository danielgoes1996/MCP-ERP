# Migration 035: Enhance expense_invoices with Fiscal Fields

**Created:** 2025-11-07
**Status:** Ready to apply
**Type:** Schema enhancement + New table

## 📋 Overview

This migration extends the `expense_invoices` table with comprehensive CFDI fiscal fields and creates a new `invoice_import_logs` table for complete audit trail of invoice imports.

## 🎯 Objectives

1. **Add CFDI fiscal fields** - UUID, RFC, dates, tax details
2. **Add computed total column** - Auto-calculated from components
3. **Enforce data integrity** - Make critical columns NOT NULL
4. **Improve performance** - Create indexes on commonly queried fields
5. **Add audit trail** - New table to log all invoice imports

## 📊 Changes Summary

### expense_invoices Table

#### New Columns (19 total)

**CFDI Identification:**
- `uuid` TEXT - UUID del CFDI (Folio Fiscal) - **UNIQUE INDEX**
- `rfc_emisor` TEXT - RFC del emisor
- `nombre_emisor` TEXT - Razón social del emisor
- `rfc_receptor` TEXT - RFC del receptor

**CFDI Dates:**
- `fecha_emision` TIMESTAMP - Fecha de emisión
- `fecha_timbrado` TIMESTAMP - Fecha de timbrado SAT

**CFDI Status:**
- `cfdi_status` TEXT DEFAULT 'vigente' - Estado (vigente/cancelado)
- `version_cfdi` TEXT DEFAULT '4.0' - Versión CFDI (3.3/4.0)

**Tax Details:**
- `tasa` REAL - Tasa del impuesto (0.16 para IVA 16%)
- `tipo_impuesto` TEXT - IVA, ISR, IEPS
- `tipo_factor` TEXT - Tasa, Cuota, Exento
- `isr_retenido` REAL DEFAULT 0
- `iva_retenido` REAL DEFAULT 0
- `ieps` REAL DEFAULT 0
- `otros_impuestos` REAL DEFAULT 0

**Organization:**
- `mes_fiscal` TEXT - Mes fiscal (YYYY-MM)
- `xml_path` TEXT - Ruta al XML CFDI
- `origen_importacion` TEXT DEFAULT 'manual' - Origen de importación

**Computed:**
- `total` REAL - Total auto-calculado

#### NOT NULL Constraints

Changed from nullable to NOT NULL:
- ✅ `expense_id` - FK a expense_records (crítico)
- ✅ `tenant_id` - FK a tenants (multi-tenancy)
- ✅ `filename` - Nombre del archivo
- ✅ `content_type` - MIME type

#### New Indexes (12 total)

```sql
-- Unique constraint
CREATE UNIQUE INDEX idx_expense_invoices_uuid ON expense_invoices(uuid) WHERE uuid IS NOT NULL;

-- Single column indexes
CREATE INDEX idx_expense_invoices_mes_fiscal ON expense_invoices(mes_fiscal);
CREATE INDEX idx_expense_invoices_cfdi_status ON expense_invoices(cfdi_status);
CREATE INDEX idx_expense_invoices_tenant_id ON expense_invoices(tenant_id);
CREATE INDEX idx_expense_invoices_rfc_emisor ON expense_invoices(rfc_emisor);
CREATE INDEX idx_expense_invoices_fecha_emision ON expense_invoices(fecha_emision);
CREATE INDEX idx_expense_invoices_origen ON expense_invoices(origen_importacion);

-- Compound indexes for common queries
CREATE INDEX idx_expense_invoices_tenant_status ON expense_invoices(tenant_id, cfdi_status);
CREATE INDEX idx_expense_invoices_tenant_mes ON expense_invoices(tenant_id, mes_fiscal);
CREATE INDEX idx_expense_invoices_tenant_fecha ON expense_invoices(tenant_id, fecha_emision);
```

#### New Triggers (2 total)

**Auto-calculate total on INSERT:**
```sql
total = subtotal + iva_amount - discount - retention + ieps + otros_impuestos - isr_retenido - iva_retenido
```

**Auto-update total on UPDATE:**
- Triggers when any amount field changes

### invoice_import_logs Table (NEW)

Complete audit trail for invoice imports.

#### Columns (23 total)

```sql
CREATE TABLE invoice_import_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Import Details
    filename TEXT NOT NULL,
    uuid_detectado TEXT,
    tenant_id INTEGER NOT NULL,

    -- Status
    status TEXT NOT NULL CHECK(status IN ('success', 'error', 'duplicate', 'skipped', 'pending')),
    error_message TEXT,

    -- Source
    source TEXT DEFAULT 'manual',  -- manual, email, api, bulk_upload
    import_method TEXT,  -- drag_drop, file_upload, email_forward

    -- Metadata
    file_size INTEGER,
    file_hash TEXT,  -- MD5/SHA256 for duplicate detection
    detected_format TEXT,  -- XML, PDF, JPG, PNG
    processing_time_ms INTEGER,

    -- User Context
    imported_by INTEGER,  -- FK to users
    batch_id TEXT,  -- For bulk imports

    -- Timestamps
    import_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP,

    -- Relations
    invoice_id INTEGER,  -- FK to expense_invoices if created
    expense_id INTEGER,  -- FK to expense_records if matched

    -- Additional
    metadata TEXT,  -- JSON with context

    FOREIGN KEY (tenant_id) REFERENCES tenants(id),
    FOREIGN KEY (imported_by) REFERENCES users(id),
    FOREIGN KEY (invoice_id) REFERENCES expense_invoices(id) ON DELETE SET NULL,
    FOREIGN KEY (expense_id) REFERENCES expense_records(id) ON DELETE SET NULL
);
```

#### Indexes (8 total)

```sql
CREATE INDEX idx_invoice_import_logs_tenant ON invoice_import_logs(tenant_id);
CREATE INDEX idx_invoice_import_logs_status ON invoice_import_logs(status);
CREATE INDEX idx_invoice_import_logs_uuid ON invoice_import_logs(uuid_detectado);
CREATE INDEX idx_invoice_import_logs_date ON invoice_import_logs(import_date DESC);
CREATE INDEX idx_invoice_import_logs_batch ON invoice_import_logs(batch_id);
CREATE INDEX idx_invoice_import_logs_source ON invoice_import_logs(source);
CREATE INDEX idx_invoice_import_logs_file_hash ON invoice_import_logs(file_hash);

-- Compound
CREATE INDEX idx_invoice_import_logs_tenant_status ON invoice_import_logs(tenant_id, status);
CREATE INDEX idx_invoice_import_logs_tenant_date ON invoice_import_logs(tenant_id, import_date DESC);
```

## 🚀 How to Apply

### Option 1: Python Script (Recommended)

```bash
# With automatic backup
python migrations/apply_035_migration.py
```

**Features:**
- ✅ Automatic database backup
- ✅ Pre-flight checks
- ✅ Post-migration verification
- ✅ Rollback on error
- ✅ Detailed logging

### Option 2: Direct SQL

```bash
sqlite3 unified_mcp_system.db < migrations/035_enhance_expense_invoices_fiscal_fields.sql
```

**⚠️ Warning:** Create manual backup first!

```bash
cp unified_mcp_system.db unified_mcp_system_backup_$(date +%Y%m%d_%H%M%S).db
```

## 🔄 Rollback

If you need to revert the migration:

```bash
sqlite3 unified_mcp_system.db < migrations/rollback_035_migration.sql
```

**⚠️ WARNING:** This will:
- Drop all new columns and data
- Drop `invoice_import_logs` table
- Restore original structure

## 📝 Usage Examples

### Example 1: Insert Invoice with CFDI Data

```python
import sqlite3
import json
from datetime import datetime

conn = sqlite3.connect('unified_mcp_system.db')
cursor = conn.cursor()

# Parse CFDI XML data
cfdi_data = {
    "uuid": "A1B2C3D4-E5F6-7890-ABCD-EF1234567890",
    "rfc_emisor": "ABC123456789",
    "nombre_emisor": "Proveedor S.A. de C.V.",
    "rfc_receptor": "XYZ987654321",
    "fecha_emision": "2025-11-07T10:30:00",
    "fecha_timbrado": "2025-11-07T10:31:15",
    "subtotal": 1000.00,
    "iva": 160.00,
    "total": 1160.00
}

# Insert invoice
cursor.execute("""
    INSERT INTO expense_invoices (
        expense_id, tenant_id, filename, content_type,
        uuid, rfc_emisor, nombre_emisor, rfc_receptor,
        fecha_emision, fecha_timbrado,
        subtotal, iva_amount,
        cfdi_status, version_cfdi,
        mes_fiscal, origen_importacion,
        xml_content, parsed_data
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (
    123,  # expense_id
    2,    # tenant_id
    'factura_A12345.xml',
    'application/xml',
    cfdi_data['uuid'],
    cfdi_data['rfc_emisor'],
    cfdi_data['nombre_emisor'],
    cfdi_data['rfc_receptor'],
    cfdi_data['fecha_emision'],
    cfdi_data['fecha_timbrado'],
    cfdi_data['subtotal'],
    cfdi_data['iva'],
    'vigente',
    '4.0',
    '2025-11',  # mes_fiscal
    'manual',
    xml_content_string,
    json.dumps(cfdi_data)
))

invoice_id = cursor.lastrowid

# Log the import
cursor.execute("""
    INSERT INTO invoice_import_logs (
        filename, uuid_detectado, tenant_id,
        status, source, imported_by,
        invoice_id, expense_id
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""", (
    'factura_A12345.xml',
    cfdi_data['uuid'],
    2,
    'success',
    'manual',
    1,  # user_id
    invoice_id,
    123  # expense_id
))

conn.commit()
print(f"✅ Invoice {invoice_id} created and logged")
```

### Example 2: Query Invoices by Fiscal Month

```python
# Get all invoices for November 2025
cursor.execute("""
    SELECT
        id, filename, uuid, rfc_emisor, nombre_emisor,
        fecha_emision, total, cfdi_status
    FROM expense_invoices
    WHERE tenant_id = ?
    AND mes_fiscal = ?
    ORDER BY fecha_emision DESC
""", (2, '2025-11'))

invoices = cursor.fetchall()
for inv in invoices:
    print(f"{inv[1]}: ${inv[6]:.2f} - {inv[7]}")
```

### Example 3: Check for Duplicate Imports

```python
# Before importing, check if UUID already exists
cursor.execute("""
    SELECT id, filename, created_at
    FROM expense_invoices
    WHERE uuid = ? AND tenant_id = ?
""", (uuid_to_check, tenant_id))

existing = cursor.fetchone()
if existing:
    # Log as duplicate
    cursor.execute("""
        INSERT INTO invoice_import_logs (
            filename, uuid_detectado, tenant_id,
            status, error_message, source
        ) VALUES (?, ?, ?, ?, ?, ?)
    """, (
        new_filename,
        uuid_to_check,
        tenant_id,
        'duplicate',
        f'Already imported as {existing[1]} on {existing[2]}',
        'manual'
    ))
    print(f"⚠️ Duplicate invoice detected!")
else:
    # Proceed with import
    ...
```

### Example 4: Bulk Import with Logging

```python
import uuid as uuid_lib

batch_id = str(uuid_lib.uuid4())
successful = 0
errors = 0

for xml_file in xml_files:
    try:
        # Parse and insert
        invoice_id = insert_invoice(xml_file)

        # Log success
        log_import(xml_file.name, 'success', batch_id, invoice_id)
        successful += 1

    except Exception as e:
        # Log error
        log_import(xml_file.name, 'error', batch_id, error_msg=str(e))
        errors += 1

print(f"✅ Imported {successful} invoices, {errors} errors")
print(f"📦 Batch ID: {batch_id}")
```

## 🔍 Verification Queries

After applying the migration, run these queries to verify:

```sql
-- Check new columns exist
PRAGMA table_info(expense_invoices);

-- Check indexes
SELECT name FROM sqlite_master
WHERE type='index' AND tbl_name='expense_invoices'
ORDER BY name;

-- Check triggers
SELECT name FROM sqlite_master
WHERE type='trigger' AND tbl_name='expense_invoices';

-- Check invoice_import_logs table
SELECT COUNT(*) FROM invoice_import_logs;

-- Verify total calculation trigger works
INSERT INTO expense_invoices (
    expense_id, tenant_id, filename, content_type,
    subtotal, iva_amount, discount, retention
) VALUES (999, 2, 'test.xml', 'application/xml', 1000, 160, 50, 20);

SELECT id, subtotal, iva_amount, discount, retention, total
FROM expense_invoices
WHERE expense_id = 999;
-- Expected total: 1000 + 160 - 50 - 20 = 1090
```

## 📚 Related Files

- `035_enhance_expense_invoices_fiscal_fields.sql` - Main migration
- `apply_035_migration.py` - Python application script
- `rollback_035_migration.sql` - Rollback script
- `README_035.md` - This documentation

## ⚠️ Important Notes

1. **Backup First:** Always create a backup before running migrations
2. **Foreign Keys:** Ensure foreign key support is enabled (`PRAGMA foreign_keys = ON`)
3. **NOT NULL Changes:** The migration handles existing NULL values automatically
4. **Total Calculation:** The `total` column is auto-calculated by triggers
5. **UUID Uniqueness:** The UUID index is partial (only for non-NULL values)

## 🐛 Troubleshooting

### Error: "NOT NULL constraint failed"

**Cause:** Existing records with NULL in expense_id, tenant_id, filename, or content_type

**Solution:** The migration handles this automatically, but if you run into issues:

```sql
-- Check for NULLs
SELECT
    COUNT(*) FILTER (WHERE expense_id IS NULL) as null_expense_id,
    COUNT(*) FILTER (WHERE tenant_id IS NULL) as null_tenant_id
FROM expense_invoices;

-- Fix manually if needed
UPDATE expense_invoices SET tenant_id = 1 WHERE tenant_id IS NULL;
```

### Error: "UNIQUE constraint failed: expense_invoices.uuid"

**Cause:** Trying to insert duplicate UUID

**Solution:** Check for existing UUID before insert:

```sql
SELECT id FROM expense_invoices WHERE uuid = 'YOUR-UUID-HERE';
```

## 📞 Support

If you encounter issues:

1. Check the migration log output
2. Verify prerequisites are met
3. Review troubleshooting section
4. Restore from backup if needed
5. Contact development team

## ✅ Checklist

Before applying:
- [ ] Database backup created
- [ ] Read this README completely
- [ ] Understood the changes
- [ ] Know how to rollback if needed

After applying:
- [ ] Run verification queries
- [ ] Check application still works
- [ ] Test invoice import functionality
- [ ] Update application code if needed
