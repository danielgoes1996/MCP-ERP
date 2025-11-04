"""
API endpoints para gestión de cuentas de pago de usuarios
Incluye CRUD completo para bancos, efectivo, terminales y tarjetas de crédito
"""

from fastapi import APIRouter, HTTPException, Depends, status, Query
from typing import List, Optional
import logging

from core.unified_auth import get_current_active_user, User
from core.payment_accounts_models import (
    UserPaymentAccount,
    CreateUserPaymentAccountRequest,
    UpdateUserPaymentAccountRequest,
    BankingInstitution,
    TipoCuenta,
    SubtipoCuenta,
    EstadoSaldo,
    payment_account_service
)

logger = logging.getLogger(__name__)

# Router para endpoints de cuentas de pago
router = APIRouter(prefix="/payment-accounts", tags=["Payment Accounts"])


@router.get("/", response_model=List[UserPaymentAccount])
async def get_user_payment_accounts(
    current_user: User = Depends(get_current_active_user),
    active_only: bool = Query(True, description="Solo cuentas activas"),
    tipo: Optional[TipoCuenta] = Query(None, description="Filtrar por tipo de cuenta")
):
    """
    Obtener todas las cuentas de pago del usuario autenticado

    Parámetros:
    - active_only: Si solo mostrar cuentas activas (default: True)
    - tipo: Filtrar por tipo específico de cuenta (opcional)

    Retorna:
    - Lista de cuentas de pago del usuario
    """
    try:
        logger.info(f"Getting payment accounts for user: {current_user.email}")

        if tipo:
            accounts = payment_account_service.get_accounts_by_type(
                current_user.id, current_user.tenant_id, tipo
            )
        else:
            accounts = payment_account_service.get_user_accounts(
                current_user.id, current_user.tenant_id, active_only
            )

        logger.info(f"Found {len(accounts)} payment accounts for user {current_user.email}")
        return accounts

    except Exception as e:
        logger.error(f"Error getting payment accounts for user {current_user.email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener cuentas de pago"
        )


@router.get("/{account_id}", response_model=UserPaymentAccount)
async def get_payment_account(
    account_id: int,
    current_user: User = Depends(get_current_active_user)
):
    """
    Obtener una cuenta de pago específica

    Parámetros:
    - account_id: ID de la cuenta a obtener

    Retorna:
    - Información completa de la cuenta
    """
    try:
        logger.info(f"Getting payment account {account_id} for user: {current_user.email}")

        account = payment_account_service.get_account(
            account_id, current_user.id, current_user.tenant_id
        )

        return account

    except ValueError:
        logger.warning(f"Payment account {account_id} not found for user {current_user.email}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cuenta de pago no encontrada"
        )
    except Exception as e:
        logger.error(f"Error getting payment account {account_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener cuenta de pago"
        )


