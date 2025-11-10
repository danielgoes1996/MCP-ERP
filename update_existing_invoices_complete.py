#!/usr/bin/env python3
"""
Re-procesar las 209 facturas existentes para extraer TODOS los campos del XML

Este script:
1. Lee todas las facturas existentes en expense_invoices
2. Para cada una, lee el XML almacenado (raw_xml)
3. Extrae TODOS los campos faltantes
4. Actualiza la base de datos con los campos completos
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import xml.etree.ElementTree as ET
from datetime import datetime

POSTGRES_CONFIG = {
    "host": "127.0.0.1",
    "port": 5433,
    "database": "mcp_system",
    "user": "mcp_user",
    "password": "changeme"
}

print("=" * 100)
print("🔄 RE-PROCESANDO FACTURAS EXISTENTES - EXTRACCIÓN COMPLETA DE CAMPOS")
print("=" * 100 + "\n")

conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
cursor = conn.cursor()

# Obtener todas las facturas
cursor.execute("""
    SELECT
        id,
        filename,
        uuid,
        raw_xml,
        tipo_comprobante,
        forma_pago,
        metodo_pago,
        uso_cfdi,
        rfc_receptor,
        nombre_receptor,
        fecha_timbrado
    FROM expense_invoices
    WHERE raw_xml IS NOT NULL
    ORDER BY id;
""")

facturas = cursor.fetchall()
total_facturas = len(facturas)

print(f"📊 Total facturas a procesar: {total_facturas}\n")

# Namespaces CFDI
ns = {
    'cfdi': 'http://www.sat.gob.mx/cfd/4',
    'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital'
}

# Contadores
updated_count = 0
skipped_count = 0
errors = []

# Estadísticas de campos actualizados
stats = {
    'tipo_comprobante': 0,
    'forma_pago': 0,
    'metodo_pago': 0,
    'uso_cfdi': 0,
    'lugar_expedicion': 0,
    'rfc_receptor': 0,
    'nombre_receptor': 0,
    'fecha_timbrado': 0,
    'regimen_fiscal': 0
}

for idx, factura in enumerate(facturas, 1):
    if idx % 50 == 0:
        print(f"   Procesando {idx}/{total_facturas}...")

    try:
        # Parsear XML
        root = ET.fromstring(factura['raw_xml'])

        # Valores a actualizar
        updates = {}

        # 1. Tipo de Comprobante
        tipo_comprobante = root.get('TipoDeComprobante')
        if tipo_comprobante and tipo_comprobante != factura['tipo_comprobante']:
            updates['tipo_comprobante'] = tipo_comprobante
            stats['tipo_comprobante'] += 1

        # 2. Forma de Pago
        forma_pago = root.get('FormaPago')
        if forma_pago and forma_pago != factura['forma_pago']:
            updates['forma_pago'] = forma_pago
            stats['forma_pago'] += 1

        # 3. Método de Pago
        metodo_pago = root.get('MetodoPago')
        if metodo_pago and metodo_pago != factura['metodo_pago']:
            updates['metodo_pago'] = metodo_pago
            stats['metodo_pago'] += 1

        # 4. Lugar de Expedición
        lugar_expedicion = root.get('LugarExpedicion')
        if lugar_expedicion:
            updates['lugar_expedicion'] = lugar_expedicion
            stats['lugar_expedicion'] += 1

        # 5. Versión CFDI
        version_cfdi = root.get('Version')
        if version_cfdi:
            updates['version_cfdi'] = version_cfdi

        # 6. Emisor - Régimen Fiscal
        emisor = root.find('cfdi:Emisor', ns)
        if emisor is not None:
            regimen_fiscal = emisor.get('RegimenFiscal')
            if regimen_fiscal:
                updates['regimen_fiscal'] = regimen_fiscal
                stats['regimen_fiscal'] += 1

        # 7. Receptor - RFC, Nombre, Uso CFDI
        receptor = root.find('cfdi:Receptor', ns)
        if receptor is not None:
            rfc_receptor = receptor.get('Rfc')
            if rfc_receptor and rfc_receptor != factura['rfc_receptor']:
                updates['rfc_receptor'] = rfc_receptor
                stats['rfc_receptor'] += 1

            nombre_receptor = receptor.get('Nombre')
            if nombre_receptor and nombre_receptor != factura['nombre_receptor']:
                updates['nombre_receptor'] = nombre_receptor
                stats['nombre_receptor'] += 1

            uso_cfdi = receptor.get('UsoCFDI')
            if uso_cfdi and uso_cfdi != factura['uso_cfdi']:
                updates['uso_cfdi'] = uso_cfdi
                stats['uso_cfdi'] += 1

        # 8. Timbre Fiscal Digital - Fecha de Timbrado
        complemento = root.find('cfdi:Complemento', ns)
        if complemento is not None:
            timbre = complemento.find('tfd:TimbreFiscalDigital', ns)
            if timbre is not None:
                fecha_timbrado_str = timbre.get('FechaTimbrado')
                if fecha_timbrado_str and not factura['fecha_timbrado']:
                    try:
                        fecha_timbrado = datetime.fromisoformat(fecha_timbrado_str)
                        updates['fecha_timbrado'] = fecha_timbrado
                        stats['fecha_timbrado'] += 1
                    except:
                        pass

        # Ejecutar UPDATE si hay campos para actualizar
        if updates:
            # Construir query dinámico
            set_clause = ', '.join([f"{key} = %s" for key in updates.keys()])
            update_query = f"""
                UPDATE expense_invoices
                SET {set_clause}, updated_at = %s
                WHERE id = %s;
            """

            values = list(updates.values()) + [datetime.utcnow(), factura['id']]
            cursor.execute(update_query, values)

            updated_count += 1
        else:
            skipped_count += 1

    except Exception as e:
        errors.append(f"{factura['filename']}: {e}")
        print(f"   ⚠️  Error en {factura['filename']}: {e}")

# Commit changes
conn.commit()

print(f"\n{'=' * 100}")
print("✅ ACTUALIZACIÓN COMPLETADA")
print(f"{'=' * 100}\n")

print(f"📊 RESULTADOS:")
print(f"   Total facturas:        {total_facturas}")
print(f"   Actualizadas:          {updated_count}")
print(f"   Sin cambios:           {skipped_count}")
print(f"   Errores:               {len(errors)}")
print()

print(f"📋 CAMPOS ACTUALIZADOS:")
print(f"   tipo_comprobante:      {stats['tipo_comprobante']} facturas")
print(f"   forma_pago:            {stats['forma_pago']} facturas")
print(f"   metodo_pago:           {stats['metodo_pago']} facturas")
print(f"   uso_cfdi:              {stats['uso_cfdi']} facturas")
print(f"   lugar_expedicion:      {stats['lugar_expedicion']} facturas")
print(f"   rfc_receptor:          {stats['rfc_receptor']} facturas")
print(f"   nombre_receptor:       {stats['nombre_receptor']} facturas")
print(f"   fecha_timbrado:        {stats['fecha_timbrado']} facturas")
print(f"   regimen_fiscal:        {stats['regimen_fiscal']} facturas")
print()

# Verificar estado final
cursor.execute("""
    SELECT
        COUNT(*) as total,
        COUNT(tipo_comprobante) as con_tipo,
        COUNT(forma_pago) as con_forma_pago,
        COUNT(metodo_pago) as con_metodo_pago,
        COUNT(uso_cfdi) as con_uso_cfdi,
        COUNT(lugar_expedicion) as con_lugar_exp,
        COUNT(rfc_receptor) as con_rfc_receptor,
        COUNT(nombre_receptor) as con_nombre_receptor,
        COUNT(fecha_timbrado) as con_fecha_timbrado,
        COUNT(regimen_fiscal) as con_regimen_fiscal
    FROM expense_invoices;
