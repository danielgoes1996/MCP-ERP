# Audit Trail - Implementación Completa

## Objetivo
Que un auditor en 2 años pueda reconstruir completamente:
1. Quién creó el gasto
2. Cuándo y cómo se concilió
3. Score de confianza IA (si aplica)
4. Acción manual vs automática
5. Factura adjunta

## Tablas Nuevas Propuestas

### 1. expense_audit_log
```sql
CREATE TABLE expense_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Referencia
    expense_id INTEGER NOT NULL,
    action_type TEXT NOT NULL,  -- 'created', 'updated', 'reconciled', 'deleted'

    -- Usuario
    user_id INTEGER,
    user_name TEXT,
    user_role TEXT,  -- 'employee', 'accountant', 'admin'

    -- Cambios
    field_changed TEXT,
    old_value TEXT,
    new_value TEXT,

    -- Metadata
    action_source TEXT,  -- 'manual', 'ai_suggestion', 'voice_input', 'api'
    ip_address TEXT,
    user_agent TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (expense_id) REFERENCES expense_records(id) ON DELETE CASCADE
);

CREATE INDEX idx_expense_audit_expense ON expense_audit_log(expense_id);
CREATE INDEX idx_expense_audit_timestamp ON expense_audit_log(timestamp DESC);
CREATE INDEX idx_expense_audit_user ON expense_audit_log(user_id);
```

**Ejemplo de registro**:
```sql
-- Cuando se crea un gasto
INSERT INTO expense_audit_log VALUES (
    1, 123, 'created', 5, 'Juan Pérez', 'employee',
    NULL, NULL, NULL, 'voice_input', '192.168.1.10',
    'Mozilla/5.0...', '2025-01-15 10:30:00'
);

-- Cuando se concilia con IA
INSERT INTO expense_audit_log VALUES (
    2, 123, 'reconciled', 8, 'María García', 'accountant',
    'bank_status', 'pending', 'reconciled', 'ai_suggestion',
    '192.168.1.15', 'Mozilla/5.0...', '2025-01-17 14:20:00'
);
```

### 2. reconciliation_evidence
```sql
CREATE TABLE reconciliation_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Referencia
    expense_id INTEGER,
    movement_id INTEGER,
    split_group_id TEXT,

    -- Score IA (si aplica)
    ai_confidence_score REAL,
    ai_algorithm_version TEXT,  -- 'greedy_v1.0'
    ai_breakdown JSON,  -- {"amount_score": 47.5, "date_score": 27, "text_score": 18}

    -- Acción
    reconciliation_method TEXT,  -- 'ai_auto', 'ai_manual_review', 'manual'
    user_id INTEGER,
    user_action TEXT,  -- 'applied_suggestion', 'manual_match', 'edited_amounts'

    -- Factura
    invoice_uuid TEXT,  -- CFDI UUID
    invoice_pdf_path TEXT,
    invoice_xml_path TEXT,

    -- Evidencia adicional
    notes TEXT,
    attachments JSON,  -- ["receipt.jpg", "approval_email.pdf"]

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (expense_id) REFERENCES expense_records(id),
    FOREIGN KEY (movement_id) REFERENCES bank_movements(id)
);

CREATE INDEX idx_evidence_expense ON reconciliation_evidence(expense_id);
CREATE INDEX idx_evidence_movement ON reconciliation_evidence(movement_id);
CREATE INDEX idx_evidence_split_group ON reconciliation_evidence(split_group_id);
```

**Ejemplo de registro**:
```sql
-- Conciliación automática con IA alta confianza
INSERT INTO reconciliation_evidence VALUES (
    1, 123, 8181, 'split_one_to_many_20250117_142000',
    92.5, 'greedy_v1.0',
    '{"amount_score": 47.5, "date_score": 27, "text_score": 18}',
    'ai_auto', 8, 'applied_suggestion',
    'A1B2C3D4-1234-5678-90AB-CDEF12345678',
    '/uploads/invoices/123_factura.pdf',
    '/uploads/invoices/123_factura.xml',
    'Aplicada automáticamente - confianza alta',
    '["ticket_gasolina.jpg"]',
    '2025-01-17 14:20:00'
);

-- Conciliación manual sin IA
INSERT INTO reconciliation_evidence VALUES (
    2, 456, 9191, NULL,
    NULL, NULL, NULL,
    'manual', 8, 'manual_match',
    NULL, NULL, NULL,
    'Conciliación manual - gasto sin descripción clara',
    NULL,
    '2025-01-18 09:15:00'
);
```

