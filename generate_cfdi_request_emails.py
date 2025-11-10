"""
Generar Templates de Email para Solicitar CFDIs Faltantes

Este script:
1. Lee los 21 gastos sin CFDI
2. Los agrupa por proveedor
3. Genera templates de email personalizados para cada uno
4. Guarda los templates en archivos .txt
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from collections import defaultdict

POSTGRES_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "127.0.0.1"),
    "port": int(os.getenv("POSTGRES_PORT", 5433)),
    "database": os.getenv("POSTGRES_DB", "mcp_system"),
    "user": os.getenv("POSTGRES_USER", "mcp_user"),
    "password": os.getenv("POSTGRES_PASSWORD", "changeme")
}


def classify_provider(description):
    """Clasifica el proveedor por la descripción"""
    desc_upper = description.upper()

    # Tech/Software
    if 'ADOBE' in desc_upper:
        return ('Adobe', 'Software/Diseño', 'facturacion@adobe.com')
    elif 'APPLE' in desc_upper:
        return ('Apple', 'Software/Hardware', 'facturacion@apple.com')
    elif 'GOOGLE' in desc_upper or 'YOUTUBE' in desc_upper:
        return ('Google', 'Software/Publicidad', 'facturacion@google.com')
    elif 'SPOTIFY' in desc_upper:
        return ('Spotify', 'Software', 'facturacion@spotify.com')
    elif 'GITHUB' in desc_upper:
        return ('GitHub', 'Software', 'billing@github.com')

    # Telecomunicaciones
    elif 'TELCEL' in desc_upper:
        return ('Telcel', 'Telecomunicaciones', 'atencionclientes@telcel.com')
    elif 'TELMEX' in desc_upper:
        return ('Telmex', 'Telecomunicaciones', 'atencionclientes@telmex.com')

    # Gasolina
    elif 'GASOLINERO' in desc_upper or 'GASOL' in desc_upper:
        if 'BERISA' in desc_upper:
            return ('Grupo Gasolinero Berisa', 'Gasolina', 'facturacion@berisa.com.mx')
        else:
            return ('Gasolinera', 'Gasolina', 'facturacion@gasolinera.com.mx')

    # Alimentos/Restaurantes
    elif 'SUSHI' in desc_upper:
        return ('Sushi Roll', 'Alimentos', 'facturacion@sushiroll.com.mx')
    elif 'TAQUERIA' in desc_upper:
        return ('Taquería', 'Alimentos', 'facturacion@taqueria.com.mx')
    elif 'STARBUCKS' in desc_upper:
        return ('Starbucks', 'Alimentos', 'facturacion@starbucks.com.mx')
    elif 'POLANQUITO' in desc_upper:
        return ('Polanquito', 'Alimentos', 'facturacion@polanquito.com.mx')

    # Default
    else:
        # Extraer nombre del proveedor de la descripción
        parts = desc_upper.split()
        provider_name = parts[0] if parts else 'Proveedor'
        return (provider_name, 'Otros', 'facturacion@proveedor.com')


def generate_email_template(provider_name, provider_type, transactions, rfc_receptor):
    """Genera template de email para un proveedor"""

    # Header
    template = f"""
{'='*100}
📧 SOLICITUD DE FACTURA ELECTRÓNICA (CFDI)
{'='*100}

Para: {provider_name}
Asunto: Solicitud de Facturas Electrónicas (CFDIs) - {datetime.now().strftime('%B %Y')}

{'='*100}

Estimado equipo de {provider_name},

Por medio del presente, solicito amablemente la emisión de las siguientes facturas electrónicas (CFDIs)
correspondientes a los cargos realizados a mi tarjeta/cuenta durante el mes de enero 2025:

"""

    # Tabla de transacciones
    template += f"""
{'─'*100}
{'Fecha':<12} {'Monto':>12} {'Referencia/Descripción':<70}
{'─'*100}
"""

    total_amount = 0
    for tx in sorted(transactions, key=lambda x: x['transaction_date']):
        fecha = tx['transaction_date'].strftime('%d/%m/%Y')
        monto = abs(float(tx['amount']))
        desc = tx['description'][:70]
        template += f"{fecha:<12} ${monto:>10,.2f} {desc:<70}\n"
        total_amount += monto

    template += f"""{'─'*100}
{'TOTAL':<12} ${total_amount:>10,.2f}
{'─'*100}

