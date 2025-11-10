"""
Sistema de Escalamiento Automático de Gastos a Facturación.

Este módulo gestiona el escalamiento automático de gastos creados en Voice Expenses
hacia el flujo de Advanced Ticket Dashboard cuando:
- El usuario marca "will_have_cfdi=True" (requiere factura)
- El sistema detecta que el gasto debe facturarse
- El gasto proviene de WhatsApp con expectativa de factura

El escalamiento crea un "ticket espejo" vinculado al expense_id original,
sin duplicar datos, permitiendo que ambas interfaces trabajen sobre el mismo gasto.
"""

import json
import logging
import sqlite3
from datetime import datetime
from typing import Any, Dict, Optional

from core.internal_db import _DB_LOCK, _get_db_path

logger = logging.getLogger(__name__)


class ExpenseEscalationSystem:
    """Sistema de escalamiento automático de gastos a facturación."""

    def __init__(self):
        self.db_path = _get_db_path()

    def should_escalate(self, expense_data: Dict[str, Any]) -> tuple[bool, str]:
        """
        Determina si un gasto debe escalar automáticamente a facturación.

        Args:
            expense_data: Datos del gasto creado

        Returns:
            (should_escalate: bool, reason: str)
        """
        # 1. Verificar si explícitamente requiere factura
        will_have_cfdi = expense_data.get("will_have_cfdi", True)
        if will_have_cfdi is False:
            return False, "Usuario marcó que NO requiere CFDI"

        # 2. Determinar razón de escalamiento (la verificación de duplicados se hace en escalate_expense_to_invoicing)
        reasons = []

        # 3.1. Usuario explícito
        if will_have_cfdi is True:
            reasons.append("Usuario marcó will_have_cfdi=True")

        # 3.2. Monto alto (> 2000 MXN)
        monto = expense_data.get("monto_total", expense_data.get("amount", 0))
        if monto > 2000:
            reasons.append(f"Monto alto (${monto:,.2f} MXN)")

        # 3.3. Tiene RFC de proveedor
        rfc = expense_data.get("rfc") or expense_data.get("provider_rfc")
        if rfc:
            reasons.append(f"Tiene RFC proveedor ({rfc})")

        # 3.4. Proviene de WhatsApp
        whatsapp_id = expense_data.get("whatsapp_message_id")
        if whatsapp_id:
            reasons.append("Proviene de WhatsApp")

        # 3.5. Categoría típicamente facturable
        categoria = expense_data.get("categoria", expense_data.get("category", ""))
        categorias_facturables = [
            "servicios", "honorarios", "renta", "software",
            "publicidad", "mantenimiento", "equipos"
        ]
        if categoria.lower() in categorias_facturables:
            reasons.append(f"Categoría facturable ({categoria})")

        # 4. Decisión final
        if will_have_cfdi or len(reasons) >= 2:
            reason_text = " | ".join(reasons)
            return True, reason_text

        return False, "No cumple criterios de escalamiento"

    def escalate_expense_to_invoicing(
        self,
        expense_id: int,
        expense_data: Dict[str, Any],
        reason: str,
        user_id: Optional[int] = None,
        company_id: str = "default",
    ) -> Optional[int]:
        """
        Escala un gasto a facturación creando un ticket espejo.

        Args:
            expense_id: ID del gasto en expense_records
            expense_data: Datos completos del gasto
            reason: Razón del escalamiento
            user_id: ID del usuario (opcional)
            company_id: ID de la empresa

        Returns:
            ticket_id del ticket espejo creado, o None si falla
        """
        try:
            logger.info(
                f"🚀 Escalando expense {expense_id} a facturación. Razón: {reason}"
            )

            # 1. Verificar si ya está escalado
            if self._is_already_escalated(expense_id):
                logger.warning(
                    f"Expense {expense_id} ya está escalado. Skipping."
                )
                return None

            # 2. Crear ticket espejo
            ticket_id = self._create_mirror_ticket(
                expense_id=expense_id,
                expense_data=expense_data,
                user_id=user_id,
                company_id=company_id,
            )

            if not ticket_id:
                logger.error(
                    f"❌ Error creando ticket espejo para expense {expense_id}"
                )
                return None

            # 3. Crear job de facturación
            job_id = self._create_invoicing_job(
                ticket_id=ticket_id, company_id=company_id
            )

            # 4. Marcar expense como escalado
            self._mark_expense_as_escalated(
                expense_id=expense_id,
                ticket_id=ticket_id,
                reason=reason,
            )

            logger.info(
                f"✅ Expense {expense_id} escalado exitosamente. "
                f"Ticket: {ticket_id}, Job: {job_id}"
            )

            return ticket_id

        except Exception as e:
            logger.error(f"❌ Error en escalamiento de expense {expense_id}: {e}")
            return None

    def get_escalation_status(self, expense_id: int) -> Dict[str, Any]:
        """
        Obtiene el estado de escalamiento de un gasto.

        Returns:
            {
                "is_escalated": bool,
                "ticket_id": int | None,
                "escalation_reason": str | None,
                "escalated_at": str | None,
                "ticket_estado": str | None,
                "job_estado": str | None,
            }
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT
                    e.escalated_to_invoicing,
                    e.escalated_ticket_id,
                    e.escalation_reason,
                    e.escalated_at,
                    t.estado AS ticket_estado,
                    j.estado AS job_estado
                FROM expense_records e
                LEFT JOIN tickets t ON e.escalated_ticket_id = t.id
                LEFT JOIN invoicing_jobs j ON t.id = j.ticket_id
                WHERE e.id = ?
                """,
                (expense_id,),
            ).fetchone()

            if not row:
                return {"is_escalated": False}

            return {
                "is_escalated": bool(row["escalated_to_invoicing"]),
                "ticket_id": row["escalated_ticket_id"],
                "escalation_reason": row["escalation_reason"],
                "escalated_at": row["escalated_at"],
                "ticket_estado": row["ticket_estado"],
                "job_estado": row["job_estado"],
            }

    def sync_ticket_back_to_expense(
        self, ticket_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Sincroniza datos del ticket de vuelta al expense original.

        Usado cuando RPA completa descarga de factura en Advanced Dashboard
        y necesita actualizar el expense en Voice Expenses.

        Args:
            ticket_id: ID del ticket espejo

        Returns:
            Datos actualizados del expense o None
        """
        try:
            # 1. Obtener ticket con invoice_data
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                ticket = conn.execute(
                    """
                    SELECT * FROM tickets
                    WHERE id = ? AND is_mirror_ticket = 1
                    """,
                    (ticket_id,),
                ).fetchone()

                if not ticket or not ticket["expense_id"]:
                    logger.warning(
                        f"Ticket {ticket_id} no es ticket espejo o no tiene expense_id"
                    )
                    return None

                expense_id = ticket["expense_id"]
                invoice_data_json = ticket["invoice_data"]

                if not invoice_data_json:
                    logger.warning(
                        f"Ticket {ticket_id} no tiene invoice_data para sincronizar"
                    )
                    return None

                invoice_data = json.loads(invoice_data_json)

                # 2. Actualizar expense con datos de factura
                updates = []
                params = []

                # Actualizar workflow status
                updates.append("workflow_status = ?")
                params.append("facturado")

                # Actualizar estado_factura
                updates.append("estado_factura = ?")
                params.append("facturado")

                # Actualizar invoice_uuid si existe
                if invoice_data.get("uuid"):
                    updates.append("cfdi_uuid = ?")
                    params.append(invoice_data["uuid"])

                # Actualizar RFC emisor
                if invoice_data.get("rfc_emisor"):
                    updates.append("rfc_proveedor = ?")
                    params.append(invoice_data["rfc_emisor"])

                # Actualizar totales
                if invoice_data.get("total"):
                    updates.append("monto_total = ?")
                    params.append(float(invoice_data["total"]))

                if invoice_data.get("subtotal"):
                    updates.append("subtotal = ?")
                    params.append(float(invoice_data["subtotal"]))

                # Timestamp
                updates.append("updated_at = ?")
                params.append(datetime.utcnow().isoformat())

                params.append(expense_id)

                # 3. Ejecutar actualización
                with _DB_LOCK:
                    conn.execute(
                        f"UPDATE expense_records SET {', '.join(updates)} WHERE id = ?",
                        params,
                    )
                    conn.commit()

                logger.info(
                    f"✅ Sincronizado ticket {ticket_id} → expense {expense_id} "
                    f"con factura {invoice_data.get('uuid', 'N/A')}"
                )

                # 4. Retornar expense actualizado
                updated_expense = conn.execute(
                    "SELECT * FROM expense_records WHERE id = ?",
                    (expense_id,),
                ).fetchone()

                return dict(updated_expense) if updated_expense else None

        except Exception as e:
            logger.error(
                f"❌ Error sincronizando ticket {ticket_id} → expense: {e}"
            )
            return None

    # Métodos privados

    def _is_already_escalated(self, expense_id: int) -> bool:
        """Verifica si el expense ya fue escalado."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT escalated_to_invoicing FROM expense_records WHERE id = ?",
                (expense_id,),
            ).fetchone()
            return bool(row and row[0])

    def _create_mirror_ticket(
        self,
        expense_id: int,
        expense_data: Dict[str, Any],
        user_id: Optional[int],
        company_id: str,
    ) -> Optional[int]:
        """Crea un ticket espejo vinculado al expense."""
        now = datetime.utcnow().isoformat()

        # Construir datos para el ticket
        descripcion = (
            expense_data.get("descripcion")
            or expense_data.get("description")
            or f"Gasto #{expense_id}"
        )

        # Construir raw_data compatible con Advanced Ticket Dashboard
        raw_data = json.dumps(
            {
                "expense_id": expense_id,
                "descripcion": descripcion,
                "monto_total": expense_data.get(
                    "monto_total", expense_data.get("amount", 0)
                ),
                "fecha_gasto": expense_data.get(
                    "fecha_gasto", expense_data.get("date")
                ),
                "categoria": expense_data.get(
                    "categoria", expense_data.get("category")
                ),
                "proveedor": expense_data.get("proveedor"),
                "rfc": expense_data.get("rfc"),
                "origen": "escalamiento_automatico",
            }
        )

        merchant_name = None
        if expense_data.get("proveedor"):
            if isinstance(expense_data["proveedor"], dict):
                merchant_name = expense_data["proveedor"].get("nombre")
            else:
                merchant_name = str(expense_data["proveedor"])

        try:
            with _DB_LOCK:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute("PRAGMA foreign_keys = ON;")
                    cursor = conn.execute(
                        """
                        INSERT INTO tickets (
                            user_id,
                            raw_data,
                            tipo,
                            estado,
                            company_id,
                            merchant_name,
                            category,
                            expense_id,
                            is_mirror_ticket,
                            created_at,
                            updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            user_id,
                            raw_data,
                            "expense_mirror",
                            "pendiente_factura",
                            company_id,
                            merchant_name,
                            expense_data.get("categoria"),
                            expense_id,
                            1,  # is_mirror_ticket = True
                            now,
                            now,
                        ),
                    )
                    conn.commit()
                    ticket_id = int(cursor.lastrowid)
                    logger.info(f"✅ Ticket espejo creado: ID={ticket_id} para expense #{expense_id}")
                    return ticket_id

        except Exception as e:
            logger.error(f"Error creando ticket espejo: {e}")
            return None

    def _create_invoicing_job(
        self, ticket_id: int, company_id: str
    ) -> Optional[int]:
        """Crea un job de facturación para el ticket."""
        now = datetime.utcnow().isoformat()

        try:
            with _DB_LOCK:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute("PRAGMA foreign_keys = ON;")
                    cursor = conn.execute(
                        """
                        INSERT INTO invoicing_jobs (
                            ticket_id,
                            estado,
                            company_id,
                            scheduled_at,
                            created_at,
                            updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            ticket_id,
                            "pendiente",
                            company_id,
                            now,
                            now,
                            now,
                        ),
                    )
                    conn.commit()
                    return int(cursor.lastrowid)

        except Exception as e:
            logger.error(f"Error creando invoicing job: {e}")
            return None

    def _mark_expense_as_escalated(
        self, expense_id: int, ticket_id: int, reason: str
    ):
        """Marca el expense como escalado."""
        now = datetime.utcnow().isoformat()

        with _DB_LOCK:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    UPDATE expense_records
                    SET
                        escalated_to_invoicing = 1,
                        escalated_ticket_id = ?,
                        escalation_reason = ?,
                        escalated_at = ?
                    WHERE id = ?
                    """,
                    (ticket_id, reason, now, expense_id),
                )
                conn.commit()


# Instancia global del sistema
escalation_system = ExpenseEscalationSystem()