""")

final_stats = cursor.fetchone()

print(f"{'=' * 100}")
print("📊 ESTADO FINAL DE LA BASE DE DATOS")
print(f"{'=' * 100}\n")

total = final_stats['total']
print(f"Total facturas: {total}\n")

print(f"Campo                  | Con datos      | %        | Faltantes")
print(f"{'─' * 100}")
print(f"tipo_comprobante       | {final_stats['con_tipo']:14} | {final_stats['con_tipo']/total*100:6.1f}% | {total - final_stats['con_tipo']}")
print(f"forma_pago             | {final_stats['con_forma_pago']:14} | {final_stats['con_forma_pago']/total*100:6.1f}% | {total - final_stats['con_forma_pago']}")
print(f"metodo_pago            | {final_stats['con_metodo_pago']:14} | {final_stats['con_metodo_pago']/total*100:6.1f}% | {total - final_stats['con_metodo_pago']}")
print(f"uso_cfdi               | {final_stats['con_uso_cfdi']:14} | {final_stats['con_uso_cfdi']/total*100:6.1f}% | {total - final_stats['con_uso_cfdi']}")
print(f"lugar_expedicion       | {final_stats['con_lugar_exp']:14} | {final_stats['con_lugar_exp']/total*100:6.1f}% | {total - final_stats['con_lugar_exp']}")
print(f"rfc_receptor           | {final_stats['con_rfc_receptor']:14} | {final_stats['con_rfc_receptor']/total*100:6.1f}% | {total - final_stats['con_rfc_receptor']}")
print(f"nombre_receptor        | {final_stats['con_nombre_receptor']:14} | {final_stats['con_nombre_receptor']/total*100:6.1f}% | {total - final_stats['con_nombre_receptor']}")
print(f"fecha_timbrado         | {final_stats['con_fecha_timbrado']:14} | {final_stats['con_fecha_timbrado']/total*100:6.1f}% | {total - final_stats['con_fecha_timbrado']}")
print(f"regimen_fiscal         | {final_stats['con_regimen_fiscal']:14} | {final_stats['con_regimen_fiscal']/total*100:6.1f}% | {total - final_stats['con_regimen_fiscal']}")

print(f"\n{'=' * 100}")

# Mostrar tipos de comprobante encontrados
cursor.execute("""
    SELECT
        tipo_comprobante,
        COUNT(*) as cantidad
    FROM expense_invoices
    GROUP BY tipo_comprobante
    ORDER BY cantidad DESC;
""")

tipos = cursor.fetchall()

print("📋 TIPOS DE COMPROBANTE EN BD:")
print(f"{'=' * 100}\n")

tipos_cfdi = {
    'I': 'Ingreso (Factura)',
    'E': 'Egreso (Nota de Crédito)',
    'P': 'Pago (Complemento)',
    'T': 'Traslado',
    'N': 'Nómina'
}

for row in tipos:
    tipo = row['tipo_comprobante'] or 'NULL'
    tipo_desc = tipos_cfdi.get(tipo, 'Desconocido')
    cantidad = row['cantidad']
    print(f"   {tipo} - {tipo_desc:30}: {cantidad} facturas")

if errors:
    print(f"\n⚠️  ERRORES ENCONTRADOS ({len(errors)}):")
    for error in errors[:10]:
        print(f"   {error}")
    if len(errors) > 10:
        print(f"   ... y {len(errors) - 10} errores más")

conn.close()

print(f"\n{'=' * 100}")
print("🎉 PROCESO COMPLETADO")
print(f"{'=' * 100}")