"""

    # Datos fiscales
    template += f"""
DATOS FISCALES PARA LA FACTURACIÓN:

RFC:                {rfc_receptor}
Razón Social:       [COMPLETAR CON RAZÓN SOCIAL DE LA EMPRESA]
Régimen Fiscal:     [COMPLETAR - ej: 601 General de Ley Personas Morales]
Código Postal:      [COMPLETAR]
Uso de CFDI:        G03 - Gastos en General

Email de envío:     facturacion@[EMPRESA].com

"""

    # Instrucciones específicas por tipo
    if provider_type == 'Software/Diseño' or provider_type == 'Software/Hardware' or provider_type == 'Software':
        template += f"""
INSTRUCCIONES ESPECÍFICAS:

Por favor, emitir las facturas con los siguientes datos:
- Método de pago: PUE (Pago en una sola exhibición)
- Forma de pago: 04 - Tarjeta de crédito
- Moneda: MXN (Pesos mexicanos)

Si los cargos fueron realizados en USD, favor de usar el tipo de cambio oficial del día de la transacción
según el Diario Oficial de la Federación (DOF).

"""
    elif provider_type == 'Telecomunicaciones':
        template += f"""
INSTRUCCIONES ESPECÍFICAS:

- Si tiene portal de facturación en línea, favor de indicar la URL
- Método de pago: PUE (Pago en una sola exhibición)
- Forma de pago: 04 - Tarjeta de crédito (o la que corresponda)

"""
    elif provider_type == 'Gasolina':
        template += f"""
INSTRUCCIONES ESPECÍFICAS:

- Favor de facturar cada cargo de manera individual con la fecha exacta del consumo
- Incluir litros despachados y precio por litro si es posible
- Método de pago: PUE (Pago en una sola exhibición)
- Forma de pago: 04 - Tarjeta de crédito

"""
    elif provider_type == 'Alimentos':
        template += f"""
INSTRUCCIONES ESPECÍFICAS:

- Favor de facturar cada consumo de manera individual con la fecha exacta
- Método de pago: PUE (Pago en una sola exhibición)
- Forma de pago: 04 - Tarjeta de crédito o efectivo (según corresponda)

"""

    # Footer
    template += f"""
PLAZO DE ENTREGA:

Por disposiciones fiscales del SAT, las facturas deben emitirse en el mismo mes del consumo.
Agradecería que pudieran enviarme las facturas a la brevedad posible.

Si tienen algún portal de autofacturación en línea, favor de compartir la liga y las instrucciones.

{'─'*100}

Quedo al pendiente de su respuesta.

Saludos cordiales,
[NOMBRE DEL SOLICITANTE]
[PUESTO]
[EMPRESA]
[TELÉFONO]
[EMAIL]

{'='*100}

NOTAS INTERNAS:
- Total de transacciones: {len(transactions)}
- Monto total a facturar: ${total_amount:,.2f} MXN
- Categoría: {provider_type}
- Prioridad: {'ALTA' if total_amount > 500 else 'MEDIA' if total_amount > 200 else 'BAJA'}

