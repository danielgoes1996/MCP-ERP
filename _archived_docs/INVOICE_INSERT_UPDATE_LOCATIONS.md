# Invoice INSERT/UPDATE Operations - Quick Reference Guide

## PostgreSQL Operations (PRIMARY - ACTIVE)

### 1. CREATE INVOICE SESSION - universal_invoice_engine_system.py:905-912
```python
async def create_processing_session(self, company_id: str, file_path: str,
                                  original_filename: str,
                                  user_id: Optional[str] = None) -> str:
    session_id = f"uis_{hashlib.md5(...).hexdigest()[:16]}"
    
    async with await self._get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO sat_invoices (
                id, company_id, user_id, invoice_file_path, original_filename,
                file_hash, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (session_id, company_id, user_id, file_path, original_filename,
              file_hash, datetime.utcnow()))
        conn.commit()
```
**Table**: `sat_invoices`
**Operation**: INSERT (Creates new invoice processing session)
**Database**: PostgreSQL
**Status**: ACTIVE - PRIMARY USAGE

---

### 2. UPDATE SESSION WITH EXTRACTED DATA - universal_invoice_engine_system.py:1131-1148
```python
async def _save_processing_result(self, session_id: str, result: Dict[str, Any],
                                template_match: TemplateMatch, 
                                validation_rules: List[ValidationRule]):
    async with await self._get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Actualizar sesión principal
        cursor.execute("""
            UPDATE sat_invoices
            SET detected_format = %s, parser_used = %s, template_match = %s,
                validation_rules = %s, extraction_status = %s, extracted_data = %s,
                parsed_data = %s, extraction_confidence = %s, validation_score = %s,
                overall_quality_score = %s, processing_time_ms = %s, completed_at = %s,
                updated_at = %s
            WHERE id = %s
        """, (result['detected_format'], result['parser_used'],
              json.dumps(result['template_match']),
              json.dumps(result['validation_rules']),
              'completed', json.dumps(result['extracted_data']),
              json.dumps(result['parsed_data']),
              result['extraction_confidence'], 
              result['validation_rules']['validation_score'],
              result['overall_quality_score'], 
              result['processing_metrics']['total_time_ms'],
              datetime.utcnow(), datetime.utcnow(), session_id))
```
**Table**: `sat_invoices`
**Operation**: UPDATE (Sets extracted data, template match, validation rules)
**Database**: PostgreSQL
**Status**: ACTIVE - PRIMARY USAGE

---

### 3. INSERT TEMPLATE MATCH DETAILS - universal_invoice_engine_system.py:1152-1166
```python
# Guardar template match detallado
template_id = f"uit_{hashlib.md5(...).hexdigest()[:16]}"
cursor.execute("""
    INSERT INTO universal_invoice_templates (
        id, session_id, format_id, template_match, template_name,
        match_score, matched_patterns, confidence_factors, matching_method,
        is_selected, created_at
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (id) DO NOTHING
""", (template_id, session_id, 'default_format',
      json.dumps(result['template_match']),
      template_match.template_name, template_match.match_score,
      json.dumps(template_match.matched_patterns),
      json.dumps(template_match.confidence_factors),
      template_match.matching_method.value, True, datetime.utcnow()))
```
**Table**: `universal_invoice_templates`
**Operation**: INSERT (Stores template matching audit trail)
**Database**: PostgreSQL
**Status**: ACTIVE - AUDIT TRAIL

---

### 4. INSERT VALIDATION RULES - universal_invoice_engine_system.py:1171-1187
```python
# Guardar validaciones aplicadas
for rule in validation_rules:
    validation_id = f"uiv_{hashlib.md5(...).hexdigest()[:16]}"
    cursor.execute("""
        INSERT INTO universal_invoice_validations (
            id, session_id, validation_rules, rule_set_name, rule_category,
            rule_definition, validation_status, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING
    """, (validation_id, session_id,
          json.dumps({
              'rule_name': rule.rule_name,
              'rule_definition': rule.rule_definition,
              'rule_parameters': rule.rule_parameters,
              'priority': rule.priority
          }),
          rule.rule_name, rule.rule_category.value,
          json.dumps(rule.rule_definition), 'passed', datetime.utcnow()))
```
**Table**: `universal_invoice_validations`
**Operation**: INSERT (Stores validation rules applied)
**Database**: PostgreSQL
**Status**: ACTIVE - AUDIT TRAIL

---

