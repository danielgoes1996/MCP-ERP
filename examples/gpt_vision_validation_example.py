#!/usr/bin/env python3
"""
Ejemplo de Validación Inteligente con GPT Vision
Demuestra cómo usar el sistema para corregir errores de OCR
"""

import asyncio
import base64
import logging
from typing import Dict, Any

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def example_basic_validation():
    """
    Ejemplo básico: validar un campo específico
    """
    print("=== EJEMPLO 1: VALIDACIÓN BÁSICA ===")

    from core.intelligent_field_validator import validate_single_field

    # Imagen de ejemplo (en producción vendría del upload del usuario)
    test_image = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="

    # Validar folio específico
    result = await validate_single_field(
        image_data=test_image,
        field_name="folio"
    )

    print(f"📄 Folio detectado: '{result.final_value}'")
    print(f"🎯 Confianza: {result.confidence:.2%}")
    print(f"🔧 Método usado: {result.method_used}")
    print(f"👥 Candidatos encontrados: {result.all_candidates}")

    if result.gpt_reasoning:
        print(f"🧠 Razonamiento GPT: {result.gpt_reasoning}")


async def example_portal_error_correction():
    """
    Ejemplo avanzado: corregir error específico del portal web
    """
    print("\n=== EJEMPLO 2: CORRECCIÓN POR ERROR DE PORTAL ===")

    from core.intelligent_field_validator import validate_single_field

    # Simular imagen de ticket donde OCR detectó mal el folio
    test_image = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="

    # Portal web rechazó el folio con error específico
    portal_error = "El folio ingresado no existe en nuestros registros. Verifique el número."

    result = await validate_single_field(
        image_data=test_image,
        field_name="folio",
        portal_error=portal_error
    )

    print(f"🚨 Error del portal: {portal_error}")
    print(f"🔄 Folio corregido por GPT Vision: '{result.final_value}'")
    print(f"🎯 Confianza en corrección: {result.confidence:.2%}")
    print(f"🧠 Explicación de GPT: {result.gpt_reasoning[:200]}...")


async def example_multiple_fields_validation():
    """
    Ejemplo completo: validar múltiples campos de un ticket
    """
    print("\n=== EJEMPLO 3: VALIDACIÓN MÚLTIPLE ===")

    from core.intelligent_field_validator import validate_ticket_fields

    # Imagen de ticket completo
    test_image = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="

    # Validar campos estándar de facturación
    fields = await validate_ticket_fields(
        image_data=test_image,
        required_fields=['folio', 'rfc_emisor', 'monto_total', 'fecha']
    )

    print("📋 CAMPOS EXTRAÍDOS:")
    for field_name, value in fields.items():
        emoji = {"folio": "🎫", "rfc_emisor": "🏢", "monto_total": "💰", "fecha": "📅"}.get(field_name, "📄")
        print(f"   {emoji} {field_name}: '{value}'")


