#!/usr/bin/env python3
"""
Reprocesamiento Completo de CFDIs
==================================
Este script:
1. Encuentra todos los XMLs de CFDIs
2. Parsea datos completos (RFC, nombre, conceptos)
3. Actualiza la base de datos
4. Verifica cada CFDI con el SAT
5. Genera reporte final

Uso:
    python3 reprocesar_cfdis_completo.py --company-id 2 --verify-sat
    python3 reprocesar_cfdis_completo.py --company-id 2 --limit 10  # Solo 10 para prueba
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import xml.etree.ElementTree as ET
import os
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime
import requests

# Configuración
POSTGRES_CONFIG = {
    "host": "127.0.0.1",
    "port": 5433,
    "database": "mcp_system",
    "user": "mcp_user",
    "password": "changeme"
}

API_BASE = "http://localhost:8000"

# Namespaces CFDI
NAMESPACES = {
    'cfdi': 'http://www.sat.gob.mx/cfd/4',
    'cfdi3': 'http://www.sat.gob.mx/cfd/3',
    'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital'
}


def parse_cfdi_complete(xml_path):
    """
    Parsea un XML de CFDI y extrae TODOS los datos importantes

    Returns:
        dict con todos los datos del CFDI
    """
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        # Determinar versión del CFDI
        version = root.get('Version') or root.get('version')
        ns = NAMESPACES['cfdi'] if version == '4.0' else NAMESPACES['cfdi3']

        data = {}

        # UUID (TimbreFiscalDigital)
        tfd = root.find('.//tfd:TimbreFiscalDigital', NAMESPACES)
        data['uuid'] = tfd.get('UUID') if tfd is not None else None

        # Datos generales
        data['version'] = version
        data['serie'] = root.get('Serie')
        data['folio'] = root.get('Folio')
        data['fecha'] = root.get('Fecha')
        data['forma_pago'] = root.get('FormaPago')
        data['metodo_pago'] = root.get('MetodoPago')
        data['tipo_comprobante'] = root.get('TipoDeComprobante')
        data['moneda'] = root.get('Moneda')
        data['tipo_cambio'] = root.get('TipoCambio')

        # Totales
        data['subtotal'] = float(root.get('SubTotal', 0))
        data['total'] = float(root.get('Total', 0))
        data['descuento'] = float(root.get('Descuento', 0)) if root.get('Descuento') else None

        # Emisor
        emisor = root.find(f'.//{{{ns}}}Emisor')
        if emisor is not None:
            data['rfc_emisor'] = emisor.get('Rfc')
            data['nombre_emisor'] = emisor.get('Nombre')
            data['regimen_fiscal'] = emisor.get('RegimenFiscal')
        else:
            data['rfc_emisor'] = None
            data['nombre_emisor'] = None
            data['regimen_fiscal'] = None

        # Receptor
        receptor = root.find(f'.//{{{ns}}}Receptor')
        if receptor is not None:
            data['rfc_receptor'] = receptor.get('Rfc')
            data['nombre_receptor'] = receptor.get('Nombre')
            data['uso_cfdi'] = receptor.get('UsoCFDI')
            data['domicilio_fiscal_receptor'] = receptor.get('DomicilioFiscalReceptor')
        else:
            data['rfc_receptor'] = None
            data['nombre_receptor'] = None
            data['uso_cfdi'] = None
            data['domicilio_fiscal_receptor'] = None

        # Conceptos
        conceptos = []
        for concepto in root.findall(f'.//{{{ns}}}Concepto'):
            conceptos.append({
                'clave_prod_serv': concepto.get('ClaveProdServ'),
                'cantidad': float(concepto.get('Cantidad', 0)),
                'clave_unidad': concepto.get('ClaveUnidad'),
                'unidad': concepto.get('Unidad'),
                'descripcion': concepto.get('Descripcion'),
                'valor_unitario': float(concepto.get('ValorUnitario', 0)),
                'importe': float(concepto.get('Importe', 0)),
                'descuento': float(concepto.get('Descuento', 0)) if concepto.get('Descuento') else None
            })

        data['conceptos'] = conceptos
        data['num_conceptos'] = len(conceptos)

        # Impuestos
        impuestos = root.find(f'.//{{{ns}}}Impuestos')
        if impuestos is not None:
            data['total_impuestos_trasladados'] = float(impuestos.get('TotalImpuestosTrasladados', 0))
            data['total_impuestos_retenidos'] = float(impuestos.get('TotalImpuestosRetenidos', 0)) if impuestos.get('TotalImpuestosRetenidos') else None
        else:
            data['total_impuestos_trasladados'] = None
            data['total_impuestos_retenidos'] = None

        return data

    except Exception as e:
        print(f"   ❌ Error parseando {xml_path}: {e}")
        return None


def update_cfdi_in_db(data, conn):
    """
    Actualiza un CFDI en la base de datos con todos los datos parseados
    """
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE expense_invoices
            SET
                rfc_emisor = %s,
                nombre_emisor = %s,
                rfc_receptor = %s,
                fecha_emision = %s,
                forma_pago = %s,
                metodo_pago = %s,
                updated_at = NOW()
            WHERE LOWER(uuid) = LOWER(%s)
            RETURNING id;
        """, (
            data['rfc_emisor'],
            data['nombre_emisor'],
            data['rfc_receptor'],
            data['fecha'],
            data['forma_pago'],
            data['metodo_pago'],
            data['uuid']
        ))

        result = cursor.fetchone()

        if result:
            invoice_id = result['id']
            if invoice_id > 0:
                return invoice_id
            else:
                print(f"   ⚠️  ID inválido: {invoice_id}")
                return None
        else:
            print(f"   ⚠️  CFDI {data['uuid']} no existe en BD")
            return None

    except Exception as e:
        print(f"   ❌ Error actualizando BD: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return None


def verify_cfdi_with_sat(uuid):
    """
    Verifica un CFDI con el SAT usando la API
    """
    try:
        response = requests.post(
            f"{API_BASE}/cfdi/{uuid}/verificar",
            timeout=10
        )

        if response.status_code == 200:
            return True, response.json()
        else:
            return False, response.json()

    except Exception as e:
        return False, str(e)


def find_xml_for_uuid(uuid, search_paths):
    """
    Busca el archivo XML correspondiente a un UUID
    """
    # Normalizar UUID
    uuid_lower = uuid.lower()
    uuid_upper = uuid.upper()

    for search_path in search_paths:
        # Buscar con diferentes variaciones
        for uuid_variant in [uuid_lower, uuid_upper, uuid]:
            xml_path = Path(search_path) / f"{uuid_variant}.xml"
            if xml_path.exists():
                return str(xml_path)

    # Búsqueda recursiva como último recurso
    for search_path in search_paths:
        for xml_path in Path(search_path).rglob(f"*{uuid_lower}*.xml"):
            return str(xml_path)

    return None


def main():
    parser = argparse.ArgumentParser(
        description='Reprocesa todos los CFDIs: parsea datos completos y verifica con SAT'
    )

    parser.add_argument('--company-id', type=int, default=2, help='ID de la compañía')
    parser.add_argument('--verify-sat', action='store_true', help='Verificar con SAT')
    parser.add_argument('--limit', type=int, help='Limitar cantidad de CFDIs a procesar')
    parser.add_argument('--skip-existing', action='store_true', help='Saltar CFDIs ya procesados')

    args = parser.parse_args()

    print("="*80)
    print("🔄 REPROCESAMIENTO COMPLETO DE CFDIs")
    print("="*80)
    print(f"\nCompañía: {args.company_id}")
    print(f"Verificar SAT: {'Sí' if args.verify_sat else 'No'}")
    print(f"Límite: {args.limit if args.limit else 'Sin límite'}")
    print()

    # Conectar a BD
    conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
    cursor = conn.cursor()

    # Obtener CFDIs a procesar
    where_clause = "WHERE company_id = %s"
    params = [args.company_id]

    if args.skip_existing:
        where_clause += " AND (rfc_emisor IS NULL OR nombre_emisor IS NULL)"

    if args.limit:
        limit_clause = f"LIMIT {args.limit}"
    else:
        limit_clause = ""

    cursor.execute(f"""
        SELECT uuid, filename
        FROM expense_invoices
        {where_clause}
        ORDER BY created_at DESC
        {limit_clause};
    """, params)

    cfdis = cursor.fetchall()

    total_cfdis = len(cfdis)
    print(f"📋 CFDIs a procesar: {total_cfdis}\n")

    if total_cfdis == 0:
        print("✅ No hay CFDIs para procesar")
        return

    # Rutas de búsqueda de XMLs
    search_paths = [
        './test_invoices/facturas_reales',
        './uploads/expense_invoices',
        './test_invoices'
    ]

    # Estadísticas
    stats = {
        'procesados': 0,
        'actualizados': 0,
        'verificados': 0,
        'vigentes': 0,
        'cancelados': 0,
        'no_encontrados': 0,
        'errores': 0,
        'xml_no_encontrado': 0
    }

    start_time = time.time()

    # Procesar cada CFDI
    for i, cfdi in enumerate(cfdis, 1):
        uuid = cfdi['uuid']

        print(f"\n[{i}/{total_cfdis}] {uuid}")

        # Buscar XML
        xml_path = find_xml_for_uuid(uuid, search_paths)

        if not xml_path:
            print(f"   ⚠️  XML no encontrado")
            stats['xml_no_encontrado'] += 1
            continue

        print(f"   📄 XML: {xml_path}")

        # Parsear XML
        data = parse_cfdi_complete(xml_path)

        if not data:
            stats['errores'] += 1
            continue

        print(f"   🏢 Emisor: {data['nombre_emisor'] or 'Sin nombre'} ({data['rfc_emisor']})")
        print(f"   💰 Total: ${data['total']:,.2f}")

        # Actualizar BD
        invoice_id = update_cfdi_in_db(data, conn)

        if invoice_id:
            stats['actualizados'] += 1
            conn.commit()
            print(f"   ✅ BD actualizada")

        # Verificar con SAT
        if args.verify_sat and data['rfc_emisor'] and data['rfc_receptor']:
            print(f"   🔍 Verificando con SAT...", end='', flush=True)

            success, result = verify_cfdi_with_sat(uuid)

            if success:
                status = result.get('status', 'unknown')
                print(f" {status}")

                stats['verificados'] += 1

                if status == 'vigente':
                    stats['vigentes'] += 1
                elif status == 'cancelado':
                    stats['cancelados'] += 1
                elif status == 'no_encontrado':
                    stats['no_encontrados'] += 1

                # Esperar un poco para no saturar el SAT
                time.sleep(0.5)
            else:
                print(f" ❌ Error")
                stats['errores'] += 1

        stats['procesados'] += 1

        # Progress cada 10
        if i % 10 == 0:
            elapsed = time.time() - start_time
            rate = i / elapsed
            remaining = (total_cfdis - i) / rate if rate > 0 else 0
            print(f"\n   ⏱️  Progreso: {i}/{total_cfdis} ({i/total_cfdis*100:.1f}%)")
            print(f"   ⚡ Velocidad: {rate:.1f} CFDIs/seg")
            print(f"   🕐 Tiempo restante: {remaining/60:.1f} min")

    cursor.close()
    conn.close()

    # Reporte final
    elapsed_total = time.time() - start_time

    print("\n" + "="*80)
    print("✅ REPROCESAMIENTO COMPLETADO")
    print("="*80)
    print(f"\n📊 ESTADÍSTICAS:")
    print(f"   Total CFDIs: {total_cfdis}")
    print(f"   Procesados: {stats['procesados']}")
    print(f"   Actualizados en BD: {stats['actualizados']}")
    print(f"   XMLs no encontrados: {stats['xml_no_encontrado']}")

    if args.verify_sat:
        print(f"\n   Verificados con SAT: {stats['verificados']}")
        print(f"   ├── Vigentes: {stats['vigentes']} ({stats['vigentes']/stats['verificados']*100:.1f}%)" if stats['verificados'] > 0 else "")
        print(f"   ├── Cancelados: {stats['cancelados']}")
        print(f"   └── No encontrados: {stats['no_encontrados']}")

    print(f"\n   Errores: {stats['errores']}")
    print(f"\n⏱️  Tiempo total: {elapsed_total/60:.1f} minutos")
    print(f"⚡ Velocidad promedio: {stats['procesados']/elapsed_total:.1f} CFDIs/seg")

    print("\n🎯 Siguiente paso:")
    print("   Consulta la BD para ver los datos actualizados:")
    print("   SELECT rfc_emisor, nombre_emisor, COUNT(*) FROM expense_invoices GROUP BY 1,2;")
    print()


if __name__ == '__main__':
    main()
