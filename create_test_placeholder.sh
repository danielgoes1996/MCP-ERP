#!/bin/bash

echo "Creating test placeholder in data/mcp_internal.db..."

sqlite3 data/mcp_internal.db << SQL
INSERT INTO expense_records (
    description,
    amount,
    currency,
    expense_date,
    category,
    provider_name,
    provider_rfc,
    workflow_status,
    invoice_status,
    payment_account_id,
    will_have_cfdi,
    bank_status,
    metadata,
    created_at,
    updated_at,
    company_id
) VALUES (
    'Test Placeholder - UI Integration',
    999.99,
    'MXN',
    '2025-01-15',
    NULL,
    'ACME SA de CV',
    NULL,
    'requiere_completar',
    'pendiente',
    NULL,
    1,
    'pendiente',
    '{"missing_fields": ["category", "payment_account_id"], "source": "test"}',
    datetime('now'),
    datetime('now'),
    'default'
);

SELECT 'Placeholder created with ID: ' || last_insert_rowid();

SELECT 'Total placeholders now:';
SELECT COUNT(*) FROM expense_records WHERE workflow_status = 'requiere_completar';
SQL

echo ""
echo "✅ Test placeholder created successfully!"
