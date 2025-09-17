#!/usr/bin/env python3
"""
Ejemplos completos de payloads JSON para gastos empresariales
Incluye todos los campos requeridos y opcionales con validaciones
"""

import json
import base64
from datetime import datetime, timedelta


def get_basic_expense_example():
    """Ejemplo básico con campos mínimos requeridos"""
    return {
        "name": "Comida de trabajo con cliente ACME Corp",
        "description": "Reunión de negocios en restaurante para cerrar contrato anual",
        "amount": 1250.00,
        "expense_date": (datetime.now() - timedelta(days=1)).isoformat(),

        "supplier": {
            "name": "Restaurante El Buen Gusto S.A. de C.V.",
            "rfc": "RBG920515ABC",
            "address": "Av. Reforma 123, Col. Centro, CDMX",
            "phone": "55-1234-5678",
            "email": "facturacion@elbuengusto.com"
        },

        "tax_info": {
            "subtotal": 1077.59,
            "iva_rate": 0.16,
            "iva_amount": 172.41,
            "total": 1250.00
        },

        "payment_method": "tarjeta_empleado",
        "who_paid": "employee",
        "status": "draft"
    }


def get_complete_expense_with_cfdi():
    """Ejemplo completo con CFDI y todos los campos"""

    # Simular contenido XML de CFDI (simplificado)
    cfdi_xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
                  Version="4.0"
                  Folio="12345"
                  Total="800.00"
                  SubTotal="689.66">
    <cfdi:Emisor Rfc="GAS850315XYZ" Nombre="Gasolinera Premium S.A."/>
    <cfdi:TimbreFiscalDigital UUID="12345678-1234-1234-1234-123456789012"/>
