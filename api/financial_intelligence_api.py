#!/usr/bin/env python3
"""
API de Inteligencia Financiera
Endpoints para reportes automáticos y insights de copiloto financiero
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import json

from core.unified_auth import get_current_active_user, User
from core.tenancy_middleware import get_tenancy_context, TenancyContext
from core.financial_reports_engine import FinancialReportsEngine

router = APIRouter(prefix="/financial-intelligence", tags=["Financial Intelligence"])

@router.get("/tax-deductibility-report")
async def get_tax_deductibility_report(
    current_user: User = Depends(get_current_active_user),
    tenancy: TenancyContext = Depends(get_tenancy_context)
) -> Dict[str, Any]:
    """
    Obtiene reporte de deducibilidad fiscal automático
    """
    try:
        engine = FinancialReportsEngine()
        report = engine.generate_tax_deductibility_report()

        return {
            "status": "success",
            "data": report,
            "generated_for_user": current_user.email,
            "tenant_id": tenancy.tenant_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating tax report: {str(e)}")

@router.get("/cash-flow-analysis")
async def get_cash_flow_analysis(
    current_user: User = Depends(get_current_active_user),
    tenancy: TenancyContext = Depends(get_tenancy_context)
) -> Dict[str, Any]:
    """
    Obtiene análisis de flujo de efectivo
    """
    try:
        engine = FinancialReportsEngine()
        analysis = engine.generate_cash_flow_analysis()

        return {
            "status": "success",
            "data": analysis,
            "generated_for_user": current_user.email,
            "tenant_id": tenancy.tenant_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating cash flow analysis: {str(e)}")

@router.get("/financial-insights")
async def get_financial_insights(
    severity: Optional[str] = Query(None, description="Filter by severity: info, warning, critical"),
    current_user: User = Depends(get_current_active_user),
    tenancy: TenancyContext = Depends(get_tenancy_context)
) -> Dict[str, Any]:
    """
    Obtiene insights financieros y anomalías detectadas
    """
    try:
        engine = FinancialReportsEngine()
        insights = engine.detect_financial_anomalies()

        # Filtrar por severidad si se especifica
        if severity:
            insights = [insight for insight in insights if insight.severity == severity]

        return {
            "status": "success",
            "data": {
                "insights": [insight.__dict__ for insight in insights],
                "total_insights": len(insights),
                "action_required_count": len([i for i in insights if i.action_required]),
                "severity_breakdown": {
                    "critical": len([i for i in insights if i.severity == "critical"]),
                    "warning": len([i for i in insights if i.severity == "warning"]),
                    "info": len([i for i in insights if i.severity == "info"])
                }
            },
            "generated_for_user": current_user.email,
            "tenant_id": tenancy.tenant_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating insights: {str(e)}")

@router.get("/optimization-suggestions")
async def get_optimization_suggestions(
    current_user: User = Depends(get_current_active_user),
    tenancy: TenancyContext = Depends(get_tenancy_context)
) -> Dict[str, Any]:
    """
    Obtiene sugerencias de optimización de gastos
    """
    try:
        engine = FinancialReportsEngine()
        suggestions = engine.generate_expense_optimization_suggestions()

        total_potential_savings = sum(s.get('potential_savings', 0) for s in suggestions)

        return {
            "status": "success",
            "data": {
                "suggestions": suggestions,
                "total_suggestions": len(suggestions),
                "total_potential_savings": round(total_potential_savings, 2),
                "categories_analyzed": len(set(s.get('category', '') for s in suggestions))
            },
            "generated_for_user": current_user.email,
            "tenant_id": tenancy.tenant_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating suggestions: {str(e)}")

@router.get("/comprehensive-report")
async def get_comprehensive_financial_report(
    current_user: User = Depends(get_current_active_user),
    tenancy: TenancyContext = Depends(get_tenancy_context)
) -> Dict[str, Any]:
    """
    Obtiene reporte financiero comprensivo con todos los análisis
    """
    try:
        engine = FinancialReportsEngine()
        comprehensive_report = engine.generate_comprehensive_financial_report()

        return {
            "status": "success",
            "data": comprehensive_report,
            "generated_for_user": current_user.email,
            "tenant_id": tenancy.tenant_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating comprehensive report: {str(e)}")

@router.get("/expense-breakdown")
async def get_expense_breakdown(
    period: str = Query("current_month", description="Period: current_month, last_month, current_year"),
    current_user: User = Depends(get_current_active_user),
    tenancy: TenancyContext = Depends(get_tenancy_context)
) -> Dict[str, Any]:
    """
    Obtiene desglose detallado de gastos por período
    """
    try:
        import sqlite3

        # Determinar filtro de fecha
        date_filter = ""
        if period == "current_month":
            date_filter = "AND strftime('%Y-%m', date) = strftime('%Y-%m', 'now')"
        elif period == "last_month":
            date_filter = "AND strftime('%Y-%m', date) = strftime('%Y-%m', 'now', '-1 month')"
        elif period == "current_year":
            date_filter = "AND strftime('%Y', date) = strftime('%Y', 'now')"

        conn = sqlite3.connect('unified_mcp_system.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = f"""
            SELECT
                category_auto,
                subcategory,
                movement_kind,
                COUNT(*) as transaction_count,
                ROUND(SUM(ABS(amount)), 2) as total_amount,
                ROUND(AVG(ABS(amount)), 2) as avg_amount,
                ROUND(SUM(CASE WHEN tax_deductible = 1 THEN ABS(amount) ELSE 0 END), 2) as deductible_amount,
                ROUND(SUM(iva_amount), 2) as total_iva
            FROM bank_movements
            WHERE account_id IN (7, 11)
                AND movement_kind = 'Gasto'
                {date_filter}
            GROUP BY category_auto, subcategory, movement_kind
            ORDER BY total_amount DESC
        """

        cursor.execute(query)
        breakdown = cursor.fetchall()

        # Totales del período
        total_query = f"""
            SELECT
                COUNT(*) as total_transactions,
                ROUND(SUM(ABS(amount)), 2) as total_expenses,
                ROUND(SUM(CASE WHEN tax_deductible = 1 THEN ABS(amount) ELSE 0 END), 2) as total_deductible,
                ROUND(SUM(iva_amount), 2) as total_iva
            FROM bank_movements
            WHERE account_id IN (7, 11)
                AND movement_kind = 'Gasto'
                {date_filter}
        """

        cursor.execute(total_query)
        totals = cursor.fetchone()

        conn.close()

        return {
            "status": "success",
            "data": {
                "period": period,
                "breakdown": [dict(row) for row in breakdown],
                "totals": dict(totals),
                "top_categories": [dict(row) for row in breakdown[:5]]
            },
            "generated_for_user": current_user.email,
            "tenant_id": tenancy.tenant_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating expense breakdown: {str(e)}")

@router.get("/financial-health-score")
async def get_financial_health_score(
    current_user: User = Depends(get_current_active_user),
    tenancy: TenancyContext = Depends(get_tenancy_context)
) -> Dict[str, Any]:
    """
    Calcula un score de salud financiera basado en múltiples factores
    """
    try:
        import sqlite3

        conn = sqlite3.connect('unified_mcp_system.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Factores para el score
        factors = {}

        # 1. Ratio de clasificación (% transacciones clasificadas)
        cursor.execute("""
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN category_auto != 'Sin categoría' THEN 1 END) as classified
            FROM bank_movements
            WHERE account_id IN (7, 11) AND movement_kind = 'Gasto'
        """)

        classification_data = cursor.fetchone()
        classification_ratio = (classification_data['classified'] / classification_data['total']) * 100 if classification_data['total'] > 0 else 0
        factors['classification_score'] = min(100, classification_ratio)

        # 2. Ratio de conciliación (% gastos con facturas)
        cursor.execute("""
            SELECT
                COUNT(*) as total_requiring_receipts,
                COUNT(CASE WHEN reconciliation_status != 'pending' THEN 1 END) as reconciled
            FROM bank_movements
            WHERE account_id IN (7, 11) AND requires_receipt = 1
        """)

        reconciliation_data = cursor.fetchone()
        reconciliation_ratio = (reconciliation_data['reconciled'] / reconciliation_data['total_requiring_receipts']) * 100 if reconciliation_data['total_requiring_receipts'] > 0 else 100
        factors['reconciliation_score'] = min(100, reconciliation_ratio)

        # 3. Score de anomalías (penaliza anomalías)
        cursor.execute("""
            SELECT COUNT(*) as anomalies, COUNT(*) * 1.0 / (SELECT COUNT(*) FROM bank_movements WHERE account_id IN (7, 11)) as anomaly_rate
            FROM bank_movements
            WHERE account_id IN (7, 11) AND is_anomaly = 1
        """)

        anomaly_data = cursor.fetchone()
        anomaly_score = max(0, 100 - (anomaly_data['anomaly_rate'] * 1000))  # Penalizar anomalías
        factors['anomaly_score'] = anomaly_score

        # 4. Score de diversificación de gastos (penaliza concentración)
        cursor.execute("""
            SELECT category_auto, SUM(ABS(amount)) as category_total
            FROM bank_movements
            WHERE account_id IN (7, 11) AND movement_kind = 'Gasto'
            GROUP BY category_auto
            ORDER BY category_total DESC
        """)

        category_totals = cursor.fetchall()
        total_expenses = sum(row['category_total'] for row in category_totals)

        if category_totals and total_expenses > 0:
            top_category_ratio = category_totals[0]['category_total'] / total_expenses
            diversification_score = max(0, 100 - (top_category_ratio * 100))
        else:
            diversification_score = 100

        factors['diversification_score'] = diversification_score

        # Calcular score general (promedio ponderado)
        weights = {
            'classification_score': 0.3,
            'reconciliation_score': 0.4,
            'anomaly_score': 0.2,
            'diversification_score': 0.1
        }

        overall_score = sum(factors[factor] * weights[factor] for factor in factors)

        # Determinar nivel de salud
        if overall_score >= 85:
            health_level = "Excellent"
            health_color = "green"
        elif overall_score >= 70:
            health_level = "Good"
            health_color = "yellow"
        elif overall_score >= 50:
            health_level = "Fair"
            health_color = "orange"
        else:
            health_level = "Poor"
            health_color = "red"

        conn.close()

        return {
            "status": "success",
            "data": {
                "overall_score": round(overall_score, 1),
                "health_level": health_level,
                "health_color": health_color,
                "factor_scores": factors,
                "recommendations": [
                    "Clasificar transacciones sin categoría" if factors['classification_score'] < 80 else None,
                    "Obtener facturas faltantes" if factors['reconciliation_score'] < 80 else None,
                    "Revisar anomalías detectadas" if factors['anomaly_score'] < 80 else None,
                    "Diversificar categorías de gasto" if factors['diversification_score'] < 70 else None
                ]
            },
            "generated_for_user": current_user.email,
            "tenant_id": tenancy.tenant_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating financial health score: {str(e)}")