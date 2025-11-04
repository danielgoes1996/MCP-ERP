#!/usr/bin/env python3
"""
Identificar y agregar automáticamente las 8 transacciones faltantes
"""

import re
import sqlite3
from datetime import datetime
from core.robust_pdf_parser import RobustPDFParser

def extraer_transacciones_pdf():
    """Extrae todas las transacciones del PDF con detalles completos"""

    pdf_path = "./uploads/statements/9_20250928_000304_Periodo_JUL 2025 (1).pdf"

    parser = RobustPDFParser()
    texto = parser.extract_text(pdf_path)
    lineas = texto.split('\n')

    transacciones = []

    last_balance = None

    for i, linea in enumerate(lineas):
        linea_clean = linea.strip()
        if not linea_clean.startswith('JUL'):
            continue

        # Balance Inicial
        if 'BALANCE INICIAL' in linea_clean:
            match = re.match(r'JUL\.\s+(\d{1,2})\s+BALANCE INICIAL\s+([\d,]+\.\d{2})', linea_clean)
            if match:
                dia, saldo = match.groups()
                last_balance = float(saldo.replace(',', ''))
                transacciones.append({
                    'fecha': f"2025-07-{int(dia):02d}",
                    'referencia': 'BALANCE_INICIAL',
                    'descripcion': 'Balance Inicial - Saldo del Período Anterior',
                    'monto': 0.00,
                    'saldo': float(saldo.replace(',', '')),
                    'tipo': 'balance',
                    'linea_pdf': i+1,
                    'texto_original': linea_clean
                })
            continue

        # Transacciones normales
        # Patrón: JUL. DD REFERENCIA DESCRIPCION MONTO SALDO
        match = re.match(r'JUL\.\s+(\d{1,2})\s+(\S+)\s+(.+?)\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})', linea_clean)
        if match:
            dia, referencia, descripcion, monto_str, saldo_str = match.groups()

            saldo_actual = float(saldo_str.replace(',', ''))
            monto_original = float(monto_str.replace(',', ''))

            monto_final = None
            if last_balance is not None:
                diferencia = round(saldo_actual - last_balance, 2)
                if abs(diferencia) >= 0.01:
                    monto_final = diferencia

            if monto_final is None:
                # Fallback heurístico basado en descripción
                descripcion_upper = descripcion.upper()
                credit_keywords = ['DEPOSITO', 'INTERES', 'SPEI', 'TRANSFERENCIA RECIBIDA']
                if any(keyword in descripcion_upper for keyword in credit_keywords):
                    monto_final = monto_original
                else:
                    monto_final = -monto_original

            last_balance = saldo_actual

            transacciones.append({
                'fecha': f"2025-07-{int(dia):02d}",
                'referencia': referencia,
                'descripcion': descripcion.strip(),
                'monto': monto_final,
                'saldo': float(saldo_str.replace(',', '')),
                'tipo': 'transaccion',
                'linea_pdf': i+1,
                'texto_original': linea_clean
            })

    return transacciones

def obtener_transacciones_bd():
    """Obtiene todas las transacciones de la BD"""

    conn = sqlite3.connect('unified_mcp_system.db')
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, date, description, amount, balance_after, raw_data
        FROM bank_movements
        WHERE account_id = 5 AND user_id = 9
        ORDER BY date ASC, id ASC
    """)

    transacciones_bd = []
    for row in cursor.fetchall():
        transacciones_bd.append({
            'id': row[0],
            'fecha': row[1],
            'descripcion': row[2],
            'monto': row[3],
            'saldo': row[4],
            'raw_data': row[5]
        })

    conn.close()
    return transacciones_bd

def identificar_faltantes(transacciones_pdf, transacciones_bd):
    """Identifica cuáles transacciones del PDF no están en la BD"""

    print("🔍 IDENTIFICANDO TRANSACCIONES FALTANTES")
    print("=" * 50)

    # Crear conjunto de referencias de BD para comparación rápida
    referencias_bd = set()
    descripciones_bd = set()

    for txn_bd in transacciones_bd:
        # Extraer referencia del raw_data si existe
        raw_data = txn_bd.get('raw_data', '') or ''
        ref_match = re.search(r'\d{8,}', raw_data)
        if ref_match:
            referencias_bd.add(ref_match.group())

        # También agregar descripción normalizada
        desc_norm = txn_bd['descripcion'].lower().replace(' ', '')[:50]
        descripciones_bd.add(desc_norm)

    faltantes = []

    for txn_pdf in transacciones_pdf:
        encontrada = False

        # Buscar por referencia
        if txn_pdf['referencia'] != 'BALANCE_INICIAL':
            if txn_pdf['referencia'] in referencias_bd:
                encontrada = True
        else:
            # Para balance inicial, buscar por descripción
            if 'balance inicial' in descripciones_bd:
                encontrada = True

        # Si no encontrada por referencia, buscar por descripción similar
        if not encontrada:
            desc_pdf_norm = txn_pdf['descripcion'].lower().replace(' ', '')[:50]
            for desc_bd in descripciones_bd:
                if desc_pdf_norm in desc_bd or desc_bd in desc_pdf_norm:
                    if len(desc_pdf_norm) > 10:  # Solo si la descripción es significativa
                        encontrada = True
                        break

        if not encontrada:
            faltantes.append(txn_pdf)

    print(f"📊 Resultado:")
    print(f"   Transacciones en PDF: {len(transacciones_pdf)}")
    print(f"   Transacciones en BD: {len(transacciones_bd)}")
    print(f"   Faltantes identificadas: {len(faltantes)}")

    return faltantes

def agregar_transacciones_faltantes(faltantes):
    """Agrega las transacciones faltantes a la BD"""

    if not faltantes:
        print("✅ No hay transacciones que agregar")
        return

    print(f"\n🔧 AGREGANDO {len(faltantes)} TRANSACCIONES FALTANTES")
    print("=" * 55)

    conn = sqlite3.connect('unified_mcp_system.db')
    cursor = conn.cursor()

    agregadas = 0

    for i, txn in enumerate(faltantes):
        try:
            print(f"  {i+1}. {txn['fecha']} | {txn['descripcion'][:50]} | ${txn['monto']:8.2f}")

            # Determinar movement_kind
            if txn['tipo'] == 'balance':
                movement_kind = 'balance'
                transaction_type = 'credit'
            elif txn['monto'] > 0:
                movement_kind = 'ingreso'
                transaction_type = 'credit'
            else:
                movement_kind = 'gasto'
                transaction_type = 'debit'

            # Categorizar automáticamente
            categoria = categorizar_transaccion(txn['descripcion'])

            cursor.execute("""
                INSERT INTO bank_movements (
                    account_id, user_id, tenant_id, date, description, amount,
                    transaction_type, category, confidence, raw_data,
                    movement_kind, reference, balance_after, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                5,  # account_id
                9,  # user_id
                3,  # tenant_id
                txn['fecha'],
                txn['descripcion'],
                txn['monto'],
                transaction_type,
                categoria,
                0.95,  # high confidence
                f"PDF_LINE_{txn['linea_pdf']}: {txn['texto_original']}",
                movement_kind,
                txn['referencia'],
                txn['saldo'],
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))

            agregadas += 1

        except Exception as e:
            print(f"     ❌ Error agregando transacción: {e}")

    conn.commit()
    conn.close()

    print(f"\n✅ {agregadas} transacciones agregadas exitosamente")
    return agregadas

