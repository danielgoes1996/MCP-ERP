#!/usr/bin/env python3
"""
Backfill SAT Validation for Payment Complements (Tipo P)
=========================================================

This script validates existing payment complements (tipo P) against SAT.

The regular SAT validation service looks for data in `extracted_data`, but
payment complements store their data in `parsed_data`. This script handles
both cases.

Usage:
    python3 scripts/backfill_payment_complement_sat_validation.py --company-id contaflow --limit 10 [--dry-run] [--use-mock]

Arguments:
    --company-id: Company ID to process (required)
    --limit: Maximum number of payment complements to validate (default: 10)
    --dry-run: Show what would be validated without actually calling SAT
    --use-mock: Use mock SAT responses for testing
"""

import argparse
import logging
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from psycopg2.extras import RealDictCursor, Json
from core.sat.sat_cfdi_verifier import SATCFDIVerifier, format_cfdi_verification_url

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def validate_payment_complement_sat(
    conn,
    session_id: str,
    parsed_data: dict,
    company_id: str,
    use_mock: bool = False,
    dry_run: bool = False
) -> tuple[bool, str]:
    """
    Validate a payment complement against SAT

    Args:
        conn: Database connection
        session_id: Session ID
        parsed_data: Parsed CFDI data
        company_id: Company ID
        use_mock: Use mock SAT responses
        dry_run: Don't actually call SAT or update database

    Returns:
        (success, status_message)
    """
    try:
        # Extract required fields from parsed_data
        uuid = parsed_data.get('uuid')
        rfc_emisor = parsed_data.get('rfc_emisor')
        rfc_receptor = parsed_data.get('rfc_receptor')
        total = parsed_data.get('total', 0.0)

        # Validate required fields
        if not uuid:
            return False, "❌ Missing UUID"
        if not rfc_emisor:
            return False, "❌ Missing RFC emisor"
        if not rfc_receptor:
            return False, "❌ Missing RFC receptor"

        # Convert total to float
        try:
            total = float(total)
        except (ValueError, TypeError):
            return False, f"❌ Invalid total: {total}"

        if dry_run:
            return True, f"✓ Would validate: UUID={uuid[:8]}... Emisor={rfc_emisor} Receptor={rfc_receptor} Total=${total:,.2f}"

        # Call SAT verification
        verifier = SATCFDIVerifier(use_mock=use_mock)
        logger.info(f"Verifying {session_id} against SAT: UUID={uuid}")

        success, status_info, error = verifier.check_cfdi_status(
            uuid=uuid,
            rfc_emisor=rfc_emisor,
            rfc_receptor=rfc_receptor,
            total=total
        )

        if not success:
            # Update session with error
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE sat_invoices
                SET sat_validation_status = 'error',
                    sat_verification_error = %s,
                    sat_last_check_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (error, session_id))
            conn.commit()
            cursor.close()

            return False, f"❌ SAT Error: {error}"

        # Generate verification URL
        verification_url = format_cfdi_verification_url(
            uuid=uuid,
            rfc_emisor=rfc_emisor,
            rfc_receptor=rfc_receptor,
            total=total
        )

        # Update parsed_data.sat_status
        parsed_data['sat_status'] = status_info['status']

        # Update session with SAT validation results
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE sat_invoices
            SET sat_validation_status = %s,
                sat_codigo_estatus = %s,
                sat_es_cancelable = %s,
                sat_estado = %s,
                sat_validacion_efos = %s,
                sat_verified_at = CURRENT_TIMESTAMP,
                sat_last_check_at = CURRENT_TIMESTAMP,
                sat_verification_error = NULL,
                sat_verification_url = %s,
                parsed_data = %s
            WHERE id = %s
        """, (
            status_info['status'],
            status_info.get('codigo_estatus'),
            status_info.get('es_cancelable'),
            status_info.get('estado'),
            status_info.get('validacion_efos'),
            verification_url,
            Json(parsed_data),
            session_id
        ))

        # Insert into verification history
        cursor.execute("""
            INSERT INTO sat_verification_history (
                session_id,
                company_id,
                uuid,
                rfc_emisor,
                rfc_receptor,
                total,
                status,
                codigo_estatus,
                es_cancelable,
                estado,
                validacion_efos,
                verification_url
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            session_id,
            company_id,
            uuid,
            rfc_emisor,
            rfc_receptor,
            total,
            status_info['status'],
            status_info.get('codigo_estatus'),
            status_info.get('es_cancelable'),
            status_info.get('estado'),
            status_info.get('validacion_efos'),
            verification_url
        ))

        conn.commit()
        cursor.close()

        sat_status = status_info['status']
        status_emoji = "✓" if sat_status == "vigente" else "✗" if sat_status == "cancelado" else "⚠"

        return True, f"{status_emoji} {sat_status.upper()}: UUID={uuid[:8]}... Total=${total:,.2f}"

    except Exception as e:
        logger.error(f"Error validating {session_id}: {e}")
        return False, f"❌ Exception: {str(e)}"