{'='*100}
"""

    return template


def main():
    print("\n" + "="*100)
    print("📧 GENERADOR DE TEMPLATES DE EMAIL PARA SOLICITUD DE CFDIs")
    print("="*100 + "\n")

    conn = psycopg2.connect(**POSTGRES_CONFIG)
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # Obtener gastos sin CFDI
        cursor.execute("""
            WITH gastos_sin_match AS (
              SELECT
                bt.id,
                bt.transaction_date,
                bt.description,
                bt.amount,
                vr.match_status
              FROM bank_transactions bt
              LEFT JOIN vw_reconciliation_ready_improved vr ON bt.id = vr.transaction_id AND vr.match_rank = 1
              WHERE bt.transaction_type = 'debit'
                AND NOT (
                  bt.description ILIKE '%traspaso%' OR bt.description ILIKE '%spei%' OR bt.description ILIKE '%transferencia%' OR
                  bt.description ILIKE '%comision%' OR bt.description ILIKE '%iva comision%' OR bt.description ILIKE '%isr retenido%' OR
                  bt.description ILIKE '%recarga%' OR bt.description ILIKE '%tutag%' OR bt.description ILIKE '%pase%'
                )
                AND (vr.match_status IS NULL OR vr.match_status NOT LIKE 'AUTO_MATCH%')
            )
            SELECT * FROM gastos_sin_match
            ORDER BY ABS(amount) DESC
        """)

        gastos_sin_cfdi = cursor.fetchall()

        # Obtener RFC receptor de la empresa
        cursor.execute("""
            SELECT DISTINCT rfc_receptor
            FROM expense_invoices
            WHERE rfc_receptor IS NOT NULL
            LIMIT 1
        """)

        rfc_result = cursor.fetchone()
        rfc_receptor = rfc_result['rfc_receptor'] if rfc_result else 'XXXXXXXXXXX'

        print(f"📋 Gastos sin CFDI encontrados: {len(gastos_sin_cfdi)}")
        print(f"🏢 RFC Receptor: {rfc_receptor}\n")

        # Agrupar por proveedor
        by_provider = defaultdict(list)

        for tx in gastos_sin_cfdi:
            provider_name, provider_type, email = classify_provider(tx['description'])
            by_provider[(provider_name, provider_type, email)].append(tx)

        print(f"🏪 Proveedores únicos: {len(by_provider)}\n")

        # Crear directorio para templates
        output_dir = "/Users/danielgoes96/Desktop/mcp-server/cfdi_requests"
        os.makedirs(output_dir, exist_ok=True)

        # Generar template para cada proveedor
        print("="*100)
        print("📝 GENERANDO TEMPLATES DE EMAIL")
        print("="*100 + "\n")

        templates_generated = 0
        total_amount = 0

        for (provider_name, provider_type, email), transactions in sorted(
            by_provider.items(),
            key=lambda x: -sum(abs(float(t['amount'])) for t in x[1])
        ):
            provider_total = sum(abs(float(tx['amount'])) for tx in transactions)
            total_amount += provider_total

            print(f"✓ {provider_name:<30} {len(transactions):>2} tx  ${provider_total:>8,.2f}  ({provider_type})")

            # Generar template
            template = generate_email_template(provider_name, provider_type, transactions, rfc_receptor)

            # Guardar archivo
            safe_filename = provider_name.replace(' ', '_').replace('/', '_').lower()
            filename = f"{output_dir}/{safe_filename}_cfdi_request.txt"

            with open(filename, 'w', encoding='utf-8') as f:
                f.write(template)

            templates_generated += 1

        print("\n" + "="*100)
        print("✅ TEMPLATES GENERADOS EXITOSAMENTE")
        print("="*100 + "\n")

        print(f"📊 RESUMEN:")
        print(f"   Templates creados:             {templates_generated}")
        print(f"   Total de transacciones:        {len(gastos_sin_cfdi)}")
        print(f"   Monto total a facturar:        ${total_amount:,.2f} MXN")
        print(f"   Directorio de salida:          {output_dir}/")

        print("\n💡 PRÓXIMOS PASOS:")
        print("   1. Revisa cada template en el directorio cfdi_requests/")
        print("   2. Completa los datos faltantes ([COMPLETAR])")
        print("   3. Envía los emails a cada proveedor")
        print("   4. Cuando recibas los CFDIs, súbelos al sistema")
        print("   5. El sistema de embeddings los conciliará automáticamente")

        print("\n🎯 OBJETIVO:")
        print(f"   Con estos {len(gastos_sin_cfdi)} CFDIs faltantes, la tasa de conciliación subirá de 38.2% a 100%")

        print("\n" + "="*100 + "\n")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()
