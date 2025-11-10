#!/usr/bin/env python3
"""
Motor de Reportes Financieros Automáticos
Genera insights derivados automáticamente para copiloto financiero
"""
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Any
from dataclasses import dataclass
import json

@dataclass
class FinancialInsight:
    """Insight financiero con metadatos"""
    title: str
    description: str
    value: float
    category: str
    severity: str  # info, warning, critical
    action_required: bool
    details: Dict[str, Any]

class FinancialReportsEngine:
    def __init__(self, db_path: str = "unified_mcp_system.db"):
        self.db_path = db_path

    def _get_connection(self):
        """Obtener conexión a la base de datos"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def generate_tax_deductibility_report(self) -> Dict[str, Any]:
        """
        Reporte de deducibilidad fiscal automático
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Gastos deducibles por categoría
        cursor.execute("""
            SELECT
                category_auto,
                subcategory,
                COUNT(*) as transaction_count,
                ROUND(SUM(ABS(amount)), 2) as total_amount,
                ROUND(SUM(iva_amount), 2) as total_iva,
                ROUND(AVG(ABS(amount)), 2) as avg_amount
            FROM bank_movements
            WHERE account_id IN (7, 11)
                AND tax_deductible = 1
                AND movement_kind = 'Gasto'
            GROUP BY category_auto, subcategory
            ORDER BY total_amount DESC
        """)

        deductible_expenses = cursor.fetchall()

        # Gastos que requieren factura
        cursor.execute("""
            SELECT COUNT(*) as pending_receipts, SUM(ABS(amount)) as pending_amount
            FROM bank_movements
            WHERE account_id IN (7, 11)
                AND requires_receipt = 1
                AND reconciliation_status = 'pending'
                AND movement_kind = 'Gasto'
        """)

        pending_receipts = cursor.fetchone()

        # Total deducible
        cursor.execute("""
            SELECT SUM(ABS(amount)) as total_deductible, SUM(iva_amount) as total_iva_acreditable
            FROM bank_movements
            WHERE account_id IN (7, 11) AND tax_deductible = 1
        """)

        totals = cursor.fetchone()

        conn.close()

        return {
            "report_type": "tax_deductibility",
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total_deductible": totals['total_deductible'] or 0,
                "total_iva_acreditable": totals['total_iva_acreditable'] or 0,
                "pending_receipts_count": pending_receipts['pending_receipts'] or 0,
                "pending_receipts_amount": pending_receipts['pending_amount'] or 0
            },
            "deductible_by_category": [dict(row) for row in deductible_expenses],
            "compliance_status": "needs_attention" if pending_receipts['pending_receipts'] > 0 else "good"
        }

    def generate_cash_flow_analysis(self) -> Dict[str, Any]:
        """
        Análisis de flujo de efectivo por categorías
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Flujo por tipo de movimiento
        cursor.execute("""
            SELECT
                cash_flow_category,
                movement_kind,
                COUNT(*) as transaction_count,
                ROUND(SUM(CASE WHEN movement_kind = 'Ingreso' THEN amount ELSE 0 END), 2) as total_inflows,
                ROUND(SUM(CASE WHEN movement_kind = 'Gasto' THEN ABS(amount) ELSE 0 END), 2) as total_outflows
            FROM bank_movements
            WHERE account_id IN (7, 11)
                AND display_type != 'balance_inicial'
            GROUP BY cash_flow_category, movement_kind
            ORDER BY cash_flow_category, movement_kind
        """)

        cash_flow_data = cursor.fetchall()

        # Balance inicial y final
        cursor.execute("""
            SELECT
                MIN(running_balance) as min_balance,
                MAX(running_balance) as max_balance,
                (SELECT running_balance FROM bank_movements WHERE account_id IN (7,11) ORDER BY date DESC, id DESC LIMIT 1) as final_balance
            FROM bank_movements
            WHERE account_id IN (7, 11)
        """)

        balance_info = cursor.fetchone()

        # Tendencia semanal
        cursor.execute("""
            SELECT
                strftime('%Y-%W', date) as week,
                ROUND(SUM(CASE WHEN movement_kind = 'Ingreso' THEN amount ELSE 0 END), 2) as weekly_income,
                ROUND(SUM(CASE WHEN movement_kind = 'Gasto' THEN ABS(amount) ELSE 0 END), 2) as weekly_expenses,
                ROUND(SUM(CASE WHEN movement_kind = 'Ingreso' THEN amount ELSE -ABS(amount) END), 2) as net_flow
            FROM bank_movements
            WHERE account_id IN (7, 11)
                AND display_type != 'balance_inicial'
            GROUP BY strftime('%Y-%W', date)
            ORDER BY week
        """)

        weekly_trends = cursor.fetchall()

        conn.close()

        return {
            "report_type": "cash_flow_analysis",
            "generated_at": datetime.now().isoformat(),
            "balance_summary": dict(balance_info),
            "cash_flow_by_category": [dict(row) for row in cash_flow_data],
            "weekly_trends": [dict(row) for row in weekly_trends]
        }

    def detect_financial_anomalies(self) -> List[FinancialInsight]:
        """
        Detecta anomalías financieras y genera insights
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        insights = []

        # 1. Gastos inusuales por monto
        cursor.execute("""
            SELECT description, amount, category_auto, date
            FROM bank_movements
            WHERE account_id IN (7, 11)
                AND unusual_amount = 1
                AND movement_kind = 'Gasto'
            ORDER BY ABS(amount) DESC
            LIMIT 5
        """)

        unusual_expenses = cursor.fetchall()
        if unusual_expenses:
            insights.append(FinancialInsight(
                title="Gastos de Monto Inusual Detectados",
                description=f"Se detectaron {len(unusual_expenses)} gastos con montos inusuales que requieren revisión",
                value=sum(abs(row['amount']) for row in unusual_expenses),
                category="expense_anomaly",
                severity="warning",
                action_required=True,
                details={"transactions": [dict(row) for row in unusual_expenses]}
            ))

        # 2. Categorías sin clasificar
        cursor.execute("""
            SELECT COUNT(*) as unclassified_count, SUM(ABS(amount)) as unclassified_amount
            FROM bank_movements
            WHERE account_id IN (7, 11)
                AND category_auto = 'Sin categoría'
                AND movement_kind = 'Gasto'
        """)

        unclassified = cursor.fetchone()
        if unclassified['unclassified_count'] > 0:
            insights.append(FinancialInsight(
                title="Transacciones Sin Clasificar",
                description=f"{unclassified['unclassified_count']} transacciones necesitan clasificación manual",
                value=unclassified['unclassified_amount'] or 0,
                category="classification",
                severity="info",
                action_required=True,
                details={"count": unclassified['unclassified_count']}
            ))

        # 3. Facturas pendientes de alto valor
        cursor.execute("""
            SELECT COUNT(*) as pending_count, SUM(ABS(amount)) as pending_amount
            FROM bank_movements
            WHERE account_id IN (7, 11)
                AND requires_receipt = 1
                AND reconciliation_status = 'pending'
                AND ABS(amount) > 1000
        """)

        pending_receipts = cursor.fetchone()
        if pending_receipts['pending_count'] > 0:
            insights.append(FinancialInsight(
                title="Facturas Pendientes de Alto Valor",
                description=f"{pending_receipts['pending_count']} gastos >$1,000 sin factura",
                value=pending_receipts['pending_amount'] or 0,
                category="compliance",
                severity="critical",
                action_required=True,
                details={"count": pending_receipts['pending_count']}
            ))

        # 4. Análisis de tendencia de gastos
        cursor.execute("""
            SELECT
                strftime('%Y-%m', date) as month,
                SUM(ABS(amount)) as monthly_expenses
            FROM bank_movements
            WHERE account_id IN (7, 11)
                AND movement_kind = 'Gasto'
                AND date >= date('now', '-3 months')
            GROUP BY strftime('%Y-%m', date)
            ORDER BY month
        """)

        monthly_expenses = cursor.fetchall()
        if len(monthly_expenses) >= 2:
            latest = monthly_expenses[-1]['monthly_expenses']
            previous = monthly_expenses[-2]['monthly_expenses']
            change_pct = ((latest - previous) / previous * 100) if previous > 0 else 0

            if abs(change_pct) > 20:
                insights.append(FinancialInsight(
                    title="Cambio Significativo en Gastos",
                    description=f"Gastos {'aumentaron' if change_pct > 0 else 'disminuyeron'} {abs(change_pct):.1f}% vs mes anterior",
                    value=change_pct,
                    category="trend",
                    severity="warning" if abs(change_pct) > 50 else "info",
                    action_required=abs(change_pct) > 50,
                    details={"current_month": latest, "previous_month": previous}
                ))

        conn.close()
        return insights

    def generate_expense_optimization_suggestions(self) -> List[Dict[str, Any]]:
        """
        Genera sugerencias de optimización de gastos
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        suggestions = []

        # 1. Categorías con mayor gasto que podrían optimizarse
        cursor.execute("""
            SELECT
                category_auto,
                subcategory,
                COUNT(*) as transaction_count,
                ROUND(SUM(ABS(amount)), 2) as total_spent,
                ROUND(AVG(ABS(amount)), 2) as avg_amount
            FROM bank_movements
            WHERE account_id IN (7, 11)
                AND movement_kind = 'Gasto'
                AND category_auto != 'Sin categoría'
            GROUP BY category_auto, subcategory
            HAVING total_spent > 1000
            ORDER BY total_spent DESC
        """)

        high_spend_categories = cursor.fetchall()

        for category in high_spend_categories[:3]:  # Top 3
            suggestions.append({
                "type": "cost_optimization",
                "category": category['category_auto'],
                "subcategory": category['subcategory'],
                "current_spend": category['total_spent'],
                "transaction_count": category['transaction_count'],
                "suggestion": f"Revisar gastos en {category['subcategory']} - ${category['total_spent']:,.2f} en {category['transaction_count']} transacciones",
                "potential_savings": category['total_spent'] * 0.15  # Asume 15% de ahorro potencial
            })

        # 2. Gastos recurrentes que podrían negociarse
        cursor.execute("""
            SELECT
                cleaned_description,
                COUNT(*) as frequency,
                ROUND(SUM(ABS(amount)), 2) as total_amount,
                ROUND(AVG(ABS(amount)), 2) as avg_amount
            FROM bank_movements
            WHERE account_id IN (7, 11)
                AND movement_kind = 'Gasto'
            GROUP BY cleaned_description
            HAVING frequency >= 2 AND avg_amount > 500
            ORDER BY total_amount DESC
        """)

        recurring_expenses = cursor.fetchall()

        for expense in recurring_expenses[:2]:  # Top 2
            suggestions.append({
                "type": "recurring_negotiation",
                "description": expense['cleaned_description'],
                "frequency": expense['frequency'],
                "total_amount": expense['total_amount'],
                "suggestion": f"Negociar precio para {expense['cleaned_description']} - gasto recurrente de ${expense['avg_amount']:,.2f}",
                "potential_savings": expense['total_amount'] * 0.10
            })

        conn.close()
        return suggestions

    def generate_comprehensive_financial_report(self) -> Dict[str, Any]:
        """
        Genera un reporte financiero comprensivo
        """
        return {
            "report_id": f"financial_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "generated_at": datetime.now().isoformat(),
            "tax_deductibility": self.generate_tax_deductibility_report(),
            "cash_flow_analysis": self.generate_cash_flow_analysis(),
            "financial_insights": [insight.__dict__ for insight in self.detect_financial_anomalies()],
            "optimization_suggestions": self.generate_expense_optimization_suggestions()
        }

# Test del motor de reportes
if __name__ == "__main__":
    print("📊 TESTING FINANCIAL REPORTS ENGINE")
    print("=" * 60)

    engine = FinancialReportsEngine()

    # Test reporte fiscal
    print("\n💼 TAX DEDUCTIBILITY REPORT:")
    tax_report = engine.generate_tax_deductibility_report()
    print(f"   Total Deducible: ${tax_report['summary']['total_deductible']:,.2f}")
    print(f"   IVA Acreditable: ${tax_report['summary']['total_iva_acreditable']:,.2f}")
    print(f"   Facturas Pendientes: {tax_report['summary']['pending_receipts_count']}")

    # Test insights
    print("\n🔍 FINANCIAL INSIGHTS:")
    insights = engine.detect_financial_anomalies()
    for insight in insights:
        print(f"   {insight.severity.upper()}: {insight.title}")
        print(f"   └─ {insight.description}")

    # Test sugerencias
    print("\n💡 OPTIMIZATION SUGGESTIONS:")
    suggestions = engine.generate_expense_optimization_suggestions()
    for suggestion in suggestions[:3]:
        print(f"   📈 {suggestion['type']}: {suggestion['suggestion']}")
        print(f"   └─ Potential savings: ${suggestion['potential_savings']:,.2f}")

    print(f"\n🎯 Generated comprehensive report with {len(insights)} insights and {len(suggestions)} suggestions")