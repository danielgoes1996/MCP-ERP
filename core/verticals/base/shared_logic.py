"""
Shared business logic across ALL verticals.

NO MÁS COPY-PASTE. Usa composición, no duplicación.
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import logging
from dataclasses import dataclass
import json

# Import execute_query at module level for testing/patching
from core.shared.unified_db_adapter import execute_query

logger = logging.getLogger(__name__)


# ==================== Shared Data Access Layer ====================

class VerticalDAL:
    """
    Data Access Layer compartido para todos los verticals.

    NO copiar este código en cada vertical.
    Usar composición: self.dal = VerticalDAL()
    """

    def __init__(self, table_name: str, id_column: str = "id"):
        self.table_name = table_name
        self.id_column = id_column

    def create(self, company_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generic CREATE operation.

        NO duplicar esta lógica en cada vertical.
        """
        # Auto-add company_id and tenant_id
        if "company_id" not in data:
            data["company_id"] = company_id

        if "tenant_id" not in data:
            tenant_result = execute_query(
                "SELECT tenant_id FROM companies WHERE company_id = %s",
                (company_id,),
                fetch_one=True
            )
            data["tenant_id"] = tenant_result.get("tenant_id") if tenant_result else None

        # Build dynamic INSERT
        columns = list(data.keys())
        placeholders = ["%s"] * len(columns)
        values = []

        for col in columns:
            value = data[col]
            # Auto-serialize JSONB fields
            if isinstance(value, (dict, list)):
                values.append(json.dumps(value))
            else:
                values.append(value)

        query = f"""
            INSERT INTO {self.table_name} ({', '.join(columns)})
            VALUES ({', '.join(placeholders)})
            RETURNING *
        """

        result = execute_query(query, tuple(values), fetch_one=True)
        logger.info(f"Created {self.table_name} record: {result[self.id_column]}")
        return result

    def get(self, company_id: str, record_id: int) -> Optional[Dict[str, Any]]:
        """Generic GET by ID."""
        result = execute_query(
            f"""
            SELECT *
            FROM {self.table_name}
            WHERE {self.id_column} = %s AND company_id = %s
            """,
            (record_id, company_id),
            fetch_one=True
        )
        return result

    def list(
        self,
        company_id: str,
        filters: Optional[Dict[str, Any]] = None,
        order_by: str = "created_at DESC",
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Generic LIST with filters."""
        where_clauses = ["company_id = %s"]
        params = [company_id]

        if filters:
            for field, value in filters.items():
                where_clauses.append(f"{field} = %s")
                params.append(value)

        query = f"""
            SELECT *
            FROM {self.table_name}
            WHERE {' AND '.join(where_clauses)}
            ORDER BY {order_by}
        """

        if limit:
            query += f" LIMIT {limit}"

        results = execute_query(query, tuple(params))
        return results or []

    def update(
        self,
        company_id: str,
        record_id: int,
        updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Generic UPDATE."""
        if not updates:
            return self.get(company_id, record_id)

        set_clauses = []
        params = []

        for field, value in updates.items():
            set_clauses.append(f"{field} = %s")
            if isinstance(value, (dict, list)):
                params.append(json.dumps(value))
            else:
                params.append(value)

        params.extend([record_id, company_id])

        query = f"""
            UPDATE {self.table_name}
            SET {', '.join(set_clauses)}, updated_at = NOW()
            WHERE {self.id_column} = %s AND company_id = %s
            RETURNING *
        """

        result = execute_query(query, tuple(params), fetch_one=True)
        if result:
            logger.info(f"Updated {self.table_name} record: {record_id}")
        return result

    def delete(self, company_id: str, record_id: int) -> Dict[str, Any]:
        """Generic soft DELETE (set status = 'inactive')."""
        result = execute_query(
            f"""
            UPDATE {self.table_name}
            SET status = 'inactive', updated_at = NOW()
            WHERE {self.id_column} = %s AND company_id = %s
            RETURNING *
            """,
            (record_id, company_id),
            fetch_one=True
        )
        return result


# ==================== Shared Business Logic ====================

class StatusMachine:
    """
    Generic state machine for status transitions.

    NO duplicar esta lógica en cada vertical.
    """

    def __init__(self, valid_transitions: Dict[str, List[str]]):
        """
        Args:
            valid_transitions: Dict of current_status -> [allowed_next_statuses]

        Example:
            {
                "pending": ["sold", "returned"],
                "sold": ["paid"],
                "paid": []
            }
        """
        self.valid_transitions = valid_transitions

    def can_transition(self, from_status: str, to_status: str) -> bool:
        """Check if transition is valid."""
        allowed = self.valid_transitions.get(from_status, [])
        return to_status in allowed

    def validate_transition(self, from_status: str, to_status: str):
        """Raise exception if transition is invalid."""
        if not self.can_transition(from_status, to_status):
            raise ValueError(
                f"Invalid status transition: {from_status} -> {to_status}. "
                f"Allowed: {self.valid_transitions.get(from_status, [])}"
            )


class FinancialCalculator:
    """
    Shared financial calculations.

    NO duplicar fórmulas en cada vertical.
    """

    @staticmethod
    def calculate_total(items: List[Dict[str, Any]], qty_field: str = "qty", price_field: str = "precio") -> float:
        """Calculate total from line items."""
        return sum(
            item.get(qty_field, 0) * item.get(price_field, 0.0)
            for item in items
        )

    @staticmethod
    def apply_tax(subtotal: float, tax_rate: float) -> Tuple[float, float]:
        """
        Apply tax to subtotal.

        Returns:
            (tax_amount, total)
        """
        tax_amount = subtotal * tax_rate
        total = subtotal + tax_amount
        return (tax_amount, total)

    @staticmethod
    def calculate_aging_days(start_date: datetime, end_date: Optional[datetime] = None) -> int:
        """Calculate days between dates."""
        end = end_date or datetime.now()
        delta = end - start_date
        return delta.days


class ValidationHelpers:
    """
    Shared validation logic.

    NO duplicar validaciones en cada vertical.
    """

    @staticmethod
    def validate_required_fields(data: Dict[str, Any], required: List[str]) -> List[str]:
        """
        Validate required fields are present.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []
        for field in required:
            if field not in data or data[field] is None:
                errors.append(f"Missing required field: {field}")
        return errors

    @staticmethod
    def validate_positive_amount(amount: float, field_name: str = "amount") -> List[str]:
        """Validate amount is positive."""
        if amount <= 0:
            return [f"{field_name} must be positive, got {amount}"]
        return []

    @staticmethod
    def validate_date_range(start_date: datetime, end_date: datetime) -> List[str]:
        """Validate date range."""
        if end_date < start_date:
            return [f"End date ({end_date}) cannot be before start date ({start_date})"]
        return []


# ==================== Shared Query Builders ====================

class ReportBuilder:
    """
    Shared report generation logic.

    NO duplicar queries de reportes en cada vertical.
    """

    @staticmethod
    def build_summary_query(
        table_name: str,
        group_by_fields: List[str],
        aggregate_fields: Dict[str, str],
        filters: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, List[Any]]:
        """
        Build generic summary/aggregation query.

        Args:
            table_name: Table to query
            group_by_fields: Fields to GROUP BY
            aggregate_fields: Dict of {alias: aggregate_expression}
            filters: WHERE clause filters

        Returns:
            (query, params)

        Example:
            build_summary_query(
                "cpg_consignment",
                ["pos_id", "status"],
                {
                    "total_amount": "SUM(monto_total)",
                    "count": "COUNT(*)"
                },
                {"company_id": "carreta_verde"}
            )
        """
        # SELECT clause
        select_parts = group_by_fields.copy()
        select_parts.extend([f"{expr} as {alias}" for alias, expr in aggregate_fields.items()])
        select_clause = ", ".join(select_parts)

        # WHERE clause
        where_clauses = []
        params = []
        if filters:
            for field, value in filters.items():
                where_clauses.append(f"{field} = %s")
                params.append(value)

        where_clause = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        # GROUP BY clause
        group_clause = f"GROUP BY {', '.join(group_by_fields)}" if group_by_fields else ""

        query = f"""
            SELECT {select_clause}
            FROM {table_name}
            {where_clause}
            {group_clause}
        """

        return (query, params)


# ==================== Base Class Enhancement ====================

class EnhancedVerticalBase:
    """
    Enhanced base class with shared utilities.

    Todos los verticals deberían heredar de esto, no copiar código.
    """

    def __init__(self):
        # Shared utilities
        self.validators = ValidationHelpers()
        self.financial = FinancialCalculator()
        self.report_builder = ReportBuilder()

    def create_dal(self, table_name: str, id_column: str = "id") -> VerticalDAL:
        """Create a DAL instance for a table."""
        return VerticalDAL(table_name, id_column)

    def create_status_machine(self, transitions: Dict[str, List[str]]) -> StatusMachine:
        """Create a status machine."""
        return StatusMachine(transitions)

    def log_operation(self, operation: str, entity: str, entity_id: Any, details: Optional[Dict] = None):
        """Shared logging."""
        logger.info(
            f"[{self.vertical_id}] {operation} {entity}:{entity_id}",
            extra={"details": details or {}}
        )

    def handle_error(self, operation: str, error: Exception):
        """Shared error handling."""
        logger.error(
            f"[{self.vertical_id}] Error in {operation}: {error}",
            exc_info=True
        )
        raise


# ==================== Composable Mixins ====================

class AuditMixin:
    """
    Mixin for audit trail functionality.

    Usar composición, no herencia múltiple si es posible.
    """

    def create_audit_log(
        self,
        company_id: str,
        action: str,
        entity_type: str,
        entity_id: int,
        user_id: Optional[int] = None,
        changes: Optional[Dict[str, Any]] = None
    ):
        """Create audit log entry."""
        execute_query(
            """
            INSERT INTO audit_logs (
                company_id, action, entity_type, entity_id,
                user_id, changes, created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
            """,
            (
                company_id,
                action,
                entity_type,
                entity_id,
                user_id,
                json.dumps(changes) if changes else None
            )
        )


class NotificationMixin:
    """
    Mixin for notifications.

    Todos los verticals pueden notificar, no duplicar código.
    """

    def send_notification(
        self,
        company_id: str,
        notification_type: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Send notification (email, webhook, etc.)."""
        # TODO: Integrate with notification service
        logger.info(f"Notification [{notification_type}] for {company_id}: {message}")


# ==================== Usage Example ====================

"""
Cómo usar shared logic en un vertical:

class CPGRetailVertical(VerticalBase, EnhancedVerticalBase):
    def __init__(self):
        super().__init__()

        # Usar DAL compartido, no duplicar código
        self.pos_dal = self.create_dal("cpg_pos")
        self.consignment_dal = self.create_dal("cpg_consignment")

        # Usar state machine compartido
        self.consignment_sm = self.create_status_machine({
            "pending": ["sold", "returned"],
            "sold": ["paid", "partial"],
            "partial": ["paid"],
            "paid": []
        })

    async def create_pos(self, company_id: str, data: Dict[str, Any]):
        # ✅ Usar DAL compartido
        return self.pos_dal.create(company_id, data)

    async def mark_consignment_sold(self, company_id: str, consignment_id: int):
        # ✅ Validar transición con state machine compartido
        current = await self.consignment_dal.get(company_id, consignment_id)
        self.consignment_sm.validate_transition(current["status"], "sold")

        # ✅ Actualizar con DAL compartido
        return self.consignment_dal.update(
            company_id,
            consignment_id,
            {"status": "sold", "fecha_venta": "NOW()"}
        )
"""
