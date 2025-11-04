"""
Hooks para integrar el sistema de escalamiento automático con endpoints.

Estos hooks se llaman desde POST /expenses y POST /ocr/intake para
escalar automáticamente gastos a facturación cuando corresponde.
"""

import logging
from typing import Any, Dict, Optional

from core.expense_escalation_system import escalation_system

logger = logging.getLogger(__name__)


async def post_expense_creation_hook(
    expense_id: int,
    expense_data: Dict[str, Any],
    user_id: Optional[int] = None,
    company_id: str = "default",
) -> Dict[str, Any]:
    """
    Hook que se ejecuta DESPUÉS de crear un gasto en POST /expenses.

    Args:
        expense_id: ID del gasto recién creado
        expense_data: Datos completos del gasto
        user_id: ID del usuario que creó el gasto
        company_id: ID de la empresa

    Returns:
        Información del escalamiento (si ocurrió)
    """
    try:
        # 1. Determinar si debe escalar
        should_escalate, reason = escalation_system.should_escalate(expense_data)

        if not should_escalate:
            logger.debug(
                f"Expense {expense_id} NO escala a facturación. Razón: {reason}"
            )
            return {
                "escalated": False,
                "reason": reason,
            }

        # 2. Escalar automáticamente
        logger.info(
            f"🚀 Escalando expense {expense_id} automáticamente. Razón: {reason}"
        )

        ticket_id = escalation_system.escalate_expense_to_invoicing(
            expense_id=expense_id,
            expense_data=expense_data,
            reason=reason,
            user_id=user_id,
            company_id=company_id,
        )

        if ticket_id:
            return {
                "escalated": True,
                "reason": reason,
                "ticket_id": ticket_id,
                "message": f"Gasto escalado automáticamente a facturación (Ticket #{ticket_id})",
            }
        else:
            return {
                "escalated": False,
                "reason": "Error al crear ticket espejo",
                "error": True,
            }

    except Exception as e:
        logger.error(f"❌ Error en post_expense_creation_hook: {e}")
        return {
            "escalated": False,
            "reason": f"Error: {str(e)}",
            "error": True,
        }


async def post_ocr_intake_hook(
    expense_id: int,
    ocr_data: Dict[str, Any],
    extracted_fields: Dict[str, Any],
    company_id: str = "default",
) -> Dict[str, Any]:
    """
    Hook que se ejecuta DESPUÉS de procesar OCR en POST /ocr/intake.

    Nota: En el flujo actual, /ocr/intake NO crea gasto directamente,
    solo retorna campos extraídos. Este hook se activa SOLO si se
    modifica /ocr/intake para crear gastos automáticamente.

    Args:
        expense_id: ID del gasto creado (si se creó)
        ocr_data: Datos del OCR
        extracted_fields: Campos extraídos del ticket
        company_id: ID de la empresa

    Returns:
        Información del escalamiento
    """
    try:
        # Construir expense_data a partir de campos OCR
        expense_data = {
            "id": expense_id,
            "monto_total": extracted_fields.get("total", 0),
            "descripcion": extracted_fields.get("descripcion", "Gasto desde OCR"),
            "rfc": extracted_fields.get("rfc"),
            "fecha_gasto": extracted_fields.get("fecha"),
            "proveedor": {
                "nombre": extracted_fields.get("proveedor", "Desconocido")
            },
            "categoria": extracted_fields.get("categoria"),
            "will_have_cfdi": True,  # Asumimos que OCR implica factura
            "company_id": company_id,
        }

        # Verificar si debe escalar
        should_escalate, reason = escalation_system.should_escalate(expense_data)

        if should_escalate:
            ticket_id = escalation_system.escalate_expense_to_invoicing(
                expense_id=expense_id,
                expense_data=expense_data,
                reason=f"OCR: {reason}",
                company_id=company_id,
            )

            if ticket_id:
                return {
                    "escalated": True,
                    "ticket_id": ticket_id,
                    "reason": reason,
                }

        return {"escalated": False, "reason": reason}

    except Exception as e:
        logger.error(f"❌ Error en post_ocr_intake_hook: {e}")
        return {"escalated": False, "reason": f"Error: {str(e)}", "error": True}


async def post_rpa_completion_hook(
    ticket_id: int, invoice_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Hook que se ejecuta DESPUÉS de que RPA completa descarga de factura.

    Sincroniza datos de factura desde Advanced Ticket Dashboard
    de vuelta a Voice Expenses (expense_records).

    Args:
        ticket_id: ID del ticket que completó RPA
        invoice_data: Datos de la factura descargada

    Returns:
        Información de la sincronización
    """
    try:
        logger.info(
            f"🔄 Sincronizando factura desde ticket {ticket_id} → expense"
        )

        updated_expense = escalation_system.sync_ticket_back_to_expense(
            ticket_id=ticket_id
        )

        if updated_expense:
            return {
                "synced": True,
                "expense_id": updated_expense["id"],
                "message": f"Factura sincronizada a expense #{updated_expense['id']}",
            }
        else:
            return {
                "synced": False,
                "reason": "Ticket no es espejo o no tiene expense_id",
            }

    except Exception as e:
        logger.error(f"❌ Error en post_rpa_completion_hook: {e}")
        return {"synced": False, "reason": f"Error: {str(e)}", "error": True}


def get_expense_escalation_info(expense_id: int) -> Dict[str, Any]:
    """
    Obtiene información de escalamiento para un gasto.

    Útil para mostrar en Voice Expenses si el gasto está siendo
    procesado por Advanced Ticket Dashboard.

    Args:
        expense_id: ID del gasto

    Returns:
        Estado de escalamiento
    """
    return escalation_system.get_escalation_status(expense_id)
