#!/bin/bash
#
# Full Backfill Script for ContaFlow Invoices
# Runs multiple batches until all are classified
#

COMPANY_ID="contaflow"
BATCH_SIZE=100
NUM_BATCHES=10

echo "========================================"
echo "CONTAFLOW FULL BACKFILL"
echo "========================================"
echo "Company: $COMPANY_ID"
echo "Batch size: $BATCH_SIZE"
echo "Number of batches: $NUM_BATCHES"
echo ""

for i in $(seq 1 $NUM_BATCHES); do
    echo "========================================"
    echo "BATCH $i/$NUM_BATCHES"
    echo "========================================"
    echo "Starting batch $i at $(date)"

    python3 scripts/backfill_invoice_classifications.py \
        --company-id "$COMPANY_ID" \
        --limit "$BATCH_SIZE" \
        2>&1 | tee -a "/tmp/backfill_batch${i}.log"

    exit_code=$?

    if [ $exit_code -eq 0 ]; then
        echo "✓ Batch $i completed successfully"
    else
        echo "✗ Batch $i failed with exit code $exit_code"
    fi

    # Check if there are more invoices to process
    remaining=$(docker exec mcp-postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c \
        "SELECT COUNT(*) FROM expense_invoices WHERE tenant_id = 2 AND accounting_classification IS NULL AND raw_xml IS NOT NULL;")

    echo "Remaining unclassified invoices: $remaining"

    if [ "$remaining" -le 0 ]; then
        echo "✓ All invoices have been classified!"
        break
    fi

    echo ""
    echo "Waiting 5 seconds before next batch..."
    sleep 5
done

echo ""
echo "========================================"
echo "BACKFILL COMPLETE"
echo "========================================"
echo "Completed at $(date)"

# Final statistics
echo ""
echo "FINAL STATISTICS:"
docker exec mcp-postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
    "SELECT
        COUNT(*) as total_invoices,
        COUNT(accounting_classification) as classified,
        COUNT(*) - COUNT(accounting_classification) as unclassified,
        ROUND(100.0 * COUNT(accounting_classification) / COUNT(*), 2) as classification_rate
     FROM expense_invoices
     WHERE tenant_id = 2 AND raw_xml IS NOT NULL;"
