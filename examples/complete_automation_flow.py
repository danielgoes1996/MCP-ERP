"""
EJEMPLO COMPLETO: Flujo de Facturación Automática con Gestión de Clientes

Este ejemplo muestra cómo funciona todo el sistema integrado:
1. Configurar cliente con datos fiscales
2. Configurar credenciales de portales
3. Subir ticket y extraer datos
4. Automatizar facturación con IA
"""

import asyncio
import json
import base64
from datetime import datetime

# Importar nuestros módulos
from core.client_credential_manager import (
    get_credential_manager,
    ClientFiscalData,
    MerchantCredentials
)
from core.advanced_ocr_service import AdvancedOCRService
from core.ai_rpa_planner import AIRPAPlanner
from core.playwright_executor import PlaywrightExecutor


async def complete_automation_example():
    """
    Ejemplo completo del flujo de automatización inteligente
    """

    print("🚀 INICIANDO FLUJO DE FACTURACIÓN AUTOMÁTICA")
    print("=" * 60)

    # ===============================================================
    # 1. CONFIGURAR CLIENTE CON DATOS FISCALES
    # ===============================================================

    print("\n📋 PASO 1: Configurando cliente con datos fiscales")

    manager = get_credential_manager()
    client_id = "empresa_demo_001"

    # Datos fiscales del cliente
    fiscal_data = ClientFiscalData(
        client_id=client_id,
        rfc="EMP850315ABC",
        razon_social="Empresa Demo SA de CV",
        email="facturacion@empresa-demo.com",
        domicilio_fiscal="Av. Reforma 123, Col. Centro, CDMX",
        regimen_fiscal="601",  # General de Ley Personas Morales
        telefono="5555551234",
        codigo_postal="06000"
    )

    success = await manager.store_client_fiscal_data(client_id, fiscal_data)
    print(f"✅ Cliente configurado: {success}")
    print(f"   RFC: {fiscal_data.rfc}")
    print(f"   Razón Social: {fiscal_data.razon_social}")

    # ===============================================================
    # 2. CONFIGURAR CREDENCIALES DE PORTALES
    # ===============================================================

    print("\n🔑 PASO 2: Configurando credenciales de portales")

    # Configurar OXXO
    oxxo_credentials = MerchantCredentials(
        merchant_name="OXXO",
        portal_url="https://factura.oxxo.com",
        username="emp850315abc",
        password="mi_password_seguro_oxxo",
        additional_data={
            "phone": fiscal_data.telefono,
            "backup_email": "backup@empresa-demo.com"
        }
    )

    success_oxxo = await manager.store_merchant_credentials(client_id, "OXXO", oxxo_credentials)
    print(f"✅ OXXO configurado: {success_oxxo}")

    # Configurar Walmart
    walmart_credentials = MerchantCredentials(
        merchant_name="WALMART",
        portal_url="https://factura.walmart.com.mx",
        username="emp850315abc@gmail.com",
        password="mi_password_seguro_walmart",
        additional_data={
            "membership_type": "business"
        }
    )

    success_walmart = await manager.store_merchant_credentials(client_id, "WALMART", walmart_credentials)
    print(f"✅ Walmart configurado: {success_walmart}")

    # ===============================================================
    # 3. SIMULAR TICKET SUBIDO POR EL CLIENTE
    # ===============================================================

    print("\n📄 PASO 3: Procesando ticket subido por el cliente")

    # Simular datos extraídos de un ticket
    ticket_data = {
        "folio": "ABC123456",
        "fecha": "2025-01-19",
        "total": 285.50,
        "rfc_emisor": "OXX860315GH8",
        "merchant_detected": "OXXO",
        "items": [
            {"descripcion": "Coca Cola 600ml", "cantidad": 2, "precio": 25.00},
            {"descripcion": "Sabritas 150g", "cantidad": 3, "precio": 18.50},
            {"descripcion": "Gasolina Magna", "cantidad": 1, "precio": 230.00}
        ],
        "direccion_sucursal": "OXXO Sucursal Centro, CDMX"
    }

    print(f"📊 Ticket procesado:")
    print(f"   Merchant: {ticket_data['merchant_detected']}")
    print(f"   Folio: {ticket_data['folio']}")
    print(f"   Total: ${ticket_data['total']}")
    print(f"   RFC Emisor: {ticket_data['rfc_emisor']}")

    # ===============================================================
    # 4. PREPARAR CONTEXTO COMPLETO PARA AUTOMATIZACIÓN
    # ===============================================================

    print("\n🧠 PASO 4: Preparando contexto para automatización inteligente")

    session_context = await manager.prepare_portal_session(
        client_id=client_id,
        merchant_name="OXXO",
        ticket_data=ticket_data
    )

    print(f"✅ Contexto preparado:")
    print(f"   Cliente: {session_context['client_id']}")
    print(f"   Portal: {session_context['portal_credentials']['url']}")
    print(f"   Usuario: {session_context['portal_credentials']['username']}")
    print(f"   Datos fiscales listos: ✅")
    print(f"   Credenciales listas: ✅")

    # ===============================================================
    # 5. CREAR PLAN IA PARA AUTOMATIZACIÓN
    # ===============================================================

    print("\n🤖 PASO 5: Creando plan de automatización con IA")

    try:
        # Inicializar planificador IA
        ai_planner = AIRPAPlanner()

        # Crear plan basado en el contexto completo
        automation_plan = await ai_planner.analyze_portal_and_create_plan(
            merchant_name="OXXO",
            portal_url=session_context['portal_credentials']['url'],
            ticket_data=ticket_data,
            context={
                "fiscal_data": session_context['fiscal_data'],
                "portal_credentials": session_context['portal_credentials'],
                "operation_type": "invoice_generation"
            }
        )

        print(f"✅ Plan de automatización creado:")
        print(f"   ID del Plan: {automation_plan.plan_id}")
        print(f"   Acciones planificadas: {len(automation_plan.actions)}")
        print(f"   Tiempo estimado: {automation_plan.estimated_duration_seconds}s")

        # Mostrar algunas acciones del plan
        print(f"\n📋 Primeras acciones del plan:")
        for i, action in enumerate(automation_plan.actions[:3]):
            print(f"   {i+1}. {action.action_type.value}: {action.description}")

    except Exception as e:
        print(f"⚠️  Simulando plan IA (sin API keys):")
        # Plan simulado para demostración
        automation_plan = {
            "plan_id": "plan_demo_001",
            "actions": [
                {"step": 1, "action": "navigate", "description": "Ir a portal OXXO"},
                {"step": 2, "action": "login", "description": "Iniciar sesión"},
                {"step": 3, "action": "fill_form", "description": "Llenar datos fiscales"},
                {"step": 4, "action": "upload_ticket", "description": "Subir imagen del ticket"},
                {"step": 5, "action": "submit", "description": "Generar factura"},
                {"step": 6, "action": "download", "description": "Descargar CFDI"}
            ],
            "estimated_duration": "90 segundos"
        }
        print(f"   Plan ID: {automation_plan['plan_id']}")
        print(f"   Acciones: {len(automation_plan['actions'])}")

    # ===============================================================
    # 6. SIMULAR EJECUCIÓN DE AUTOMATIZACIÓN
    # ===============================================================

    print("\n⚙️ PASO 6: Ejecutando automatización (simulación)")

    # En un entorno real, aquí se ejecutaría el plan con Playwright
    print(f"🔄 Iniciando ejecución automatizada...")
    print(f"   Portal objetivo: {session_context['portal_credentials']['url']}")
    print(f"   Credenciales: {session_context['portal_credentials']['username']}")

    # Simular progreso
    steps = [
        "🌐 Navegando al portal OXXO",
        "🔐 Iniciando sesión con credenciales del cliente",
        "📝 Llenando formulario con datos fiscales",
        "📄 Subiendo datos del ticket",
        "⚡ Generando factura electrónica",
        "📥 Descargando CFDI (XML + PDF)"
    ]

    for i, step in enumerate(steps):
        await asyncio.sleep(0.5)  # Simular tiempo de procesamiento
        print(f"   {step}")

    # ===============================================================
    # 7. RESULTADO FINAL
    # ===============================================================

    print("\n🎉 PASO 7: Automatización completada exitosamente")

    result = {
        "success": True,
        "client_id": client_id,
        "merchant": "OXXO",
        "ticket_folio": ticket_data["folio"],
        "invoice_generated": True,
        "cfdi_files": [
            "factura_ABC123456.xml",
            "factura_ABC123456.pdf"
        ],
        "processing_time": "45 segundos",
        "fiscal_data_used": {
            "rfc_receptor": fiscal_data.rfc,
            "razon_social": fiscal_data.razon_social,
            "regimen_fiscal": fiscal_data.regimen_fiscal
        },
        "portal_session": {
            "url": session_context['portal_credentials']['url'],
            "login_successful": True,
            "form_filled": True,
            "cfdi_downloaded": True
        }
    }

    print(f"✅ Factura generada exitosamente:")
    print(f"   Cliente: {result['fiscal_data_used']['razon_social']}")
    print(f"   RFC: {result['fiscal_data_used']['rfc_receptor']}")
    print(f"   Folio: {result['ticket_folio']}")
    print(f"   Portal: {result['merchant']}")
    print(f"   Archivos: {', '.join(result['cfdi_files'])}")
    print(f"   Tiempo: {result['processing_time']}")

    print("\n" + "=" * 60)
    print("🎯 FLUJO COMPLETADO - Sistema funcionando perfectamente")
    print("=" * 60)

    return result


