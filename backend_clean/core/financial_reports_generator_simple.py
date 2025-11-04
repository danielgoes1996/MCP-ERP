"""
Generador simplificado de reportes fiscales.
Adaptado a la estructura actual de la base de datos.
"""

import logging
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger(__name__)


class FinancialReportsGenerator:
    """Generador simplificado de reportes fiscales."""

    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id

    def generate_resumen_fiscal(self, year: int, month: int) -> Dict[str, Any]:
        """
        Genera resumen fiscal simplificado del periodo.
        """
        import sqlite3

        try:
            # Conectar a la BD
            conn = sqlite3.connect('unified_mcp_system.db')
            cursor = conn.cursor()

            # Obtener totales del mes
            periodo_str = f"{year}-{str(month).zfill(2)}"

            cursor.execute("""
                SELECT
                    COUNT(*) as total_gastos,
                    COALESCE(SUM(amount), 0) as monto_total,
                    SUM(CASE WHEN cfdi_status = 'factura_lista' THEN 1 ELSE 0 END) as con_cfdi,
                    SUM(CASE WHEN cfdi_status != 'factura_lista' THEN 1 ELSE 0 END) as sin_cfdi
                FROM expense_records
                WHERE tenant_id = ?
                AND strftime('%Y-%m', date) = ?
            """, (self.tenant_id, periodo_str))

            row = cursor.fetchone()
            total_gastos = row[0] or 0
            monto_total = float(row[1] or 0)
            con_cfdi = row[2] or 0
            sin_cfdi = row[3] or 0

            # Obtener gastos por categoría
            cursor.execute("""
                SELECT
                    category,
                    COUNT(*) as cantidad,
                    COALESCE(SUM(amount), 0) as total
                FROM expense_records
                WHERE tenant_id = ?
                AND strftime('%Y-%m', date) = ?
                GROUP BY category
                ORDER BY total DESC
                LIMIT 5
            """, (self.tenant_id, periodo_str))

            categorias = []
            for row in cursor:
                categorias.append({
                    'slug': row[0] or 'sin_categoria',
                    'cantidad': row[1],
                    'total': float(row[2])
                })

            conn.close()

            # Generar alertas simples
            alertas = []
            if sin_cfdi > 0:
                alertas.append({
                    'tipo': 'info',
                    'mensaje': f"{sin_cfdi} gastos sin CFDI",
                    'recomendacion': 'Solicitar facturas para deducibilidad fiscal'
                })

            # Calcular IVA aproximado (16% del total)
            iva_estimado = monto_total * 0.16 / 1.16
            subtotal_estimado = monto_total - iva_estimado

            return {
                'periodo': {
                    'año': year,
                    'mes': month
                },
                'totales': {
                    'gastos_total': monto_total,
                    'subtotal': subtotal_estimado,
                    'iva_total': iva_estimado,
                    'iva_acreditable': iva_estimado * 0.8,  # Estimado 80% acreditable
                    'iva_no_acreditable': iva_estimado * 0.2
                },
                'cfdi': {
                    'con_cfdi': con_cfdi,
                    'sin_cfdi': sin_cfdi,
                    'porcentaje_cfdi': (con_cfdi / total_gastos * 100) if total_gastos > 0 else 0
                },
                'categorias': categorias,
                'revision': {
                    'total': 0,
                    'monto': 0,
                    'razones': {}
                },
                'alertas': alertas,
                'generado_en': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error generando resumen fiscal: {e}")
            # Retornar datos dummy en caso de error
            return {
                'periodo': {'año': year, 'mes': month},
                'totales': {
                    'gastos_total': 0,
                    'subtotal': 0,
                    'iva_total': 0,
                    'iva_acreditable': 0,
                    'iva_no_acreditable': 0
                },
                'cfdi': {
                    'con_cfdi': 0,
                    'sin_cfdi': 0,
                    'porcentaje_cfdi': 0
                },
                'categorias': [],
                'revision': {'total': 0, 'monto': 0, 'razones': {}},
                'alertas': [],
                'generado_en': datetime.now().isoformat()
            }