"""
Service layer for Split Reconciliation

Handles database operations for split matching:
- One-to-Many (1 movement → N expenses)
- Many-to-One (N movements → 1 expense)
"""

import sqlite3
import logging
from typing import List, Optional
from datetime import datetime
from pathlib import Path

from core.split_reconciliation_models import (
    SplitType,
    SplitStatus,
    SplitOneToManyRequest,
    SplitManyToOneRequest,
    SplitResponse,
    SplitDetailResponse,
    SplitItemResponse,
    SplitSummary,
    validate_split_amounts,
    calculate_percentages,
    generate_split_group_id,
)

logger = logging.getLogger(__name__)

# Database path
DB_PATH = Path(__file__).parent.parent / "unified_mcp_system.db"


def _get_db_connection() -> sqlite3.Connection:
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# =====================================================
# ONE-TO-MANY SPLIT (1 Movement → N Expenses)
# =====================================================

def create_one_to_many_split(
    request: SplitOneToManyRequest,
    user_id: Optional[int] = None,
    tenant_id: Optional[int] = None
) -> SplitResponse:
    """
    Create a one-to-many split reconciliation.

    Args:
        request: Split request with movement and expenses
        user_id: ID of user creating the split
        tenant_id: Tenant ID for multi-tenancy

    Returns:
        SplitResponse with details

    Raises:
        ValueError: If validation fails
        sqlite3.Error: If database operation fails
    """
    # 🔐 Validate tenant_id provided
    if tenant_id is None:
        raise ValueError("tenant_id is required for multi-tenant operation")

    # 1. Validate amounts
    validation = validate_split_amounts(request.movement_amount, request.expenses)

    if not validation.is_complete:
        raise ValueError(f"Split validation failed: {', '.join(validation.errors)}")

    # 2. Generate split group ID
    split_group_id = generate_split_group_id(SplitType.ONE_TO_MANY)

    # 3. Calculate percentages
    percentages = calculate_percentages(request.expenses, request.movement_amount)

    conn = _get_db_connection()
    cursor = conn.cursor()

    try:
        # 4. Verify movement exists, belongs to tenant, and is not already reconciled
        cursor.execute("""
            SELECT id, amount, is_reconciled, reconciliation_type, tenant_id
            FROM bank_movements
            WHERE id = ? AND tenant_id = ?
        """, (request.movement_id, tenant_id))

        movement = cursor.fetchone()
        if not movement:
            raise ValueError(f"Bank movement {request.movement_id} not found in tenant {tenant_id}")

        if movement['is_reconciled'] and movement['reconciliation_type'] == 'simple':
            raise ValueError(f"Movement {request.movement_id} is already reconciled (simple)")

        # 5. Verify all expenses exist, belong to tenant, and are not already reconciled
        for expense_item in request.expenses:
            cursor.execute("""
                SELECT id, amount, bank_status, reconciliation_type, tenant_id
                FROM expense_records
                WHERE id = ? AND tenant_id = ?
            """, (expense_item.expense_id, tenant_id))

            expense = cursor.fetchone()
            if not expense:
                raise ValueError(f"Expense {expense_item.expense_id} not found in tenant {tenant_id}")

            if expense['bank_status'] == 'reconciled' and expense['reconciliation_type'] == 'simple':
                raise ValueError(f"Expense {expense_item.expense_id} is already reconciled (simple)")

        # 6. Create split records with tenant_id
        split_items = []
        for i, (expense_item, percentage) in enumerate(zip(request.expenses, percentages)):
            cursor.execute("""
                INSERT INTO bank_reconciliation_splits (
                    split_group_id, split_type, expense_id, movement_id,
                    allocated_amount, percentage, notes, created_by, is_complete, tenant_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                split_group_id,
                SplitType.ONE_TO_MANY.value,
                expense_item.expense_id,
                request.movement_id,
                expense_item.amount,
                percentage,
                expense_item.notes,
                user_id,
                True,  # Mark as complete if validation passed
                tenant_id  # 🔐 Multi-tenancy
            ))

            split_items.append(SplitItemResponse(
                id=cursor.lastrowid,
                expense_id=expense_item.expense_id,
                movement_id=request.movement_id,
                allocated_amount=expense_item.amount,
                percentage=percentage,
                notes=expense_item.notes
            ))

        # 7. Update movement as split reconciliation
        cursor.execute("""
            UPDATE bank_movements
            SET
                reconciliation_type = 'split',
                split_group_id = ?,
                amount_allocated = ?,
                amount_unallocated = 0,
                is_reconciled = TRUE,
                matched_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (split_group_id, request.movement_amount, request.movement_id))

        # 8. Update each expense
        for expense_item in request.expenses:
            cursor.execute("""
                UPDATE expense_records
                SET
                    reconciliation_type = 'split',
                    split_group_id = ?,
                    amount_reconciled = ?,
                    amount_pending = 0,
                    bank_status = 'reconciled'
                WHERE id = ?
            """, (split_group_id, expense_item.amount, expense_item.expense_id))

        # 9. Commit transaction
        conn.commit()

        logger.info(f"Created one-to-many split {split_group_id}: 1 movement → {len(request.expenses)} expenses")

        return SplitResponse(
            success=True,
            split_group_id=split_group_id,
            reconciliation_type=SplitType.ONE_TO_MANY,
            created_at=datetime.utcnow(),
            total_amount=request.movement_amount,
            total_allocated=sum(e.amount for e in request.expenses),
            expenses_count=len(request.expenses),
            movements_count=1,
            validation=validation,
            splits=split_items,
            notes=request.notes
        )

    except Exception as e:
        conn.rollback()
        logger.error(f"Error creating one-to-many split: {e}")
        raise

    finally:
        conn.close()


