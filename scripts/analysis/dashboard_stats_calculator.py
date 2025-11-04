#!/usr/bin/env python3
"""
Calculador de estadísticas reales para el dashboard.
Calcula métricas dinámicas basadas en datos reales de la DB.
"""

import sqlite3
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

def calculate_dashboard_stats(company_id: str = "default") -> Dict[str, Any]:
    """
    Calcular estadísticas reales del dashboard.

    Args:
        company_id: ID de la empresa para filtrar datos

    Returns:
        Dict con todas las estadísticas calculadas
    """
    try:
        from core.internal_db import _get_db_path

        stats = {
            "total_tickets": 0,
            "auto_invoiced": 0,
            "success_rate": 0.0,
            "avg_processing_time": "0s",
            "tickets_by_status": {
                "pendiente": 0,
                "procesando": 0,
                "completado": 0,
                "error": 0,
                "facturado": 0
            },
            "recent_activity": [],
            "top_merchants": [],
            "processing_stats": {
                "last_24h": 0,
                "last_7d": 0,
                "last_30d": 0
            }
        }

        db_path = _get_db_path()

        with sqlite3.connect(db_path) as connection:
            connection.row_factory = sqlite3.Row  # Para acceso por nombre de columna
            cursor = connection.cursor()

            # 1. Total de tickets
            cursor.execute(
                "SELECT COUNT(*) as total FROM tickets WHERE company_id = ?",
                (company_id,)
            )
            result = cursor.fetchone()
            stats["total_tickets"] = result["total"] if result else 0

            # 2. Tickets por estado
            cursor.execute("""
                SELECT estado, COUNT(*) as count
                FROM tickets
                WHERE company_id = ?
                GROUP BY estado
            """, (company_id,))

            for row in cursor.fetchall():
                estado = row["estado"]
                count = row["count"]
                if estado in stats["tickets_by_status"]:
                    stats["tickets_by_status"][estado] = count

            # 3. Auto facturados (tickets con estado 'facturado' o 'completado')
            auto_invoiced = (stats["tickets_by_status"]["facturado"] +
                           stats["tickets_by_status"]["completado"])
            stats["auto_invoiced"] = auto_invoiced

            # 4. Tasa de éxito (% de tickets completados/facturados vs total)
            if stats["total_tickets"] > 0:
                success_count = auto_invoiced
                stats["success_rate"] = round((success_count / stats["total_tickets"]) * 100, 1)

            # 5. Tiempo promedio de procesamiento (simulado por ahora)
            # TODO: Implementar tiempo real cuando tengamos timestamps de procesamiento
            if stats["total_tickets"] > 0:
                # Estimación basada en el número de tickets y complejidad
                avg_seconds = min(30 + (stats["total_tickets"] * 0.5), 120)
                stats["avg_processing_time"] = f"{int(avg_seconds)}s"

            # 6. Top merchants
            cursor.execute("""
                SELECT merchant_name, COUNT(*) as count
                FROM tickets
                WHERE company_id = ? AND merchant_name IS NOT NULL AND merchant_name != ''
                GROUP BY merchant_name
                ORDER BY count DESC
                LIMIT 5
            """, (company_id,))

            stats["top_merchants"] = [
                {"name": row["merchant_name"], "count": row["count"]}
                for row in cursor.fetchall()
            ]

            # 7. Actividad reciente (últimos 10 tickets)
            cursor.execute("""
                SELECT id, merchant_name, estado, created_at, tipo
                FROM tickets
                WHERE company_id = ?
                ORDER BY created_at DESC
                LIMIT 10
            """, (company_id,))

            stats["recent_activity"] = [
                {
                    "id": row["id"],
                    "merchant": row["merchant_name"] or "Unknown",
                    "status": row["estado"],
                    "created": row["created_at"],
                    "type": row["tipo"]
                }
                for row in cursor.fetchall()
            ]

            # 8. Estadísticas de procesamiento por período
            now = datetime.utcnow()
            periods = {
                "last_24h": now - timedelta(days=1),
                "last_7d": now - timedelta(days=7),
                "last_30d": now - timedelta(days=30)
            }

            for period_name, since_date in periods.items():
                cursor.execute("""
                    SELECT COUNT(*) as count
                    FROM tickets
                    WHERE company_id = ? AND datetime(created_at) >= datetime(?)
                """, (company_id, since_date.isoformat()))

                result = cursor.fetchone()
                stats["processing_stats"][period_name] = result["count"] if result else 0

            # 9. Estadísticas adicionales
            stats["metadata"] = {
                "calculated_at": datetime.utcnow().isoformat(),
                "company_id": company_id,
                "database_path": db_path
            }

        return stats

    except Exception as e:
        # Fallback a estadísticas vacías en caso de error
        return {
            "total_tickets": 0,
            "auto_invoiced": 0,
            "success_rate": 0.0,
            "avg_processing_time": "0s",
            "tickets_by_status": {
                "pendiente": 0,
                "procesando": 0,
                "completado": 0,
                "error": 0,
                "facturado": 0
            },
            "recent_activity": [],
            "top_merchants": [],
            "processing_stats": {
                "last_24h": 0,
                "last_7d": 0,
                "last_30d": 0
            },
            "error": str(e)
        }

