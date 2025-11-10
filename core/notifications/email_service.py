#!/usr/bin/env python3
"""
Servicio de Notificaciones por Email
=====================================
Sistema para enviar notificaciones por correo electrónico sobre:
- CFDIs cancelados detectados
- Completación de verificaciones automáticas
- Completación de extracciones automáticas
- Alertas de errores críticos
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import List, Dict, Optional
import os
from dataclasses import dataclass


@dataclass
class EmailConfig:
    """Configuración de email desde variables de entorno"""
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    from_email: str
    from_name: str
    enabled: bool = True
    use_tls: bool = True

    @classmethod
    def from_env(cls):
        """Carga configuración desde variables de entorno"""
        return cls(
            smtp_host=os.getenv('SMTP_HOST', 'smtp.gmail.com'),
            smtp_port=int(os.getenv('SMTP_PORT', '587')),
            smtp_user=os.getenv('SMTP_USER', ''),
            smtp_password=os.getenv('SMTP_PASSWORD', ''),
            from_email=os.getenv('SMTP_FROM_EMAIL', os.getenv('SMTP_USER', '')),
            from_name=os.getenv('SMTP_FROM_NAME', 'Sistema CFDI'),
            enabled=os.getenv('EMAIL_NOTIFICATIONS_ENABLED', 'true').lower() == 'true',
            use_tls=os.getenv('SMTP_USE_TLS', 'true').lower() == 'true'
        )


class EmailNotificationService:
    """Servicio de notificaciones por email"""

    def __init__(self, config: Optional[EmailConfig] = None):
        """
        Inicializa el servicio de email

        Args:
            config: Configuración de email (si no se provee, carga desde env)
        """
        self.config = config or EmailConfig.from_env()

    def _send_email(self, to_emails: List[str], subject: str, html_body: str, text_body: Optional[str] = None):
        """
        Envía un email usando SMTP

        Args:
            to_emails: Lista de destinatarios
            subject: Asunto del email
            html_body: Contenido HTML del email
            text_body: Contenido texto plano (fallback)
        """
        if not self.config.enabled:
            print("📧 [EMAIL] Notificaciones desactivadas (EMAIL_NOTIFICATIONS_ENABLED=false)")
            return False

        if not self.config.smtp_user or not self.config.smtp_password:
            print("⚠️  [EMAIL] Credenciales SMTP no configuradas. Configurar SMTP_USER y SMTP_PASSWORD")
            return False

        try:
            # Crear mensaje
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{self.config.from_name} <{self.config.from_email}>"
            msg['To'] = ', '.join(to_emails)

            # Agregar contenido texto plano (fallback)
            if text_body:
                part1 = MIMEText(text_body, 'plain', 'utf-8')
                msg.attach(part1)

            # Agregar contenido HTML
            part2 = MIMEText(html_body, 'html', 'utf-8')
            msg.attach(part2)

            # Conectar y enviar
            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
                if self.config.use_tls:
                    server.starttls()
                server.login(self.config.smtp_user, self.config.smtp_password)
                server.send_message(msg)

            print(f"✅ [EMAIL] Notificación enviada a {len(to_emails)} destinatario(s)")
            return True

        except Exception as e:
            print(f"❌ [EMAIL] Error al enviar notificación: {e}")
            return False

    def send_verification_complete(
        self,
        to_emails: List[str],
        results: Dict,
        execution_date: datetime
    ):
        """
        Envía notificación de verificación completada

        Args:
            to_emails: Destinatarios
            results: Diccionario con resultados de verificación
            execution_date: Fecha de ejecución
        """
        companies_success = results.get('companies_success', [])
        companies_failed = results.get('companies_failed', [])
        total_companies = len(companies_success) + len(companies_failed)
        total_verificados = results.get('total_verificados', 0)
        total_vigentes = results.get('total_vigentes', 0)
        total_cancelados = results.get('total_cancelados', 0)
        total_errores = results.get('total_errores', 0)
        total_time = results.get('total_time', 0)

        # Asunto
        if total_cancelados > 0:
            subject = f"🚨 ALERTA: {total_cancelados} CFDIs Cancelados Detectados"
        else:
            subject = f"✅ Verificación CFDI Completada - {total_verificados} facturas verificadas"

        # Contenido HTML
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #4CAF50; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0; }}
        .alert {{ background: #f44336; }}
        .content {{ background: #f9f9f9; padding: 20px; border: 1px solid #ddd; }}
        .stats {{ background: white; padding: 15px; margin: 10px 0; border-left: 4px solid #4CAF50; }}
        .alert-stats {{ border-left-color: #f44336; }}
        .company-list {{ margin: 10px 0; }}
        .company-item {{ padding: 8px; background: white; margin: 5px 0; border-radius: 3px; }}
        .success {{ color: #4CAF50; }}
        .error {{ color: #f44336; }}
        .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header {'alert' if total_cancelados > 0 else ''}">
            <h1>{'🚨 ALERTA CFDI' if total_cancelados > 0 else '✅ Verificación CFDI'}</h1>
            <p>{execution_date.strftime('%d de %B, %Y - %H:%M')}</p>
        </div>

        <div class="content">
            <h2>Resumen de Verificación</h2>

            <div class="stats {'alert-stats' if total_cancelados > 0 else ''}">
                <h3>📊 Estadísticas Generales</h3>
                <ul>
                    <li><strong>Compañías procesadas:</strong> {len(companies_success)}/{total_companies}</li>
                    <li><strong>CFDIs verificados:</strong> {total_verificados:,}</li>
                    <li><strong>Vigentes:</strong> <span class="success">{total_vigentes:,}</span></li>
                    <li><strong>Cancelados:</strong> <span class="error">{total_cancelados:,}</span></li>
                    <li><strong>Errores:</strong> {total_errores:,}</li>
                    <li><strong>Tiempo total:</strong> {total_time/60:.1f} minutos</li>
                </ul>
            </div>

            {f'''
            <div class="stats alert-stats">
                <h3>🚨 CFDIs Cancelados Detectados</h3>
                <p><strong>Se encontraron {total_cancelados} facturas canceladas en el SAT.</strong></p>
                <p>Por favor, revisa las facturas marcadas como canceladas en el sistema y toma las acciones necesarias:</p>
                <ul>
                    <li>Verifica con los proveedores</li>
                    <li>Solicita reexpedición si es necesario</li>
                    <li>Actualiza registros contables</li>
                </ul>
            </div>
            ''' if total_cancelados > 0 else ''}

            {f'''
            <div class="company-list">
                <h3 class="success">✅ Compañías Exitosas ({len(companies_success)})</h3>
                {''.join([f'<div class="company-item">• {c["name"]}: {c["verificados"]:,} verificados en {c["time"]:.1f}s</div>' for c in companies_success])}
            </div>
            ''' if companies_success else ''}

            {f'''
            <div class="company-list">
                <h3 class="error">❌ Compañías con Errores ({len(companies_failed)})</h3>
                {''.join([f'<div class="company-item">• {c["name"]} (ID: {c["id"]})</div>' for c in companies_failed])}
            </div>
            ''' if companies_failed else ''}
        </div>

        <div class="footer">
            <p>Este es un mensaje automático del Sistema de Verificación CFDI</p>
            <p>Próxima verificación: {(execution_date.replace(month=execution_date.month % 12 + 1, day=1)).strftime('%d de %B, %Y')}</p>
        </div>
    </div>
</body>
</html>
        """

        # Texto plano (fallback)
        text_body = f"""
VERIFICACIÓN CFDI COMPLETADA
============================
Fecha: {execution_date.strftime('%d de %B, %Y - %H:%M')}

RESUMEN:
- Compañías procesadas: {len(companies_success)}/{total_companies}
- CFDIs verificados: {total_verificados:,}
- Vigentes: {total_vigentes:,}
- Cancelados: {total_cancelados:,}
- Errores: {total_errores:,}
- Tiempo total: {total_time/60:.1f} minutos

{'ALERTA: Se encontraron ' + str(total_cancelados) + ' CFDIs cancelados.' if total_cancelados > 0 else ''}

Compañías Exitosas ({len(companies_success)}):
{chr(10).join([f'- {c["name"]}: {c["verificados"]:,} verificados' for c in companies_success])}

{'Compañías con Errores (' + str(len(companies_failed)) + '):' + chr(10) + chr(10).join([f'- {c["name"]} (ID: {c["id"]})' for c in companies_failed]) if companies_failed else ''}
        """

        return self._send_email(to_emails, subject, html_body, text_body)

    def send_extraction_complete(
        self,
        to_emails: List[str],
        results: Dict,
        execution_date: datetime,
        date_range: tuple
    ):
        """
        Envía notificación de extracción completada

        Args:
            to_emails: Destinatarios
            results: Diccionario con resultados de extracción
            execution_date: Fecha de ejecución
            date_range: Tupla (fecha_inicio, fecha_fin)
        """
        fecha_inicio, fecha_fin = date_range
        companies_success = results.get('companies_success', [])
        companies_failed = results.get('companies_failed', [])
        total_companies = len(companies_success) + len(companies_failed)
        total_nuevas = results.get('total_nuevas', 0)
        total_existentes = results.get('total_existentes', 0)
        total_errores = results.get('total_errores', 0)
        total_time = results.get('total_time', 0)

        # Asunto
        if total_nuevas > 0:
            subject = f"📥 {total_nuevas} Nuevas Facturas Extraídas del SAT"
        else:
            subject = f"✅ Extracción SAT Completada - Sin facturas nuevas"

        # Contenido HTML
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #2196F3; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0; }}
        .content {{ background: #f9f9f9; padding: 20px; border: 1px solid #ddd; }}
        .stats {{ background: white; padding: 15px; margin: 10px 0; border-left: 4px solid #2196F3; }}
        .company-list {{ margin: 10px 0; }}
        .company-item {{ padding: 8px; background: white; margin: 5px 0; border-radius: 3px; }}
        .success {{ color: #4CAF50; }}
        .error {{ color: #f44336; }}
        .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📥 Extracción SAT</h1>
            <p>{execution_date.strftime('%d de %B, %Y - %H:%M')}</p>
        </div>

        <div class="content">
            <h2>Resumen de Extracción</h2>

            <div class="stats">
                <h3>📊 Estadísticas Generales</h3>
                <ul>
                    <li><strong>Período:</strong> {fecha_inicio.strftime('%d/%m/%Y')} - {fecha_fin.strftime('%d/%m/%Y')}</li>
                    <li><strong>Compañías procesadas:</strong> {len(companies_success)}/{total_companies}</li>
                    <li><strong>Facturas nuevas:</strong> <span class="success">{total_nuevas:,}</span></li>
                    <li><strong>Facturas existentes:</strong> {total_existentes:,}</li>
                    <li><strong>Errores:</strong> {total_errores:,}</li>
                    <li><strong>Tiempo total:</strong> {total_time/60:.1f} minutos</li>
                </ul>
            </div>

            {f'''
            <div class="company-list">
                <h3 class="success">✅ Compañías Exitosas ({len(companies_success)})</h3>
                {''.join([f'<div class="company-item">• {c["name"]}: {c["nuevas"]:,} nuevas en {c["time"]:.1f}s</div>' for c in companies_success])}
            </div>
            ''' if companies_success else ''}

            {f'''
            <div class="company-list">
                <h3 class="error">❌ Compañías con Errores ({len(companies_failed)})</h3>
                {''.join([f'<div class="company-item">• {c["name"]} (ID: {c["id"]})</div>' for c in companies_failed])}
            </div>
            ''' if companies_failed else ''}
        </div>

        <div class="footer">
            <p>Este es un mensaje automático del Sistema de Extracción CFDI</p>
            <p>Próxima extracción: {(execution_date.replace(day=execution_date.day + 7)).strftime('%d de %B, %Y')}</p>
        </div>
    </div>
</body>
</html>
        """

        # Texto plano (fallback)
        text_body = f"""
EXTRACCIÓN SAT COMPLETADA
=========================
Fecha: {execution_date.strftime('%d de %B, %Y - %H:%M')}
Período: {fecha_inicio.strftime('%d/%m/%Y')} - {fecha_fin.strftime('%d/%m/%Y')}

RESUMEN:
- Compañías procesadas: {len(companies_success)}/{total_companies}
- Facturas nuevas: {total_nuevas:,}
- Facturas existentes: {total_existentes:,}
- Errores: {total_errores:,}
- Tiempo total: {total_time/60:.1f} minutos

Compañías Exitosas ({len(companies_success)}):
{chr(10).join([f'- {c["name"]}: {c["nuevas"]:,} nuevas' for c in companies_success])}

{'Compañías con Errores (' + str(len(companies_failed)) + '):' + chr(10) + chr(10).join([f'- {c["name"]} (ID: {c["id"]})' for c in companies_failed]) if companies_failed else ''}
        """

        return self._send_email(to_emails, subject, html_body, text_body)

    def send_critical_alert(
        self,
        to_emails: List[str],
        alert_type: str,
        message: str,
        details: Optional[Dict] = None
    ):
        """
        Envía alerta crítica

        Args:
            to_emails: Destinatarios
            alert_type: Tipo de alerta (error, warning, critical)
            message: Mensaje principal
            details: Detalles adicionales (opcional)
        """
        subject = f"🚨 ALERTA: {alert_type.upper()} - Sistema CFDI"

        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #f44336; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0; }}
        .content {{ background: #f9f9f9; padding: 20px; border: 1px solid #ddd; }}
        .alert {{ background: white; padding: 15px; margin: 10px 0; border-left: 4px solid #f44336; }}
        .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚨 ALERTA CRÍTICA</h1>
            <p>{datetime.now().strftime('%d de %B, %Y - %H:%M')}</p>
        </div>

        <div class="content">
            <div class="alert">
                <h3>{alert_type.upper()}</h3>
                <p>{message}</p>
                {f'<pre>{details}</pre>' if details else ''}
            </div>
        </div>

        <div class="footer">
            <p>Este es un mensaje automático del Sistema CFDI</p>
        </div>
    </div>
</body>
</html>
        """

        text_body = f"""
ALERTA CRÍTICA - SISTEMA CFDI
=============================
Fecha: {datetime.now().strftime('%d de %B, %Y - %H:%M')}

TIPO: {alert_type.upper()}

MENSAJE:
{message}

{('DETALLES:' + chr(10) + str(details)) if details else ''}
        """

        return self._send_email(to_emails, subject, html_body, text_body)


# Función helper para obtener destinatarios desde ENV
def get_notification_recipients() -> List[str]:
    """
    Obtiene lista de destinatarios desde variable de entorno

    Returns:
        Lista de emails separados por coma desde NOTIFICATION_EMAILS
    """
    emails_str = os.getenv('NOTIFICATION_EMAILS', '')
    if not emails_str:
        return []
    return [email.strip() for email in emails_str.split(',') if email.strip()]