async def example_web_automation_integration():
    """
    Ejemplo de integración con automatización web
    """
    print("\n=== EJEMPLO 4: INTEGRACIÓN CON AUTOMATIZACIÓN WEB ===")

    # Simulación de flujo real
    class MockWebPortal:
        """Simula un portal web que rechaza valores incorrectos"""

        def validate_form_data(self, data: Dict[str, str]) -> Dict[str, str]:
            """Simula validación del portal y retorna errores específicos"""
            errors = {}

            # Simular que el folio OCR está mal
            if data.get('folio') == 'OCR_MISTAKE_123':
                errors['folio'] = "Folio no encontrado. Verifique el número del ticket."

            # Simular que el RFC tiene formato incorrecto
            if data.get('rfc_emisor') and len(data['rfc_emisor']) != 13:
                errors['rfc_emisor'] = "RFC debe tener exactamente 13 caracteres."

            return errors

    # Datos extraídos por OCR (con errores simulados)
    ocr_data = {
        'folio': 'OCR_MISTAKE_123',  # Error: OCR leyó mal
        'rfc_emisor': 'ABC12345678',  # Error: RFC incompleto
        'monto_total': '150.75'       # Correcto
    }

    # Portal rechaza los datos
    portal = MockWebPortal()
    errors = portal.validate_form_data(ocr_data)

    if errors:
        print(f"❌ Portal rechazó datos: {errors}")

        # Usar validador inteligente para corregir
        from core.intelligent_field_validator import intelligent_validator

        # Imagen original del ticket
        ticket_image = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="

        # Validar solo campos problemáticos
        corrected_results = await intelligent_validator.validate_multiple_fields(
            image_data=ticket_image,
            required_fields=list(errors.keys()),
            portal_errors=errors
        )

        print("🔧 CORRECCIONES DE GPT VISION:")
        for field_name, result in corrected_results.items():
            print(f"   📝 {field_name}:")
            print(f"      Antes: '{ocr_data.get(field_name)}'")
            print(f"      Después: '{result.final_value}'")
            print(f"      Confianza: {result.confidence:.2%}")
            print(f"      Razonamiento: {result.gpt_reasoning[:100]}...")

        # Crear datos corregidos
        corrected_data = ocr_data.copy()
        for field_name, result in corrected_results.items():
            if result.final_value and result.confidence >= 0.7:
                corrected_data[field_name] = result.final_value

        # Validar de nuevo con portal
        final_errors = portal.validate_form_data(corrected_data)
        if not final_errors:
            print("✅ Portal acepta datos corregidos!")
        else:
            print(f"⚠️ Aún hay errores: {final_errors}")


async def example_real_world_scenario():
    """
    Ejemplo de escenario real: ticket de OXXO con folio mal detectado
    """
    print("\n=== EJEMPLO 5: ESCENARIO REAL - TICKET OXXO ===")

    # Simulación de texto OCR con errores típicos
    simulated_ocr_text = """
    OXXO TIENDA #1234
    RFC: OXX970814HS9
    FECHA: 19/09/2024 18:30
    FOLIO: A-78945б  <-- Error: OCR leyó 'б' en lugar de '6'

    Coca Cola 600ml    $25.00
    Sabritas Original  $15.50
    TOTAL: $40.50
    """

    # Portal OXXO rechaza el folio
    portal_error = "Folio de ticket no válido. Formato esperado: A-######"

    print(f"📄 Texto OCR (con errores): {simulated_ocr_text}")
    print(f"🚨 Error de portal OXXO: {portal_error}")

    # GPT Vision analiza la imagen original para corregir
    from core.intelligent_field_validator import validate_single_field

    ticket_image = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="

    result = await validate_single_field(
        image_data=ticket_image,
        field_name="folio",
        portal_error=portal_error
    )

    print(f"🔍 GPT Vision detectó:")
    print(f"   Folio corregido: '{result.final_value}'")
    print(f"   Confianza: {result.confidence:.2%}")
    print(f"   Explicación: {result.gpt_reasoning}")

    # Simular éxito con valor corregido
    if result.final_value == "A-789456":
        print("✅ ¡Portal OXXO acepta el folio corregido!")
    else:
        print("⚠️ Necesita revisión manual")


async def main():
    """Ejecutar todos los ejemplos"""
    print("🚀 INICIANDO EJEMPLOS DE VALIDACIÓN INTELIGENTE CON GPT VISION")
    print("=" * 70)

    try:
        await example_basic_validation()
        await example_portal_error_correction()
        await example_multiple_fields_validation()
        await example_web_automation_integration()
        await example_real_world_scenario()

        print("\n✅ TODOS LOS EJEMPLOS COMPLETADOS")
        print("\n💡 BENEFICIOS DEL SISTEMA:")
        print("   🎯 Corrección automática de errores de OCR")
        print("   🧠 Análisis inteligente con contexto visual")
        print("   🔄 Recuperación automática de errores de portal")
        print("   📊 Múltiples candidatos para máxima precisión")
        print("   🏷️ Razonamiento explicable de las decisiones")

    except Exception as e:
        logger.error(f"Error en ejemplos: {e}")


if __name__ == "__main__":
    # Ejecutar ejemplos
    asyncio.run(main())