### 5. SAVE CLASSIFICATION TO expense_invoices - universal_invoice_engine_system.py:1542-1552
```python
# This is the CRITICAL OPERATION that saves to the main invoice table
async def _save_classification_to_invoice(
    self, cursor, session_id: str, parsed_data: Dict[str, Any],
    accounting_classification: Dict[str, Any], company_id: str
):
    # 1. Extract UUID from parsed CFDI data
    uuid = parsed_data.get('uuid')
    
    # 2. Find expense_invoice by UUID
    cursor.execute("""
        SELECT id, tenant_id, accounting_classification
        FROM expense_invoices
        WHERE uuid = %s
        LIMIT 1
    """, (uuid,))
    
    invoice_row = cursor.fetchone()
    
    # 5. Update expense_invoices atomically with merged classification
    cursor.execute("""
        UPDATE expense_invoices
        SET
            accounting_classification = %s,
            session_id = %s
        WHERE id = %s
    """, (json.dumps(final_classification), session_id, invoice_id))
```
**Table**: `expense_invoices` (MAIN INVOICE TABLE)
**Operation**: UPDATE (Saves classification, links to session)
**Database**: PostgreSQL
**Status**: ACTIVE - SINGLE SOURCE OF TRUTH

---

### 6. INSERT INTO expense_invoices - unified_db_adapter.py:1022
```python
def register_expense_invoice(self, expense_id: int, filename: str, file_path: str,
                            content_type: str = "application/pdf", 
                            parsed_data: str = None,
                            tenant_id: int = 1, 
                            metadata: Optional[Dict[str, Any]] = None,
                            model_used: Optional[str] = None, 
                            processed_by: Optional[int] = None,
                            processing_source: Optional[str] = None) -> int:
    """Registra una factura asociada a un gasto"""
    with self.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO expense_invoices
            (expense_id, filename, file_path, content_type, parsed_data, tenant_id,
             processing_metadata, parser_used, processed_by, processing_source, processed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            expense_id, filename, file_path, content_type, parsed_data,
            tenant_id, json.dumps(metadata) if metadata else None,
            model_used, processed_by, processing_source,
        ))
        conn.commit()
        return cursor.lastrowid
```
**Table**: `expense_invoices`
**Operation**: INSERT (Adds new invoice record)
**Database**: PostgreSQL (via unified_db_adapter)
**Status**: ACTIVE - ALTERNATIVE PATH

---

### 7. UPDATE expense_invoices - unified_db_adapter.py:1583
```python
cursor.execute("""
    UPDATE expense_invoices
    SET
        <fields> = %s,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = %s
""", (values..., invoice_id))
```
**Table**: `expense_invoices`
**Operation**: UPDATE (General invoice updates)
**Database**: PostgreSQL
**Status**: ACTIVE - FLEXIBILITY

---

## SQLite Operations (LEGACY - TO BE DEPRECATED)

### 1. INSERT INTO invoice_attachments - invoice_manager.py:144-156
```python
def attach_invoice_file(self, ticket_id: int, file_content: bytes,
                       file_type: AttachmentType, 
                       original_filename: str = None) -> Optional[InvoiceAttachment]:
    # ... file saving code ...
    
    # Guardar en base de datos
    conn = sqlite3.connect(self.db_path)  # USES SQLITE!
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO invoice_attachments
        (ticket_id, file_type, file_path, file_size, uploaded_at, is_valid, validation_details)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (ticket_id, file_type.value, str(file_path), file_size,
          datetime.datetime.now().isoformat(),
          validation_result["is_valid"],
          json.dumps(validation_result, ensure_ascii=False)))
```
**Table**: `invoice_attachments`
**Database**: SQLite
**Status**: DEPRECATED - REMOVE THIS

---

### 2. UPDATE tickets TABLE - invoice_manager.py:84-97
```python
def update_invoice_status(self, ticket_id: int, status: InvoiceStatus,
                         failure_reason: Optional[str] = None,
                         metadata: Dict[str, Any] = None) -> bool:
    conn = sqlite3.connect(self.db_path)  # USES SQLITE!
    cursor = conn.cursor()
    
    current_time = datetime.datetime.now().isoformat()
    metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
    
    cursor.execute("""
        UPDATE tickets
        SET
            invoice_status = ?,
            invoice_failure_reason = ?,
            invoice_metadata = ?,
            invoice_last_check = ?
        WHERE id = ?
    """, (status.value, failure_reason, metadata_json, current_time, ticket_id))
    
    conn.commit()
    conn.close()
```
**Table**: `tickets`
**Database**: SQLite
**Status**: DEPRECATED - REMOVE THIS

