#!/usr/bin/env python3
"""
Find GARIN ETIQUETAS invoice for reclassification test.
"""

import sys
sys.path.insert(0, '/Users/danielgoes96/Desktop/mcp-server')

import psycopg2
from psycopg2.extras import RealDictCursor
from core.shared.db_config import POSTGRES_CONFIG
import json

def main():
    conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
    cursor = conn.cursor()

    # Buscar factura de GARIN ETIQUETAS
    cursor.execute('''
        SELECT
            id,
            file_name,
            status,
            parsed_data
        FROM sat_invoices
        WHERE company_id = 1  -- Carreta Verde
        AND parsed_data::text LIKE '%GET130827SN7%'  -- GARIN ETIQUETAS RFC
        ORDER BY created_at DESC
        LIMIT 1
    ''')

    session = cursor.fetchone()

    if session:
        parsed = json.loads(session['parsed_data']) if isinstance(session['parsed_data'], str) else session['parsed_data']
        emisor = parsed.get('emisor', {})
        conceptos = parsed.get('conceptos', [])
        concepto = conceptos[0] if conceptos else {}
        receptor = parsed.get('receptor', {})
        uso_cfdi = receptor.get('uso_cfdi') or parsed.get('uso_cfdi')

        print('=' * 100)
        print('FACTURA GARIN ETIQUETAS ENCONTRADA')
        print('=' * 100)
        print(f'Session ID: {session["id"]}')
        print(f'Archivo: {session["file_name"]}')
        print(f'\nPROVEEDOR: {emisor.get("nombre", "N/A")} (RFC: {emisor.get("rfc", "N/A")})')
        print(f'DESCRIPCIÓN: {concepto.get("descripcion", "N/A")}')
        print(f'TOTAL: ${parsed.get("total", 0):,.2f} MXN')
        print(f'CLAVE SAT: {concepto.get("clave_prod_serv", "N/A")}')
        print(f'UsoCFDI: {uso_cfdi or "N/A"}')
        print('=' * 100)
        print(f'\nPróximo paso: Reclasificar session_id={session["id"]} con el nuevo sistema')
        print('Ahora voy a subir una nueva factura de prueba con el mismo proveedor...')
        return session["id"]
    else:
        print('❌ No se encontró factura de GARIN ETIQUETAS en la base de datos.')
        print('Esto significa que necesitamos subir una factura de GARIN ETIQUETAS primero.')
        return None

    conn.close()

if __name__ == "__main__":
    main()