### 3. ai_suggestion_history
```sql
CREATE TABLE ai_suggestion_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Identificador
    suggestion_id TEXT UNIQUE NOT NULL,

    -- Tipo
    suggestion_type TEXT,  -- 'one_to_many', 'many_to_one'

    -- IDs relacionados
    movement_ids TEXT,  -- JSON: [8181, 8182]
    expense_ids TEXT,   -- JSON: [123, 124, 125]

    -- Scoring detallado
    confidence_score REAL,
    amount_score REAL,
    amount_diff REAL,
    date_score REAL,
    date_diff_avg REAL,
    text_score REAL,
    text_similarity REAL,

    -- Metadata algoritmo
    algorithm_version TEXT,
    execution_time_ms INTEGER,

    -- Resultado
    status TEXT,  -- 'pending', 'applied', 'rejected', 'edited'
    applied_by INTEGER,
    applied_at TIMESTAMP,
    rejection_reason TEXT,

    -- Feedback
    user_rating TEXT,  -- 'helpful', 'incorrect', 'partially_correct'
    user_feedback TEXT,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (applied_by) REFERENCES users(id)
);

CREATE INDEX idx_suggestion_status ON ai_suggestion_history(status);
CREATE INDEX idx_suggestion_applied_at ON ai_suggestion_history(applied_at DESC);
```

## Modificaciones a Servicios

### employee_advances_service.py
```python
def reimburse_advance(self, request: ReimburseAdvanceRequest, user_id: int = None):
    # ... código existente ...

    # AGREGAR: Registrar en audit log
    cursor.execute("""
        INSERT INTO expense_audit_log (
            expense_id, action_type, user_id, field_changed,
            old_value, new_value, action_source
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        advance.expense_id, 'reimbursed', user_id,
        'reimbursed_amount',
        str(advance.reimbursed_amount),
        str(new_reimbursed),
        'manual'
    ))

    # AGREGAR: Guardar evidencia de reembolso
    cursor.execute("""
        INSERT INTO reconciliation_evidence (
            expense_id, movement_id, reconciliation_method,
            user_id, user_action, notes
        ) VALUES (?, ?, ?, ?, ?, ?)
    """, (
        advance.expense_id,
        request.reimbursement_movement_id,
        'manual_reimbursement',
        user_id,
        f'Reembolso ${request.reimbursement_amount} via {request.reimbursement_type}',
        request.notes
    ))
```

### ai_reconciliation_service.py
```python
def suggest_one_to_many_splits(self, limit: int = 10):
    # ... código existente que genera sugerencias ...

    # AGREGAR: Guardar cada sugerencia en historial
    for suggestion in suggestions:
        suggestion_id = f"ai_suggest_{uuid.uuid4()}"

        cursor.execute("""
            INSERT INTO ai_suggestion_history (
                suggestion_id, suggestion_type,
                movement_ids, expense_ids,
                confidence_score, amount_score, date_score, text_score,
                algorithm_version, execution_time_ms, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            suggestion_id, 'one_to_many',
            json.dumps([suggestion['movement']['id']]),
            json.dumps([e['id'] for e in suggestion['expenses']]),
            suggestion['confidence_score'],
            suggestion['breakdown']['amount_score'],
            suggestion['breakdown']['date_score'],
            suggestion['breakdown']['description_score'],
            'greedy_v1.0', elapsed_ms, 'pending'
        ))

        suggestion['suggestion_id'] = suggestion_id

    return suggestions
```

### ai_reconciliation_api.py
```python
@router.post("/auto-apply/{suggestion_id}")
async def auto_apply_suggestion(suggestion_id: str, user_id: int = Depends(get_current_user)):
    # ... aplicar conciliación ...

    # AGREGAR: Actualizar historial de sugerencia
    cursor.execute("""
        UPDATE ai_suggestion_history
        SET status = 'applied',
            applied_by = ?,
            applied_at = CURRENT_TIMESTAMP
        WHERE suggestion_id = ?
    """, (user_id, suggestion_id))

    # AGREGAR: Registrar evidencia con score IA
    cursor.execute("""
        INSERT INTO reconciliation_evidence (
            expense_id, movement_id, split_group_id,
            ai_confidence_score, ai_algorithm_version, ai_breakdown,
            reconciliation_method, user_id, user_action
        ) SELECT
            ?, ?, ?,
            confidence_score, algorithm_version,
            json_object('amount', amount_score, 'date', date_score, 'text', text_score),
            'ai_auto', ?, 'applied_suggestion'
        FROM ai_suggestion_history
        WHERE suggestion_id = ?
    """, (expense_id, movement_id, split_group_id, user_id, suggestion_id))
```

