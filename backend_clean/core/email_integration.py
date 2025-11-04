"""
Email Integration - Integración con correo electrónico para detectar gastos automáticamente
"""

import os
import logging
import imaplib
import email
import smtplib
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from .intent_analyzer import get_intent_analyzer, ExpenseIntent

logger = logging.getLogger(__name__)


@dataclass
class EmailMessage:
    """Representa un mensaje de email"""
    message_id: str
    sender: str
    subject: str
    body: str
    date: datetime
    attachments: List[str]
    is_html: bool


class EmailIntegration:
    """
    Integración con correo electrónico para detectar gastos automáticamente
    Soporta IMAP para recibir y SMTP para enviar
    """

    def __init__(self):
        # Configuración IMAP (para recibir)
        self.imap_server = os.getenv('EMAIL_IMAP_SERVER', 'imap.gmail.com')
        self.imap_port = int(os.getenv('EMAIL_IMAP_PORT', '993'))
        self.email_address = os.getenv('EMAIL_ADDRESS')
        self.email_password = os.getenv('EMAIL_PASSWORD')

        # Configuración SMTP (para enviar)
        self.smtp_server = os.getenv('EMAIL_SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('EMAIL_SMTP_PORT', '587'))

        # Configuraciones adicionales
        self.check_interval = int(os.getenv('EMAIL_CHECK_INTERVAL', '300'))  # 5 minutos
        self.authorized_senders = self._load_authorized_senders()
        self.expense_keywords = self._load_expense_keywords()

        self.intent_analyzer = get_intent_analyzer()

        if not self.email_address or not self.email_password:
            logger.warning("Email credentials not configured")

    def _load_authorized_senders(self) -> List[str]:
        """Cargar remitentes autorizados"""
        senders_str = os.getenv('EMAIL_AUTHORIZED_SENDERS', '')
        if senders_str:
            return [sender.strip().lower() for sender in senders_str.split(',')]
        return []

    def _load_expense_keywords(self) -> List[str]:
        """Keywords en asunto que indican posibles gastos"""
        return [
            'factura', 'recibo', 'comprobante', 'ticket', 'invoice',
            'gasto', 'pago', 'compra', 'purchase', 'payment',
            'reembolso', 'reimbursement', 'expense', 'receipt'
        ]

    def connect_imap(self) -> Optional[imaplib.IMAP4_SSL]:
        """Conectar al servidor IMAP"""
        try:
            mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            mail.login(self.email_address, self.email_password)
            return mail
        except Exception as e:
            logger.error(f"Error connecting to IMAP server: {e}")
            return None

    def check_new_messages(self, folder: str = 'INBOX', days_back: int = 1) -> List[EmailMessage]:
        """
        Revisar nuevos mensajes en busca de gastos

        Args:
            folder: Carpeta de email a revisar
            days_back: Días hacia atrás para revisar

        Returns:
            Lista de mensajes parseados
        """
        messages = []

        try:
            mail = self.connect_imap()
            if not mail:
                return messages

            mail.select(folder)

            # Buscar mensajes recientes
            import datetime as dt
            since_date = (dt.datetime.now() - dt.timedelta(days=days_back)).strftime('%d-%b-%Y')
            search_criteria = f'SINCE {since_date}'

            # Filtrar por remitentes autorizados si están configurados
            if self.authorized_senders:
                sender_criteria = ' '.join([f'FROM "{sender}"' for sender in self.authorized_senders])
                search_criteria = f'({search_criteria}) ({sender_criteria})'

            status, message_ids = mail.search(None, search_criteria)

            if status != 'OK':
                logger.warning(f"Email search failed: {status}")
                return messages

            for msg_id in message_ids[0].split():
                try:
                    email_msg = self._fetch_and_parse_message(mail, msg_id)
                    if email_msg:
                        messages.append(email_msg)
                except Exception as e:
                    logger.error(f"Error parsing email {msg_id}: {e}")

            mail.close()
            mail.logout()

        except Exception as e:
            logger.error(f"Error checking email messages: {e}")

        return messages

    def _fetch_and_parse_message(self, mail: imaplib.IMAP4_SSL, msg_id: bytes) -> Optional[EmailMessage]:
        """Obtener y parsear un mensaje individual"""

        try:
            status, msg_data = mail.fetch(msg_id, '(RFC822)')
            if status != 'OK':
                return None

            raw_email = msg_data[0][1]
            email_message = email.message_from_bytes(raw_email)

            # Extraer información básica
            message_id = email_message.get('Message-ID', str(msg_id))
            sender = email_message.get('From', '')
            subject = email_message.get('Subject', '')
            date_str = email_message.get('Date', '')

            # Parsear fecha
            try:
                date = email.utils.parsedate_to_datetime(date_str)
            except:
                date = datetime.now()

            # Extraer cuerpo del mensaje
            body, is_html = self._extract_body(email_message)

            # Extraer attachments
            attachments = self._extract_attachments(email_message)

            return EmailMessage(
                message_id=message_id,
                sender=sender,
                subject=subject,
                body=body,
                date=date,
                attachments=attachments,
                is_html=is_html
            )

        except Exception as e:
            logger.error(f"Error fetching email message: {e}")
            return None

    def _extract_body(self, email_message: email.message.Message) -> Tuple[str, bool]:
        """Extraer el cuerpo del mensaje"""

        body = ""
        is_html = False

        try:
            if email_message.is_multipart():
                for part in email_message.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get('Content-Disposition'))

                    # Skip attachments
                    if 'attachment' in content_disposition:
                        continue

                    if content_type == 'text/plain':
                        body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        break
                    elif content_type == 'text/html' and not body:
                        body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        is_html = True
            else:
                body = email_message.get_payload(decode=True).decode('utf-8', errors='ignore')
                if email_message.get_content_type() == 'text/html':
                    is_html = True

        except Exception as e:
            logger.error(f"Error extracting email body: {e}")

        return body, is_html

    def _extract_attachments(self, email_message: email.message.Message) -> List[str]:
        """Extraer lista de nombres de attachments"""

        attachments = []

        try:
            for part in email_message.walk():
                content_disposition = str(part.get('Content-Disposition'))
                if 'attachment' in content_disposition:
                    filename = part.get_filename()
                    if filename:
                        attachments.append(filename)

        except Exception as e:
            logger.error(f"Error extracting attachments: {e}")

        return attachments

    def process_messages_for_expenses(self, messages: List[EmailMessage]) -> List[Dict[str, Any]]:
        """
        Procesar mensajes de email para detectar gastos

        Returns:
            Lista de gastos detectados
        """
        detected_expenses = []

        for message in messages:
            try:
                # Verificar si el asunto sugiere un gasto
                subject_suggests_expense = any(
                    keyword in message.subject.lower()
                    for keyword in self.expense_keywords
                )

                # Combinar asunto y cuerpo para análisis
                full_text = f"{message.subject}\n\n{message.body}"

                # Limpiar HTML si es necesario
                if message.is_html:
                    full_text = self._clean_html(full_text)

                # Metadatos del email
                metadata = {
                    'message_id': message.message_id,
                    'sender': message.sender,
                    'subject': message.subject,
                    'date': message.date.isoformat(),
                    'attachments': message.attachments,
                    'is_html': message.is_html,
                    'subject_suggests_expense': subject_suggests_expense
                }

                # Analizar intención de gasto
                intent = self.intent_analyzer.analyze_intent(
                    text=full_text[:1000],  # Limitar texto para análisis
                    source='email',
                    metadata=metadata
                )

                # Ajustar confianza si el asunto sugiere gasto
                if subject_suggests_expense and intent.confidence > 0.3:
                    intent.confidence = min(0.9, intent.confidence + 0.2)

                # Si se detectó un gasto con confianza suficiente
                if intent.is_expense and intent.confidence > 0.4:
                    expense_data = self._create_expense_from_email_intent(intent, message, metadata)

                    # Enviar confirmación por email
                    self._send_confirmation_email(message.sender, intent, expense_data)

                    detected_expenses.append(expense_data)
                    logger.info(f"Expense detected from email: {expense_data.get('descripcion')}")

            except Exception as e:
                logger.error(f"Error processing email message for expenses: {e}")

        return detected_expenses

    def _clean_html(self, html_text: str) -> str:
        """Limpiar tags HTML del texto"""
        try:
            import re
            # Remover tags HTML básicos
            clean_text = re.sub(r'<[^>]+>', '', html_text)
            # Decodificar entidades HTML comunes
            clean_text = clean_text.replace('&nbsp;', ' ')
            clean_text = clean_text.replace('&amp;', '&')
            clean_text = clean_text.replace('&lt;', '<')
            clean_text = clean_text.replace('&gt;', '>')
            return clean_text
        except:
            return html_text

    def _create_expense_from_email_intent(self, intent: ExpenseIntent, message: EmailMessage, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Crear registro de gasto desde intención detectada en email"""

        extracted = intent.extracted_data

        # Usar asunto como descripción si no hay descripción extraída
        description = extracted.get('descripcion') or message.subject
        if len(description) > 200:
            description = description[:200] + "..."

        expense_data = {
            'id': f"EMAIL-{message.message_id.replace('<', '').replace('>', '').replace('@', '-')[:20]}",
            'descripcion': description,
            'monto_total': extracted.get('monto', 0.0),
            'categoria': extracted.get('categoria', 'oficina'),
            'fecha_gasto': extracted.get('fecha_probable', message.date.strftime('%Y-%m-%d')),
            'input_method': 'email_auto',
            'estado_factura': 'pendiente',
            'workflow_status': 'pendiente_factura',
            'proveedor': {
                'nombre': extracted.get('proveedor') or self._extract_sender_name(message.sender),
                'rfc': ''
            },
            'metadata': {
                'email': metadata,
                'intent_analysis': {
                    'confidence': intent.confidence,
                    'reasoning': intent.reasoning,
                    'source': intent.source,
                    'original_text': intent.original_text[:500]
                },
                'auto_detected': True,
                'requires_validation': intent.confidence < 0.7,
                'has_attachments': len(message.attachments) > 0
            },
            'asientos_contables': {
                'numero_poliza': f"EMAIL-{datetime.now().strftime('%Y%m%d')}-{message.message_id[-8:] if len(message.message_id) > 8 else message.message_id}",
                'tipo_poliza': 'Diario',
                'fecha_asiento': datetime.now().strftime('%Y-%m-%d'),
                'concepto': f"Gasto detectado automáticamente por email: {description[:100]}",
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

    def _extract_sender_name(self, sender: str) -> str:
        """Extraer nombre del remitente del email"""
        try:
            # El formato puede ser "Nombre <email@domain.com>" o solo "email@domain.com"
            if '<' in sender:
                name = sender.split('<')[0].strip().strip('"')
                return name if name else sender.split('@')[0]
            else:
                return sender.split('@')[0]
        except:
            return sender

    def _send_confirmation_email(self, to_email: str, intent: ExpenseIntent, expense_data: Dict[str, Any]):
        """Enviar email de confirmación"""

        if not self.email_address or not self.email_password:
            logger.warning("Cannot send confirmation email: credentials not configured")
            return

        try:
            confidence_level = "Alta" if intent.confidence > 0.8 else "Media" if intent.confidence > 0.6 else "Baja"

            subject = "✅ Gasto Detectado Automáticamente - Confirmación"

            body = f"""
Hola,

Se ha detectado automáticamente un gasto a partir de tu mensaje de correo electrónico:

DETALLES DEL GASTO:
• Descripción: {expense_data['descripcion']}
• Monto: ${expense_data['monto_total']:,.2f}
• Categoría: {expense_data['categoria']}
• Fecha: {expense_data['fecha_gasto']}

ANÁLISIS DE IA:
• Confianza: {confidence_level} ({intent.confidence * 100:.1f}%)
• Razonamiento: {intent.reasoning}

{'⚠️ REQUIERE VALIDACIÓN MANUAL - Por favor revisa y confirma los datos en el sistema.' if expense_data['metadata']['requires_validation'] else '✅ REGISTRADO AUTOMÁTICAMENTE - El gasto ha sido procesado exitosamente.'}

Puedes revisar y editar este gasto accediendo al sistema de gestión de gastos.

Saludos,
Sistema Automático de Gestión de Gastos
            """

            self._send_email(to_email, subject, body)

        except Exception as e:
            logger.error(f"Error sending confirmation email: {e}")

    def _send_email(self, to_email: str, subject: str, body: str):
        """Enviar email usando SMTP"""

        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_address
            msg['To'] = to_email
            msg['Subject'] = subject

            msg.attach(MIMEText(body, 'plain', 'utf-8'))

            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.email_address, self.email_password)
            text = msg.as_string()
            server.sendmail(self.email_address, to_email, text)
            server.quit()

            logger.info(f"Confirmation email sent to {to_email}")

        except Exception as e:
            logger.error(f"Error sending email: {e}")

    def send_expense_summary_email(self, to_email: str, expenses: List[Dict[str, Any]], period: str = "hoy"):
        """Enviar resumen de gastos por email"""

        if not expenses:
            return

        total_amount = sum(exp.get('monto_total', 0) for exp in expenses)

        subject = f"📊 Resumen de Gastos Detectados - {period.title()}"

        body = f"""
Resumen de Gastos Detectados Automáticamente

PERÍODO: {period.upper()}
TOTAL DE GASTOS: {len(expenses)}
MONTO TOTAL: ${total_amount:,.2f}

DETALLES:
"""

        for i, expense in enumerate(expenses, 1):
            validation_status = "⚠️ Requiere validación" if expense['metadata']['requires_validation'] else "✅ Validado automáticamente"
            body += f"""
{i}. {expense['descripcion']}
   Monto: ${expense['monto_total']:,.2f}
   Categoría: {expense['categoria']}
   Fuente: {expense['metadata']['email']['sender']}
   Estado: {validation_status}

"""

        body += """
Accede al sistema de gestión de gastos para revisar todos los detalles y realizar cualquier ajuste necesario.

Saludos,
Sistema Automático de Gestión de Gastos
        """

        self._send_email(to_email, subject, body)

    def get_configuration_info(self) -> Dict[str, Any]:
        """Obtener información de configuración necesaria"""

        return {
            'required_env_vars': [
                'EMAIL_ADDRESS - Dirección de email principal',
                'EMAIL_PASSWORD - Contraseña de aplicación (no la contraseña normal)',
                'EMAIL_IMAP_SERVER - Servidor IMAP (default: imap.gmail.com)',
                'EMAIL_IMAP_PORT - Puerto IMAP (default: 993)',
                'EMAIL_SMTP_SERVER - Servidor SMTP (default: smtp.gmail.com)',
                'EMAIL_SMTP_PORT - Puerto SMTP (default: 587)',
                'EMAIL_AUTHORIZED_SENDERS - Remitentes autorizados (opcional)',
                'EMAIL_CHECK_INTERVAL - Intervalo de revisión en segundos (default: 300)'
            ],
            'gmail_setup': [
                '1. Habilitar autenticación de 2 factores en tu cuenta Gmail',
                '2. Ir a Configuración de cuenta > Seguridad > Contraseñas de aplicaciones',
                '3. Generar una contraseña de aplicación para "Correo"',
                '4. Usar esa contraseña en EMAIL_PASSWORD (no tu contraseña normal)',
                '5. Asegurarte de que IMAP esté habilitado en Gmail'
            ],
            'current_config': {
                'email_configured': bool(self.email_address and self.email_password),
                'imap_server': self.imap_server,
                'smtp_server': self.smtp_server,
                'authorized_senders': len(self.authorized_senders),
                'check_interval': self.check_interval
            }
        }


# Instancia global
_email_integration = None

def get_email_integration() -> EmailIntegration:
    """Obtener instancia global de la integración de email"""
    global _email_integration
    if _email_integration is None:
        _email_integration = EmailIntegration()
    return _email_integration