</cfdi:Comprobante>"""

    # Simular PDF base64 (contenido pequeño de ejemplo)
    fake_pdf_content = base64.b64encode(b"PDF-content-placeholder").decode('utf-8')

    return {
        "name": "⛽ Combustible vehículo empresa - Viaje Guadalajara",
        "description": "Gasolina para viaje de negocios a sucursal Guadalajara. Vehículo placas ABC-1234",
        "amount": 800.00,
        "expense_date": (datetime.now() - timedelta(days=2)).isoformat(),

        # Información del proveedor
        "supplier": {
            "name": "Gasolinera Premium S.A. de C.V.",
            "rfc": "GAS850315XYZ",
            "tax_id": "GAS850315XYZ",
            "address": "Carretera Federal 15D Km 45, Guadalajara, JAL",
            "phone": "33-9876-5432",
            "email": "facturacion@gaspremium.mx"
        },

        # Información financiera detallada
        "tax_info": {
            "subtotal": 689.66,
            "iva_rate": 0.16,
            "iva_amount": 110.34,
            "total": 800.00
        },

        # Clasificación contable
        "account_code": "5105001",  # Gastos de combustible
        "analytic_account": "PROYECTO_EXPANSION_GDL",  # Centro de costos
        "category": "Combustibles y Lubricantes",

        # Información de pago
        "payment_method": "tarjeta_empresa",
        "who_paid": "company",

        # Empleado responsable
        "employee_id": 1,
        "employee_name": "Daniel Gomez Escobedo",

        # CFDI específico
        "cfdi_uuid": "12345678-1234-1234-1234-123456789012",
        "cfdi_folio": "12345",

        # Adjuntos
        "attachments": [
            {
                "filename": "CFDI_GAS850315XYZ_12345.xml",
                "content": base64.b64encode(cfdi_xml_content.encode('utf-8')).decode('utf-8'),
                "attachment_type": "cfdi_xml",
                "mime_type": "application/xml",
                "description": "CFDI XML original de la factura"
            },
            {
                "filename": "CFDI_GAS850315XYZ_12345.pdf",
                "content": fake_pdf_content,
                "attachment_type": "cfdi_pdf",
                "mime_type": "application/pdf",
                "description": "CFDI PDF para archivo contable"
            },
            {
                "filename": "comprobante_pago_tarjeta.pdf",
                "content": fake_pdf_content,
                "attachment_type": "payment_receipt",
                "mime_type": "application/pdf",
                "description": "Comprobante de pago con tarjeta empresarial"
            },
            {
                "filename": "foto_bomba_gasolina.jpg",
                "content": fake_pdf_content,  # Simular imagen
                "attachment_type": "evidence",
                "mime_type": "image/jpeg",
                "description": "Foto de la bomba de gasolina como evidencia"
            }
        ],

        # Estado y metadatos
        "status": "draft",
        "created_by": "daniel@carretaverde.com",
        "notes": "Gasto pre-autorizado por gerencia para viaje de expansión comercial"
    }


def get_restaurant_expense_example():
    """Ejemplo de gasto de restaurante con cliente"""
    return {
        "name": "🍽️ Cena de negocios - Cliente ACME Corporation",
        "description": "Cena de negocios para cerrar contrato de distribución nacional. Asistieron 4 personas: 2 de nuestra empresa y 2 del cliente.",
        "amount": 2850.00,
        "expense_date": (datetime.now() - timedelta(days=3)).isoformat(),

        "supplier": {
            "name": "Restaurante Casa Real S.A. de C.V.",
            "rfc": "RCR890420DEF",
            "address": "Polanco 456, Col. Polanco, CDMX 11560",
            "phone": "55-5555-0123",
            "email": "contabilidad@casareal.mx"
        },

        "tax_info": {
            "subtotal": 2456.90,
            "iva_rate": 0.16,
            "iva_amount": 393.10,
            "total": 2850.00
        },

        "account_code": "5203001",  # Gastos de representación
        "analytic_account": "VENTAS_NACIONAL",
        "category": "Gastos de Representación",

        "payment_method": "tarjeta_empresa",
        "who_paid": "company",

        "employee_id": 1,
        "employee_name": "Daniel Gomez Escobedo",

        "cfdi_uuid": "87654321-4321-4321-4321-210987654321",
        "cfdi_folio": "A-789",

        "attachments": [
            {
                "filename": "factura_casa_real_A789.xml",
                "content": base64.b64encode(b"<cfdi:Comprobante...></cfdi:Comprobante>").decode('utf-8'),
                "attachment_type": "cfdi_xml",
                "mime_type": "application/xml",
                "description": "CFDI XML de factura del restaurante"
            },
            {
                "filename": "factura_casa_real_A789.pdf",
                "content": base64.b64encode(b"PDF-content").decode('utf-8'),
                "attachment_type": "cfdi_pdf",
                "mime_type": "application/pdf",
                "description": "CFDI PDF para contabilidad"
            }
        ],

        "status": "draft",
        "created_by": "daniel@carretaverde.com",
        "notes": "Gasto justificado para desarrollo de nuevos clientes. Contrato firmado por $500,000 anuales."
    }


def get_office_supplies_expense():
    """Ejemplo de gastos de oficina con múltiples artículos"""
    return {
        "name": "📚 Suministros de oficina - Material para equipo ventas",
        "description": "Compra de material de oficina para equipar nuevas estaciones de trabajo del equipo de ventas",
        "amount": 1540.00,
        "expense_date": (datetime.now() - timedelta(days=1)).isoformat(),

        "supplier": {
            "name": "Office Depot de México S.A. de C.V.",
            "rfc": "ODM940228GHI",
            "address": "Av. Insurgentes Sur 1234, Col. Del Valle, CDMX",
            "phone": "800-OFFICE-1",
            "email": "facturacion@officedepot.com.mx"
        },

        "tax_info": {
            "subtotal": 1327.59,
            "iva_rate": 0.16,
            "iva_amount": 212.41,
            "total": 1540.00
        },

        "account_code": "5104002",  # Gastos de oficina
        "analytic_account": "ADMINISTRACION",
        "category": "Suministros de Oficina",

        "payment_method": "transferencia",
        "who_paid": "company",

        "employee_id": 1,
        "employee_name": "Daniel Gomez Escobedo",

        "attachments": [
            {
                "filename": "ticket_office_depot_001234.jpg",
                "content": base64.b64encode(b"JPEG-image-content").decode('utf-8'),
                "attachment_type": "evidence",
                "mime_type": "image/jpeg",
                "description": "Foto del ticket de compra"
            }
        ],

        "status": "draft",
        "created_by": "daniel@carretaverde.com",
        "notes": "Material autorizado por HR para nuevas contrataciones Q1 2025"
    }


def get_travel_expense_example():
    """Ejemplo de gasto de viaje con hotel y transportación"""
    return {
        "name": "✈️ Viaje de negocios Monterrey - Hotel y transportación",
        "description": "Estancia en Monterrey para reuniones con clientes potenciales y presentación de productos",
        "amount": 4200.00,
        "expense_date": (datetime.now() - timedelta(days=7)).isoformat(),

        "supplier": {
            "name": "Hotel Business Center Monterrey S.A.",
            "rfc": "HBC850615JKL",
            "address": "Av. Constitución 789, San Pedro Garza García, NL",
            "phone": "81-8888-9999",
            "email": "reservaciones@hotelbusinessmty.com"
        },

        "tax_info": {
            "subtotal": 3620.69,
            "iva_rate": 0.16,
            "iva_amount": 579.31,
            "total": 4200.00
        },

        "account_code": "5205001",  # Gastos de viaje
        "analytic_account": "DESARROLLO_COMERCIAL",
        "category": "Viajes y Hospedaje",

        "payment_method": "tarjeta_empresa",
        "who_paid": "company",

        "employee_id": 1,
        "employee_name": "Daniel Gomez Escobedo",

        "cfdi_uuid": "55667788-5566-5566-5566-556677889900",
        "cfdi_folio": "MTY-0987",

        "attachments": [
            {
                "filename": "factura_hotel_mty_0987.xml",
                "content": base64.b64encode(b"<cfdi:Comprobante Total='4200.00'...></cfdi:Comprobante>").decode('utf-8'),
                "attachment_type": "cfdi_xml",
                "mime_type": "application/xml",
                "description": "CFDI XML del hotel"
            },
            {
                "filename": "factura_hotel_mty_0987.pdf",
                "content": base64.b64encode(b"PDF-hotel-invoice").decode('utf-8'),
                "attachment_type": "cfdi_pdf",
                "mime_type": "application/pdf",
                "description": "Factura PDF del hotel"
            },
            {
                "filename": "boarding_pass_monterrey.pdf",
                "content": base64.b64encode(b"PDF-boarding-pass").decode('utf-8'),
                "attachment_type": "evidence",
                "mime_type": "application/pdf",
                "description": "Pase de abordar como evidencia del viaje"
            }
        ],

        "status": "draft",
        "created_by": "daniel@carretaverde.com",
        "notes": "Viaje aprobado por dirección general. Resultó en 3 nuevos prospectos calificados."
    }


def get_minimal_cash_expense():
    """Ejemplo mínimo con pago en efectivo"""
    return {
        "name": "Estacionamiento centro comercial",
        "description": "Pago de estacionamiento durante visita a cliente en centro comercial",
        "amount": 45.00,
        "expense_date": datetime.now().isoformat(),

        "supplier": {
            "name": "Estacionamiento Plaza Central"
        },

        "tax_info": {
            "subtotal": 45.00,
            "iva_rate": 0.0,
            "iva_amount": 0.0,
            "total": 45.00
        },

        "payment_method": "efectivo",
        "who_paid": "employee",
        "status": "draft"
    }


def print_example(example_name: str, example_data: dict):
    """Imprime un ejemplo con formato"""
    print(f"\n{'='*60}")
    print(f"EJEMPLO: {example_name}")
    print(f"{'='*60}")
    print(json.dumps(example_data, indent=2, ensure_ascii=False))
    print(f"{'='*60}")


def generate_curl_command(example_data: dict, port: int = 8001):
    """Genera comando curl para probar el ejemplo"""
    json_data = json.dumps(example_data, ensure_ascii=False)
    return f"""curl -X POST "http://localhost:{port}/mcp" \\
     -H "Content-Type: application/json" \\
     -d '{json_data}'"""


if __name__ == "__main__":
    print("🎯 EJEMPLOS DE PAYLOADS PARA GASTOS EMPRESARIALES COMPLETOS")
    print("=" * 80)

    examples = [
        ("GASTO BÁSICO MÍNIMO", get_basic_expense_example()),
        ("COMBUSTIBLE CON CFDI COMPLETO", get_complete_expense_with_cfdi()),
        ("CENA DE NEGOCIOS", get_restaurant_expense_example()),
        ("SUMINISTROS DE OFICINA", get_office_supplies_expense()),
        ("VIAJE DE NEGOCIOS", get_travel_expense_example()),
        ("EFECTIVO MÍNIMO", get_minimal_cash_expense())
    ]

    for name, example in examples:
        print_example(name, example)

        # Mostrar comando curl para el primer ejemplo
        if name == "GASTO BÁSICO MÍNIMO":
            print(f"\n📡 COMANDO CURL PARA PROBAR:")
            print("-" * 60)
            print(generate_curl_command(example))
            print("-" * 60)

    print(f"\n\n🎯 ENDPOINT MCP SERVER:")
    print(f"POST http://localhost:8001/mcp")
    print(f"Method: create_complete_expense")

    print(f"\n🔍 CAMPOS REQUERIDOS MÍNIMOS:")
    print(f"• name (string): Descripción del gasto")
    print(f"• description (string): Detalles del gasto")
    print(f"• amount (number): Monto total")
    print(f"• expense_date (ISO date): Fecha del gasto")
    print(f"• supplier.name (string): Nombre del proveedor")
    print(f"• tax_info.subtotal (number): Subtotal")
    print(f"• tax_info.total (number): Total")

    print(f"\n✅ VALIDACIONES IMPLEMENTADAS:")
    print(f"• Campos requeridos presentes")
    print(f"• Formatos de fecha ISO válidos")
    print(f"• RFC mexicano válido (12-13 caracteres)")
    print(f"• UUID de CFDI válido")
    print(f"• Montos consistentes (subtotal + IVA = total)")
    print(f"• Límite máximo de $100,000 MXN")
    print(f"• Máximo 30 días de antigüedad")
    print(f"• Coherencia entre forma de pago y quien pagó")
    print(f"• Validación de estructura de CFDI XML")
    print(f"• Un solo archivo CFDI XML por gasto")

    print(f"\n🚀 USO DEL ENDPOINT:")
    print(f"1. Enviar JSON al endpoint /mcp con method: 'create_complete_expense'")
    print(f"2. El sistema validará todos los campos")
    print(f"3. Creará/buscará el proveedor en Odoo")
    print(f"4. Creará el gasto con todos los campos mapeados")
    print(f"5. Subirá todos los adjuntos como ir.attachment")
    print(f"6. Retornará ID del gasto y detalles de creación")