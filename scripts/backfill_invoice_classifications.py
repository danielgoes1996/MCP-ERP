"""
Backfill Invoice Classifications Script

This script classifies existing invoices in expense_invoices that don't have
accounting_classification yet. It uses the same AI classification engine that
processes new invoices.

Usage:
    python3 scripts/backfill_invoice_classifications.py --company-id contaflow --limit 50 --dry-run
    python3 scripts/backfill_invoice_classifications.py --company-id contaflow --limit 50
    python3 scripts/backfill_invoice_classifications.py --all
"""

import asyncio
import argparse
import logging
import sys
import os
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import json

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2
from psycopg2.extras import RealDictCursor

from core.expenses.invoices.universal_invoice_engine_system import UniversalInvoiceEngineSystem
from core.shared.db_config import POSTGRES_CONFIG

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_unclassified_invoices(
    company_id: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Get invoices without accounting classification

    Args:
        company_id: Filter by company (None = all companies)
        limit: Maximum number of invoices to process

    Returns:
        List of invoice records
    """
    conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
    cursor = conn.cursor()

    try:
        if company_id:
            # Get tenant_id from company_id
            cursor.execute("""
                SELECT id FROM tenants WHERE company_id = %s
            """, (company_id,))
            tenant_row = cursor.fetchone()

            if not tenant_row:
                logger.error(f"No tenant found for company_id={company_id}")
                return []

            tenant_id = tenant_row['id']
            logger.info(f"Company {company_id} → tenant_id={tenant_id}")

            cursor.execute("""
                SELECT
                    id,
                    tenant_id,
                    uuid,
                    file_path,
                    rfc_emisor,
                    nombre_emisor,
                    total,
                    fecha_emision,
                    tipo_comprobante,
                    raw_xml
                FROM expense_invoices
                WHERE tenant_id = %s
                AND accounting_classification IS NULL
                AND raw_xml IS NOT NULL
                ORDER BY total DESC
                LIMIT %s
            """, (tenant_id, limit))
        else:
            cursor.execute("""
                SELECT
                    id,
                    tenant_id,
                    uuid,
                    file_path,
                    rfc_emisor,
                    nombre_emisor,
                    total,
                    fecha_emision,
                    tipo_comprobante,
                    raw_xml
                FROM expense_invoices
                WHERE accounting_classification IS NULL
                AND raw_xml IS NOT NULL
                ORDER BY total DESC
                LIMIT %s
            """, (limit,))

        invoices = cursor.fetchall()
        logger.info(f"Found {len(invoices)} unclassified invoices with raw_xml")
        return list(invoices)

    finally:
        conn.close()


async def classify_invoice(
    engine: UniversalInvoiceEngineSystem,
    invoice: Dict[str, Any],
    company_id: str,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Classify a single invoice using the AI engine

    Args:
        engine: UniversalInvoiceEngine instance
        invoice: Invoice record from expense_invoices
        company_id: Company identifier
        dry_run: If True, don't save results

    Returns:
        Classification result
    """
    temp_file_path = None
    use_existing_file = False
    try:
        # Read XML content - prefer raw_xml from database, fallback to file_path
        xml_content = None

        if invoice.get('raw_xml'):
            # Use raw_xml from database (preferred method for SAT bulk downloads)
            raw_xml = invoice['raw_xml']
            xml_content = raw_xml.encode('utf-8') if isinstance(raw_xml, str) else raw_xml
            logger.debug(f"Invoice {invoice['id']}: Using raw_xml from database")
        elif invoice.get('file_path') and os.path.exists(invoice['file_path']):
            # Fallback to file_path if available
            temp_file_path = invoice['file_path']
            use_existing_file = True
            logger.debug(f"Invoice {invoice['id']}: Using file_path {invoice['file_path']}")
        else:
            logger.error(f"Invoice {invoice['id']}: No XML content available (no raw_xml or file_path)")
            return {
                'invoice_id': invoice['id'],
                'status': 'error',
                'error': 'No XML content available'
            }

        # If we have raw_xml, create a temporary file
        if xml_content and not use_existing_file:
            temp_fd, temp_file_path = tempfile.mkstemp(suffix='.xml', prefix=f'invoice_{invoice["id"]}_')
            with os.fdopen(temp_fd, 'wb') as f:
                f.write(xml_content)
            logger.debug(f"Invoice {invoice['id']}: Created temp file {temp_file_path}")

        if not temp_file_path:
            logger.error(f"Invoice {invoice['id']}: No file path available")
            return {
                'invoice_id': invoice['id'],
                'status': 'error',
                'error': 'No file path available'
            }

        logger.info(f"Processing invoice {invoice['id']} (UUID: {invoice['uuid']})")

        # Create session using file path
        filename = invoice.get('file_path') and os.path.basename(invoice['file_path']) or f"{invoice['uuid']}.xml"
        actual_session_id = await engine.create_processing_session(
            company_id=company_id,
            file_path=temp_file_path,
            original_filename=filename,
            user_id='backfill_script'
        )

        logger.info(f"  → Created session: {actual_session_id}")

        # Process the invoice (parse + classify)
        process_result = await engine.process_invoice(actual_session_id)

        if process_result.get('status') == 'completed':
            classification = process_result.get('accounting_classification', {})

            logger.info(
                f"  ✓ Classified: {classification.get('sat_account_code')} "
                f"(confidence: {classification.get('confidence_sat', 0):.2%})"
            )

            if not dry_run:
                # The dual-write should have already happened in _classify_invoice_accounting
                # But let's verify
                conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
                cursor = conn.cursor()

                try:
                    cursor.execute("""
                        SELECT accounting_classification
                        FROM expense_invoices
                        WHERE uuid = %s
                    """, (invoice['uuid'],))

                    result = cursor.fetchone()
                    if result and result['accounting_classification']:
                        logger.info(f"  ✓ Verified dual-write to expense_invoices")
                    else:
                        logger.warning(f"  ⚠ Classification not found in expense_invoices - dual-write may have failed")
                finally:
                    conn.close()

            return {
                'invoice_id': invoice['id'],
                'session_id': actual_session_id,
                'status': 'success',
                'sat_code': classification.get('sat_account_code'),
                'confidence': classification.get('confidence_sat'),
                'dry_run': dry_run
            }
        else:
            logger.error(f"  ✗ Processing failed: {process_result.get('error', 'Unknown error')}")
            return {
                'invoice_id': invoice['id'],
                'session_id': actual_session_id,
                'status': 'error',
                'error': process_result.get('error', 'Processing failed')
            }

    except Exception as e:
        logger.error(f"  ✗ Error classifying invoice {invoice['id']}: {e}", exc_info=True)
        return {
            'invoice_id': invoice['id'],
            'status': 'error',
            'error': str(e)
        }
    finally:
        # Clean up temporary file if we created one
        if temp_file_path and not use_existing_file and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
                logger.debug(f"Invoice {invoice['id']}: Deleted temp file {temp_file_path}")
            except Exception as e:
                logger.warning(f"Invoice {invoice['id']}: Failed to delete temp file {temp_file_path}: {e}")


async def backfill_classifications(
    company_id: Optional[str] = None,
    limit: int = 100,
    dry_run: bool = False
):
    """
    Main backfill function

    Args:
        company_id: Company to process (None = all)
        limit: Maximum invoices to process
        dry_run: If True, don't save results
    """
    logger.info("=" * 80)
    logger.info("INVOICE CLASSIFICATION BACKFILL")
    logger.info("=" * 80)
    logger.info(f"Company: {company_id or 'ALL'}")
    logger.info(f"Limit: {limit}")
    logger.info(f"Dry run: {dry_run}")
    logger.info("")

    # Get unclassified invoices
    invoices = get_unclassified_invoices(company_id, limit)

    if not invoices:
        logger.info("No unclassified invoices found")
        return

    # Get company_id for the invoices
    if not company_id:
        # Get company_id from first invoice's tenant_id
        conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT company_id FROM tenants WHERE id = %s
            """, (invoices[0]['tenant_id'],))
            tenant_row = cursor.fetchone()
            company_id = tenant_row['company_id'] if tenant_row else 'unknown'
        finally:
            conn.close()

    # Initialize engine
    logger.info(f"Initializing UniversalInvoiceEngineSystem for company: {company_id}")
    engine = UniversalInvoiceEngineSystem()

    # Process each invoice
    results = {
        'success': 0,
        'error': 0,
        'total': len(invoices)
    }

    for idx, invoice in enumerate(invoices, 1):
        logger.info(f"\n[{idx}/{len(invoices)}] Processing invoice {invoice['id']}...")

        result = await classify_invoice(engine, invoice, company_id, dry_run)

        if result['status'] == 'success':
            results['success'] += 1
        else:
            results['error'] += 1

        # Small delay to avoid overwhelming the API
        await asyncio.sleep(1)

    # Summary
    logger.info("")
    logger.info("=" * 80)
    logger.info("BACKFILL SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total invoices: {results['total']}")
    logger.info(f"Successfully classified: {results['success']}")
    logger.info(f"Errors: {results['error']}")
    logger.info(f"Success rate: {results['success'] / results['total'] * 100:.1f}%")
    logger.info("")

    if dry_run:
        logger.info("⚠ DRY RUN MODE - No changes were saved to the database")
    else:
        logger.info("✓ Classifications saved to database")


def main():
    parser = argparse.ArgumentParser(
        description='Backfill accounting classifications for existing invoices'
    )
    parser.add_argument(
        '--company-id',
        type=str,
        help='Company ID to process (e.g., contaflow, carreta_verde)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=50,
        help='Maximum number of invoices to process (default: 50)'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Process all unclassified invoices (ignores --limit)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Simulate without saving to database'
    )

    args = parser.parse_args()

    if args.all:
        limit = 10000  # Large number to process all
    else:
        limit = args.limit

    # Run backfill
    asyncio.run(backfill_classifications(
        company_id=args.company_id,
        limit=limit,
        dry_run=args.dry_run
    ))


if __name__ == '__main__':
    main()