def main():
    parser = argparse.ArgumentParser(description='Backfill SAT validation for payment complements')
    parser.add_argument('--company-id', required=True, help='Company ID to process')
    parser.add_argument('--limit', type=int, default=10, help='Maximum number to validate (default: 10)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without doing it')
    parser.add_argument('--use-mock', action='store_true', help='Use mock SAT responses')

    args = parser.parse_args()

    # Connect to database
    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', '127.0.0.1'),
        port=int(os.getenv('POSTGRES_PORT', '5433')),
        database=os.getenv('POSTGRES_DB', 'mcp_system'),
        user=os.getenv('POSTGRES_USER', 'mcp_user'),
        password=os.getenv('POSTGRES_PASSWORD', 'changeme')
    )

    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Find payment complements without SAT validation
    cursor.execute("""
        SELECT id, parsed_data, company_id, created_at
        FROM sat_invoices
        WHERE company_id = %s
            AND parsed_data->>'tipo_comprobante' = 'P'
            AND (sat_validation_status IS NULL OR sat_validation_status = 'pending')
        ORDER BY created_at DESC
        LIMIT %s
    """, (args.company_id, args.limit))

    sessions = cursor.fetchall()

    print(f"\n{'='*80}")
    print(f"SAT Validation Backfill for Payment Complements (Tipo P)")
    print(f"{'='*80}")
    print(f"Company ID: {args.company_id}")
    print(f"Found: {len(sessions)} payment complements")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print(f"SAT Calls: {'MOCK' if args.use_mock else 'REAL'}")
    print(f"{'='*80}\n")

    if len(sessions) == 0:
        print("✓ No payment complements need SAT validation\n")
        cursor.close()
        conn.close()
        return

    # Validate each payment complement
    summary = {
        'total': len(sessions),
        'success': 0,
        'failed': 0,
        'vigente': 0,
        'cancelado': 0,
        'sustituido': 0,
        'error': 0
    }

    for i, session in enumerate(sessions, 1):
        session_id = session['id']
        parsed_data = session['parsed_data']
        company_id = session['company_id']
        created_at = session['created_at']

        print(f"[{i}/{len(sessions)}] {session_id} ({created_at.strftime('%Y-%m-%d')}):")

        success, message = validate_payment_complement_sat(
            conn,
            session_id,
            parsed_data,
            company_id,
            use_mock=args.use_mock,
            dry_run=args.dry_run
        )

        print(f"    {message}")

        if success:
            summary['success'] += 1
            # Extract status from message
            if 'vigente' in message.lower():
                summary['vigente'] += 1
            elif 'cancelado' in message.lower():
                summary['cancelado'] += 1
            elif 'sustituido' in message.lower():
                summary['sustituido'] += 1
        else:
            summary['failed'] += 1
            summary['error'] += 1

    # Print summary
    print(f"\n{'='*80}")
    print(f"Summary")
    print(f"{'='*80}")
    print(f"Total:     {summary['total']}")
    print(f"Success:   {summary['success']}")
    print(f"Failed:    {summary['failed']}")
    print(f"")
    print(f"Vigente:   {summary['vigente']}")
    print(f"Cancelado: {summary['cancelado']}")
    print(f"Sustituido: {summary['sustituido']}")
    print(f"Error:     {summary['error']}")
    print(f"{'='*80}\n")

    cursor.close()
    conn.close()


if __name__ == '__main__':
    main()
