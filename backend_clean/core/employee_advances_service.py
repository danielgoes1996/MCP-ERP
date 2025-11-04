"""
Service for Employee Advances (Anticipos/Préstamos)
"""

import sqlite3
import logging
from typing import List, Optional

from core.employee_advances_models import (
    CreateAdvanceRequest,
    ReimburseAdvanceRequest,
    UpdateAdvanceRequest,
    AdvanceResponse,
    AdvanceSummary,
    EmployeeAdvancesSummary,
    AdvanceStatus,
    validate_reimbursement
)

logger = logging.getLogger(__name__)


class EmployeeAdvancesService:
    """Service for managing employee advances"""

    def __init__(self, db_path: str = "unified_mcp_system.db"):
        self.db_path = db_path

    def get_db_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # =====================================================
    # CREATE ADVANCE
    # =====================================================

    def create_advance(
        self,
        request: CreateAdvanceRequest,
        tenant_id: Optional[int] = None,
        company_id: str = "default"
    ) -> AdvanceResponse:
        """
        Create a new employee advance

        Process:
        1. Validate expense exists and is not already an advance
        2. Create advance record
        3. Update expense with bank_status = 'advance' (no conciliable)
        4. Calculate pending_amount
        """
        conn = self.get_db_connection()
        cursor = conn.cursor()

        try:
            # 🔐 Validate tenant_id provided
            if tenant_id is None:
                raise ValueError("tenant_id is required for multi-tenant operation")

            # Check if expense exists AND belongs to tenant
            cursor.execute("""
                SELECT id, amount, description, bank_status, tenant_id
                FROM expense_records
                WHERE id = ? AND tenant_id = ?
            """, (request.expense_id, tenant_id))
            expense = cursor.fetchone()

            if not expense:
                raise ValueError(f"Expense {request.expense_id} not found in tenant {tenant_id}")

            # Check if expense is already an advance
            if expense['bank_status'] == 'advance':
                raise ValueError(f"Expense {request.expense_id} is already registered as an advance")

            # Validate amount matches expense (optional warning)
            if abs(request.advance_amount - expense['amount']) > 0.01:
                logger.warning(
                    f"Advance amount ({request.advance_amount}) differs from expense amount ({expense['amount']})"
                )

            # Create advance with tenant_id
            cursor.execute("""
                INSERT INTO employee_advances (
                    employee_id, employee_name, expense_id, advance_amount,
                    reimbursed_amount, pending_amount, reimbursement_type,
                    advance_date, status, payment_method, notes, tenant_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                request.employee_id,
                request.employee_name,
                request.expense_id,
                request.advance_amount,
                0.0,  # reimbursed_amount
                request.advance_amount,  # pending_amount
                'pending',
                request.advance_date,
                AdvanceStatus.PENDING,
                request.payment_method,
                request.notes,
                tenant_id  # 🔐 Multi-tenancy
            ))

            advance_id = cursor.lastrowid

            # Update expense status
            cursor.execute("""
                UPDATE expense_records
                SET bank_status = 'advance',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (request.expense_id,))

            conn.commit()

            logger.info(f"Created advance {advance_id} for employee {request.employee_name} (tenant={tenant_id})")

            # Return created advance
            return self.get_advance_by_id(advance_id, tenant_id=tenant_id)

        except Exception as e:
            conn.rollback()
            logger.error(f"Error creating advance: {e}")
            raise
        finally:
            conn.close()

    # =====================================================
    # REIMBURSE ADVANCE
    # =====================================================

    def reimburse_advance(
        self,
        request: ReimburseAdvanceRequest,
        tenant_id: Optional[int] = None
    ) -> AdvanceResponse:
        """
        Reimburse (partially or fully) an advance

        Process:
        1. Validate advance exists and can be reimbursed
        2. Update reimbursed_amount and pending_amount
        3. Update status (partial or completed)
        4. Record reimbursement details
        """
        conn = self.get_db_connection()
        cursor = conn.cursor()

        try:
            # 🔐 Validate tenant_id provided
            if tenant_id is None:
                raise ValueError("tenant_id is required for multi-tenant operation")

            # Get advance (with tenant validation)
            advance = self.get_advance_by_id(request.advance_id, tenant_id=tenant_id)

            if not advance:
                raise ValueError(f"Advance {request.advance_id} not found in tenant {tenant_id}")

            # Validate reimbursement
            validation = validate_reimbursement(advance, request.reimbursement_amount)

            if not validation.is_valid:
                raise ValueError(f"Invalid reimbursement: {', '.join(validation.errors)}")

            # Calculate new amounts
            new_reimbursed = advance.reimbursed_amount + request.reimbursement_amount
            new_pending = advance.advance_amount - new_reimbursed

            # Determine new status
            if new_pending <= 0.01:  # Tolerance for floating point
                new_status = AdvanceStatus.COMPLETED
                new_pending = 0.0
            else:
                new_status = AdvanceStatus.PARTIAL

            # Update advance
            cursor.execute("""
                UPDATE employee_advances
                SET reimbursed_amount = ?,
                    pending_amount = ?,
                    status = ?,
                    reimbursement_type = ?,
                    reimbursement_date = ?,
                    reimbursement_movement_id = ?,
                    notes = CASE
                        WHEN notes IS NULL THEN ?
                        ELSE notes || '\n' || ?
                    END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                new_reimbursed,
                new_pending,
                new_status,
                request.reimbursement_type,
                request.reimbursement_date,
                request.reimbursement_movement_id,
                f"Reembolso: ${request.reimbursement_amount:.2f} via {request.reimbursement_type} - {request.notes or ''}",
                f"Reembolso: ${request.reimbursement_amount:.2f} via {request.reimbursement_type} - {request.notes or ''}",
                request.advance_id
            ))

            conn.commit()

            logger.info(
                f"Reimbursed ${request.reimbursement_amount:.2f} for advance {request.advance_id}. "
                f"New status: {new_status}"
            )

            return self.get_advance_by_id(request.advance_id)

        except Exception as e:
            conn.rollback()
            logger.error(f"Error reimbursing advance: {e}")
            raise
        finally:
            conn.close()

    # =====================================================
    # QUERY ADVANCES
    # =====================================================

    def get_advance_by_id(
        self,
        advance_id: int,
        tenant_id: Optional[int] = None
    ) -> Optional[AdvanceResponse]:
        """Get advance by ID with expense details (tenant-aware)"""
        conn = self.get_db_connection()
        cursor = conn.cursor()

        try:
            # 🔐 Build query with tenant filter
            query = """
                SELECT
                    a.*,
                    e.description as expense_description,
                    e.category as expense_category,
                    e.date as expense_date
                FROM employee_advances a
                LEFT JOIN expense_records e ON a.expense_id = e.id
                WHERE a.id = ?
            """
            params = [advance_id]

            # Add tenant filter if provided
            if tenant_id is not None:
                query += " AND a.tenant_id = ?"
                params.append(tenant_id)

            cursor.execute(query, params)
            row = cursor.fetchone()

            if not row:
                return None

            return AdvanceResponse(**dict(row))

        finally:
            conn.close()

    def list_advances(
        self,
        status: Optional[AdvanceStatus] = None,
        employee_id: Optional[int] = None,
        limit: int = 100,
        tenant_id: Optional[int] = None
    ) -> List[AdvanceResponse]:
        """List advances with optional filters (tenant-aware)"""
        conn = self.get_db_connection()
        cursor = conn.cursor()

        try:
            # 🔐 Start with tenant filter
            query = """
                SELECT
                    a.*,
                    e.description as expense_description,
                    e.category as expense_category,
                    e.date as expense_date
                FROM employee_advances a
                LEFT JOIN expense_records e ON a.expense_id = e.id
                WHERE 1=1
            """
            params = []

            # Add tenant filter if provided
            if tenant_id is not None:
                query += " AND a.tenant_id = ?"
                params.append(tenant_id)

            if status:
                query += " AND a.status = ?"
                params.append(status)

            if employee_id:
                query += " AND a.employee_id = ?"
                params.append(employee_id)

            query += " ORDER BY a.created_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            return [AdvanceResponse(**dict(row)) for row in rows]

        finally:
            conn.close()

    def get_advances_by_employee(
        self,
        employee_id: int,
        tenant_id: Optional[int] = None
    ) -> EmployeeAdvancesSummary:
        """Get all advances for a specific employee (tenant-aware)"""
        advances = self.list_advances(employee_id=employee_id, limit=1000, tenant_id=tenant_id)

        total_advanced = sum(a.advance_amount for a in advances)
        total_reimbursed = sum(a.reimbursed_amount for a in advances)
        total_pending = sum(a.pending_amount for a in advances)

        employee_name = advances[0].employee_name if advances else "Unknown"

        return EmployeeAdvancesSummary(
            employee_id=employee_id,
            employee_name=employee_name,
            total_advances=len(advances),
            total_amount_advanced=total_advanced,
            total_reimbursed=total_reimbursed,
            total_pending=total_pending,
            advances=advances
        )

    def get_summary(self, tenant_id: Optional[int] = None) -> AdvanceSummary:
        """Get summary of all advances (tenant-aware)"""
        conn = self.get_db_connection()
        cursor = conn.cursor()

        try:
            # Get totals with tenant filter
            query = """
                SELECT
                    COUNT(*) as total_advances,
                    SUM(advance_amount) as total_amount_advanced,
                    SUM(reimbursed_amount) as total_reimbursed,
                    SUM(pending_amount) as total_pending,
                    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending_count,
                    SUM(CASE WHEN status = 'partial' THEN 1 ELSE 0 END) as partial_count,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_count
                FROM employee_advances
            """
            params = []

            # 🔐 Add tenant filter
            if tenant_id is not None:
                query += " WHERE tenant_id = ?"
                params.append(tenant_id)

            cursor.execute(query, params)
            totals = dict(cursor.fetchone())

            # Get by employee with tenant filter
            query_by_employee = """
                SELECT
                    employee_id,
                    employee_name,
                    COUNT(*) as count,
                    SUM(advance_amount) as total_advanced,
                    SUM(reimbursed_amount) as total_reimbursed,
                    SUM(pending_amount) as total_pending
                FROM employee_advances
            """
            if tenant_id is not None:
                query_by_employee += " WHERE tenant_id = ?"

            query_by_employee += """
                GROUP BY employee_id, employee_name
                ORDER BY total_pending DESC
            """

            if tenant_id is not None:
                cursor.execute(query_by_employee, (tenant_id,))
            else:
                cursor.execute(query_by_employee)

            by_employee = [dict(row) for row in cursor.fetchall()]

            # Get recent advances with tenant filter
            recent = self.list_advances(limit=5, tenant_id=tenant_id)

            return AdvanceSummary(
                total_advances=totals['total_advances'] or 0,
                total_amount_advanced=totals['total_amount_advanced'] or 0.0,
                total_reimbursed=totals['total_reimbursed'] or 0.0,
                total_pending=totals['total_pending'] or 0.0,
                pending_count=totals['pending_count'] or 0,
                partial_count=totals['partial_count'] or 0,
                completed_count=totals['completed_count'] or 0,
                by_employee=by_employee,
                recent_advances=recent
            )

        finally:
            conn.close()

    # =====================================================
    # UPDATE/DELETE ADVANCES
    # =====================================================

    def update_advance(
        self,
        advance_id: int,
        request: UpdateAdvanceRequest
    ) -> AdvanceResponse:
        """Update an advance"""
        conn = self.get_db_connection()
        cursor = conn.cursor()

        try:
            # Build update query dynamically
            updates = []
            params = []

            if request.employee_name is not None:
                updates.append("employee_name = ?")
                params.append(request.employee_name)

            if request.payment_method is not None:
                updates.append("payment_method = ?")
                params.append(request.payment_method)

            if request.notes is not None:
                updates.append("notes = ?")
                params.append(request.notes)

            if request.status is not None:
                updates.append("status = ?")
                params.append(request.status)

            if not updates:
                raise ValueError("No fields to update")

            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(advance_id)

            query = f"UPDATE employee_advances SET {', '.join(updates)} WHERE id = ?"

            cursor.execute(query, params)
            conn.commit()

            return self.get_advance_by_id(advance_id)

        except Exception as e:
            conn.rollback()
            logger.error(f"Error updating advance: {e}")
            raise
        finally:
            conn.close()

    def cancel_advance(self, advance_id: int, reason: Optional[str] = None) -> AdvanceResponse:
        """Cancel an advance (only if not reimbursed)"""
        conn = self.get_db_connection()
        cursor = conn.cursor()

        try:
            advance = self.get_advance_by_id(advance_id)

            if not advance:
                raise ValueError(f"Advance {advance_id} not found")

            if advance.reimbursed_amount > 0:
                raise ValueError("Cannot cancel advance that has been partially or fully reimbursed")

            # Update advance status
            cursor.execute("""
                UPDATE employee_advances
                SET status = 'cancelled',
                    notes = CASE
                        WHEN notes IS NULL THEN ?
                        ELSE notes || '\n' || ?
                    END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                f"Cancelado: {reason or 'Sin razón especificada'}",
                f"Cancelado: {reason or 'Sin razón especificada'}",
                advance_id
            ))

            # Reset expense bank_status
            cursor.execute("""
                UPDATE expense_records
                SET bank_status = 'pending',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (advance.expense_id,))

            conn.commit()

            return self.get_advance_by_id(advance_id)

        except Exception as e:
            conn.rollback()
            logger.error(f"Error cancelling advance: {e}")
            raise
        finally:
            conn.close()


# =====================================================
# FACTORY FUNCTION
# =====================================================

def get_employee_advances_service() -> EmployeeAdvancesService:
    """Get singleton instance"""
    return EmployeeAdvancesService()
