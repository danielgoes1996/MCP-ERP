#!/usr/bin/env python3
"""
Process uploaded XML files that are in the uploads folder but not yet in the database.
This script creates sessions and triggers processing for each file.
"""

import sys
import os
import asyncio
import glob
from datetime import datetime

# Add project root to path
sys.path.insert(0, '/Users/danielgoes96/Desktop/mcp-server')

from core.expenses.invoices.universal_invoice_engine_system import universal_invoice_engine_system
from core.shared.db_config import get_connection
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def process_xml_file(file_path: str, company_id: str, user_id: str):
    """
    Process a single XML file:
    1. Create session
    2. Process invoice (extract data)
    3. Classify
    4. SAT validate
    """
    original_filename = os.path.basename(file_path)

    try:
        # Create processing session
        logger.info(f"Creating session for: {original_filename}")
        session_id = await universal_invoice_engine_system.create_processing_session(
            company_id=company_id,
            file_path=file_path,
            original_filename=original_filename,
            user_id=user_id
        )

        logger.info(f"  ✓ Session created: {session_id}")

        # Process invoice (extract data from XML)
        logger.info(f"  → Processing invoice...")
        result = await universal_invoice_engine_system.process_invoice(session_id)

        if result.get('status') == 'completed':
            logger.info(f"  ✓ Invoice processed successfully")

            # Auto-trigger classification
            parsed_data = result.get('parsed_data')
            if parsed_data:
                logger.info(f"  → Classifying invoice...")
                await trigger_classification(session_id, company_id, parsed_data)
                logger.info(f"  ✓ Classification completed")

                # Auto-trigger SAT validation
                logger.info(f"  → SAT validation...")
                await trigger_sat_validation(session_id, result)
                logger.info(f"  ✓ SAT validation completed")
        else:
            logger.warning(f"  ✗ Invoice processing failed: {result.get('error')}")

        return session_id, result.get('status')

    except Exception as e:
        logger.error(f"  ✗ Error processing {original_filename}: {e}")
        return None, 'failed'


async def trigger_classification(session_id: str, company_id: str, parsed_data: dict):
    """Trigger classification for the invoice"""
    from core.ai_pipeline.classification.classification_service import classify_invoice_session
    from core.shared.tenant_utils import get_tenant_and_company
    import json

    # Map company_id string to tenant_id
    tenant_id, _ = get_tenant_and_company(company_id)

    # Call classification service
    classification_dict = classify_invoice_session(
        session_id=session_id,
        company_id=tenant_id,
        parsed_data=parsed_data,
        top_k=10
    )

    if classification_dict:
        # Save to database
        conn = get_connection(dict_cursor=True)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE sat_invoices
            SET accounting_classification = %s,
                updated_at = now()
            WHERE id = %s
        """, (json.dumps(classification_dict), session_id))

        conn.commit()
        cursor.close()
        conn.close()


async def trigger_sat_validation(session_id: str, processing_result: dict):
    """Trigger SAT validation for the invoice"""
    from core.sat_validation.sat_validation_service import validate_invoice_session
    import json

    parsed_data = processing_result.get('parsed_data')
    if not parsed_data:
        return

    # Extract CFDI UUID
    uuid = parsed_data.get('uuid') or parsed_data.get('folio_fiscal')
    if not uuid:
        logger.warning(f"Session {session_id}: No UUID found, skipping SAT validation")
        return

    # Run SAT validation
    validation_result = await validate_invoice_session(session_id, uuid, parsed_data)

    if validation_result:
        # Save to database
        conn = get_connection(dict_cursor=True)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE sat_invoices
            SET sat_validation = %s,
                updated_at = now()
            WHERE id = %s
        """, (json.dumps(validation_result), session_id))

        conn.commit()
        cursor.close()
        conn.close()


async def main():
    """Main function to process all uploaded XMLs for a company"""
    company_id = 'carreta_verde'
    user_id = None  # Will get from database

    # Get user_id for daniel@carretaverde.com
    conn = get_connection(dict_cursor=True)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id FROM users WHERE email = 'daniel@carretaverde.com'
    """)
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if user:
        user_id = str(user['id'])
        logger.info(f"Found user: daniel@carretaverde.com (ID: {user_id})")
    else:
        logger.error("User daniel@carretaverde.com not found")
        return

    # Find all XML files uploaded at 2025-11-14 17:13 (23:13 in logs)
    upload_dir = f'/Users/danielgoes96/Desktop/mcp-server/uploads/invoices/{company_id}'
    xml_files = glob.glob(f'{upload_dir}/20251114_231355_*.xml')

    # Remove duplicates by keeping only unique filenames
    unique_files = {}
    for xml_file in xml_files:
        basename = os.path.basename(xml_file)
        if basename not in unique_files:
            unique_files[basename] = xml_file

    xml_files = list(unique_files.values())

    logger.info(f"\nFound {len(xml_files)} XML files to process:\n")

    if not xml_files:
        logger.warning("No XML files found matching pattern 20251114_231355_*.xml")
        logger.info(f"Checking directory: {upload_dir}")
        all_files = glob.glob(f'{upload_dir}/*.xml')
        logger.info(f"Total XML files in directory: {len(all_files)}")
        if all_files:
            logger.info("Latest 10 XML files:")
            for f in sorted(all_files, key=os.path.getmtime, reverse=True)[:10]:
                mtime = datetime.fromtimestamp(os.path.getmtime(f))
                logger.info(f"  - {os.path.basename(f)} (modified: {mtime})")
        return

    # Process each file
    results = []
    for xml_file in xml_files:
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing: {os.path.basename(xml_file)}")
        logger.info(f"{'='*60}")

        session_id, status = await process_xml_file(xml_file, company_id, user_id)
        results.append({
            'file': os.path.basename(xml_file),
            'session_id': session_id,
            'status': status
        })

        # Small delay between files to avoid rate limits
        await asyncio.sleep(2)

    # Summary
    logger.info(f"\n\n{'='*60}")
    logger.info("PROCESSING SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"Total files: {len(results)}")
    logger.info(f"Completed: {sum(1 for r in results if r['status'] == 'completed')}")
    logger.info(f"Failed: {sum(1 for r in results if r['status'] == 'failed')}")
    logger.info(f"\nDetails:")
    for r in results:
        status_icon = '✓' if r['status'] == 'completed' else '✗'
        logger.info(f"  {status_icon} {r['file']} → {r['session_id']} ({r['status']})")


if __name__ == "__main__":
    asyncio.run(main())
