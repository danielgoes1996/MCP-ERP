#!/usr/bin/env python3
"""
State Machine para automatización inteligente de facturación
"""

from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass
import json
import logging

logger = logging.getLogger(__name__)

class AutomationState(Enum):
    """Estados del flujo de automatización"""
    NAVIGATION = "navigation"
    LOGIN_OR_REGISTER = "login_or_register"
    FORM_FILLING = "form_filling"
    CONFIRMATION = "confirmation"
    DONE = "done"
    ERROR = "error"

@dataclass
class StateDecision:
    """Decisión del LLM con información de estado"""
    action: str  # "click", "input", "select", "done", "error"
    selector: str
    value: str = ""
    reason: str = ""
    next_state: Optional[AutomationState] = None
    confidence: float = 0.0

    @classmethod
    def from_llm_response(cls, response_text: str) -> 'StateDecision':
        """Crear StateDecision desde respuesta JSON del LLM"""
        try:
            data = json.loads(response_text.strip())
            next_state = None
            if "next_state" in data:
                try:
                    next_state = AutomationState(data["next_state"].lower())
                except ValueError:
                    logger.warning(f"Estado inválido: {data.get('next_state')}")

            return cls(
                action=data.get("action", "error"),
                selector=data.get("selector", ""),
                value=data.get("value", ""),
                reason=data.get("reason", ""),
                next_state=next_state,
                confidence=data.get("confidence", 0.0)
            )
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Error parseando respuesta LLM: {e}")
            return cls(
                action="error",
                selector="",
                reason=f"Error parseando respuesta: {response_text[:100]}..."
            )

