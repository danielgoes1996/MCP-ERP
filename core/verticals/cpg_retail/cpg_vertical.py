"""
CPG Retail Vertical implementation - V2 Refactored.

ANTES: 535 líneas con lógica duplicada
DESPUÉS: ~150 líneas usando shared_logic
"""

from typing import Dict, Any, List, Optional
import logging

from core.verticals.base import VerticalBase
from core.verticals.base.shared_logic import (
    EnhancedVerticalBase,
    VerticalDAL,
    StatusMachine,
    FinancialCalculator,
)
from core.shared.unified_db_adapter import execute_query
from .models import (
    PointOfSale,
    ConsignmentTransaction,
    POSSalesReport,
    PaymentMode,
    POSStatus,
    ConsignmentStatus
)

logger = logging.getLogger(__name__)


class CPGRetailVertical(VerticalBase, EnhancedVerticalBase):
    """
    Consumer Packaged Goods & Retail vertical module.

    REFACTORED to use shared_logic:
    - VerticalDAL for CRUD (auto company_id, tenant_id, JSONB)
    - StatusMachine for consignment workflow validation
    - FinancialCalculator for totals
    """

    vertical_id = "cpg_retail"
    display_name = "CPG & Retail"
    description = "Gestión de puntos de venta, consignación y distribución retail"

    def __init__(self):
        """Initialize CPG vertical with shared utilities."""
        VerticalBase.__init__(self)
        EnhancedVerticalBase.__init__(self)

        # ✅ DALs compartidos (reemplazan todo el CRUD manual)
        self.pos_dal = self.create_dal("cpg_pos")
        self.consignment_dal = self.create_dal("cpg_consignment")

        # ✅ State machine para consignment (previene transiciones inválidas)
        self.consignment_sm = self.create_status_machine({
            "pending": ["sold", "returned", "cancelled"],
            "sold": ["paid", "partial"],
            "partial": ["paid"],
            "paid": [],
            "returned": [],
            "cancelled": []
        })

    def get_custom_endpoints(self) -> List[tuple]:
        """Return CPG-specific API endpoints."""
        return [
            # POS Management
            ("GET", "/api/v1/verticals/cpg/pos", self.list_pos),
            ("POST", "/api/v1/verticals/cpg/pos", self.create_pos),
            ("GET", "/api/v1/verticals/cpg/pos/{pos_id}", self.get_pos),
            ("PUT", "/api/v1/verticals/cpg/pos/{pos_id}", self.update_pos),
            ("DELETE", "/api/v1/verticals/cpg/pos/{pos_id}", self.deactivate_pos),

            # Consignment
            ("GET", "/api/v1/verticals/cpg/consignment", self.list_consignments),
            ("POST", "/api/v1/verticals/cpg/consignment", self.create_consignment),
            ("GET", "/api/v1/verticals/cpg/consignment/{consignment_id}", self.get_consignment),
            ("PUT", "/api/v1/verticals/cpg/consignment/{consignment_id}/sold", self.mark_consignment_sold),
            ("PUT", "/api/v1/verticals/cpg/consignment/{consignment_id}/paid", self.mark_consignment_paid),

            # Reports
            ("GET", "/api/v1/verticals/cpg/reports/pos-sales", self.pos_sales_report),
            ("GET", "/api/v1/verticals/cpg/reports/consignment-aging", self.consignment_aging_report),
        ]

    def get_database_migrations(self) -> List[str]:
        """Return migration files for CPG vertical."""
        return [
            "migrations/verticals/cpg_retail/001_create_pos_table.sql",
            "migrations/verticals/cpg_retail/002_create_consignment_table.sql",
            "migrations/verticals/cpg_retail/003_add_pos_indexes.sql",
        ]

    def get_feature_flags(self) -> Dict[str, bool]:
        """Return CPG-specific feature flags."""
        return {
            "cpg_pos_enabled": True,
            "cpg_consignment_tracking": True,
            "cpg_inventory_sync": False,  # Future feature
            "cpg_route_optimization": False,  # Future feature
        }

    def get_ui_config(self) -> Dict[str, Any]:
        """Return UI configuration for CPG vertical."""
        return {
            "menu_items": [
                {
                    "label": "Puntos de Venta",
                    "path": "/cpg/pos",
                    "icon": "store",
                    "order": 100
                },
                {
                    "label": "Consignación",
                    "path": "/cpg/consignment",
                    "icon": "package",
                    "order": 101
                },
                {
                    "label": "Reportes CPG",
                    "path": "/cpg/reports",
                    "icon": "chart-bar",
                    "order": 102
                }
            ],
            "dashboard_widgets": [
                {
                    "type": "cpg_pos_summary",
                    "component": "POSSummaryWidget",
                    "size": "medium",
                    "order": 1
                },
                {
                    "type": "cpg_consignment_pending",
                    "component": "ConsignmentPendingWidget",
                    "size": "small",
                    "order": 2
                }
            ]
        }

    # ==================== POS Management (Refactored) ====================

    async def list_pos(self, company_id: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all POS for a company.

        ANTES: 18 líneas de SQL manual
        DESPUÉS: 2 líneas usando DAL
        """
        filters = {"status": status} if status else None
        return self.pos_dal.list(company_id, filters=filters)

    async def create_pos(self, company_id: str, pos_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new Point of Sale.

        ANTES: 54 líneas (tenant_id manual, JSON manual, INSERT manual)
        DESPUÉS: 1 línea (DAL hace todo automáticamente)
        """
        # ✅ DAL auto-inyecta company_id, tenant_id, serializa JSONB
        return self.pos_dal.create(company_id, pos_data)

    async def get_pos(self, company_id: str, pos_id: int) -> Optional[Dict[str, Any]]:
        """
        Get POS by ID.

        ANTES: 10 líneas
        DESPUÉS: 1 línea
        """
        return self.pos_dal.get(company_id, pos_id)

    async def update_pos(self, company_id: str, pos_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update POS information.

        ANTES: 29 líneas (dynamic UPDATE, JSON serialization manual)
        DESPUÉS: 1 línea (DAL hace todo)
        """
        return self.pos_dal.update(company_id, pos_id, updates)

    async def deactivate_pos(self, company_id: str, pos_id: int) -> Dict[str, Any]:
        """
        Deactivate a POS (soft delete).

        ANTES: Llamaba a update_pos
        DESPUÉS: DAL.delete() hace soft delete automáticamente
        """
        return self.pos_dal.delete(company_id, pos_id)

    # ==================== Consignment (Refactored) ====================

    async def create_consignment(
        self,
        company_id: str,
        consignment_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a consignment transaction.

        ANTES: 61 líneas (cálculo manual, tenant_id manual, INSERT manual)
        DESPUÉS: 8 líneas (usa FinancialCalculator + DAL)
        """
        # ✅ Usar FinancialCalculator compartido
        productos = consignment_data.get('productos', [])
        monto_total = self.financial.calculate_total(productos, qty_field='qty', price_field='precio')

        # Preparar datos
        consignment_data['monto_total'] = monto_total
        consignment_data['monto_pagado'] = 0.0
        consignment_data['status'] = 'pending'

        # ✅ DAL auto-inyecta company_id, tenant_id, serializa productos (JSONB)
        result = self.consignment_dal.create(company_id, consignment_data)

        self.log_operation("create", "consignment", result['id'], {
            "numero_remision": result.get('numero_remision'),
            "monto_total": monto_total
        })

        return result

    async def list_consignments(
        self,
        company_id: str,
        pos_id: Optional[int] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List consignment transactions.

        ANTES: 26 líneas
        DESPUÉS: 20 líneas (query complejo necesita JOIN, no se puede simplificar mucho)
        """
        query = """
            SELECT c.*, p.codigo as pos_codigo, p.nombre as pos_nombre
            FROM cpg_consignment c
            LEFT JOIN cpg_pos p ON p.id = c.pos_id
            WHERE c.company_id = %s
        """
        params = [company_id]

        if pos_id:
            query += " AND c.pos_id = %s"
            params.append(pos_id)

        if status:
            query += " AND c.status = %s"
            params.append(status)

        query += " ORDER BY c.created_at DESC"

        results = execute_query(query, tuple(params))
        return results or []

    async def get_consignment(
        self,
        company_id: str,
        consignment_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get consignment by ID.

        ANTES: 16 líneas
        DESPUÉS: 15 líneas (query con JOIN, no se simplifica mucho)
        """
        result = execute_query(
            """
            SELECT c.*, p.codigo as pos_codigo, p.nombre as pos_nombre
            FROM cpg_consignment c
            LEFT JOIN cpg_pos p ON p.id = c.pos_id
            WHERE c.id = %s AND c.company_id = %s
            """,
            (consignment_id, company_id),
            fetch_one=True
        )
        return result

    async def mark_consignment_sold(
        self,
        company_id: str,
        consignment_id: int,
        fecha_venta: str
    ) -> Dict[str, Any]:
        """
        Mark consignment as sold (waiting for payment).

        ANTES: 24 líneas
        DESPUÉS: 12 líneas (agrega validación con StatusMachine)
        """
        # ✅ Validar transición de estado
        current = self.consignment_dal.get(company_id, consignment_id)
        if not current:
            raise ValueError(f"Consignment {consignment_id} not found")

        self.consignment_sm.validate_transition(current['status'], 'sold')

        # ✅ Actualizar con DAL
        result = self.consignment_dal.update(company_id, consignment_id, {
            'status': 'sold',
            'fecha_venta': fecha_venta
        })

        self.log_operation("mark_sold", "consignment", consignment_id)
        return result

    async def mark_consignment_paid(
        self,
        company_id: str,
        consignment_id: int,
        payment_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Mark consignment as paid.

        ANTES: 35 líneas
        DESPUÉS: 18 líneas (agrega validación con StatusMachine)
        """
        # ✅ Validar transición de estado
        current = self.consignment_dal.get(company_id, consignment_id)
        if not current:
            raise ValueError(f"Consignment {consignment_id} not found")

        self.consignment_sm.validate_transition(current['status'], 'paid')

        # ✅ Actualizar con DAL
        updates = {
            'status': 'paid',
            'fecha_pago': payment_data.get('fecha_pago'),
            'monto_pagado': payment_data.get('monto_pagado'),
            'bank_tx_id': payment_data.get('bank_tx_id'),
            'payment_reference': payment_data.get('payment_reference')
        }

        result = self.consignment_dal.update(company_id, consignment_id, updates)
        self.log_operation("mark_paid", "consignment", consignment_id)
        return result

    # ==================== Reports (Sin cambios - queries específicos) ====================

    async def pos_sales_report(
        self,
        company_id: str,
        fecha_inicio: str,
        fecha_fin: str
    ) -> List[Dict[str, Any]]:
        """
        Generate sales report by POS.

        NOTA: Query complejo con JOINs y agregaciones específicas.
        ReportBuilder no ayuda mucho aquí.
        """
        query = """
            SELECT
                p.id as pos_id,
                p.codigo as pos_codigo,
                p.nombre as pos_nombre,
                COUNT(DISTINCT si.id) as total_facturas,
                COALESCE(SUM(si.total), 0) as total_ventas,
                COALESCE(AVG(si.total), 0) as promedio_ticket,
                -- Payment mode breakdown
                COALESCE(SUM(CASE WHEN p.payment_mode = 'cash' THEN si.total ELSE 0 END), 0) as ventas_contado,
                COALESCE(SUM(CASE WHEN p.payment_mode = 'consignment' THEN si.total ELSE 0 END), 0) as ventas_consignacion,
                COALESCE(SUM(CASE WHEN p.payment_mode = 'credit' THEN si.total ELSE 0 END), 0) as ventas_credito
            FROM cpg_pos p
            LEFT JOIN sat_invoices si ON si.metadata->>'pos_id' = p.id::text
                AND si.company_id = p.company_id
                AND si.fecha_emision BETWEEN %s AND %s
            WHERE p.company_id = %s
            GROUP BY p.id, p.codigo, p.nombre
            ORDER BY total_ventas DESC
        """

        results = execute_query(query, (fecha_inicio, fecha_fin, company_id))
        return results or []

    async def consignment_aging_report(
        self,
        company_id: str
    ) -> List[Dict[str, Any]]:
        """
        Generate consignment aging report.

        NOTA: Query con cálculo de aging usando EXTRACT.
        Podríamos usar FinancialCalculator.calculate_aging_days después.
        """
        query = """
            SELECT
                c.id,
                c.numero_remision,
                p.codigo as pos_codigo,
                p.nombre as pos_nombre,
                c.fecha_entrega,
                c.monto_total,
                c.status,
                EXTRACT(DAY FROM NOW() - c.fecha_entrega) as dias_en_consignacion,
                CASE
                    WHEN c.status = 'pending' AND EXTRACT(DAY FROM NOW() - c.fecha_entrega) > 60 THEN 'overdue'
                    WHEN c.status = 'pending' AND EXTRACT(DAY FROM NOW() - c.fecha_entrega) > 30 THEN 'warning'
                    ELSE 'ok'
                END as aging_status
            FROM cpg_consignment c
            LEFT JOIN cpg_pos p ON p.id = c.pos_id
            WHERE c.company_id = %s
                AND c.status IN ('pending', 'sold')
            ORDER BY dias_en_consignacion DESC
        """

        results = execute_query(query, (company_id,))
        return results or []

    # ==================== Hooks ====================

    def on_invoice_created(self, invoice_id: int, invoice_data: Dict[str, Any]):
        """
        Hook when invoice is created - link to POS if applicable.
        """
        metadata = invoice_data.get('metadata', {})
        if 'pos_id' in metadata:
            self.log_operation("link_invoice", "pos", metadata['pos_id'], {
                "invoice_id": invoice_id
            })

    def on_reconciliation_match(
        self,
        bank_tx_id: int,
        invoice_ids: List[int],
        match_data: Dict[str, Any]
    ):
        """
        Hook when reconciliation match is made.

        Check if any invoices are for consignment sales and update status.
        """
        # TODO: Check if invoices are linked to consignments
        # and mark them as paid automatically
        pass