# =====================================================
# MANY-TO-ONE SPLIT (N Movements → 1 Expense)
# =====================================================

def create_many_to_one_split(
    request: SplitManyToOneRequest,
    user_id: Optional[int] = None,
    tenant_id: Optional[int] = None
) -> SplitResponse:
    """
    Create a many-to-one split reconciliation (partial payments).

    Args:
        request: Split request with expense and movements
        user_id: ID of user creating the split
        tenant_id: Tenant ID for multi-tenancy

    Returns:
        SplitResponse with details

    Raises:
        ValueError: If validation fails
        sqlite3.Error: If database operation fails
    """
    # 🔐 Validate tenant_id provided
    if tenant_id is None:
        raise ValueError("tenant_id is required for multi-tenant operation")

    # 1. Validate amounts
    validation = validate_split_amounts(request.expense_amount, request.movements)

    if not validation.is_complete:
        raise ValueError(f"Split validation failed: {', '.join(validation.errors)}")

    # 2. Generate split group ID
    split_group_id = generate_split_group_id(SplitType.MANY_TO_ONE)

    # 3. Calculate percentages
    percentages = calculate_percentages(request.movements, request.expense_amount)

    conn = _get_db_connection()
    cursor = conn.cursor()

    try:
        # 4. Verify expense exists, belongs to tenant, and is not already reconciled
        cursor.execute("""
            SELECT id, amount, bank_status, reconciliation_type, tenant_id
            FROM expense_records
            WHERE id = ? AND tenant_id = ?
        """, (request.expense_id, tenant_id))

        expense = cursor.fetchone()
        if not expense:
            raise ValueError(f"Expense {request.expense_id} not found in tenant {tenant_id}")

        if expense['bank_status'] == 'reconciled' and expense['reconciliation_type'] == 'simple':
            raise ValueError(f"Expense {request.expense_id} is already reconciled (simple)")

        # 5. Verify all movements exist, belong to tenant, and are not already reconciled
        for movement_item in request.movements:
            cursor.execute("""
                SELECT id, amount, is_reconciled, reconciliation_type, tenant_id
                FROM bank_movements
                WHERE id = ? AND tenant_id = ?
            """, (movement_item.movement_id, tenant_id))

            movement = cursor.fetchone()
            if not movement:
                raise ValueError(f"Movement {movement_item.movement_id} not found in tenant {tenant_id}")

            if movement['is_reconciled'] and movement['reconciliation_type'] == 'simple':
                raise ValueError(f"Movement {movement_item.movement_id} is already reconciled (simple)")

        # 6. Create split records with tenant_id
        split_items = []
        for i, (movement_item, percentage) in enumerate(zip(request.movements, percentages)):
            cursor.execute("""
                INSERT INTO bank_reconciliation_splits (
                    split_group_id, split_type, expense_id, movement_id,
                    allocated_amount, percentage, notes, created_by, is_complete, tenant_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                split_group_id,
                SplitType.MANY_TO_ONE.value,
                request.expense_id,
                movement_item.movement_id,
                movement_item.amount,
                percentage,
                movement_item.notes,
                user_id,
                True,
                tenant_id  # 🔐 Multi-tenancy
            ))

            split_items.append(SplitItemResponse(
                id=cursor.lastrowid,
                expense_id=request.expense_id,
                movement_id=movement_item.movement_id,
                allocated_amount=movement_item.amount,
                percentage=percentage,
                payment_number=movement_item.payment_number,
                notes=movement_item.notes
            ))

        # 7. Update expense as split reconciliation
        cursor.execute("""
            UPDATE expense_records
            SET
                reconciliation_type = 'split',
                split_group_id = ?,
                amount_reconciled = ?,
                amount_pending = 0,
                bank_status = 'reconciled'
            WHERE id = ?
        """, (split_group_id, request.expense_amount, request.expense_id))

        # 8. Update each movement
        for movement_item in request.movements:
            cursor.execute("""
                UPDATE bank_movements
                SET
                    reconciliation_type = 'split',
                    split_group_id = ?,
                    amount_allocated = ?,
                    amount_unallocated = 0,
                    is_reconciled = TRUE,
                    matched_expense_id = ?,
                    matched_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (split_group_id, movement_item.amount, request.expense_id, movement_item.movement_id))

        # 9. Commit transaction
        conn.commit()

        logger.info(f"Created many-to-one split {split_group_id}: {len(request.movements)} movements → 1 expense")

        return SplitResponse(
            success=True,
            split_group_id=split_group_id,
            reconciliation_type=SplitType.MANY_TO_ONE,
            created_at=datetime.utcnow(),
            total_amount=request.expense_amount,
            total_allocated=sum(m.amount for m in request.movements),
            expenses_count=1,
            movements_count=len(request.movements),
            validation=validation,
            splits=split_items,
            notes=request.notes
        )

    except Exception as e:
        conn.rollback()
        logger.error(f"Error creating many-to-one split: {e}")
        raise

    finally:
        conn.close()