class StateMachine:
    """Máquina de estados para automatización de facturación"""

    def __init__(self, initial_state: AutomationState = AutomationState.NAVIGATION):
        self.current_state = initial_state
        self.history = []
        self.context = {}

    def transition_to(self, new_state: AutomationState, reason: str = ""):
        """Transición a nuevo estado"""
        old_state = self.current_state
        self.current_state = new_state

        transition = {
            "from": old_state.value,
            "to": new_state.value,
            "reason": reason,
            "timestamp": self._get_timestamp()
        }
        self.history.append(transition)

        logger.info(f"🔄 Estado: {old_state.value} → {new_state.value} ({reason})")

    def get_state_prompt(self, ticket_data: Dict[str, Any], html_content: str, elementos_detectados: list) -> str:
        """Generar prompt específico para el estado actual"""

        base_context = f"""
🤖 AGENTE DE AUTOMATIZACIÓN INTELIGENTE - FACTURACIÓN

🎯 OBJETIVO GLOBAL: Descargar factura PDF completando formulario con datos fiscales

📋 DATOS DEL TICKET:
- RFC: {ticket_data.get('rfc', 'XAXX010101000')}
- Email: {ticket_data.get('email', 'test@example.com')}
- Total: ${ticket_data.get('total', '0.00')}
- Folio: {ticket_data.get('folio', 'N/A')}
- Fecha: {ticket_data.get('fecha', 'N/A')}

🔍 ELEMENTOS DETECTADOS EN LA PÁGINA:
{json.dumps(elementos_detectados[:5], indent=2, ensure_ascii=False)}

🌐 HTML ACTUAL (resumido):
{html_content[:2000]}
"""

        if self.current_state == AutomationState.NAVIGATION:
            return f"""{base_context}

📍 ESTADO ACTUAL: NAVEGACIÓN
🎯 OBJETIVO: Encontrar entrada al portal de facturación

BUSCAR EN ORDEN DE PRIORIDAD:
1. Links/botones con texto: "Facturación", "Factura", "Portal", "Servicios"
2. Botones hero: "CLICK AQUÍ", "Generar Factura", "Solicitar Factura"
3. Enlaces en navegación principal (header, menú)
4. Formularios directos de facturación

TRANSICIONES POSIBLES:
- Si detectas login/registro → next_state: "login_or_register"
- Si detectas formulario directo → next_state: "form_filling"
- Si hay múltiples opciones → click en la más específica

FORMATO RESPUESTA:
{{
    "action": "click",
    "selector": "#facturacion-link",
    "value": "",
    "reason": "Enlace de facturación detectado en menú principal",
    "next_state": "form_filling",
    "confidence": 0.9
}}"""

        elif self.current_state == AutomationState.LOGIN_OR_REGISTER:
            return f"""{base_context}

📍 ESTADO ACTUAL: LOGIN O REGISTRO
🎯 OBJETIVO: Acceder al sistema de facturación

ACCIONES POSIBLES:
1. Si hay campos login (usuario/password) → intentar credenciales automáticas
2. Si hay "Crear cuenta" → usar datos del ticket para registro
3. Si hay "Continuar sin registro" → preferir esta opción

DATOS PARA REGISTRO AUTOMÁTICO:
- Email: {ticket_data.get('email', 'test@example.com')}
- RFC como usuario: {ticket_data.get('rfc', 'XAXX010101000')}
- Password genérico: "Factura123"

FORMATO RESPUESTA:
{{
    "action": "input|click",
    "selector": "#email",
    "value": "{ticket_data.get('email', 'test@example.com')}",
    "reason": "Llenar email para registro",
    "next_state": "form_filling",
    "confidence": 0.8
}}"""

        elif self.current_state == AutomationState.FORM_FILLING:
            return f"""{base_context}

📍 ESTADO ACTUAL: LLENADO DE FORMULARIO
🎯 OBJETIVO: Completar datos fiscales del cliente

CAMPOS A BUSCAR Y LLENAR:
1. RFC: {ticket_data.get('rfc', 'XAXX010101000')}
2. Email: {ticket_data.get('email', 'test@example.com')}
3. Razón Social: "PUBLICO EN GENERAL"
4. Total/Importe: {ticket_data.get('total', '0.00')}
5. Folio/Referencia: {ticket_data.get('folio', 'N/A')}
6. Fecha: {ticket_data.get('fecha', 'N/A')}

ESTRATEGIA:
- Llenar campos uno por uno
- Si no encuentras un campo específico, continúa con otros
- Al completar los esenciales (RFC, email) → buscar botón "Continuar"

FORMATO RESPUESTA:
{{
    "action": "input",
    "selector": "#rfc",
    "value": "{ticket_data.get('rfc', 'XAXX010101000')}",
    "reason": "Llenar RFC del cliente",
    "next_state": "form_filling",
    "confidence": 0.9
}}"""

        elif self.current_state == AutomationState.CONFIRMATION:
            return f"""{base_context}

📍 ESTADO ACTUAL: CONFIRMACIÓN Y GENERACIÓN
🎯 OBJETIVO: Generar y descargar la factura

BUSCAR BOTONES:
1. "Generar Factura", "Crear Factura", "Procesar"
2. "Continuar", "Siguiente", "Finalizar"
3. "Descargar PDF", "Download", "Obtener Factura"

ESTRATEGIA:
- Click en botón de generación
- Esperar confirmación o descarga automática
- Si aparece link de descarga → click inmediato

FORMATO RESPUESTA:
{{
    "action": "click",
    "selector": "#generar-btn",
    "value": "",
    "reason": "Generar factura con datos completados",
    "next_state": "done",
    "confidence": 0.95
}}"""

        else:  # ERROR or unknown state
            return f"""{base_context}

📍 ESTADO: ERROR O DESCONOCIDO
🎯 Analizar situación y reportar problema

FORMATO RESPUESTA:
{{
    "action": "error",
    "selector": "",
    "value": "",
    "reason": "Estado no manejado o situación inesperada",
    "next_state": "error",
    "confidence": 0.0
}}"""

    def _get_timestamp(self) -> str:
        """Obtener timestamp actual"""
        from datetime import datetime
        return datetime.now().isoformat()

    def get_summary(self) -> Dict[str, Any]:
        """Obtener resumen del estado actual"""
        return {
            "current_state": self.current_state.value,
            "history": self.history,
            "context": self.context
        }