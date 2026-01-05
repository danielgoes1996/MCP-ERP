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

        # 🆕 NEW: Field Sales DALs
        self.productos_dal = self.create_dal("cpg_productos")
        self.routes_dal = self.create_dal("cpg_routes")
        self.visits_dal = self.create_dal("cpg_visits")
        self.delivery_items_dal = self.create_dal("cpg_delivery_items")

        # ✅ State machine para consignment (previene transiciones inválidas)
        self.consignment_sm = self.create_status_machine({
            "pending": ["sold", "returned", "cancelled"],
            "sold": ["paid", "partial"],
            "partial": ["paid"],
            "paid": [],
            "returned": [],
            "cancelled": []
        })

        # 🆕 NEW: State machine para visits
        self.visit_sm = self.create_status_machine({
            "scheduled": ["completed", "cancelled", "no_show", "rescheduled"],
            "completed": [],
            "cancelled": ["scheduled"],  # Can reschedule
            "no_show": ["scheduled"],
            "rescheduled": ["completed", "cancelled", "no_show"]
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

            # 🆕 Products
            ("GET", "/api/v1/verticals/cpg/productos", self.list_productos),
            ("POST", "/api/v1/verticals/cpg/productos", self.create_producto),
            ("GET", "/api/v1/verticals/cpg/productos/{producto_id}", self.get_producto),
            ("PUT", "/api/v1/verticals/cpg/productos/{producto_id}", self.update_producto),
            ("DELETE", "/api/v1/verticals/cpg/productos/{producto_id}", self.deactivate_producto),

            # 🆕 Routes
            ("GET", "/api/v1/verticals/cpg/routes", self.list_routes),
            ("POST", "/api/v1/verticals/cpg/routes", self.create_route),
            ("GET", "/api/v1/verticals/cpg/routes/{route_id}", self.get_route),
            ("PUT", "/api/v1/verticals/cpg/routes/{route_id}", self.update_route),
            ("DELETE", "/api/v1/verticals/cpg/routes/{route_id}", self.deactivate_route),

            # 🆕 Visits
            ("GET", "/api/v1/verticals/cpg/visits", self.list_visits),
            ("POST", "/api/v1/verticals/cpg/visits", self.create_visit),
            ("GET", "/api/v1/verticals/cpg/visits/{visit_id}", self.get_visit),
            ("PUT", "/api/v1/verticals/cpg/visits/{visit_id}", self.update_visit),
            ("POST", "/api/v1/verticals/cpg/visits/{visit_id}/checkin", self.visit_checkin),
            ("POST", "/api/v1/verticals/cpg/visits/{visit_id}/checkout", self.visit_checkout),
            ("POST", "/api/v1/verticals/cpg/visits/{visit_id}/signature", self.visit_signature),
            ("POST", "/api/v1/verticals/cpg/visits/{visit_id}/complete", self.complete_visit),

            # Reports
            ("GET", "/api/v1/verticals/cpg/reports/pos-sales", self.pos_sales_report),
            ("GET", "/api/v1/verticals/cpg/reports/consignment-aging", self.consignment_aging_report),
            ("GET", "/api/v1/verticals/cpg/reports/route-performance", self.route_performance_report),
            ("GET", "/api/v1/verticals/cpg/reports/visit-compliance", self.visit_compliance_report),
            ("GET", "/api/v1/verticals/cpg/reports/product-performance", self.product_performance_report),
            ("GET", "/api/v1/verticals/cpg/reports/inventory-variance", self.inventory_variance_report),
        ]

    def get_database_migrations(self) -> List[str]:
        """Return migration files for CPG vertical."""
        return [
            "migrations/verticals/cpg_retail/001_create_pos_table.sql",
            "migrations/verticals/cpg_retail/002_create_consignment_table.sql",
            "migrations/verticals/cpg_retail/003_add_pos_indexes.sql",
            "migrations/verticals/cpg_retail/004_field_sales_system.sql",
        ]

    def get_feature_flags(self) -> Dict[str, bool]:
        """Return CPG-specific feature flags."""
        return {
            "cpg_pos_enabled": True,
            "cpg_consignment_tracking": True,
            "cpg_field_sales": True,  # 🆕 NEW
            "cpg_route_management": True,  # 🆕 NEW
            "cpg_gps_tracking": True,  # 🆕 NEW
            "cpg_digital_signature": True,  # 🆕 NEW
            "cpg_inventory_audit": True,  # 🆕 NEW
            "cpg_route_optimization": False,  # Future: AI-based route optimization
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
                    "label": "Productos",  # 🆕 NEW
                    "path": "/cpg/productos",
                    "icon": "box",
                    "order": 102
                },
                {
                    "label": "Rutas",  # 🆕 NEW
                    "path": "/cpg/routes",
                    "icon": "map",
                    "order": 103
                },
                {
                    "label": "Visitas",  # 🆕 NEW
                    "path": "/cpg/visits",
                    "icon": "map-pin",
                    "order": 104
                },
                {
                    "label": "Reportes CPG",
                    "path": "/cpg/reports",
                    "icon": "chart-bar",
                    "order": 105
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
                },
                {
                    "type": "cpg_visits_today",  # 🆕 NEW
                    "component": "VisitsTodayWidget",
                    "size": "medium",
                    "order": 3
                },
                {
                    "type": "cpg_route_compliance",  # 🆕 NEW
                    "component": "RouteComplianceWidget",
                    "size": "small",
                    "order": 4
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

    # ==================== Products Management (🆕 NEW) ====================

    async def list_productos(self, company_id: str, disponible: Optional[bool] = None) -> List[Dict[str, Any]]:
        """List all products for a company."""
        filters = {"disponible": disponible} if disponible is not None else None
        return self.productos_dal.list(company_id, filters=filters)

    async def create_producto(self, company_id: str, producto_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new product."""
        return self.productos_dal.create(company_id, producto_data)

    async def get_producto(self, company_id: str, producto_id: int) -> Optional[Dict[str, Any]]:
        """Get product by ID."""
        return self.productos_dal.get(company_id, producto_id)

    async def update_producto(self, company_id: str, producto_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update product information."""
        return self.productos_dal.update(company_id, producto_id, updates)

    async def deactivate_producto(self, company_id: str, producto_id: int) -> Dict[str, Any]:
        """Deactivate a product (soft delete)."""
        return self.productos_dal.update(company_id, producto_id, {"disponible": False})

    # ==================== Routes Management (🆕 NEW) ====================

    async def list_routes(self, company_id: str, status: Optional[str] = None, vendedor_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """List all routes for a company."""
        filters = {}
        if status:
            filters["status"] = status
        if vendedor_id:
            filters["vendedor_id"] = vendedor_id
        return self.routes_dal.list(company_id, filters=filters if filters else None)

    async def create_route(self, company_id: str, route_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new sales route."""
        return self.routes_dal.create(company_id, route_data)

    async def get_route(self, company_id: str, route_id: int) -> Optional[Dict[str, Any]]:
        """Get route by ID."""
        return self.routes_dal.get(company_id, route_id)

    async def update_route(self, company_id: str, route_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update route information."""
        return self.routes_dal.update(company_id, route_id, updates)

    async def deactivate_route(self, company_id: str, route_id: int) -> Dict[str, Any]:
        """Deactivate a route (soft delete)."""
        return self.routes_dal.delete(company_id, route_id)

    # ==================== Visits Management (🆕 NEW - Complex) ====================

    async def list_visits(
        self,
        company_id: str,
        vendedor_id: Optional[int] = None,
        route_id: Optional[int] = None,
        status: Optional[str] = None,
        fecha_inicio: Optional[str] = None,
        fecha_fin: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List visits with optional filters."""
        query = """
            SELECT v.*,
                   p.codigo as pos_codigo,
                   p.nombre as pos_nombre,
                   r.codigo_ruta,
                   r.nombre_ruta
            FROM cpg_visits v
            LEFT JOIN cpg_pos p ON p.id = v.pos_id
            LEFT JOIN cpg_routes r ON r.id = v.route_id
            WHERE v.company_id = %s
        """
        params = [company_id]

        if vendedor_id:
            query += " AND v.vendedor_id = %s"
            params.append(vendedor_id)

        if route_id:
            query += " AND v.route_id = %s"
            params.append(route_id)

        if status:
            query += " AND v.status = %s"
            params.append(status)

        if fecha_inicio and fecha_fin:
            query += " AND v.fecha_programada BETWEEN %s AND %s"
            params.append(fecha_inicio)
            params.append(fecha_fin)

        query += " ORDER BY v.fecha_programada DESC"

        results = execute_query(query, tuple(params))
        return results or []

    async def create_visit(self, company_id: str, visit_data: Dict[str, Any]) -> Dict[str, Any]:
        """Schedule a new visit."""
        visit_data['status'] = 'scheduled'
        result = self.visits_dal.create(company_id, visit_data)

        # Update POS proxima_visita
        if 'pos_id' in visit_data:
            self.pos_dal.update(company_id, visit_data['pos_id'], {
                'proxima_visita': visit_data.get('fecha_programada')
            })

        self.log_operation("create", "visit", result['id'])
        return result

    async def get_visit(self, company_id: str, visit_id: int) -> Optional[Dict[str, Any]]:
        """Get visit by ID with related data."""
        result = execute_query(
            """
            SELECT v.*,
                   p.codigo as pos_codigo,
                   p.nombre as pos_nombre,
                   r.codigo_ruta,
                   r.nombre_ruta
            FROM cpg_visits v
            LEFT JOIN cpg_pos p ON p.id = v.pos_id
            LEFT JOIN cpg_routes r ON r.id = v.route_id
            WHERE v.id = %s AND v.company_id = %s
            """,
            (visit_id, company_id),
            fetch_one=True
        )
        return result

    async def update_visit(self, company_id: str, visit_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update visit information."""
        return self.visits_dal.update(company_id, visit_id, updates)

    async def visit_checkin(self, company_id: str, visit_id: int, gps_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        GPS check-in at visit location.

        gps_data: {"lat": X, "lng": Y, "accuracy": Z, "timestamp": "..."}
        """
        current = self.visits_dal.get(company_id, visit_id)
        if not current:
            raise ValueError(f"Visit {visit_id} not found")

        result = self.visits_dal.update(company_id, visit_id, {
            'gps_checkin': gps_data,
            'fecha_visita_real': gps_data.get('timestamp')
        })

        self.log_operation("checkin", "visit", visit_id, gps_data)
        return result

    async def visit_checkout(self, company_id: str, visit_id: int, gps_data: Dict[str, Any]) -> Dict[str, Any]:
        """GPS check-out from visit location."""
        result = self.visits_dal.update(company_id, visit_id, {
            'gps_checkout': gps_data
        })

        self.log_operation("checkout", "visit", visit_id, gps_data)
        return result

    async def visit_signature(
        self,
        company_id: str,
        visit_id: int,
        signature_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Upload digital signature.

        signature_data: {
            "firma_digital": "data:image/png;base64,...",
            "firma_nombre": "Juan Pérez",
            "foto_firma_url": "https://..."  # Optional
        }
        """
        result = self.visits_dal.update(company_id, visit_id, signature_data)

        self.log_operation("signature", "visit", visit_id)
        return result

    async def complete_visit(
        self,
        company_id: str,
        visit_id: int,
        completion_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Mark visit as completed with all data.

        completion_data: {
            "productos_entregados": [...],
            "monto_total_entregado": X,
            "monto_cobrado": Y,
            "inventario_contado": {...},
            "diferencia_inventario": {...},
            "observaciones": "...",
            "foto_evidencias": [...]
        }
        """
        # Validate state transition
        current = self.visits_dal.get(company_id, visit_id)
        if not current:
            raise ValueError(f"Visit {visit_id} not found")

        self.visit_sm.validate_transition(current['status'], 'completed')

        # Calculate total entregado usando FinancialCalculator
        productos = completion_data.get('productos_entregados', [])
        if productos:
            monto_total = self.financial.calculate_total(productos, qty_field='qty', price_field='precio')
            completion_data['monto_total_entregado'] = monto_total

        # Mark as completed
        completion_data['status'] = 'completed'

        result = self.visits_dal.update(company_id, visit_id, completion_data)

        # Update POS ultima_visita
        self.pos_dal.update(company_id, current['pos_id'], {
            'ultima_visita': result.get('fecha_visita_real')
        })

        # Create consignment if productos were delivered
        if productos and completion_data.get('monto_total_entregado', 0) > 0:
            await self.create_consignment(company_id, {
                'pos_id': current['pos_id'],
                'visit_id': visit_id,
                'origen_visita': True,
                'numero_remision': f"VISIT-{visit_id}",
                'fecha_entrega': result.get('fecha_visita_real'),
                'productos': productos,
                'monto_total': completion_data['monto_total_entregado'],
                'notas': f"Generado automáticamente desde visita #{visit_id}"
            })

        self.log_operation("complete", "visit", visit_id)
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

    async def route_performance_report(
        self,
        company_id: str,
        route_id: Optional[int] = None,
        vendedor_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate route performance report using cpg_route_performance view.
        """
        query = "SELECT * FROM cpg_route_performance WHERE company_id = %s"
        params = [company_id]

        if route_id:
            query += " AND route_id = %s"
            params.append(route_id)

        if vendedor_id:
            query += " AND vendedor_id = %s"
            params.append(vendedor_id)

        query += " ORDER BY tasa_cumplimiento DESC"

        results = execute_query(query, tuple(params))
        return results or []

    async def visit_compliance_report(
        self,
        company_id: str,
        vendedor_id: Optional[int] = None,
        fecha_inicio: Optional[str] = None,
        fecha_fin: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate visit compliance report using cpg_visit_compliance view.

        Shows visits missing GPS, signature, or inventory data.
        """
        query = "SELECT * FROM cpg_visit_compliance WHERE company_id = %s"
        params = [company_id]

        if vendedor_id:
            query += " AND vendedor_id = %s"
            params.append(vendedor_id)

        if fecha_inicio and fecha_fin:
            query += " AND fecha_visita_real BETWEEN %s AND %s"
            params.append(fecha_inicio)
            params.append(fecha_fin)

        query += " ORDER BY fecha_visita_real DESC"

        results = execute_query(query, tuple(params))
        return results or []

    async def product_performance_report(
        self,
        company_id: str,
        producto_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate product performance report using cpg_product_performance view.

        Shows sales, returns, and sell-through rates per product.
        """
        query = "SELECT * FROM cpg_product_performance WHERE company_id = %s"
        params = [company_id]

        if producto_id:
            query += " AND producto_id = %s"
            params.append(producto_id)

        query += " ORDER BY tasa_venta DESC"

        results = execute_query(query, tuple(params))
        return results or []

    async def inventory_variance_report(
        self,
        company_id: str,
        pos_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate inventory variance report using cpg_inventory_variance view.

        Detects missing or excess inventory.
        """
        query = "SELECT * FROM cpg_inventory_variance WHERE company_id = %s"
        params = [company_id]

        if pos_id:
            query += " AND pos_id = %s"
            params.append(pos_id)

        query += " AND productos_con_faltante > 0 ORDER BY productos_con_faltante DESC"

        results = execute_query(query, tuple(params))
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