# =====================================================
# QUERY AND MANAGEMENT
# =====================================================

def get_split_details(split_group_id: str, tenant_id: Optional[int] = None) -> Optional[SplitDetailResponse]:
    """Get details of a specific split group (tenant-aware)"""
    conn = _get_db_connection()
    cursor = conn.cursor()

    try:
        # Get split records with tenant filter
        query = """
            SELECT *
            FROM bank_reconciliation_splits
            WHERE split_group_id = ?
        """
        params = [split_group_id]

        # 🔐 Add tenant filter if provided
        if tenant_id is not None:
            query += " AND tenant_id = ?"
            params.append(tenant_id)

        query += " ORDER BY id"

        cursor.execute(query, params)

        splits = cursor.fetchall()
        if not splits:
            return None

        first_split = splits[0]
        split_type = SplitType(first_split['split_type'])

        # Prepare items with full details
        items = []
        for split in splits:
            item = {
                'id': split['id'],
                'allocated_amount': split['allocated_amount'],
                'percentage': split['percentage'],
                'notes': split['notes']
            }

            # Add expense details
            if split['expense_id']:
                cursor.execute("""
                    SELECT id, description, amount, date
                    FROM expense_records
                    WHERE id = ?
                """, (split['expense_id'],))
                expense = cursor.fetchone()
                if expense:
                    item['expense'] = dict(expense)

            # Add movement details
            if split['movement_id']:
                cursor.execute("""
                    SELECT id, description, amount, date
                    FROM bank_movements
                    WHERE id = ?
                """, (split['movement_id'],))
                movement = cursor.fetchone()
                if movement:
                    item['movement'] = dict(movement)

            items.append(item)

        total_amount = sum(split['allocated_amount'] for split in splits)

        return SplitDetailResponse(
            split_group_id=split_group_id,
            split_type=split_type,
            status=SplitStatus.COMPLETE if first_split['is_complete'] else SplitStatus.PARTIAL,
            created_at=datetime.fromisoformat(first_split['created_at']),
            created_by=first_split['created_by'],
            verified_at=datetime.fromisoformat(first_split['verified_at']) if first_split['verified_at'] else None,
            total_amount=total_amount,
            is_complete=first_split['is_complete'],
            items=items,
            notes=splits[0]['notes']
        )

    finally:
        conn.close()


def list_splits(
    split_type: Optional[SplitType] = None,
    is_complete: Optional[bool] = None,
    limit: int = 100,
    tenant_id: Optional[int] = None
) -> List[SplitDetailResponse]:
    """List all splits with optional filters (tenant-aware)"""
    conn = _get_db_connection()
    cursor = conn.cursor()

    try:
        query = """
            SELECT DISTINCT split_group_id
            FROM bank_reconciliation_splits
            WHERE 1=1
        """
        params = []

        # 🔐 Add tenant filter if provided
        if tenant_id is not None:
            query += " AND tenant_id = ?"
            params.append(tenant_id)

        if split_type:
            query += " AND split_type = ?"
            params.append(split_type.value)

        if is_complete is not None:
            query += " AND is_complete = ?"
            params.append(1 if is_complete else 0)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        split_groups = cursor.fetchall()

        # Get details for each split group (with tenant filter)
        results = []
        for row in split_groups:
            details = get_split_details(row['split_group_id'], tenant_id=tenant_id)
            if details:
                results.append(details)

        return results

    finally:
        conn.close()


