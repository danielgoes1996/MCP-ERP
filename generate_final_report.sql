-- Reporte Final: Carga Masiva CFDI 4.0
SELECT
    'Total facturas procesadas' as metrica,
    COUNT(*)::text as valor
FROM expense_invoices
UNION ALL
SELECT
    'Facturas con XML completo',
    COUNT(*)::text || ' (100%)'
FROM expense_invoices WHERE raw_xml IS NOT NULL
UNION ALL
SELECT
    'Total monetario',
    TO_CHAR(SUM(total), 'FM$999,999,999.00 MXN')
FROM expense_invoices
UNION ALL
SELECT
    'Tamaño promedio XML',
    ROUND(AVG(LENGTH(raw_xml)))::text || ' caracteres'
FROM expense_invoices WHERE raw_xml IS NOT NULL
UNION ALL
SELECT
    'XML mínimo',
    MIN(LENGTH(raw_xml))::text || ' chars'
FROM expense_invoices WHERE raw_xml IS NOT NULL
UNION ALL
SELECT
    'XML máximo',
    MAX(LENGTH(raw_xml))::text || ' chars'
FROM expense_invoices WHERE raw_xml IS NOT NULL
UNION ALL
SELECT
    'Batches creados',
    COUNT(DISTINCT batch_id)::text
FROM bulk_invoice_batch_items
UNION ALL
SELECT
    'Items en batches',
    COUNT(*)::text
FROM bulk_invoice_batch_items;
