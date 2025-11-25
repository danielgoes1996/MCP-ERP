"""
SAT Validation Service
======================
Service layer for validating CFDI invoices against SAT's web services

This service:
1. Validates individual CFDIs against SAT
2. Batch validates multiple CFDIs
3. Updates invoice sessions with real SAT status
4. Maintains verification history for audit trail
5. Handles retries for transient errors

Architecture:
- Uses SATCFDIVerifier for actual SAT communication
- Integrates with Universal Invoice Engine
- Stores results in PostgreSQL for persistence
- Provides async batch processing capabilities
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text, and_, or_

from core.sat.sat_cfdi_verifier import (
    SATCFDIVerifier,
    format_cfdi_verification_url,
    get_status_display_name,
    is_valid_for_deduction
)

logger = logging.getLogger(__name__)


class SATValidationService:
    """
    Service for validating CFDIs against SAT web services

    This service manages the full lifecycle of SAT validation:
    - Single invoice validation
    - Batch validation
    - Verification history tracking
    - Retry logic for failed validations
    """

    def __init__(self, db: Session, use_mock: bool = False):
        """
        Initialize SAT validation service

        Args:
            db: SQLAlchemy database session
            use_mock: If True, use mock responses for testing
        """
        self.db = db
        self.verifier = SATCFDIVerifier(use_mock=use_mock)
        self.use_mock = use_mock

    def validate_invoice_session(
        self,
        session_id: str,
        force_refresh: bool = False
    ) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Validate a single invoice session against SAT

        Args:
            session_id: Universal invoice session ID
            force_refresh: If True, re-validate even if already validated

        Returns:
            (success, validation_info, error_message)
        """
        try:
            # Fetch invoice session
            query = text("""
                SELECT
                    id,
                    company_id,
                    extracted_data,
                    parsed_data,
                    sat_validation_status,
                    sat_verified_at
                FROM sat_invoices
                WHERE id = :session_id
            """)

            result = self.db.execute(query, {"session_id": session_id}).fetchone()

            if not result:
                return False, None, f"Invoice session {session_id} not found"

            session_data = dict(result._mapping)

            # Check if already validated (unless force_refresh)
            if not force_refresh and session_data.get('sat_verified_at'):
                # Already validated, return cached result
                logger.info(f"Using cached SAT validation for {session_id}")
                return True, {
                    'status': session_data.get('sat_validation_status'),
                    'verified_at': session_data.get('sat_verified_at'),
                    'cached': True
                }, None

            # Extract CFDI fields from parsed_data
            parsed_data = session_data.get('parsed_data', {})

            uuid = parsed_data.get('uuid')
            rfc_emisor = parsed_data.get('rfc_emisor')
            rfc_receptor = parsed_data.get('rfc_receptor')
            total = parsed_data.get('total', 0.0)

            # Validate required fields
            if not uuid:
                return False, None, "UUID not found in parsed data"
            if not rfc_emisor:
                return False, None, "RFC emisor not found in parsed data"
            if not rfc_receptor:
                return False, None, "RFC receptor not found in parsed data"

            # Convert total to float
            try:
                total = float(total)
            except (ValueError, TypeError):
                return False, None, f"Invalid total amount: {total}"

            # Mark as verifying
            update_query = text("""
                UPDATE sat_invoices
                SET sat_validation_status = 'verifying',
                    sat_last_check_at = CURRENT_TIMESTAMP
                WHERE id = :session_id
            """)
            self.db.execute(update_query, {"session_id": session_id})
            self.db.commit()

            # Call SAT verification service
            logger.info(f"Verifying CFDI {uuid} with SAT...")
            success, status_info, error = self.verifier.check_cfdi_status(
                uuid=uuid,
                rfc_emisor=rfc_emisor,
                rfc_receptor=rfc_receptor,
                total=total
            )

            if not success:
                # Update session with error
                error_query = text("""
                    UPDATE sat_invoices
                    SET sat_validation_status = 'error',
                        sat_verification_error = :error,
                        sat_last_check_at = CURRENT_TIMESTAMP
                    WHERE id = :session_id
                """)
                self.db.execute(error_query, {
                    "session_id": session_id,
                    "error": error
                })
                self.db.commit()

                return False, None, error

            # Generate verification URL
            verification_url = format_cfdi_verification_url(
                uuid=uuid,
                rfc_emisor=rfc_emisor,
                rfc_receptor=rfc_receptor,
                total=total
            )

            # Update session with SAT validation results
            update_result_query = text("""
                UPDATE sat_invoices
                SET sat_validation_status = :status,
                    sat_codigo_estatus = :codigo_estatus,
                    sat_es_cancelable = :es_cancelable,
                    sat_estado = :estado,
                    sat_validacion_efos = :validacion_efos,
                    sat_verified_at = CURRENT_TIMESTAMP,
                    sat_last_check_at = CURRENT_TIMESTAMP,
                    sat_verification_error = NULL,
                    sat_verification_url = :verification_url
                WHERE id = :session_id
            """)

            self.db.execute(update_result_query, {
                "session_id": session_id,
                "status": status_info['status'],
                "codigo_estatus": status_info.get('codigo_estatus'),
                "es_cancelable": status_info.get('es_cancelable'),
                "estado": status_info.get('estado'),
                "validacion_efos": status_info.get('validacion_efos'),
                "verification_url": verification_url
            })

            # Insert into verification history
            history_query = text("""
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
                ) VALUES (
                    :session_id,
                    :company_id,
                    :uuid,
                    :rfc_emisor,
                    :rfc_receptor,
                    :total,
                    :status,
                    :codigo_estatus,
                    :es_cancelable,
                    :estado,
                    :validacion_efos,
                    :verification_url
                )
            """)

            self.db.execute(history_query, {
                "session_id": session_id,
                "company_id": session_data['company_id'],
                "uuid": uuid,
                "rfc_emisor": rfc_emisor,
                "rfc_receptor": rfc_receptor,
                "total": total,
                "status": status_info['status'],
                "codigo_estatus": status_info.get('codigo_estatus'),
                "es_cancelable": status_info.get('es_cancelable'),
                "estado": status_info.get('estado'),
                "validacion_efos": status_info.get('validacion_efos'),
                "verification_url": verification_url
            })

            self.db.commit()

            logger.info(f"CFDI {uuid} validated: {status_info['status']}")

            return True, {
                'status': status_info['status'],
                'codigo_estatus': status_info.get('codigo_estatus'),
                'es_cancelable': status_info.get('es_cancelable'),
                'estado': status_info.get('estado'),
                'validacion_efos': status_info.get('validacion_efos'),
                'verification_url': verification_url,
                'verified_at': datetime.utcnow(),
                'cached': False
            }, None

        except Exception as e:
            logger.error(f"Error validating invoice session {session_id}: {e}")
            self.db.rollback()
            return False, None, f"Internal error: {str(e)}"

    def batch_validate_pending(
        self,
        company_id: str,
        limit: int = 100,
        max_age_hours: int = 24
    ) -> Dict:
        """
        Batch validate pending invoices for a company

        Args:
            company_id: Company ID to validate invoices for
            limit: Maximum number of invoices to validate
            max_age_hours: Only validate invoices newer than this many hours

        Returns:
            Dictionary with validation results summary
        """
        try:
            # Find pending validations
            cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)

            query = text("""
                SELECT id
                FROM sat_invoices
                WHERE company_id = :company_id
                    AND sat_validation_status = 'pending'
                    AND extraction_status = 'completed'
                    AND created_at > :cutoff_time
                ORDER BY created_at DESC
                LIMIT :limit
            """)

            results = self.db.execute(query, {
                "company_id": company_id,
                "cutoff_time": cutoff_time,
                "limit": limit
            }).fetchall()

            session_ids = [row[0] for row in results]

            logger.info(f"Found {len(session_ids)} pending validations for company {company_id}")

            # Validate each session
            summary = {
                'total': len(session_ids),
                'successful': 0,
                'failed': 0,
                'vigente': 0,
                'cancelado': 0,
                'sustituido': 0,
                'por_cancelar': 0,
                'no_encontrado': 0,
                'errors': []
            }

            for session_id in session_ids:
                success, validation_info, error = self.validate_invoice_session(session_id)

                if success:
                    summary['successful'] += 1
                    status = validation_info.get('status', 'error')

                    if status in summary:
                        summary[status] += 1
                else:
                    summary['failed'] += 1
                    summary['errors'].append({
                        'session_id': session_id,
                        'error': error
                    })

            logger.info(f"Batch validation completed: {summary['successful']}/{summary['total']} successful")

            return summary

        except Exception as e:
            logger.error(f"Error in batch validation: {e}")
            return {
                'total': 0,
                'successful': 0,
                'failed': 0,
                'errors': [str(e)]
            }

    def revalidate_old_validations(
        self,
        company_id: str,
        days_old: int = 30,
        limit: int = 50
    ) -> Dict:
        """
        Re-validate invoices that were validated long ago

        Useful for checking if vigente invoices have been canceled

        Args:
            company_id: Company ID
            days_old: Re-validate if last check was this many days ago
            limit: Maximum number to re-validate

        Returns:
            Summary of re-validation results
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(days=days_old)

            query = text("""
                SELECT id
                FROM sat_invoices
                WHERE company_id = :company_id
                    AND sat_validation_status IN ('vigente', 'por_cancelar')
                    AND sat_verified_at < :cutoff_time
                ORDER BY sat_verified_at ASC
                LIMIT :limit
            """)

            results = self.db.execute(query, {
                "company_id": company_id,
                "cutoff_time": cutoff_time,
                "limit": limit
            }).fetchall()

            session_ids = [row[0] for row in results]

            logger.info(f"Re-validating {len(session_ids)} old validations")

            summary = {
                'total': len(session_ids),
                'changed': 0,
                'unchanged': 0,
                'errors': [],
                'changes': []
            }

            for session_id in session_ids:
                # Get old status
                old_status_query = text("""
                    SELECT sat_validation_status
                    FROM sat_invoices
                    WHERE id = :session_id
                """)
                old_result = self.db.execute(old_status_query, {"session_id": session_id}).fetchone()
                old_status = old_result[0] if old_result else None

                # Re-validate
                success, validation_info, error = self.validate_invoice_session(
                    session_id,
                    force_refresh=True
                )

                if success:
                    new_status = validation_info.get('status')

                    if old_status != new_status:
                        summary['changed'] += 1
                        summary['changes'].append({
                            'session_id': session_id,
                            'old_status': old_status,
                            'new_status': new_status
                        })
                        logger.warning(f"Status changed: {session_id} from {old_status} to {new_status}")
                    else:
                        summary['unchanged'] += 1
                else:
                    summary['errors'].append({
                        'session_id': session_id,
                        'error': error
                    })

            return summary

        except Exception as e:
            logger.error(f"Error in re-validation: {e}")
            return {
                'total': 0,
                'changed': 0,
                'unchanged': 0,
                'errors': [str(e)]
            }

    def get_validation_stats(self, company_id: str) -> Dict:
        """
        Get SAT validation statistics for a company

        Args:
            company_id: Company ID

        Returns:
            Dictionary with validation statistics
        """
        try:
            query = text("""
                SELECT
                    sat_validation_status,
                    COUNT(*) as count
                FROM sat_invoices
                WHERE company_id = :company_id
                    AND extraction_status = 'completed'
                GROUP BY sat_validation_status
            """)

            results = self.db.execute(query, {"company_id": company_id}).fetchall()

            stats = {
                'total': 0,
                'pending': 0,
                'vigente': 0,
                'cancelado': 0,
                'sustituido': 0,
                'por_cancelar': 0,
                'no_encontrado': 0,
                'error': 0
            }

            for row in results:
                status = row[0] or 'pending'
                count = row[1]
                stats['total'] += count

                if status in stats:
                    stats[status] = count

            return stats

        except Exception as e:
            logger.error(f"Error getting validation stats: {e}")
            return {
                'total': 0,
                'error': str(e)
            }


def validate_single_invoice(
    db: Session,
    session_id: str,
    use_mock: bool = False,
    force_refresh: bool = False
) -> Tuple[bool, Optional[Dict], Optional[str]]:
    """
    Utility function to validate a single invoice

    Args:
        db: Database session
        session_id: Invoice session ID
        use_mock: Use mock SAT responses
        force_refresh: Force re-validation

    Returns:
        (success, validation_info, error)
    """
    service = SATValidationService(db, use_mock=use_mock)
    return service.validate_invoice_session(session_id, force_refresh=force_refresh)


def batch_validate_company_invoices(
    db: Session,
    company_id: str,
    limit: int = 100,
    use_mock: bool = False
) -> Dict:
    """
    Utility function to batch validate company invoices

    Args:
        db: Database session
        company_id: Company ID
        limit: Max invoices to validate
        use_mock: Use mock SAT responses

    Returns:
        Validation summary dict
    """
    service = SATValidationService(db, use_mock=use_mock)
    return service.batch_validate_pending(company_id, limit=limit)
