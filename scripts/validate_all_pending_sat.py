#!/usr/bin/env python3
"""
Script to validate all pending invoices against SAT
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import SessionLocal
from core.sat.sat_validation_service import SATValidationService
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def validate_all_pending(company_id: str, limit: int = 50):
    """Validate all pending SAT invoices for a company"""
    db = SessionLocal()
    try:
        # Get all sessions with pending SAT validation
        query = text("""
            SELECT id, parsed_data->>'uuid' as uuid
            FROM sat_invoices
            WHERE company_id = :company_id
            AND sat_validation_status = 'pending'
            ORDER BY created_at DESC
            LIMIT :limit
        """)

        result = db.execute(query, {"company_id": company_id, "limit": limit})
        sessions = result.fetchall()

        if not sessions:
            logger.info(f"No pending SAT validations found for company {company_id}")
            return

        logger.info(f"Found {len(sessions)} invoices pending SAT validation")

        # Initialize SAT validation service
        sat_service = SATValidationService(db, use_mock=False)

        validated_count = 0
        failed_count = 0

        for session_id, uuid in sessions:
            try:
                logger.info(f"Validating session {session_id} with UUID {uuid}")

                # Validate against SAT using validate_invoice_session method
                success, validation_info, error_message = sat_service.validate_invoice_session(
                    session_id=session_id,
                    force_refresh=True
                )

                if success and validation_info:
                    validated_count += 1
                    status = validation_info.get('status', 'vigente')
                    logger.info(f"  ✅ UUID {uuid}: {status}")
                else:
                    failed_count += 1
                    logger.warning(f"  ❌ UUID {uuid}: {error_message or 'Validation failed'}")

            except Exception as e:
                failed_count += 1
                logger.error(f"  ❌ Error validating UUID {uuid}: {e}")
                continue

        logger.info(f"\n=== Summary ===")
        logger.info(f"Total processed: {len(sessions)}")
        logger.info(f"Successfully validated: {validated_count}")
        logger.info(f"Failed: {failed_count}")

    except Exception as e:
        logger.error(f"Error in batch validation: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Validate all pending SAT invoices")
    parser.add_argument("--company-id", required=True, help="Company ID")
    parser.add_argument("--limit", type=int, default=50, help="Max number of invoices to validate")

    args = parser.parse_args()

    validate_all_pending(args.company_id, args.limit)