@router.post("/", response_model=UserPaymentAccount, status_code=status.HTTP_201_CREATED)
async def create_payment_account(
    request: CreateUserPaymentAccountRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    Crear nueva cuenta de pago

    Body requerido:
    - nombre: Nombre descriptivo de la cuenta
    - tipo: Tipo de cuenta (banco, efectivo, terminal, tarjeta_credito, tarjeta_debito)
    - moneda: Código de moneda (default: MXN)
    - saldo_inicial: Saldo inicial de la cuenta

    Para tarjetas de crédito también se requiere:
    - limite_credito: Límite máximo de crédito
    - fecha_corte: Día del mes de corte (1-31)
    - fecha_pago: Día del mes límite de pago (1-31)
    - numero_tarjeta: Últimos 4 dígitos

    Campos opcionales según tipo:
    - banco_nombre: Nombre del banco
    - proveedor_terminal: Proveedor del terminal (Clip, MercadoPago, etc.)
    - numero_cuenta_enmascarado: Número de cuenta enmascarado

    Retorna:
    - Cuenta creada con ID asignado
    """
    try:
        logger.info(f"Creating payment account for user: {current_user.email}")

        # Validaciones específicas por tipo y subtipo
        if request.tipo == TipoCuenta.BANCARIA:
            if not request.subtipo:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Las cuentas bancarias requieren especificar subtipo (débito o crédito)"
                )

            if request.subtipo == SubtipoCuenta.CREDITO:
                if not all([request.limite_credito, request.fecha_corte, request.fecha_pago, request.numero_tarjeta]):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Las tarjetas de crédito requieren: limite_credito, fecha_corte, fecha_pago y numero_tarjeta"
                    )

            if not request.banco_nombre:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Las cuentas bancarias requieren especificar banco_nombre"
                )

        elif request.tipo == TipoCuenta.TERMINAL:
            if not request.proveedor_terminal:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Los terminales de pago requieren especificar proveedor_terminal"
                )

        elif request.tipo != TipoCuenta.BANCARIA and request.subtipo:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Solo las cuentas bancarias pueden tener subtipo"
            )

        # Usar tenant_id directamente del usuario
        tenant_id = current_user.tenant_id

        account = payment_account_service.create_account(
            request, current_user.id, tenant_id
        )

        logger.info(f"Payment account created: {account.id} for user {current_user.email}")
        return account

    except ValueError as e:
        logger.warning(f"Validation error creating payment account: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating payment account for user {current_user.email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al crear cuenta de pago"
        )


@router.put("/{account_id}", response_model=UserPaymentAccount)
async def update_payment_account(
    account_id: int,
    request: UpdateUserPaymentAccountRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    Actualizar cuenta de pago existente

    Parámetros:
    - account_id: ID de la cuenta a actualizar

    Body (todos los campos son opcionales):
    - nombre: Nuevo nombre de la cuenta
    - moneda: Nueva moneda
    - saldo_inicial: Nuevo saldo inicial
    - activo: Estado activo/inactivo
    - limite_credito: Nuevo límite (solo tarjetas de crédito)
    - fecha_corte: Nueva fecha de corte (solo tarjetas de crédito)
    - fecha_pago: Nueva fecha de pago (solo tarjetas de crédito)
    - Y otros campos específicos según tipo

    Retorna:
    - Cuenta actualizada
    """
    try:
        logger.info(f"Updating payment account {account_id} for user: {current_user.email}")
        logger.info(f"Update request data: {request.dict(exclude_unset=True)}")

        # Usar tenant_id directamente del usuario
        tenant_id = current_user.tenant_id

        account = payment_account_service.update_account(
            account_id, current_user.id, tenant_id, request
        )

        logger.info(f"Payment account updated: {account_id} for user {current_user.email}")
        return account

    except ValueError:
        logger.warning(f"Payment account {account_id} not found for user {current_user.email}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cuenta de pago no encontrada"
        )
    except Exception as e:
        logger.error(f"Error updating payment account {account_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al actualizar cuenta de pago"
        )


@router.delete("/{account_id}")
async def delete_payment_account(
    account_id: int,
    current_user: User = Depends(get_current_active_user)
):
    """
    Desactivar cuenta de pago (soft delete)

    Parámetros:
    - account_id: ID de la cuenta a desactivar

    Nota: Las cuentas no se eliminan físicamente, solo se marcan como inactivas
    para mantener la integridad de los registros históricos de gastos.

    Retorna:
    - Confirmación de eliminación
    """
    try:
        logger.info(f"Deleting payment account {account_id} for user: {current_user.email}")

        # Usar tenant_id directamente del usuario
        tenant_id = current_user.tenant_id

        success = payment_account_service.delete_account(
            account_id, current_user.id, tenant_id
        )

        if success:
            logger.info(f"Payment account deleted: {account_id} for user {current_user.email}")
            return {"message": "Cuenta de pago desactivada exitosamente"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se pudo desactivar la cuenta"
            )

    except ValueError:
        logger.warning(f"Payment account {account_id} not found for user {current_user.email}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cuenta de pago no encontrada"
        )
    except Exception as e:
        logger.error(f"Error deleting payment account {account_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al desactivar cuenta de pago"
        )


@router.get("/summary/dashboard")
async def get_accounts_summary(
    current_user: User = Depends(get_current_active_user)
):
    """
    Obtener resumen de cuentas para dashboard

    Retorna:
    - Resumen con totales por tipo de cuenta
    - Alertas de tarjetas de crédito próximas a límite
    - Cuentas con saldo bajo
    """
    try:
        logger.info(f"Getting accounts summary for user: {current_user.email}")

        # Usar tenant_id directamente del usuario
        tenant_id = current_user.tenant_id

        accounts = payment_account_service.get_user_accounts(
            current_user.id, tenant_id, active_only=True
        )

        # Calcular resumen
        summary = {
            "total_accounts": len(accounts),
            "total_balance": 0,
            "accounts_by_type": {},
            "credit_cards_summary": {
                "total_cards": 0,
                "total_limit": 0,
                "total_used": 0,
                "available_credit": 0
            },
            "alerts": []
        }

        for account in accounts:
            # Contadores por tipo
            tipo_key = account.tipo.value
            if tipo_key not in summary["accounts_by_type"]:
                summary["accounts_by_type"][tipo_key] = {
                    "count": 0,
                    "total_balance": 0
                }

            summary["accounts_by_type"][tipo_key]["count"] += 1

            # Solo sumar balance positivo para el total (no deudas de tarjetas)
            if account.tipo != TipoCuenta.TARJETA_CREDITO:
                summary["total_balance"] += account.saldo_actual
                summary["accounts_by_type"][tipo_key]["total_balance"] += account.saldo_actual

            # Resumen específico de tarjetas de crédito
            if account.tipo == TipoCuenta.TARJETA_CREDITO:
                summary["credit_cards_summary"]["total_cards"] += 1
                summary["credit_cards_summary"]["total_limit"] += account.limite_credito or 0
                summary["credit_cards_summary"]["total_used"] += account.saldo_actual
                summary["credit_cards_summary"]["available_credit"] += account.credito_disponible or 0

                # Alertas para tarjetas de crédito
                if account.estado_saldo in [EstadoSaldo.BAJO, EstadoSaldo.SIN_CREDITO]:
                    summary["alerts"].append({
                        "type": "credit_limit",
                        "account_id": account.id,
                        "account_name": account.nombre,
                        "message": f"Tarjeta {account.nombre} con poco crédito disponible",
                        "severity": "high" if account.estado_saldo == EstadoSaldo.SIN_CREDITO else "medium"
                    })

            # Alertas para cuentas con saldo bajo
            if account.tipo in [TipoCuenta.BANCO, TipoCuenta.EFECTIVO] and account.saldo_actual < 1000:
                summary["alerts"].append({
                    "type": "low_balance",
                    "account_id": account.id,
                    "account_name": account.nombre,
                    "message": f"Cuenta {account.nombre} con saldo bajo: {account.saldo_actual}",
                    "severity": "low"
                })

        logger.info(f"Generated accounts summary for user {current_user.email}")
        return summary

    except Exception as e:
        logger.error(f"Error getting accounts summary for user {current_user.email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener resumen de cuentas"
        )


@router.get("/banking-institutions", response_model=List[BankingInstitution])
async def get_banking_institutions():
    """
    Obtener lista de instituciones bancarias disponibles

    Retorna:
    - Lista de bancos ordenada por prioridad y nombre
    """
    try:
        logger.info("🏦 Getting banking institutions list")

        institutions = payment_account_service.get_banking_institutions(active_only=True)

        logger.info(f"✅ Found {len(institutions)} banking institutions")
        logger.info(f"First 3 institutions: {[inst.name for inst in institutions[:3]]}")
        return institutions

    except Exception as e:
        logger.error(f"❌ Error getting banking institutions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener instituciones bancarias"
        )


@router.get("/types/available")
async def get_available_account_types():
    """
    Obtener tipos y subtipos de cuenta disponibles

    Retorna:
    - Lista de tipos de cuenta con descripción y subtipos
    """
    return {
        "account_types": [
            {
                "value": TipoCuenta.BANCARIA.value,
                "label": "Cuenta Bancaria",
                "description": "Cuentas bancarias de débito o crédito",
                "required_fields": ["banco_nombre", "subtipo"],
                "subtypes": [
                    {
                        "value": SubtipoCuenta.DEBITO.value,
                        "label": "Tarjeta de Débito",
                        "description": "Tarjeta de débito vinculada a cuenta bancaria",
                        "required_fields": ["banco_nombre", "numero_tarjeta"]
                    },
                    {
                        "value": SubtipoCuenta.CREDITO.value,
                        "label": "Tarjeta de Crédito",
                        "description": "Tarjeta de crédito con límite establecido",
                        "required_fields": ["limite_credito", "fecha_corte", "fecha_pago", "numero_tarjeta", "banco_nombre"]
                    }
                ]
            },
            {
                "value": TipoCuenta.EFECTIVO.value,
                "label": "Efectivo",
                "description": "Caja chica, efectivo en mano",
                "required_fields": [],
                "subtypes": None
            },
            {
                "value": TipoCuenta.TERMINAL.value,
                "label": "Terminal de Pago",
                "description": "Clip, MercadoPago Point, Zettle, etc.",
                "required_fields": ["proveedor_terminal"],
                "subtypes": None
            }
        ]
    }


# Health check específico para payment accounts
@router.get("/health")
async def payment_accounts_health():
    """
    Health check del sistema de cuentas de pago
    """
    try:
        # Test básico de conectividad
        service = payment_account_service

        # Intentar obtener cuentas de un usuario de prueba
        test_accounts = service.get_user_accounts(9, 3, active_only=True)

        return {
            "status": "healthy",
            "service": "payment_accounts",
            "database_connected": True,
            "test_accounts_found": len(test_accounts),
            "version": "1.0.0"
        }

    except Exception as e:
        logger.error(f"Payment accounts health check failed: {e}")
        return {
            "status": "unhealthy",
            "service": "payment_accounts",
            "error": str(e)
        }


if __name__ == "__main__":
    # Test básico del router
    print("✅ Payment Accounts API router configured successfully")
    print(f"✅ Available endpoints: {len(router.routes)}")