def undo_split(split_group_id: str, tenant_id: Optional[int] = None) -> bool:
    """
    Undo a split reconciliation (unlink all records) - tenant-aware.

    Returns:
        True if successful, False if split not found
    """
    conn = _get_db_connection()
    cursor = conn.cursor()

    try:
        # Get split details first with tenant filter
        query = """
            SELECT expense_id, movement_id
            FROM bank_reconciliation_splits
            WHERE split_group_id = ?
        """
        params = [split_group_id]

        # 🔐 Add tenant filter if provided
        if tenant_id is not None:
            query += " AND tenant_id = ?"
            params.append(tenant_id)

        cursor.execute(query, params)

        splits = cursor.fetchall()
        if not splits:
            return False

        # Collect unique expense and movement IDs
        expense_ids = {s['expense_id'] for s in splits if s['expense_id']}
        movement_ids = {s['movement_id'] for s in splits if s['movement_id']}

        # Reset expenses
        for expense_id in expense_ids:
            cursor.execute("""
                UPDATE expense_records
                SET
                    reconciliation_type = 'simple',
                    split_group_id = NULL,
                    amount_reconciled = 0,
                    amount_pending = amount,
                    bank_status = 'pending'
                WHERE id = ?
            """, (expense_id,))

        # Reset movements
        for movement_id in movement_ids:
            cursor.execute("""
                UPDATE bank_movements
                SET
                    reconciliation_type = 'simple',
                    split_group_id = NULL,
                    amount_allocated = 0,
                    amount_unallocated = ABS(amount),
                    is_reconciled = FALSE,
                    matched_expense_id = NULL,
                    matched_at = NULL
                WHERE id = ?
            """, (movement_id,))

        # Delete split records
        cursor.execute("""
            DELETE FROM bank_reconciliation_splits
            WHERE split_group_id = ?
        """, (split_group_id,))

        conn.commit()
        logger.info(f"Undone split {split_group_id}")

        return True

    except Exception as e:
        conn.rollback()
        logger.error(f"Error undoing split {split_group_id}: {e}")
        raise

    finally:
        conn.close()


def get_split_summary(tenant_id: Optional[int] = None) -> SplitSummary:
    """Get summary statistics for all splits (tenant-aware)"""
    conn = _get_db_connection()
    cursor = conn.cursor()

    try:
        # Build WHERE clause for tenant filtering
        where_clause = ""
        params = []
        if tenant_id is not None:
            where_clause = " WHERE tenant_id = ?"
            params = [tenant_id]

        # Total splits
        query = f"""
            SELECT COUNT(DISTINCT split_group_id) as total
            FROM bank_reconciliation_splits
            {where_clause}
        """
        cursor.execute(query, params)
        total_splits = cursor.fetchone()['total']

        # Complete vs incomplete
        query = f"""
            SELECT
                SUM(CASE WHEN is_complete = 1 THEN 1 ELSE 0 END) as complete,
                SUM(CASE WHEN is_complete = 0 THEN 1 ELSE 0 END) as incomplete
            FROM (
                SELECT DISTINCT split_group_id, is_complete
                FROM bank_reconciliation_splits
                {where_clause}
            )
        """
        cursor.execute(query, params)
        counts = cursor.fetchone()

        # Total amount
        query = f"""
            SELECT SUM(allocated_amount) as total
            FROM bank_reconciliation_splits
            {where_clause}
        """
        cursor.execute(query, params)
        total_amount = cursor.fetchone()['total'] or 0

        # By type
        query = f"""
            SELECT split_type, COUNT(DISTINCT split_group_id) as count
            FROM bank_reconciliation_splits
            {where_clause}
            GROUP BY split_type
        """
        cursor.execute(query, params)
        by_type = {row['split_type']: row['count'] for row in cursor.fetchall()}

        # Recent splits (with tenant filter)
        recent = list_splits(limit=5, tenant_id=tenant_id)

        return SplitSummary(
            total_splits=total_splits,
            complete_splits=counts['complete'] or 0,
            incomplete_splits=counts['incomplete'] or 0,
            total_amount_split=total_amount,
            splits_by_type=by_type,
            recent_splits=recent
        )

    finally:
        conn.close()