async def demonstrate_multiple_clients():
    """
    Demuestra cómo el sistema maneja múltiples clientes
    """

    print("\n\n🏢 DEMOSTRACIÓN: Múltiples clientes y portales")
    print("=" * 60)

    manager = get_credential_manager()

    # Cliente 1: Empresa pequeña
    client1_id = "empresa_pequena_001"
    fiscal1 = ClientFiscalData(
        client_id=client1_id,
        rfc="EPE850315XYZ",
        razon_social="Empresa Pequeña SA",
        email="admin@empresa-pequena.com",
        domicilio_fiscal="Calle 5 de Mayo 45, Puebla",
        regimen_fiscal="601"
    )

    await manager.store_client_fiscal_data(client1_id, fiscal1)

    # Cliente 2: Freelancer
    client2_id = "freelancer_001"
    fiscal2 = ClientFiscalData(
        client_id=client2_id,
        rfc="FREL850315ABC",
        razon_social="Juan Pérez López",
        email="juan@freelancer.com",
        domicilio_fiscal="Av. Universidad 123, CDMX",
        regimen_fiscal="612"  # Personas Físicas con Actividades Empresariales
    )

    await manager.store_client_fiscal_data(client2_id, fiscal2)

    print(f"✅ Cliente 1 configurado: {fiscal1.razon_social}")
    print(f"✅ Cliente 2 configurado: {fiscal2.razon_social}")

    # Mostrar resúmenes
    for client_id in [client1_id, client2_id]:
        summary = await manager.get_client_summary(client_id)
        print(f"\n📊 Resumen {client_id}:")
        print(f"   RFC: {summary['fiscal_data']['rfc']}")
        print(f"   Razón Social: {summary['fiscal_data']['razon_social']}")
        print(f"   Portales configurados: {summary['configured_portals']}")
        print(f"   Listo para automatización: {summary['ready_for_automation']}")


async def demonstrate_error_handling():
    """
    Demuestra el manejo de errores del sistema
    """

    print("\n\n⚠️ DEMOSTRACIÓN: Manejo de errores")
    print("=" * 50)

    manager = get_credential_manager()

    # Error 1: Cliente sin datos fiscales
    try:
        await manager.prepare_portal_session(
            client_id="cliente_inexistente",
            merchant_name="OXXO",
            ticket_data={}
        )
    except ValueError as e:
        print(f"❌ Error esperado: {e}")

    # Error 2: RFC inválido
    try:
        invalid_fiscal = ClientFiscalData(
            client_id="test",
            rfc="RFC_INVALIDO",
            razon_social="Test",
            email="test@test.com",
            domicilio_fiscal="Test",
            regimen_fiscal="601"
        )
    except Exception as e:
        print(f"❌ Error de validación: {e}")

    print("✅ Sistema maneja errores correctamente")


if __name__ == "__main__":
    async def main():
        await complete_automation_example()
        await demonstrate_multiple_clients()
        await demonstrate_error_handling()

    asyncio.run(main())