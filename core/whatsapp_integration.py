"""
WhatsApp Integration - Integración con WhatsApp Business API para detectar gastos
"""

import os
import logging
import json
import hmac
import hashlib
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

try:
    import requests
except ImportError:
    requests = None

from .intent_analyzer import get_intent_analyzer, ExpenseIntent

logger = logging.getLogger(__name__)


@dataclass
class WhatsAppMessage:
    """Representa un mensaje de WhatsApp"""
    message_id: str
    from_number: str
    text: str
    timestamp: datetime
    message_type: str
    metadata: Dict[str, Any]


class WhatsAppIntegration:
    """
    Integración con WhatsApp Business API para recibir mensajes
    y detectar gastos automáticamente
    """

    def __init__(self):
        self.access_token = os.getenv('WHATSAPP_ACCESS_TOKEN')
        self.verify_token = os.getenv('WHATSAPP_VERIFY_TOKEN')
        self.phone_number_id = os.getenv('WHATSAPP_PHONE_NUMBER_ID')
        self.webhook_secret = os.getenv('WHATSAPP_WEBHOOK_SECRET')

        self.intent_analyzer = get_intent_analyzer()

        # URL base de WhatsApp Business API
        self.base_url = f"https://graph.facebook.com/v18.0/{self.phone_number_id}"

        # Números autorizados para recibir mensajes de gastos
        self.authorized_numbers = self._load_authorized_numbers()

        if not self.access_token:
            logger.warning("WHATSAPP_ACCESS_TOKEN not configured")

    def _load_authorized_numbers(self) -> List[str]:
        """Cargar números autorizados desde variable de entorno"""
        numbers_str = os.getenv('WHATSAPP_AUTHORIZED_NUMBERS', '')
        if numbers_str:
            return [num.strip() for num in numbers_str.split(',')]
        return []

    def verify_webhook(self, mode: str, token: str, challenge: str) -> Optional[str]:
        """
        Verificar webhook de WhatsApp Business API

        Returns:
            Challenge string si la verificación es exitosa, None si falla
        """
        # DEBUG: Log all parameters
        logger.info(f"DEBUG verify_webhook called:")
        logger.info(f"  - mode: '{mode}' (type: {type(mode).__name__})")
        logger.info(f"  - token received: '{token}' (type: {type(token).__name__})")
        logger.info(f"  - token expected: '{self.verify_token}' (type: {type(self.verify_token).__name__})")
        logger.info(f"  - challenge: '{challenge}'")
        logger.info(f"  - mode == 'subscribe': {mode == 'subscribe'}")
        logger.info(f"  - token == self.verify_token: {token == self.verify_token}")

        if mode == "subscribe" and token == self.verify_token:
            logger.info("WhatsApp webhook verified successfully")
            return challenge
        else:
            logger.warning(f"WhatsApp webhook verification failed - mode={mode}, token_match={token == self.verify_token}")
            return None

    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """Verificar firma del webhook para seguridad"""
        if not self.webhook_secret:
            logger.warning("Webhook secret not configured, skipping signature verification")
            return True

        expected_signature = hmac.new(
            self.webhook_secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()

        # El signature viene como "sha256=<hash>"
        signature_hash = signature.replace('sha256=', '') if signature.startswith('sha256=') else signature

        return hmac.compare_digest(expected_signature, signature_hash)

    def process_webhook_message(self, webhook_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Procesar mensaje recibido del webhook de WhatsApp

        Returns:
            Lista de gastos detectados y procesados
        """
        processed_expenses = []

        try:
            entry = webhook_data.get('entry', [])
            if not entry:
                return processed_expenses

            for entry_item in entry:
                changes = entry_item.get('changes', [])

                for change in changes:
                    if change.get('field') != 'messages':
                        continue

                    value = change.get('value', {})
                    messages = value.get('messages', [])

                    for message in messages:
                        if message.get('type') == 'text':
                            expense = self._process_text_message(message, value)
                            if expense:
                                processed_expenses.append(expense)

        except Exception as e:
            logger.error(f"Error processing WhatsApp webhook: {e}")

        return processed_expenses

    def _process_text_message(self, message: Dict[str, Any], context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Procesar mensaje de texto individual"""

        try:
            return self.process_text_payload(
                message_id=message.get('id'),
                from_number=message.get('from'),
                text=message.get('text', {}).get('body', ''),
                timestamp=message.get('timestamp'),
                contacts=context.get('contacts', []),
                extra_metadata={'raw_context': context}
            )
        except Exception as e:
            logger.error(f"Error processing WhatsApp text message: {e}")
            return None

    def process_text_payload(
        self,
        *,
        message_id: Optional[str],
        from_number: str,
        text: str,
        timestamp: Optional[str] = None,
        contacts: Optional[List[Dict[str, Any]]] = None,
        extra_metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Procesa cualquier texto (voz transcrita, OCR, etc.) como un gasto potencial"""

        if not text or not text.strip():
            logger.info("Mensaje vacío, se ignora para análisis de gastos")
            return None

        if self.authorized_numbers and from_number not in self.authorized_numbers:
            logger.info(f"Message from unauthorized number: {from_number}")
            return None

        try:
            timestamp_value = datetime.fromtimestamp(int(timestamp)) if timestamp else datetime.now()
        except Exception:
            timestamp_value = datetime.now()

        metadata = {
            'message_id': message_id or f"manual-{datetime.utcnow().timestamp()}",
            'from_number': from_number,
            'timestamp': timestamp_value.isoformat(),
            'platform': 'whatsapp',
            'contacts': contacts or [],
            'profile_name': self._get_contact_name(contacts or [], from_number)
        }

        if extra_metadata:
            metadata.update(extra_metadata)

        intent = self.intent_analyzer.analyze_intent(
            text=text,
            source='whatsapp',
            metadata=metadata
        )

        if intent.is_expense and intent.confidence > 0.5:
            expense_data = self._create_expense_from_intent(intent, metadata)
            self._send_confirmation_message(from_number, intent, expense_data)
            logger.info(f"Expense detected from WhatsApp: {expense_data.get('descripcion')}")
            return expense_data

        if intent.confidence < 0.3:
            self._send_info_message(
                from_number,
                "No detecté información de gastos en tu mensaje. "
                "Puedes enviar algo como: 'Gasté $500 en gasolina en Pemex'"
            )

        logger.info(f"No expense detected in message from {from_number}: {intent.reasoning}")
        return None

    def _get_contact_name(self, contacts: List[Dict], phone_number: str) -> str:
        """Obtener nombre del contacto"""
        for contact in contacts:
            if contact.get('wa_id') == phone_number:
                profile = contact.get('profile', {})
                return profile.get('name', phone_number)
        return phone_number

    def _create_expense_from_intent(self, intent: ExpenseIntent, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Crear registro de gasto desde la intención detectada"""

        extracted = intent.extracted_data

        expense_data = {
            'id': f"WA-{metadata['message_id']}",
            'descripcion': extracted.get('descripcion', intent.original_text[:100]),
            'monto_total': extracted.get('monto', 0.0),
            'categoria': extracted.get('categoria', 'oficina'),
            'fecha_gasto': extracted.get('fecha_probable', datetime.now().strftime('%Y-%m-%d')),
            'input_method': 'whatsapp_auto',
            'estado_factura': 'pendiente',
            'workflow_status': 'pendiente_factura',
            'proveedor': {
                'nombre': extracted.get('proveedor', 'Por definir'),
                'rfc': ''
            },
            'metadata': {
                'whatsapp': metadata,
                'intent_analysis': {
                    'confidence': intent.confidence,
                    'reasoning': intent.reasoning,
                    'source': intent.source,
                    'original_text': intent.original_text
                },
                'auto_detected': True,
                'requires_validation': intent.confidence < 0.8
            },
            'asientos_contables': {
                'numero_poliza': f"WA-{datetime.now().strftime('%Y%m%d')}-{metadata['message_id'][:8]}",
                'tipo_poliza': 'Diario',
                'fecha_asiento': datetime.now().strftime('%Y-%m-%d'),
                'concepto': f"Gasto detectado automáticamente: {extracted.get('descripcion', 'Gasto desde WhatsApp')}",
                'balanceado': True,
                'movimientos': [
                    {
                        'cuenta': '60101',
                        'nombre_cuenta': f"Gastos de {extracted.get('categoria', 'Oficina').title()}",
                        'debe': extracted.get('monto', 0.0),
                        'haber': 0,
                        'tipo': 'debe'
                    },
                    {
                        'cuenta': '11301',
                        'nombre_cuenta': 'Bancos - Cuenta Principal',
                        'debe': 0,
                        'haber': extracted.get('monto', 0.0),
                        'tipo': 'haber'
                    }
                ]
            }
        }

        return expense_data

    def _send_confirmation_message(self, to_number: str, intent: ExpenseIntent, expense_data: Dict[str, Any]):
        """Enviar mensaje de confirmación al usuario"""

        if not self.access_token:
            logger.warning("Cannot send WhatsApp message: access token not configured")
            return

        try:
            confidence_emoji = "🟢" if intent.confidence > 0.8 else "🟡" if intent.confidence > 0.6 else "🟠"

            message = f"""✅ *Gasto Detectado Automáticamente*

{confidence_emoji} Confianza: {(intent.confidence * 100):.1f}%

📋 *Detalles:*
• Descripción: {expense_data['descripcion']}
• Monto: ${expense_data['monto_total']:,.2f}
• Categoría: {expense_data['categoria']}
• Fecha: {expense_data['fecha_gasto']}

🤖 *Análisis IA:* {intent.reasoning}

{"⚠️ *Requiere validación manual*" if expense_data['metadata']['requires_validation'] else "✅ *Registrado automáticamente*"}

Puedes revisar y editar este gasto en el sistema."""

            self._send_text_message(to_number, message)

        except Exception as e:
            logger.error(f"Error sending WhatsApp confirmation: {e}")

    def _send_info_message(self, to_number: str, message: str):
        """Enviar mensaje informativo al usuario"""

        if not self.access_token:
            return

        try:
            self._send_text_message(to_number, f"ℹ️ {message}")
        except Exception as e:
            logger.error(f"Error sending WhatsApp info message: {e}")

    def _send_text_message(self, to_number: str, message: str):
        """Enviar mensaje de texto via WhatsApp Business API"""

        if not requests:
            logger.error("requests library not available for WhatsApp API")
            return

        url = f"{self.base_url}/messages"
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }

        data = {
            'messaging_product': 'whatsapp',
            'to': to_number,
            'type': 'text',
            'text': {
                'body': message
            }
        }

        response = requests.post(url, headers=headers, json=data)

        if response.status_code == 200:
            logger.info(f"WhatsApp message sent successfully to {to_number}")
        else:
            logger.error(f"Failed to send WhatsApp message: {response.status_code} - {response.text}")

    def send_expense_summary(self, to_number: str, expenses: List[Dict[str, Any]]):
        """Enviar resumen de gastos detectados"""

        if not expenses:
            return

        total_amount = sum(exp.get('monto_total', 0) for exp in expenses)

        message = f"""📊 *Resumen de Gastos Detectados*

Total de gastos: {len(expenses)}
Monto total: ${total_amount:,.2f}

"""

        for i, expense in enumerate(expenses[:5], 1):
            message += f"{i}. {expense['descripcion']} - ${expense['monto_total']:,.2f}\n"

        if len(expenses) > 5:
            message += f"\n... y {len(expenses) - 5} gastos más."

        message += "\n\n🔗 Revisa todos los detalles en el sistema de gestión de gastos."

        self._send_text_message(to_number, message)

    def send_info_message(self, to_number: str, message: str):
        """Wrapper público para enviar mensajes informativos"""
        self._send_info_message(to_number, message)

    def get_contact_display_name(self, contacts: List[Dict[str, Any]], phone_number: str) -> str:
        """Expose contact name helper"""
        return self._get_contact_name(contacts, phone_number)

    def get_webhook_info(self) -> Dict[str, Any]:
        """Obtener información para configurar el webhook"""

        return {
            'webhook_url': 'https://tu-servidor.com/webhooks/whatsapp',
            'verify_token': self.verify_token or 'CONFIGURA_WHATSAPP_VERIFY_TOKEN',
            'required_permissions': [
                'messages',
                'message_echoes'
            ],
            'webhook_fields': [
                'messages'
            ],
            'setup_instructions': [
                '1. Configura las variables de entorno:',
                '   - WHATSAPP_ACCESS_TOKEN (token de acceso de la app)',
                '   - WHATSAPP_VERIFY_TOKEN (token de verificación)',
                '   - WHATSAPP_PHONE_NUMBER_ID (ID del número de teléfono)',
                '   - WHATSAPP_WEBHOOK_SECRET (secreto para verificar firmas)',
                '   - WHATSAPP_AUTHORIZED_NUMBERS (números autorizados, separados por coma)',
                '2. Configura el webhook en la consola de Meta for Developers',
                '3. Verifica que el endpoint /webhooks/whatsapp esté accesible'
            ]
        }


# Instancia global
_whatsapp_integration = None

def get_whatsapp_integration() -> WhatsAppIntegration:
    """Obtener instancia global de la integración de WhatsApp"""
    global _whatsapp_integration
    if _whatsapp_integration is None:
        _whatsapp_integration = WhatsAppIntegration()
    return _whatsapp_integration
