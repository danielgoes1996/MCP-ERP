"""
Email Service

Servicio centralizado para envío de correos electrónicos
Soporta SMTP (Gmail, Outlook, etc.)
"""

import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# Email configuration
SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USER = os.getenv('SMTP_USER', '')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
FROM_EMAIL = os.getenv('FROM_EMAIL', SMTP_USER)
FROM_NAME = os.getenv('FROM_NAME', 'ContaFlow')

# Frontend URL
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3001')


class EmailService:
    """Servicio de email usando SMTP"""

    @staticmethod
    def _send_email(
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """
        Enviar email usando SMTP

        Args:
            to_email: Email del destinatario
            subject: Asunto del email
            html_content: Contenido HTML del email
            text_content: Contenido texto plano (opcional)

        Returns:
            True si se envió exitosamente, False en caso contrario
        """
        # Check if email is configured
        if not SMTP_USER or not SMTP_PASSWORD:
            logger.warning(
                f"Email not configured. Would send to {to_email}: {subject}"
            )
            logger.info(f"HTML Content:\n{html_content}")
            return False

        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{FROM_NAME} <{FROM_EMAIL}>"
            msg['To'] = to_email

            # Add text and HTML parts
            if text_content:
                part1 = MIMEText(text_content, 'plain')
                msg.attach(part1)

            part2 = MIMEText(html_content, 'html')
            msg.attach(part2)

            # Send email
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)

            logger.info(f"✅ Email sent successfully to {to_email}: {subject}")
            return True

        except Exception as e:
            logger.error(f"❌ Error sending email to {to_email}: {e}")
            return False

    @staticmethod
    def send_verification_email(
        to_email: str,
        full_name: str,
        verification_token: str
    ) -> bool:
        """
        Enviar email de verificación de cuenta

        Args:
            to_email: Email del usuario
            full_name: Nombre completo del usuario
            verification_token: Token de verificación

        Returns:
            True si se envió exitosamente
        """
        verification_link = f"{FRONTEND_URL}/auth/verify-email?token={verification_token}"

        subject = "Verifica tu cuenta en ContaFlow"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #11446E 0%, #60B97B 100%); padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                <h1 style="color: white; margin: 0; font-size: 28px;">¡Bienvenido a ContaFlow!</h1>
            </div>

            <div style="background: #f9fafb; padding: 30px; border-radius: 0 0 10px 10px;">
                <p style="font-size: 16px; margin-bottom: 20px;">Hola <strong>{full_name}</strong>,</p>

                <p style="font-size: 16px; margin-bottom: 20px;">
                    Gracias por registrarte en ContaFlow. Para completar tu registro y comenzar a usar la plataforma,
                    por favor verifica tu dirección de correo electrónico.
                </p>

                <div style="text-align: center; margin: 30px 0;">
                    <a href="{verification_link}"
                       style="background: linear-gradient(135deg, #11446E 0%, #60B97B 100%);
                              color: white;
                              padding: 14px 30px;
                              text-decoration: none;
                              border-radius: 6px;
                              display: inline-block;
                              font-weight: 600;
                              font-size: 16px;
                              box-shadow: 0 4px 15px rgba(17, 68, 110, 0.3);">
                        Verificar mi cuenta
                    </a>
                </div>

                <p style="font-size: 14px; color: #666; margin-top: 30px;">
                    Si no puedes hacer clic en el botón, copia y pega este enlace en tu navegador:
                </p>
                <p style="font-size: 12px; color: #11446E; word-break: break-all; background: white; padding: 10px; border-radius: 4px; border-left: 3px solid #60B97B;">
                    {verification_link}
                </p>

                <p style="font-size: 14px; color: #666; margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd;">
                    Este enlace expirará en 24 horas por seguridad.
                </p>

                <p style="font-size: 14px; color: #666;">
                    Si no creaste esta cuenta, puedes ignorar este correo.
                </p>

                <div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; text-align: center; color: #999; font-size: 12px;">
                    <p>© 2025 ContaFlow. Todos los derechos reservados.</p>
                    <p>Sistema de Gestión Contable Inteligente</p>
                </div>
            </div>
        </body>
        </html>
        """

        text_content = f"""
        ¡Bienvenido a ContaFlow!

        Hola {full_name},

        Gracias por registrarte. Por favor verifica tu email usando el siguiente enlace:

        {verification_link}

        Este enlace expirará en 24 horas.

        Si no creaste esta cuenta, ignora este correo.

        © 2025 ContaFlow
        """

        return EmailService._send_email(to_email, subject, html_content, text_content)

    @staticmethod
    def send_password_reset_email(
        to_email: str,
        full_name: str,
        reset_token: str
    ) -> bool:
        """
        Enviar email de restablecimiento de contraseña

        Args:
            to_email: Email del usuario
            full_name: Nombre completo del usuario
            reset_token: Token de restablecimiento

        Returns:
            True si se envió exitosamente
        """
        reset_link = f"{FRONTEND_URL}/auth/reset-password?token={reset_token}"

        subject = "Restablece tu contraseña - ContaFlow"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #11446E 0%, #60B97B 100%); padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                <h1 style="color: white; margin: 0; font-size: 28px;">Restablece tu contraseña</h1>
            </div>

            <div style="background: #f9fafb; padding: 30px; border-radius: 0 0 10px 10px;">
                <p style="font-size: 16px; margin-bottom: 20px;">Hola <strong>{full_name}</strong>,</p>

                <p style="font-size: 16px; margin-bottom: 20px;">
                    Recibimos una solicitud para restablecer la contraseña de tu cuenta en ContaFlow.
                    Haz clic en el botón de abajo para crear una nueva contraseña.
                </p>

                <div style="text-align: center; margin: 30px 0;">
                    <a href="{reset_link}"
                       style="background: linear-gradient(135deg, #11446E 0%, #60B97B 100%);
                              color: white;
                              padding: 14px 30px;
                              text-decoration: none;
                              border-radius: 6px;
                              display: inline-block;
                              font-weight: 600;
                              font-size: 16px;
                              box-shadow: 0 4px 15px rgba(17, 68, 110, 0.3);">
                        Restablecer contraseña
                    </a>
                </div>

                <p style="font-size: 14px; color: #666; margin-top: 30px;">
                    Si no puedes hacer clic en el botón, copia y pega este enlace en tu navegador:
                </p>
                <p style="font-size: 12px; color: #11446E; word-break: break-all; background: white; padding: 10px; border-radius: 4px; border-left: 3px solid #60B97B;">
                    {reset_link}
                </p>

                <p style="font-size: 14px; color: #666; margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd;">
                    Este enlace expirará en 1 hora por seguridad.
                </p>

                <p style="font-size: 14px; color: #666;">
                    Si no solicitaste restablecer tu contraseña, ignora este correo. Tu contraseña no cambiará.
                </p>

                <div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; text-align: center; color: #999; font-size: 12px;">
                    <p>© 2025 ContaFlow. Todos los derechos reservados.</p>
                    <p>Sistema de Gestión Contable Inteligente</p>
                </div>
            </div>
        </body>
        </html>
        """

        text_content = f"""
        Restablece tu contraseña - ContaFlow

        Hola {full_name},

        Recibimos una solicitud para restablecer tu contraseña. Usa el siguiente enlace:

        {reset_link}

        Este enlace expirará en 1 hora.

        Si no solicitaste esto, ignora este correo.

        © 2025 ContaFlow
        """

        return EmailService._send_email(to_email, subject, html_content, text_content)


# Create singleton instance
email_service = EmailService()
