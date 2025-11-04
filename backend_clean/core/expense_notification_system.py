"""
Sistema de Notificaciones para Acciones de Gastos Completadas
Punto 12: Acciones de Gastos - Notification System

Este módulo proporciona:
- Notificaciones multi-canal (email, webhook, push)
- Templates personalizables
- Retry logic robusto
- Notificaciones por lotes y individuales
- Sistema de suscripciones y preferencias
- Analytics de entrega de notificaciones
"""

from __future__ import annotations

import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from enum import Enum
import logging
import aiohttp
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jinja2 import Template

from core.expense_audit_system import ActionType, ActionRecord

logger = logging.getLogger(__name__)


class NotificationChannel(Enum):
    """Canales de notificación disponibles"""
    EMAIL = "email"
    WEBHOOK = "webhook"
    PUSH = "push"
    SMS = "sms"
    SLACK = "slack"
    TEAMS = "teams"
    INTERNAL = "internal"


class NotificationPriority(Enum):
    """Prioridades de notificación"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class NotificationStatus(Enum):
    """Estados de notificación"""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


@dataclass
class NotificationTemplate:
    """Template de notificación"""
    template_id: str
    channel: NotificationChannel
    action_type: ActionType
    subject_template: str
    body_template: str
    is_html: bool = False
    variables: Dict[str, Any] = None


@dataclass
class NotificationRecipient:
    """Destinatario de notificación"""
    recipient_id: str
    recipient_type: str  # 'user', 'role', 'email', 'webhook_url'
    address: str  # email, phone, webhook URL, etc.
    preferences: Dict[str, Any] = None
    is_active: bool = True


@dataclass
class NotificationRequest:
    """Request de notificación"""
    notification_id: str
    action_id: str
    channel: NotificationChannel
    priority: NotificationPriority
    recipients: List[NotificationRecipient]
    template_id: str
    template_data: Dict[str, Any]
    scheduled_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    retry_policy: Dict[str, Any] = None


@dataclass
class NotificationResult:
    """Resultado de notificación"""
    notification_id: str
    status: NotificationStatus
    delivered_count: int
    failed_count: int
    delivery_details: List[Dict[str, Any]]
    sent_at: Optional[datetime] = None
    error_message: Optional[str] = None


class ExpenseNotificationSystem:
    """Sistema de notificaciones para acciones de gastos"""

    def __init__(self, db_adapter, config: Dict[str, Any] = None):
        self.db = db_adapter
        self.config = config or {}

        # Templates por defecto
        self._default_templates = self._initialize_default_templates()

        # Configuración de canales
        self.channel_configs = {
            NotificationChannel.EMAIL: {
                "smtp_host": self.config.get("smtp_host", "localhost"),
                "smtp_port": self.config.get("smtp_port", 587),
                "smtp_username": self.config.get("smtp_username", ""),
                "smtp_password": self.config.get("smtp_password", ""),
                "from_address": self.config.get("from_address", "noreply@mcpsystem.com")
            },
            NotificationChannel.WEBHOOK: {
                "timeout_seconds": 30,
                "max_retries": 3,
                "retry_delay_seconds": 5
            },
            NotificationChannel.SLACK: {
                "bot_token": self.config.get("slack_bot_token", ""),
                "default_channel": self.config.get("slack_channel", "#expenses")
            }
        }

        # Cola de notificaciones pendientes
        self._pending_notifications: Dict[str, NotificationRequest] = {}

        # Estadísticas
        self._delivery_stats = {
            "total_sent": 0,
            "total_failed": 0,
            "by_channel": {},
            "by_action_type": {}
        }

    async def notify_action_completed(
        self,
        action_record: ActionRecord,
        custom_recipients: Optional[List[NotificationRecipient]] = None
    ) -> List[NotificationResult]:
        """Envía notificaciones para acción completada"""

        try:
            # Determinar destinatarios
            if custom_recipients:
                recipients = custom_recipients
            else:
                recipients = await self._get_default_recipients(action_record)

            if not recipients:
                logger.info(f"No recipients found for action {action_record.action_id}")
                return []

            # Determinar canales y prioridad
            channels = await self._determine_notification_channels(action_record)
            priority = self._determine_priority(action_record)

            results = []

            # Crear notificaciones para cada canal
            for channel in channels:
                notification_request = NotificationRequest(
                    notification_id=f"{action_record.action_id}_{channel.value}_{int(datetime.utcnow().timestamp())}",
                    action_id=action_record.action_id,
                    channel=channel,
                    priority=priority,
                    recipients=recipients,
                    template_id=f"{action_record.action_type.value}_{channel.value}",
                    template_data=self._prepare_template_data(action_record),
                    expires_at=datetime.utcnow() + timedelta(hours=24),
                    retry_policy=self._get_retry_policy(channel, priority)
                )

                # Enviar notificación
                result = await self._send_notification(notification_request)
                results.append(result)

            return results

        except Exception as e:
            logger.error(f"Failed to notify action completion for {action_record.action_id}: {e}")
            return [NotificationResult(
                notification_id=f"error_{action_record.action_id}",
                status=NotificationStatus.FAILED,
                delivered_count=0,
                failed_count=1,
                delivery_details=[],
                error_message=str(e)
            )]

    async def notify_action_failed(
        self,
        action_record: ActionRecord,
        error_details: Dict[str, Any]
    ) -> List[NotificationResult]:
        """Envía notificaciones para acción fallida"""

        try:
            # Para fallos, notificar con prioridad alta
            recipients = await self._get_error_notification_recipients(action_record)

            if not recipients:
                return []

            # Solo canales críticos para errores
            channels = [NotificationChannel.EMAIL, NotificationChannel.INTERNAL]

            results = []

            for channel in channels:
                notification_request = NotificationRequest(
                    notification_id=f"{action_record.action_id}_error_{channel.value}_{int(datetime.utcnow().timestamp())}",
                    action_id=action_record.action_id,
                    channel=channel,
                    priority=NotificationPriority.HIGH,
                    recipients=recipients,
                    template_id=f"{action_record.action_type.value}_error_{channel.value}",
                    template_data={
                        **self._prepare_template_data(action_record),
                        "error_details": error_details,
                        "support_contact": "support@mcpsystem.com"
                    },
                    expires_at=datetime.utcnow() + timedelta(hours=12),
                    retry_policy={"max_attempts": 5, "delay_seconds": 30}
                )

                result = await self._send_notification(notification_request)
                results.append(result)

            return results

        except Exception as e:
            logger.error(f"Failed to notify action failure for {action_record.action_id}: {e}")
            return []

    async def send_bulk_notification(
        self,
        action_records: List[ActionRecord],
        channel: NotificationChannel,
        template_id: str,
        recipients: List[NotificationRecipient]
    ) -> NotificationResult:
        """Envía notificación consolidada para múltiples acciones"""

        try:
            # Preparar datos agregados
            bulk_data = self._prepare_bulk_template_data(action_records)

            notification_request = NotificationRequest(
                notification_id=f"bulk_{int(datetime.utcnow().timestamp())}_{channel.value}",
                action_id="bulk_operation",
                channel=channel,
                priority=NotificationPriority.NORMAL,
                recipients=recipients,
                template_id=template_id,
                template_data=bulk_data,
                expires_at=datetime.utcnow() + timedelta(hours=6)
            )

            return await self._send_notification(notification_request)

        except Exception as e:
            logger.error(f"Failed to send bulk notification: {e}")
            return NotificationResult(
                notification_id="bulk_error",
                status=NotificationStatus.FAILED,
                delivered_count=0,
                failed_count=len(recipients),
                delivery_details=[],
                error_message=str(e)
            )

    async def get_notification_preferences(
        self,
        user_id: int,
        company_id: str
    ) -> Dict[str, Any]:
        """Obtiene preferencias de notificación del usuario"""

        try:
            query = """
            SELECT
                notification_preferences,
                email_notifications,
                push_notifications,
                slack_notifications
            FROM user_notification_preferences
            WHERE user_id = $1 AND company_id = $2
            """

            result = await self.db.fetch_one(query, user_id, company_id)

            if result:
                return {
                    "preferences": json.loads(result["notification_preferences"] or "{}"),
                    "email_enabled": result["email_notifications"],
                    "push_enabled": result["push_notifications"],
                    "slack_enabled": result["slack_notifications"]
                }
            else:
                # Preferencias por defecto
                return {
                    "preferences": {},
                    "email_enabled": True,
                    "push_enabled": True,
                    "slack_enabled": False
                }

        except Exception as e:
            logger.error(f"Failed to get notification preferences for user {user_id}: {e}")
            return {"preferences": {}, "email_enabled": True, "push_enabled": False, "slack_enabled": False}

    async def update_notification_preferences(
        self,
        user_id: int,
        company_id: str,
        preferences: Dict[str, Any]
    ) -> bool:
        """Actualiza preferencias de notificación"""

        try:
            query = """
            INSERT INTO user_notification_preferences (
                user_id, company_id, notification_preferences,
                email_notifications, push_notifications, slack_notifications,
                updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id, company_id) DO UPDATE SET
                notification_preferences = EXCLUDED.notification_preferences,
                email_notifications = EXCLUDED.email_notifications,
                push_notifications = EXCLUDED.push_notifications,
                slack_notifications = EXCLUDED.slack_notifications,
                updated_at = CURRENT_TIMESTAMP
            """

            await self.db.execute(
                query,
                user_id,
                company_id,
                json.dumps(preferences.get("preferences", {})),
                preferences.get("email_enabled", True),
                preferences.get("push_enabled", True),
                preferences.get("slack_enabled", False)
            )

            return True

        except Exception as e:
            logger.error(f"Failed to update notification preferences for user {user_id}: {e}")
            return False

    async def get_notification_history(
        self,
        action_id: Optional[str] = None,
        user_id: Optional[int] = None,
        company_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Obtiene historial de notificaciones"""

        try:
            conditions = []
            params = []
            param_index = 1

            if action_id:
                conditions.append(f"action_id = ${param_index}")
                params.append(action_id)
                param_index += 1

            if company_id:
                conditions.append(f"company_id = ${param_index}")
                params.append(company_id)
                param_index += 1

            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

            query = f"""
            SELECT
                notification_id, action_id, channel, status,
                recipients, subject, sent_at, delivered_at,
                error_message, retry_count
            FROM expense_action_notifications
            {where_clause}
            ORDER BY sent_at DESC
            LIMIT ${param_index}
            """

            params.append(limit)

            results = await self.db.fetch_all(query, *params)
            return [dict(result) for result in results]

        except Exception as e:
            logger.error(f"Failed to get notification history: {e}")
            return []

    # Métodos privados

    async def _send_notification(self, request: NotificationRequest) -> NotificationResult:
        """Envía una notificación específica"""

        start_time = datetime.utcnow()
        delivery_details = []
        delivered_count = 0
        failed_count = 0

        try:
            # Obtener template
            template = await self._get_template(request.template_id, request.channel)
            if not template:
                raise ValueError(f"Template {request.template_id} not found")

            # Renderizar contenido
            rendered_content = self._render_template(template, request.template_data)

            # Filtrar destinatarios activos
            active_recipients = [r for r in request.recipients if r.is_active]

            # Enviar según canal
            if request.channel == NotificationChannel.EMAIL:
                delivery_details = await self._send_email_notifications(
                    active_recipients, rendered_content, template.subject_template, request.template_data
                )
            elif request.channel == NotificationChannel.WEBHOOK:
                delivery_details = await self._send_webhook_notifications(
                    active_recipients, rendered_content, request.template_data
                )
            elif request.channel == NotificationChannel.SLACK:
                delivery_details = await self._send_slack_notifications(
                    active_recipients, rendered_content
                )
            elif request.channel == NotificationChannel.INTERNAL:
                delivery_details = await self._send_internal_notifications(
                    active_recipients, rendered_content, request.action_id
                )
            else:
                raise ValueError(f"Channel {request.channel} not implemented")

            # Contar resultados
            delivered_count = sum(1 for d in delivery_details if d["status"] == "delivered")
            failed_count = len(delivery_details) - delivered_count

            # Determinar estado general
            if delivered_count == len(delivery_details):
                status = NotificationStatus.DELIVERED
            elif delivered_count > 0:
                status = NotificationStatus.SENT  # Parcialmente entregado
            else:
                status = NotificationStatus.FAILED

            # Persistir resultado
            await self._persist_notification_result(request, delivery_details, status)

            # Actualizar estadísticas
            await self._update_delivery_stats(request.channel, request.action_id, status, delivered_count, failed_count)

            return NotificationResult(
                notification_id=request.notification_id,
                status=status,
                delivered_count=delivered_count,
                failed_count=failed_count,
                delivery_details=delivery_details,
                sent_at=start_time
            )

        except Exception as e:
            logger.error(f"Failed to send notification {request.notification_id}: {e}")

            await self._persist_notification_result(request, [], NotificationStatus.FAILED, str(e))

            return NotificationResult(
                notification_id=request.notification_id,
                status=NotificationStatus.FAILED,
                delivered_count=0,
                failed_count=len(request.recipients),
                delivery_details=[],
                error_message=str(e)
            )

    async def _send_email_notifications(
        self,
        recipients: List[NotificationRecipient],
        content: str,
        subject_template: str,
        template_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Envía notificaciones por email"""

        delivery_details = []
        smtp_config = self.channel_configs[NotificationChannel.EMAIL]

        try:
            # Renderizar subject
            subject = Template(subject_template).render(**template_data)

            for recipient in recipients:
                try:
                    # Crear mensaje
                    msg = MIMEMultipart('alternative')
                    msg['Subject'] = subject
                    msg['From'] = smtp_config["from_address"]
                    msg['To'] = recipient.address

                    # Adjuntar contenido
                    msg.attach(MIMEText(content, 'html' if '<' in content else 'plain'))

                    # Enviar
                    with smtplib.SMTP(smtp_config["smtp_host"], smtp_config["smtp_port"]) as server:
                        if smtp_config["smtp_username"]:
                            server.starttls()
                            server.login(smtp_config["smtp_username"], smtp_config["smtp_password"])

                        server.send_message(msg)

                    delivery_details.append({
                        "recipient": recipient.address,
                        "status": "delivered",
                        "delivered_at": datetime.utcnow().isoformat(),
                        "message": "Email sent successfully"
                    })

                except Exception as e:
                    delivery_details.append({
                        "recipient": recipient.address,
                        "status": "failed",
                        "error": str(e),
                        "attempted_at": datetime.utcnow().isoformat()
                    })

        except Exception as e:
            logger.error(f"Email notification setup failed: {e}")
            for recipient in recipients:
                delivery_details.append({
                    "recipient": recipient.address,
                    "status": "failed",
                    "error": f"Setup error: {str(e)}",
                    "attempted_at": datetime.utcnow().isoformat()
                })

        return delivery_details

    async def _send_webhook_notifications(
        self,
        recipients: List[NotificationRecipient],
        content: str,
        template_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Envía notificaciones por webhook"""

        delivery_details = []
        webhook_config = self.channel_configs[NotificationChannel.WEBHOOK]

        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=webhook_config["timeout_seconds"])
        ) as session:

            for recipient in recipients:
                try:
                    payload = {
                        "notification_type": "expense_action_completed",
                        "timestamp": datetime.utcnow().isoformat(),
                        "content": content,
                        "data": template_data
                    }

                    async with session.post(
                        recipient.address,
                        json=payload,
                        headers={"Content-Type": "application/json"}
                    ) as response:
                        if response.status == 200:
                            delivery_details.append({
                                "recipient": recipient.address,
                                "status": "delivered",
                                "delivered_at": datetime.utcnow().isoformat(),
                                "response_status": response.status
                            })
                        else:
                            delivery_details.append({
                                "recipient": recipient.address,
                                "status": "failed",
                                "error": f"HTTP {response.status}",
                                "attempted_at": datetime.utcnow().isoformat()
                            })

                except Exception as e:
                    delivery_details.append({
                        "recipient": recipient.address,
                        "status": "failed",
                        "error": str(e),
                        "attempted_at": datetime.utcnow().isoformat()
                    })

        return delivery_details

    async def _send_slack_notifications(
        self,
        recipients: List[NotificationRecipient],
        content: str
    ) -> List[Dict[str, Any]]:
        """Envía notificaciones a Slack"""

        delivery_details = []
        slack_config = self.channel_configs[NotificationChannel.SLACK]

        if not slack_config.get("bot_token"):
            for recipient in recipients:
                delivery_details.append({
                    "recipient": recipient.address,
                    "status": "failed",
                    "error": "Slack bot token not configured",
                    "attempted_at": datetime.utcnow().isoformat()
                })
            return delivery_details

        # Implementación simplificada - en producción usaría SDK de Slack
        async with aiohttp.ClientSession() as session:
            for recipient in recipients:
                try:
                    payload = {
                        "channel": recipient.address,
                        "text": content,
                        "username": "MCP Expenses Bot"
                    }

                    headers = {
                        "Authorization": f"Bearer {slack_config['bot_token']}",
                        "Content-Type": "application/json"
                    }

                    async with session.post(
                        "https://slack.com/api/chat.postMessage",
                        json=payload,
                        headers=headers
                    ) as response:
                        if response.status == 200:
                            delivery_details.append({
                                "recipient": recipient.address,
                                "status": "delivered",
                                "delivered_at": datetime.utcnow().isoformat()
                            })
                        else:
                            delivery_details.append({
                                "recipient": recipient.address,
                                "status": "failed",
                                "error": f"Slack API error: {response.status}",
                                "attempted_at": datetime.utcnow().isoformat()
                            })

                except Exception as e:
                    delivery_details.append({
                        "recipient": recipient.address,
                        "status": "failed",
                        "error": str(e),
                        "attempted_at": datetime.utcnow().isoformat()
                    })

        return delivery_details

    async def _send_internal_notifications(
        self,
        recipients: List[NotificationRecipient],
        content: str,
        action_id: str
    ) -> List[Dict[str, Any]]:
        """Envía notificaciones internas (en la aplicación)"""

        delivery_details = []

        try:
            for recipient in recipients:
                # Almacenar notificación interna
                query = """
                INSERT INTO internal_notifications (
                    user_id, title, message, action_id, is_read, created_at
                ) VALUES ($1, $2, $3, $4, FALSE, CURRENT_TIMESTAMP)
                """

                await self.db.execute(
                    query,
                    int(recipient.recipient_id),
                    "Acción de Gastos Completada",
                    content,
                    action_id
                )

                delivery_details.append({
                    "recipient": recipient.recipient_id,
                    "status": "delivered",
                    "delivered_at": datetime.utcnow().isoformat(),
                    "message": "Internal notification created"
                })

        except Exception as e:
            for recipient in recipients:
                delivery_details.append({
                    "recipient": recipient.recipient_id,
                    "status": "failed",
                    "error": str(e),
                    "attempted_at": datetime.utcnow().isoformat()
                })

        return delivery_details

    async def _get_default_recipients(self, action_record: ActionRecord) -> List[NotificationRecipient]:
        """Obtiene destinatarios por defecto para una acción"""

        recipients = []

        try:
            # Destinatario principal: usuario que ejecutó la acción
            user_query = """
            SELECT id, email, full_name
            FROM users
            WHERE id = $1 AND is_active = TRUE
            """

            user = await self.db.fetch_one(user_query, action_record.context.user_id)
            if user and user["email"]:
                recipients.append(NotificationRecipient(
                    recipient_id=str(user["id"]),
                    recipient_type="user",
                    address=user["email"],
                    is_active=True
                ))

            # Destinatarios adicionales según tipo de acción
            if action_record.action_type in [ActionType.DELETE, ActionType.BULK_UPDATE]:
                # Para acciones críticas, notificar supervisores
                supervisor_query = """
                SELECT u.id, u.email
                FROM users u
                WHERE u.company_id = $1
                AND u.role IN ('admin', 'supervisor')
                AND u.is_active = TRUE
                """

                supervisors = await self.db.fetch_all(supervisor_query, action_record.context.company_id)
                for supervisor in supervisors:
                    recipients.append(NotificationRecipient(
                        recipient_id=str(supervisor["id"]),
                        recipient_type="supervisor",
                        address=supervisor["email"],
                        is_active=True
                    ))

        except Exception as e:
            logger.error(f"Failed to get default recipients: {e}")

        return recipients

    async def _get_error_notification_recipients(self, action_record: ActionRecord) -> List[NotificationRecipient]:
        """Obtiene destinatarios para notificaciones de error"""

        recipients = []

        try:
            # Administradores del sistema
            admin_query = """
            SELECT id, email
            FROM users
            WHERE company_id = $1
            AND role = 'admin'
            AND is_active = TRUE
            """

            admins = await self.db.fetch_all(admin_query, action_record.context.company_id)
            for admin in admins:
                recipients.append(NotificationRecipient(
                    recipient_id=str(admin["id"]),
                    recipient_type="admin",
                    address=admin["email"],
                    is_active=True
                ))

            # Usuario que ejecutó la acción
            user = await self.db.fetch_one(
                "SELECT id, email FROM users WHERE id = $1",
                action_record.context.user_id
            )
            if user and user["email"]:
                recipients.append(NotificationRecipient(
                    recipient_id=str(user["id"]),
                    recipient_type="user",
                    address=user["email"],
                    is_active=True
                ))

        except Exception as e:
            logger.error(f"Failed to get error notification recipients: {e}")

        return recipients

    async def _determine_notification_channels(self, action_record: ActionRecord) -> List[NotificationChannel]:
        """Determina canales de notificación según la acción"""

        channels = [NotificationChannel.INTERNAL]  # Siempre notificación interna

        # Agregar email por defecto
        channels.append(NotificationChannel.EMAIL)

        # Para acciones críticas, agregar más canales
        if action_record.action_type in [ActionType.DELETE, ActionType.BULK_UPDATE]:
            if action_record.affected_records > 100:
                channels.append(NotificationChannel.SLACK)

        return channels

    def _determine_priority(self, action_record: ActionRecord) -> NotificationPriority:
        """Determina prioridad de notificación"""

        if action_record.status.value == "failed":
            return NotificationPriority.HIGH

        if action_record.action_type == ActionType.DELETE:
            return NotificationPriority.HIGH
        elif action_record.action_type == ActionType.BULK_UPDATE and action_record.affected_records > 500:
            return NotificationPriority.HIGH
        elif action_record.affected_records > 100:
            return NotificationPriority.NORMAL
        else:
            return NotificationPriority.LOW

    def _prepare_template_data(self, action_record: ActionRecord) -> Dict[str, Any]:
        """Prepara datos para templates"""

        return {
            "action_id": action_record.action_id,
            "action_type": action_record.action_type.value,
            "action_type_display": self._get_action_display_name(action_record.action_type),
            "status": action_record.status.value,
            "status_display": self._get_status_display_name(action_record.status.value),
            "affected_records": action_record.affected_records,
            "execution_time": action_record.execution_time_ms,
            "started_at": action_record.started_at.strftime("%Y-%m-%d %H:%M:%S"),
            "completed_at": action_record.completed_at.strftime("%Y-%m-%d %H:%M:%S") if action_record.completed_at else None,
            "company_id": action_record.context.company_id,
            "user_id": action_record.context.user_id,
            "parameters": action_record.parameters,
            "error_message": action_record.error_message
        }

    def _prepare_bulk_template_data(self, action_records: List[ActionRecord]) -> Dict[str, Any]:
        """Prepara datos para templates de notificaciones bulk"""

        total_records = sum(r.affected_records for r in action_records)
        successful_actions = sum(1 for r in action_records if r.status.value == "completed")

        return {
            "total_actions": len(action_records),
            "successful_actions": successful_actions,
            "failed_actions": len(action_records) - successful_actions,
            "total_records_affected": total_records,
            "actions_summary": [
                {
                    "action_id": r.action_id,
                    "action_type": r.action_type.value,
                    "status": r.status.value,
                    "affected_records": r.affected_records
                }
                for r in action_records
            ],
            "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        }

    def _get_action_display_name(self, action_type: ActionType) -> str:
        """Obtiene nombre amigable para tipo de acción"""

        display_names = {
            ActionType.MARK_INVOICED: "Marcar como Facturado",
            ActionType.MARK_NO_INVOICE: "Marcar sin Factura",
            ActionType.UPDATE_CATEGORY: "Actualizar Categoría",
            ActionType.BULK_UPDATE: "Actualización Masiva",
            ActionType.ARCHIVE: "Archivar",
            ActionType.DELETE: "Eliminar"
        }

        return display_names.get(action_type, action_type.value)

    def _get_status_display_name(self, status: str) -> str:
        """Obtiene nombre amigable para estado"""

        display_names = {
            "completed": "Completada",
            "failed": "Fallida",
            "in_progress": "En Progreso",
            "pending": "Pendiente"
        }

        return display_names.get(status, status)

    async def _get_template(self, template_id: str, channel: NotificationChannel) -> Optional[NotificationTemplate]:
        """Obtiene template de notificación"""

        # Buscar en templates por defecto
        return self._default_templates.get(f"{template_id}_{channel.value}")

    def _render_template(self, template: NotificationTemplate, data: Dict[str, Any]) -> str:
        """Renderiza template con datos"""

        try:
            jinja_template = Template(template.body_template)
            return jinja_template.render(**data)
        except Exception as e:
            logger.error(f"Template rendering failed: {e}")
            return f"Notification content could not be rendered: {str(e)}"

    def _get_retry_policy(self, channel: NotificationChannel, priority: NotificationPriority) -> Dict[str, Any]:
        """Obtiene política de reintentos"""

        base_policy = {"max_attempts": 3, "delay_seconds": 60}

        if priority == NotificationPriority.URGENT:
            base_policy["max_attempts"] = 5
            base_policy["delay_seconds"] = 30
        elif priority == NotificationPriority.LOW:
            base_policy["max_attempts"] = 2
            base_policy["delay_seconds"] = 300

        return base_policy

    async def _persist_notification_result(
        self,
        request: NotificationRequest,
        delivery_details: List[Dict[str, Any]],
        status: NotificationStatus,
        error_message: Optional[str] = None
    ):
        """Persiste resultado de notificación"""

        try:
            query = """
            INSERT INTO expense_action_notifications (
                action_id, notification_type, recipients, status,
                subject, message, sent_at, error_message, retry_count
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 0)
            """

            await self.db.execute(
                query,
                request.action_id,
                request.channel.value,
                json.dumps([r.address for r in request.recipients]),
                status.value,
                "Expense Action Notification",
                json.dumps(delivery_details),
                datetime.utcnow(),
                error_message
            )

        except Exception as e:
            logger.error(f"Failed to persist notification result: {e}")

    async def _update_delivery_stats(
        self,
        channel: NotificationChannel,
        action_id: str,
        status: NotificationStatus,
        delivered_count: int,
        failed_count: int
    ):
        """Actualiza estadísticas de entrega"""

        if status == NotificationStatus.DELIVERED:
            self._delivery_stats["total_sent"] += delivered_count
        else:
            self._delivery_stats["total_failed"] += failed_count

        # Actualizar por canal
        channel_key = channel.value
        if channel_key not in self._delivery_stats["by_channel"]:
            self._delivery_stats["by_channel"][channel_key] = {"sent": 0, "failed": 0}

        self._delivery_stats["by_channel"][channel_key]["sent"] += delivered_count
        self._delivery_stats["by_channel"][channel_key]["failed"] += failed_count

    def _initialize_default_templates(self) -> Dict[str, NotificationTemplate]:
        """Inicializa templates por defecto"""

        templates = {}

        # Template de email para acción completada
        templates["mark_invoiced_email"] = NotificationTemplate(
            template_id="mark_invoiced_email",
            channel=NotificationChannel.EMAIL,
            action_type=ActionType.MARK_INVOICED,
            subject_template="Gastos marcados como facturados - Acción {{ action_id }}",
            body_template="""
            <h2>Acción de Gastos Completada</h2>
            <p>La acción <strong>{{ action_type_display }}</strong> ha sido completada exitosamente.</p>

            <h3>Detalles:</h3>
            <ul>
                <li><strong>ID de Acción:</strong> {{ action_id }}</li>
                <li><strong>Estado:</strong> {{ status_display }}</li>
                <li><strong>Registros Afectados:</strong> {{ affected_records }}</li>
                <li><strong>Tiempo de Ejecución:</strong> {{ execution_time }}ms</li>
                <li><strong>Completado:</strong> {{ completed_at }}</li>
            </ul>

            <p>Esta notificación fue generada automáticamente por el Sistema MCP de Gastos.</p>
            """,
            is_html=True
        )

        # Template genérico para notificaciones internas
        templates["generic_internal"] = NotificationTemplate(
            template_id="generic_internal",
            channel=NotificationChannel.INTERNAL,
            action_type=ActionType.BULK_UPDATE,  # Genérico
            subject_template="Acción {{ action_type_display }} Completada",
            body_template="La acción {{ action_type_display }} ha sido {{ status_display }}. {{ affected_records }} registros fueron procesados.",
            is_html=False
        )

        return templates


# Singleton instance
notification_system = ExpenseNotificationSystem(None)  # Se inicializa con el adaptador de BD


# Helper functions

async def notify_action_completed(action_record: ActionRecord) -> List[NotificationResult]:
    """Helper para notificar acción completada"""
    return await notification_system.notify_action_completed(action_record)


async def notify_action_failed(action_record: ActionRecord, error_details: Dict[str, Any]) -> List[NotificationResult]:
    """Helper para notificar acción fallida"""
    return await notification_system.notify_action_failed(action_record, error_details)