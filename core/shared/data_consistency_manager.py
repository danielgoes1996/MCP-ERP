#!/usr/bin/env python3
"""
Manager para mantener consistencia de datos entre campos
"""

import json
import sqlite3
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class TicketData:
    """Estructura consistente para datos de ticket"""
    id: int
    merchant_name: str
    category: str
    confidence: float
    web_id: Optional[str] = None
    rfc: Optional[str] = None
    total: Optional[str] = None
    fecha: Optional[str] = None
    extracted_text: Optional[str] = None
    facturacion_urls: Optional[list] = None

class DataConsistencyManager:
    """
    Manager para mantener consistencia entre campos de la base de datos
    """

    def __init__(self, db_path: str = './data/mcp_internal.db'):
        self.db_path = db_path

    def update_ticket_analysis(
        self,
        ticket_id: int,
        analysis_result: Dict[str, Any],
        extracted_fields: Dict[str, str] = None,
        extracted_text: str = None
    ) -> bool:
        """
        Actualizar TODOS los campos relacionados del ticket de manera consistente

        Esta función centraliza todas las actualizaciones para evitar inconsistencias
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Construir el objeto completo de análisis
            complete_analysis = {
                "merchant_name": analysis_result.get("merchant_name", ""),
                "category": analysis_result.get("category", "otros"),
                "confidence": analysis_result.get("confidence", 0.0),
                "facturacion_urls": analysis_result.get("facturacion_urls", []),
                "extracted_fields": extracted_fields or {},
                "extracted_text_length": len(extracted_text) if extracted_text else 0,
                "last_updated": self._get_timestamp()
            }

            # Actualizar TODOS los campos de una sola vez
            cursor.execute("""
                UPDATE tickets
                SET
                    merchant_name = ?,
                    category = ?,
                    confidence = ?,
                    llm_analysis = ?
                WHERE id = ?
            """, (
                complete_analysis["merchant_name"],
                complete_analysis["category"],
                complete_analysis["confidence"],
                json.dumps(complete_analysis, ensure_ascii=False),
                ticket_id
            ))

            # Log para auditoria
            logger.info(f"✅ Ticket {ticket_id} actualizado consistentemente:")
            logger.info(f"   Merchant: {complete_analysis['merchant_name']}")
            logger.info(f"   Category: {complete_analysis['category']}")
            logger.info(f"   Fields: {list((extracted_fields or {}).keys())}")

            conn.commit()
            conn.close()

            return True

        except Exception as e:
            logger.error(f"❌ Error actualizando ticket {ticket_id}: {e}")
            return False

    def validate_ticket_consistency(self, ticket_id: int) -> Dict[str, Any]:
        """
        Validar que todos los campos del ticket estén consistentes
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, merchant_name, category, confidence, llm_analysis
                FROM tickets WHERE id = ?
            """, (ticket_id,))

            result = cursor.fetchone()
            conn.close()

            if not result:
                return {"error": f"Ticket {ticket_id} no encontrado"}

            id, merchant_name, category, confidence, llm_analysis_str = result

            # Parsear llm_analysis
            try:
                llm_analysis = json.loads(llm_analysis_str) if llm_analysis_str else {}
            except:
                llm_analysis = {}

            # Verificar consistencia
            inconsistencies = []

            # Verificar merchant_name
            llm_merchant = llm_analysis.get("merchant_name", "")
            if merchant_name != llm_merchant:
                inconsistencies.append({
                    "field": "merchant_name",
                    "direct_field": merchant_name,
                    "llm_analysis": llm_merchant,
                    "severity": "high"
                })

            # Verificar category
            llm_category = llm_analysis.get("category", "")
            if category != llm_category:
                inconsistencies.append({
                    "field": "category",
                    "direct_field": category,
                    "llm_analysis": llm_category,
                    "severity": "medium"
                })

            return {
                "ticket_id": ticket_id,
                "is_consistent": len(inconsistencies) == 0,
                "inconsistencies": inconsistencies,
                "last_check": self._get_timestamp()
            }

        except Exception as e:
            return {"error": f"Error validando ticket {ticket_id}: {e}"}

    def fix_all_inconsistencies(self) -> Dict[str, Any]:
        """
        Buscar y corregir todas las inconsistencias en la base de datos
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Obtener todos los tickets
            cursor.execute("""
                SELECT id, merchant_name, category, llm_analysis
                FROM tickets
                WHERE llm_analysis IS NOT NULL
                ORDER BY id DESC
                LIMIT 100
            """)

            tickets = cursor.fetchall()
            conn.close()

            fixed_count = 0
            inconsistent_tickets = []

            for ticket_id, merchant_name, category, llm_analysis_str in tickets:
                validation = self.validate_ticket_consistency(ticket_id)

                if not validation.get("is_consistent", True):
                    inconsistent_tickets.append({
                        "id": ticket_id,
                        "inconsistencies": validation.get("inconsistencies", [])
                    })

                    # Auto-fix: Usar los valores directos como truth
                    if merchant_name and category:
                        success = self.update_ticket_analysis(
                            ticket_id,
                            {
                                "merchant_name": merchant_name,
                                "category": category,
                                "confidence": 0.9
                            }
                        )
                        if success:
                            fixed_count += 1

            return {
                "total_checked": len(tickets),
                "inconsistent_found": len(inconsistent_tickets),
                "fixed_count": fixed_count,
                "inconsistent_tickets": inconsistent_tickets[:10]  # Solo mostrar primeros 10
            }

        except Exception as e:
            return {"error": f"Error fixing inconsistencies: {e}"}

    def _get_timestamp(self) -> str:
        """Obtener timestamp actual"""
        import datetime
        return datetime.datetime.now().isoformat()

# Instancia global
consistency_manager = DataConsistencyManager()