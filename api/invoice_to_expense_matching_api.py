"""
API endpoint for automatic invoice-to-expense matching (MVP)

Simple 3-case system:
1. Exact match → Auto-link
2. No match → Auto-create expense
3. Multiple matches → Queue for review
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging
import json

from core.error_handler import handle_error, log_endpoint_entry, log_endpoint_success
from core.auth.jwt import get_current_user, User
from core.concept_similarity import (
    calculate_concept_match_score,
    calculate_concept_match_score_hybrid,
    interpret_concept_score
)

router = APIRouter(prefix="/invoice-matching", tags=["Invoice Matching"])
logger = logging.getLogger(__name__)


def _get_db_connection():
    """Get PostgreSQL connection"""
    import psycopg2
    from psycopg2.extras import RealDictCursor
    import os

    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', '127.0.0.1'),
        port=int(os.getenv('POSTGRES_PORT', '5433')),
        database=os.getenv('POSTGRES_DB', 'mcp_system'),
        user=os.getenv('POSTGRES_USER', 'mcp_user'),
        password=os.getenv('POSTGRES_PASSWORD', 'changeme')
    )
    conn.cursor_factory = RealDictCursor
    return conn


@router.post("/match-invoice/{invoice_id}")
async def match_invoice_to_expense(
    invoice_id: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Match a classified invoice to an existing expense OR create new expense

    Simple 3-case logic:
    - Case 1: Exact match found → Link automatically
    - Case 2: No match found → Create new expense
    - Case 3: Multiple matches → Queue for manual review

    🔐 Requires authentication
    """
    log_endpoint_entry(f"/invoice-matching/match-invoice/{invoice_id}", method="POST", user_id=current_user.id)

    conn = _get_db_connection()
    try:
        cursor = conn.cursor()

        # 1. Get invoice details
        cursor.execute("""
            SELECT
                id,
                company_id,
                parsed_data,
                accounting_classification
            FROM sat_invoices
            WHERE id = %s
        """, (invoice_id,))

        invoice = cursor.fetchone()
        if not invoice:
            raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")

        parsed_data = invoice['parsed_data'] or {}
        emisor = parsed_data.get('emisor', {})

        invoice_rfc = emisor.get('rfc')
        invoice_total = float(parsed_data.get('total', 0))
        invoice_date = parsed_data.get('fecha')
        invoice_uuid = parsed_data.get('uuid')
        emisor_nombre = emisor.get('nombre')
        concepto = parsed_data.get('conceptos', [{}])[0].get('descripcion', 'Gasto sin descripción')

        if not invoice_rfc:
            raise HTTPException(status_code=400, detail="Invoice missing RFC - cannot match")

        # Convert invoice_date string to date object
        if isinstance(invoice_date, str):
            invoice_date = datetime.fromisoformat(invoice_date.replace('Z', '+00:00')).date()

        company_id = invoice['company_id']

        # 2. Search for matching expenses (CASE 1 check)
        # Strategy: Try BOTH RFC match AND name similarity match
        # This handles cases where employee captured "Pemex" but didn't have RFC yet
        cursor.execute("""
            SELECT
                id,
                description,
                amount,
                expense_date,
                provider_rfc,
                provider_name,
                ticket_extracted_concepts,
                CASE
                    WHEN provider_rfc = %s THEN 100  -- Exact RFC match = highest score
                    WHEN provider_name ILIKE %s THEN 80  -- Name similarity = good score
                    ELSE 0
                END as match_score
            FROM manual_expenses
            WHERE company_id = %s
              AND (
                  provider_rfc = %s  -- Match by RFC
                  OR provider_name ILIKE %s  -- OR match by name similarity
              )
              AND ABS(amount - %s) < 5.0  -- Allow $5 difference (tips, rounding)
              AND expense_date BETWEEN %s AND %s  -- Allow ±15 days (invoices can be delayed)
              AND invoice_uuid IS NULL
            ORDER BY match_score DESC, ABS(amount - %s) ASC, ABS(expense_date - %s) ASC
            LIMIT 5
        """, (
            invoice_rfc,  # For match_score calculation
            f"%{emisor_nombre.split()[0] if emisor_nombre else ''}%",  # First word of fiscal name
            company_id,
            invoice_rfc,  # For WHERE clause
            f"%{emisor_nombre.split()[0] if emisor_nombre else ''}%",  # For WHERE clause
            invoice_total,
            invoice_date - timedelta(days=15),  # Extended to ±15 days
            invoice_date + timedelta(days=15),
            invoice_total,
            invoice_date
        ))

        matches = cursor.fetchall()

        # 2.5. Enhance match_score with concept similarity
        # If ticket has extracted concepts AND invoice has concepts, compare them
        invoice_concepts = parsed_data.get('conceptos', [])

        for match in matches:
            # Get ticket concepts (stored as JSONB array)
            ticket_concepts_raw = match.get('ticket_extracted_concepts')

            if ticket_concepts_raw and invoice_concepts:
                # Parse JSONB if it's a string
                if isinstance(ticket_concepts_raw, str):
                    ticket_concepts = json.loads(ticket_concepts_raw)
                else:
                    ticket_concepts = ticket_concepts_raw

                # Calculate concept similarity score (0-100) usando HÍBRIDO
                # Usa string matching + Gemini LLM para mayor precisión
                concept_score, metadata = calculate_concept_match_score_hybrid(
                    ticket_concepts,
                    invoice_concepts,
                    use_gemini=True  # Habilitar Gemini para casos ambiguos
                )

                # Boost match_score based on concept similarity
                # High concept match (70+) → boost RFC/name match score
                if concept_score >= 70:
                    match['match_score'] = min(100, match['match_score'] + 15)
                    match['concept_boost'] = 'high'
                elif concept_score >= 50:
                    match['match_score'] = min(100, match['match_score'] + 10)
                    match['concept_boost'] = 'medium'
                elif concept_score >= 30:
                    match['match_score'] = min(100, match['match_score'] + 5)
                    match['concept_boost'] = 'low'
                else:
                    # Low concept similarity → may indicate wrong match
                    # Reduce confidence slightly
                    match['match_score'] = max(0, match['match_score'] - 10)
                    match['concept_boost'] = 'none'

                match['concept_score'] = concept_score
                match['concept_confidence'] = interpret_concept_score(concept_score)

                # Agregar metadata del híbrido (método usado, Gemini calls, etc.)
                match['concept_method'] = metadata.get('method_used')
                match['concept_gemini_calls'] = metadata.get('gemini_calls', 0)
                if metadata.get('string_score') is not None:
                    match['concept_string_score'] = metadata['string_score']
                if metadata.get('gemini_score') is not None:
                    match['concept_gemini_score'] = metadata['gemini_score']

                logger.info(
                    f"Expense {match['id']}: Base score={match['match_score'] - (15 if concept_score >= 70 else 10 if concept_score >= 50 else 5 if concept_score >= 30 else -10)}, "
                    f"Concept score={concept_score}, Final score={match['match_score']}"
                )
            else:
                # No concept data available
                match['concept_score'] = None
                match['concept_boost'] = 'no_data'
                match['concept_confidence'] = 'no_data'

        # Re-sort matches by enhanced match_score
        matches = sorted(matches, key=lambda m: m['match_score'], reverse=True)

        # CASE 1: Single match with HIGH confidence (RFC match + optional concept boost)
        # Only auto-match if match_score >= 95 (very high confidence)
        # This could be: RFC (100) or RFC (100) with concepts, or Name (80) + High concepts (15)
        if len(matches) == 1 and matches[0]['match_score'] >= 95:
            expense = matches[0]

            # Update expense with invoice UUID and fiscal name
            cursor.execute("""
                UPDATE manual_expenses
                SET
                    invoice_uuid = %s,
                    provider_fiscal_name = %s,
                    provider_rfc = %s,
                    status = 'invoiced',
                    updated_at = NOW()
                WHERE id = %s
            """, (invoice_uuid, emisor_nombre, invoice_rfc, expense['id']))

            conn.commit()

            log_endpoint_success(
                f"/invoice-matching/match-invoice/{invoice_id}",
                {"action": "auto_matched", "expense_id": expense['id'], "match_score": 100}
            )

            return {
                "status": "success",
                "action": "auto_matched",
                "case": 1,
                "expense_id": expense['id'],
                "expense_description": expense['description'],
                "invoice_uuid": invoice_uuid,
                "match_confidence": "high",
                "match_score": expense['match_score'],
                "concept_score": expense.get('concept_score'),
                "concept_confidence": expense.get('concept_confidence'),
                "concept_boost": expense.get('concept_boost'),
                "match_reason": "High confidence match with RFC/name + amount + date" +
                               (f" + concepts ({expense.get('concept_confidence', 'N/A')})" if expense.get('concept_score') else "")
            }

        # CASE 1b: Single match with MEDIUM confidence (name only or lower score)
        # Send to review queue instead of auto-matching
        # This includes: name-only (80), name+low concepts (85-90), etc.
        elif len(matches) == 1 and matches[0]['match_score'] < 95:
            expense = matches[0]

            # Create pending assignment for accountant review
            cursor.execute("""
                INSERT INTO invoice_expense_pending_assignments
                    (invoice_id, possible_expense_ids, status, created_at)
                VALUES (%s, %s, 'needs_manual_assignment', NOW())
                RETURNING id
            """, (
                invoice_id,
                json.dumps([expense['id']])
            ))

            assignment_id = cursor.fetchone()['id']
            conn.commit()

            log_endpoint_success(
                f"/invoice-matching/match-invoice/{invoice_id}",
                {"action": "pending_review_medium_confidence", "assignment_id": assignment_id}
            )

            return {
                "status": "success",
                "action": "pending_manual_review",
                "case": "1b",
                "assignment_id": assignment_id,
                "possible_matches": [
                    {
                        "expense_id": expense['id'],
                        "description": expense['description'],
                        "amount": float(expense['amount']),
                        "date": expense['expense_date'].isoformat(),
                        "provider_name": expense['provider_name'],
                        "match_score": expense['match_score'],
                        "concept_score": expense.get('concept_score'),
                        "concept_confidence": expense.get('concept_confidence'),
                        "concept_boost": expense.get('concept_boost')
                    }
                ],
                "match_confidence": "medium",
                "reason": f"Medium confidence match (score={expense['match_score']}). " +
                         ("Concept similarity: " + expense.get('concept_confidence', 'N/A') + ". " if expense.get('concept_score') else "") +
                         "Please review and confirm."
            }

        # CASE 3: Multiple matches
        elif len(matches) > 1:
            # Create pending assignment record
            cursor.execute("""
                INSERT INTO invoice_expense_pending_assignments
                    (invoice_id, possible_expense_ids, status, created_at)
                VALUES (%s, %s, 'needs_manual_assignment', NOW())
                RETURNING id
            """, (
                invoice_id,
                json.dumps([m['id'] for m in matches])
            ))

            assignment_id = cursor.fetchone()['id']
            conn.commit()

            log_endpoint_success(
                f"/invoice-matching/match-invoice/{invoice_id}",
                {"action": "pending_review", "assignment_id": assignment_id, "match_count": len(matches)}
            )

            return {
                "status": "success",
                "action": "pending_manual_review",
                "case": 3,
                "assignment_id": assignment_id,
                "possible_matches": [
                    {
                        "expense_id": m['id'],
                        "description": m['description'],
                        "amount": float(m['amount']),
                        "date": m['expense_date'].isoformat(),
                        "provider_name": m['provider_name'],
                        "provider_rfc": m['provider_rfc'],
                        "match_score": m['match_score'],
                        "concept_score": m.get('concept_score'),
                        "concept_confidence": m.get('concept_confidence'),
                        "concept_boost": m.get('concept_boost')
                    }
                    for m in matches
                ],
                "match_confidence": "ambiguous",
                "reason": f"Found {len(matches)} possible matches. " +
                         "Matches are sorted by score (RFC/name + concepts). " +
                         "Please review and select the correct one."
            }

        # CASE 2: No match - create new expense
        else:
            cursor.execute("""
                INSERT INTO manual_expenses (
                    company_id,
                    tenant_id,
                    description,
                    amount,
                    expense_date,
                    category,
                    provider_fiscal_name,
                    provider_rfc,
                    invoice_uuid,
                    status,
                    needs_review,
                    created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'invoiced', true, NOW())
                RETURNING id
            """, (
                company_id,
                current_user.tenant_id,
                f"{concepto[:100]} - {emisor_nombre[:50]}",
                invoice_total,
                invoice_date,
                'sin_clasificar',  # Needs categorization
                emisor_nombre,
                invoice_rfc,
                invoice_uuid
            ))

            new_expense_id = cursor.fetchone()['id']
            conn.commit()

            log_endpoint_success(
                f"/invoice-matching/match-invoice/{invoice_id}",
                {"action": "auto_created", "expense_id": new_expense_id}
            )

            return {
                "status": "success",
                "action": "auto_created_expense",
                "case": 2,
                "expense_id": new_expense_id,
                "invoice_uuid": invoice_uuid,
                "needs_review": True,
                "reason": "No existing expense found - created from invoice",
                "match_confidence": "no_match"
            }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        handle_error(e, {"invoice_id": invoice_id})
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.get("/pending-assignments")
async def get_pending_assignments(
    current_user: User = Depends(get_current_user),
    company_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Get list of invoices waiting for manual assignment (Case 3)

    🔐 Requires authentication
    """
    log_endpoint_entry("/invoice-matching/pending-assignments", method="GET", user_id=current_user.id)

    conn = _get_db_connection()
    try:
        cursor = conn.cursor()

        query = """
            SELECT
                pa.id as assignment_id,
                pa.invoice_id,
                pa.possible_expense_ids,
                pa.status,
                pa.created_at,
                si.parsed_data
            FROM invoice_expense_pending_assignments pa
            JOIN sat_invoices si ON pa.invoice_id = si.id
            WHERE pa.status = 'needs_manual_assignment'
        """

        params = []
        if company_id:
            query += " AND si.company_id = %s"
            params.append(company_id)

        query += " ORDER BY pa.created_at DESC LIMIT 50"

        cursor.execute(query, params)
        assignments = cursor.fetchall()

        return {
            "status": "success",
            "count": len(assignments),
            "pending_assignments": [
                {
                    "assignment_id": a['assignment_id'],
                    "invoice_id": a['invoice_id'],
                    "invoice_uuid": (a['parsed_data'] or {}).get('uuid'),
                    "invoice_total": (a['parsed_data'] or {}).get('total'),
                    "possible_expense_ids": json.loads(a['possible_expense_ids']),
                    "created_at": a['created_at'].isoformat()
                }
                for a in assignments
            ]
        }

    except Exception as e:
        handle_error(e, {"company_id": company_id})
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.post("/assign/{assignment_id}")
async def manually_assign_invoice(
    assignment_id: int,
    expense_id: int,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Manually assign an invoice to a specific expense (resolve Case 3)

    🔐 Requires authentication
    """
    log_endpoint_entry(
        f"/invoice-matching/assign/{assignment_id}",
        method="POST",
        user_id=current_user.id
    )

    conn = _get_db_connection()
    try:
        cursor = conn.cursor()

        # Get assignment details
        cursor.execute("""
            SELECT pa.invoice_id, si.parsed_data
            FROM invoice_expense_pending_assignments pa
            JOIN sat_invoices si ON pa.invoice_id = si.id
            WHERE pa.id = %s
        """, (assignment_id,))

        assignment = cursor.fetchone()
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")

        parsed_data = assignment['parsed_data'] or {}
        invoice_uuid = parsed_data.get('uuid')
        emisor_nombre = parsed_data.get('emisor', {}).get('nombre')

        # Update expense
        cursor.execute("""
            UPDATE manual_expenses
            SET
                invoice_uuid = %s,
                provider_fiscal_name = %s,
                status = 'invoiced',
                updated_at = NOW()
            WHERE id = %s
        """, (invoice_uuid, emisor_nombre, expense_id))

        # Mark assignment as resolved
        cursor.execute("""
            UPDATE invoice_expense_pending_assignments
            SET
                status = 'resolved',
                resolved_expense_id = %s,
                resolved_by_user_id = %s,
                resolved_at = NOW()
            WHERE id = %s
        """, (expense_id, current_user.id, assignment_id))

        conn.commit()

        log_endpoint_success(
            f"/invoice-matching/assign/{assignment_id}",
            {"expense_id": expense_id, "invoice_uuid": invoice_uuid}
        )

        return {
            "status": "success",
            "assignment_id": assignment_id,
            "expense_id": expense_id,
            "invoice_uuid": invoice_uuid,
            "message": "Invoice manually assigned to expense"
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        handle_error(e, {"assignment_id": assignment_id, "expense_id": expense_id})
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