---

### 3. INSERT INTO expense_invoices - internal_db.py:1712-1719
```python
def register_expense_invoice(self, expense_id: int, uuid: str, folio: str,
                            url: str, issued_at: str, status: str = "pendiente",
                            raw_xml: str = None, actor: Optional[int] = None) -> Optional[Dict]:
    now = datetime.utcnow().isoformat()
    
    with _DB_LOCK:
        with sqlite3.connect(_get_db_path()) as connection:  # USES SQLITE!
            connection.execute("PRAGMA foreign_keys = ON;")
            row = connection.execute(
                "SELECT company_id FROM expense_records WHERE id = ?",
                (expense_id,),
            ).fetchone()
            if not row:
                return None
            company_id = row[0] or "default"
            connection.execute(
                """
                INSERT INTO expense_invoices (
                    expense_id, company_id, uuid, folio, url, 
                    issued_at, status, raw_xml, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (expense_id, company_id, uuid, folio, url, 
                 issued_at, status, raw_xml, now, now),
            )
            connection.execute(
                """
                UPDATE expense_records
                   SET invoice_status = ?,
                       invoice_uuid = ?,
                       invoice_folio = ?,
                       invoice_url = ?,
                       will_have_cfdi = 1,
                       updated_at = ?
                 WHERE id = ?
                """,
                (status, uuid, folio, url, now, expense_id),
            )
            connection.commit()
```
**Tables**: `expense_invoices` (SQLite version), `expense_records`
**Database**: SQLite
**Status**: CRITICAL CONFLICT - SQLite and PostgreSQL using same table name!

---

## SUMMARY TABLE

| File | Method | Table | Operation | DB | Status |
|------|--------|-------|-----------|----|----|
| universal_invoice_engine_system.py | create_processing_session | sat_invoices | INSERT | PostgreSQL | ACTIVE |
| universal_invoice_engine_system.py | _save_processing_result | sat_invoices | UPDATE | PostgreSQL | ACTIVE |
| universal_invoice_engine_system.py | _save_processing_result | universal_invoice_templates | INSERT | PostgreSQL | ACTIVE |
| universal_invoice_engine_system.py | _save_processing_result | universal_invoice_validations | INSERT | PostgreSQL | ACTIVE |
| universal_invoice_engine_system.py | _save_classification_to_invoice | expense_invoices | UPDATE | PostgreSQL | ACTIVE |
| unified_db_adapter.py | register_expense_invoice | expense_invoices | INSERT | PostgreSQL | ACTIVE |
| unified_db_adapter.py | (generic) | expense_invoices | UPDATE | PostgreSQL | ACTIVE |
| invoice_manager.py | attach_invoice_file | invoice_attachments | INSERT | SQLite | DEPRECATED |
| invoice_manager.py | update_invoice_status | tickets | UPDATE | SQLite | DEPRECATED |
| internal_db.py | register_expense_invoice | expense_invoices | INSERT | SQLite | CONFLICT |
| internal_db.py | register_expense_invoice | expense_records | UPDATE | SQLite | CONFLICT |

---

## MIGRATION ACTION ITEMS

### IMMEDIATE (Fixes data conflicts)
1. **STOP using `internal_db.py:register_expense_invoice()`**
   - Replace with PostgreSQL version from `unified_db_adapter.py`
   - Update all callers to use unified_db_adapter instead

2. **DEPRECATE `invoice_manager.py`**
   - Remove all SQLite operations
   - Move file attachment handling to PostgreSQL
   - Update callers to use new system

### SHORT TERM (Clean up architecture)
3. **Migrate any remaining SQLite invoice data to PostgreSQL**
   - Write migration script for invoice_attachments → PostgreSQL
   - Write migration script for tickets → expense_invoices

4. **Add PostgreSQL constraints**
   - UUID uniqueness on expense_invoices
   - Foreign keys for referential integrity
   - NOT NULL constraints

### ONGOING (Quality)
5. **Testing**
   - Test all INSERT paths work with PostgreSQL
   - Test all UPDATE paths work with PostgreSQL
   - Load testing with 1000+ invoices

---

## DATABASE STATISTICS

PostgreSQL locations: 7 operations
SQLite locations: 4 operations
Status: 64% PostgreSQL, 36% SQLite (NEEDS MIGRATION)