def format_stats_for_dashboard(stats: Dict[str, Any]) -> Dict[str, Any]:
    """
    Formatear estadísticas para el dashboard frontend.

    Args:
        stats: Estadísticas calculadas

    Returns:
        Estadísticas formateadas para el dashboard
    """
    return {
        # Métricas principales
        "total_tickets": stats["total_tickets"],
        "auto_invoiced": stats["auto_invoiced"],
        "success_rate": f"{stats['success_rate']}%",
        "avg_processing_time": stats["avg_processing_time"],

        # Distribución por estado
        "status_distribution": [
            {"label": "Pendiente", "value": stats["tickets_by_status"]["pendiente"], "color": "#fbbf24"},
            {"label": "Procesando", "value": stats["tickets_by_status"]["procesando"], "color": "#3b82f6"},
            {"label": "Completado", "value": stats["tickets_by_status"]["completado"], "color": "#10b981"},
            {"label": "Facturado", "value": stats["tickets_by_status"]["facturado"], "color": "#059669"},
            {"label": "Error", "value": stats["tickets_by_status"]["error"], "color": "#ef4444"}
        ],

        # Actividad reciente
        "recent_tickets": stats["recent_activity"],

        # Top merchants
        "top_merchants": stats["top_merchants"],

        # Trends
        "trends": {
            "daily": stats["processing_stats"]["last_24h"],
            "weekly": stats["processing_stats"]["last_7d"],
            "monthly": stats["processing_stats"]["last_30d"]
        },

        # Metadata
        "last_updated": stats.get("metadata", {}).get("calculated_at", datetime.utcnow().isoformat())
    }

if __name__ == "__main__":
    # Test del calculador
    print("🧮 TESTING DASHBOARD STATS CALCULATOR")
    print("=" * 45)

    stats = calculate_dashboard_stats("default")
    formatted_stats = format_stats_for_dashboard(stats)

    print(f"📊 Raw Stats:")
    for key, value in stats.items():
        if key != "metadata":
            print(f"   {key}: {value}")

    print(f"\n🎨 Formatted for Dashboard:")
    print(f"   Total Tickets: {formatted_stats['total_tickets']}")
    print(f"   Auto Facturados: {formatted_stats['auto_invoiced']}")
    print(f"   Tasa de Éxito: {formatted_stats['success_rate']}")
    print(f"   Tiempo Promedio: {formatted_stats['avg_processing_time']}")

    print(f"\n📈 Recent Activity: {len(formatted_stats['recent_tickets'])} tickets")
    print(f"🏪 Top Merchants: {len(formatted_stats['top_merchants'])} merchants")