def categorizar_transaccion(descripcion):
    """Categoriza automáticamente la transacción"""
    desc_upper = descripcion.upper()

    if 'BALANCE INICIAL' in desc_upper:
        return 'Balance Inicial'
    elif 'DEPOSITO SPEI' in desc_upper:
        return 'Transferencias'
    elif 'OPENAI' in desc_upper or 'CHATGPT' in desc_upper:
        return 'Tecnología'
    elif 'APPLE' in desc_upper:
        return 'Tecnología'
    elif 'BUBBLE' in desc_upper:
        return 'Tecnología'
    elif 'STRIPE' in desc_upper:
        return 'Servicios en línea'
    elif 'DOMICILIACION' in desc_upper:
        return 'Servicios Públicos'
    elif 'COMISION' in desc_upper or 'IVA' in desc_upper:
        return 'Servicios Bancarios'
    elif 'INTERESES' in desc_upper:
        return 'Servicios Bancarios'
    else:
        return 'Otros'

def verificar_resultado(total_esperado: int):
    """Verifica que ahora tengamos todas las transacciones"""

    conn = sqlite3.connect('unified_mcp_system.db')
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*) FROM bank_movements
        WHERE account_id = 5 AND user_id = 9
    """)

    total_final = cursor.fetchone()[0]
    conn.close()

    print(f"\n🎯 VERIFICACIÓN FINAL:")
    print(f"   Total transacciones en BD: {total_final}")
    print(f"   Esperado del PDF: {total_esperado}")

    if total_final == total_esperado:
        print(f"   ✅ PERFECTO: Todas las transacciones están completas")
    elif total_final > total_esperado:
        print(f"   ⚠️ HAY {total_final - total_esperado} transacciones extra (posibles duplicados)")
    else:
        print(f"   ❌ AÚN FALTAN {total_esperado - total_final} transacciones")

def main():
    print("🎯 IDENTIFICAR Y AGREGAR TRANSACCIONES FALTANTES")
    print("=" * 60)

    # Extraer del PDF
    print("📄 Extrayendo transacciones del PDF...")
    transacciones_pdf = extraer_transacciones_pdf()
    print(f"   ✅ {len(transacciones_pdf)} transacciones extraídas")

    # Obtener de BD
    print("📊 Obteniendo transacciones de BD...")
    transacciones_bd = obtener_transacciones_bd()
    print(f"   ✅ {len(transacciones_bd)} transacciones en BD")

    # Identificar faltantes
    faltantes = identificar_faltantes(transacciones_pdf, transacciones_bd)

    if faltantes:
        print(f"\n📋 TRANSACCIONES FALTANTES IDENTIFICADAS:")
        for i, txn in enumerate(faltantes):
            print(f"  {i+1}. {txn['fecha']} | Ref: {txn['referencia']} | {txn['descripcion'][:50]} | ${txn['monto']:8.2f}")

        # Agregar automáticamente
        agregadas = agregar_transacciones_faltantes(faltantes)

        if agregadas > 0:
            # Verificar resultado
            verificar_resultado(len(transacciones_pdf))
    else:
        print("✅ No se encontraron transacciones faltantes")

if __name__ == "__main__":
    main()