## Endpoint de Auditoría

```python
# api/audit_api.py
@router.get("/audit/expense/{expense_id}")
async def get_expense_audit_trail(expense_id: int):
    """
    Retorna historial completo de un gasto para auditoría
    """
    return {
        "expense": {
            "id": 123,
            "amount": 850.50,
            "description": "Gasolina Pemex",
            "created_at": "2025-01-15 10:30:00"
        },

        "audit_log": [
            {
                "timestamp": "2025-01-15 10:30:00",
                "action": "created",
                "user": "Juan Pérez (employee)",
                "source": "voice_input",
                "details": "Gasto creado por voz desde móvil"
            },
            {
                "timestamp": "2025-01-16 11:45:00",
                "action": "updated",
                "user": "Juan Pérez (employee)",
                "source": "manual",
                "changes": {"category": "sin categoría → combustible"}
            },
            {
                "timestamp": "2025-01-17 14:20:00",
                "action": "reconciled",
                "user": "María García (accountant)",
                "source": "ai_suggestion",
                "details": "Aplicada sugerencia IA con 92% confianza"
            }
        ],

        "reconciliation_evidence": {
            "method": "ai_auto",
            "confidence_score": 92.5,
            "breakdown": {
                "amount_score": 47.5,
                "date_score": 27,
                "text_score": 18
            },
            "movement": {
                "id": 8181,
                "amount": -850.50,
                "description": "GASOLINERA PEMEX INSURGENTES",
                "date": "2025-01-17"
            },
            "invoice": {
                "uuid": "A1B2C3D4-1234-5678-90AB-CDEF12345678",
                "pdf": "/uploads/invoices/123_factura.pdf",
                "xml": "/uploads/invoices/123_factura.xml"
            },
            "attachments": ["ticket_gasolina.jpg"]
        },

        "current_status": {
            "bank_status": "reconciled",
            "is_employee_advance": false,
            "invoice_status": "completed"
        }
    }
```

## Dashboard de Auditoría

```html
<!-- audit-dashboard.html -->
<div class="audit-filters">
    <input type="date" name="date_from">
    <input type="date" name="date_to">
    <select name="action_type">
        <option value="">Todas las acciones</option>
        <option value="created">Creados</option>
        <option value="reconciled">Conciliados</option>
        <option value="deleted">Eliminados</option>
    </select>
    <select name="source">
        <option value="">Todos los orígenes</option>
        <option value="ai_suggestion">IA Automático</option>
        <option value="manual">Manual</option>
        <option value="voice_input">Voz</option>
    </select>
</div>

<table class="audit-table">
    <tr>
        <td>2025-01-17 14:20</td>
        <td>Gasto #123</td>
        <td>Conciliado</td>
        <td>María García</td>
        <td><span class="badge-ai">IA 92%</span></td>
        <td><button onclick="viewDetails(123)">Ver</button></td>
    </tr>
</table>
```

## Exportación para Auditoría Externa

```python
@router.get("/audit/export")
async def export_audit_trail(
    date_from: str,
    date_to: str,
    format: str = "xlsx"
):
    """
    Exporta audit trail a Excel/PDF para auditor externo
    """
    data = db.execute("""
        SELECT
            e.id as expense_id,
            e.amount,
            e.description,
            e.date as expense_date,
            al.timestamp,
            al.action_type,
            al.user_name,
            al.action_source,
            re.ai_confidence_score,
            re.invoice_uuid
        FROM expense_audit_log al
        JOIN expense_records e ON al.expense_id = e.id
        LEFT JOIN reconciliation_evidence re ON e.id = re.expense_id
        WHERE al.timestamp BETWEEN ? AND ?
        ORDER BY al.timestamp DESC
    """, (date_from, date_to))

    # Generar Excel
    df = pd.DataFrame(data)
    df.to_excel(f"audit_trail_{date_from}_{date_to}.xlsx")
```

## Retención de Datos

```python
# Según normativa SAT México: 5 años
RETENTION_PERIOD_DAYS = 365 * 5

@router.post("/audit/archive")
async def archive_old_records():
    """
    Archivar registros antiguos (no eliminar)
    """
    cutoff_date = datetime.now() - timedelta(days=RETENTION_PERIOD_DAYS)

    cursor.execute("""
        UPDATE expense_audit_log
        SET archived = TRUE
        WHERE timestamp < ?
    """, (cutoff_date,))
```
