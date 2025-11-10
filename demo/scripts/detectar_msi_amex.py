#!/usr/bin/env python3
"""
Script para detectar pagos con Meses Sin Intereses (MSI) en estado de cuenta AMEX
y manejar la conciliación de pagos diferidos correctamente

PROBLEMA:
- Un CFDI de $4,325 pagado a 6 MSI = $720.83/mes
- En enero solo se paga 1/6 del total
- No debemos marcar el CFDI como "pagado completo" hasta el último pago

SOLUCIÓN:
- Detectar MSI en descripción AMEX
- Crear tabla de pagos diferidos
- Conciliar parcialmente
"""

import os
import sys
import re
from datetime import datetime, timedelta
from decimal import Decimal

sys.path.append('/Users/danielgoes96/Desktop/mcp-server')
from core.shared.db_config import get_connection, POSTGRES_CONFIG

# Patrones de MSI en estados de cuenta AMEX
PATRONES_MSI = [
    r'(\d+)\s*MSI',                    # "6 MSI", "12 MSI"
    r'MESES?\s*SIN\s*INTERESES?',      # "MESES SIN INTERESES"
    r'(\d+)\s*MESE?S?',                # "6 MESES", "12 MESES"
    r'PLAN\s*(\d+)',                   # "PLAN 6", "PLAN 12"
    r'DIFERIDO\s*(\d+)',               # "DIFERIDO 6"
]


def crear_tabla_pagos_diferidos():
    """Crear tabla para rastrear pagos diferidos (MSI)"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS deferred_payments (
            id SERIAL PRIMARY KEY,
            cfdi_id INTEGER REFERENCES expense_invoices(id),
            payment_source VARCHAR(50),  -- 'AMEX', 'BBVA', etc
            total_amount NUMERIC(10,2),
            meses_sin_intereses INTEGER,
            pago_mensual NUMERIC(10,2),
            primer_pago_fecha DATE,
            ultimo_pago_fecha DATE,
            pagos_realizados INTEGER DEFAULT 0,
            monto_pagado NUMERIC(10,2) DEFAULT 0,
            status VARCHAR(20) DEFAULT 'activo',  -- 'activo', 'completado'
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    # Tabla de cuotas individuales
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS deferred_payment_installments (
            id SERIAL PRIMARY KEY,
            deferred_payment_id INTEGER REFERENCES deferred_payments(id),
            numero_cuota INTEGER,
            monto NUMERIC(10,2),
            fecha_programada DATE,
            fecha_pagada DATE,
            bank_tx_id INTEGER,
            pagado BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    conn.commit()
    cursor.close()
    conn.close()
    print("✅ Tablas de pagos diferidos creadas")


def detectar_msi_en_descripcion(descripcion: str) -> dict:
    """
    Detectar si una transacción tiene MSI

    Args:
        descripcion: Descripción de la transacción AMEX

    Returns:
        dict con 'tiene_msi' (bool) y 'meses' (int)
    """
    descripcion_upper = descripcion.upper()

    for patron in PATRONES_MSI:
        match = re.search(patron, descripcion_upper)
        if match:
            # Extraer número de meses
            meses = None
            if match.groups():
                meses = int(match.group(1))

            return {
                'tiene_msi': True,
                'meses': meses,
                'patron_detectado': patron
            }

    return {'tiene_msi': False, 'meses': None}


def registrar_pago_diferido(
    cfdi_id: int,
    payment_source: str,
    total_amount: float,
    meses: int,
    primer_pago_fecha: str
):
    """
    Registrar un pago diferido (MSI)

    Args:
        cfdi_id: ID del CFDI
        payment_source: Fuente de pago ('AMEX', etc)
        total_amount: Monto total del CFDI
        meses: Número de meses sin intereses
        primer_pago_fecha: Fecha del primer pago (YYYY-MM-DD)
    """
    conn = get_connection()
    cursor = conn.cursor()

    pago_mensual = Decimal(str(total_amount)) / Decimal(str(meses))
    primer_pago = datetime.strptime(primer_pago_fecha, '%Y-%m-%d')

    # Calcular fecha último pago
    ultimo_pago = primer_pago + timedelta(days=30 * (meses - 1))

    # Insertar registro principal
    cursor.execute("""
        INSERT INTO deferred_payments (
            cfdi_id, payment_source, total_amount, meses_sin_intereses,
            pago_mensual, primer_pago_fecha, ultimo_pago_fecha,
            pagos_realizados, monto_pagado
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, 1, %s)
        RETURNING id
    """, (
        cfdi_id,
        payment_source,
        total_amount,
        meses,
        float(pago_mensual),
        primer_pago,
        ultimo_pago,
        float(pago_mensual)  # Primera cuota ya pagada
    ))

    deferred_id = cursor.fetchone()[0]

    # Crear cuotas individuales
    for i in range(meses):
        numero_cuota = i + 1
        fecha_programada = primer_pago + timedelta(days=30 * i)
        pagado = (i == 0)  # Solo la primera está pagada

        cursor.execute("""
            INSERT INTO deferred_payment_installments (
                deferred_payment_id, numero_cuota, monto,
                fecha_programada, fecha_pagada, pagado
            ) VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            deferred_id,
            numero_cuota,
            float(pago_mensual),
            fecha_programada,
            primer_pago if pagado else None,
            pagado
        ))

    conn.commit()
    cursor.close()
    conn.close()

    print(f"✅ Pago diferido registrado:")
    print(f"   CFDI-{cfdi_id}: ${total_amount:,.2f} a {meses} MSI")
    print(f"   Pago mensual: ${float(pago_mensual):,.2f}")
    print(f"   Primer pago: {primer_pago_fecha}")
    print(f"   Último pago: {ultimo_pago.strftime('%Y-%m-%d')}")

    return deferred_id


def analizar_transacciones_amex_msi(transacciones: list):
    """
    Analizar transacciones AMEX y detectar cuáles tienen MSI

    Args:
        transacciones: Lista de transacciones del estado de cuenta AMEX
    """
    print("=" * 80)
    print("ANÁLISIS DE MESES SIN INTERESES (MSI)")
    print("=" * 80)
    print()

    tiene_msi = []
    sin_msi = []

    for tx in transacciones:
        resultado = detectar_msi_en_descripcion(tx['descripcion'])

        if resultado['tiene_msi']:
            tiene_msi.append({
                **tx,
                'meses': resultado['meses'],
                'patron': resultado['patron_detectado']
            })
        else:
            sin_msi.append(tx)

    print(f"📊 RESUMEN:")
    print(f"   Transacciones con MSI: {len(tiene_msi)}")
    print(f"   Transacciones sin MSI: {len(sin_msi)}")
    print()

    if tiene_msi:
        print("🔍 TRANSACCIONES CON MSI DETECTADAS:")
        print()
        for tx in tiene_msi:
            print(f"   {tx['fecha']} - {tx['descripcion']}")
            print(f"   Monto: ${tx['monto']:,.2f}")
            if tx['meses']:
                pago_mensual = tx['monto'] / tx['meses']
                print(f"   MSI: {tx['meses']} meses × ${pago_mensual:,.2f}")
            print()

    return tiene_msi, sin_msi


def conciliar_con_msi(cfdi_id: int, tx_amex: dict, meses_msi: int):
    """
    Conciliar un CFDI con pago AMEX a MSI

    Args:
        cfdi_id: ID del CFDI
        tx_amex: Transacción AMEX con MSI
        meses_msi: Número de meses sin intereses
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Obtener datos del CFDI
    cursor.execute("""
        SELECT id, nombre_emisor, total
        FROM expense_invoices
        WHERE id = %s
    """, (cfdi_id,))

    cfdi = cursor.fetchone()
    if not cfdi:
        print(f"❌ CFDI-{cfdi_id} no encontrado")
        return False

    cfdi_id, emisor, total = cfdi

    # Registrar pago diferido
    deferred_id = registrar_pago_diferido(
        cfdi_id,
        'AMEX',
        float(total),
        meses_msi,
        tx_amex['fecha']
    )

    # Actualizar CFDI con marca especial de pago diferido
    cursor.execute("""
        UPDATE expense_invoices
        SET
            linked_expense_id = %s,  -- Negativo = ID de deferred_payment
            match_confidence = 1.0,
            match_method = %s,
            match_date = NOW()
        WHERE id = %s
    """, (
        -1000 - deferred_id,  # -1001, -1002, etc (marca de diferido)
        f"AMEX MSI {meses_msi}M: {tx_amex['descripcion'][:50]}",
        cfdi_id
    ))

    conn.commit()
    cursor.close()
    conn.close()

    print(f"✅ CFDI-{cfdi_id} conciliado con pago diferido")
    return True


# Ejemplo de uso
if __name__ == "__main__":
    print("Creando tablas de pagos diferidos...")
    crear_tabla_pagos_diferidos()
    print()

    # Ejemplo: Transacciones AMEX de enero 2025
    transacciones_ejemplo = [
        {
            'fecha': '2025-01-23',
            'descripcion': 'TODOLLANTAS SUC CONSTI 6 MSI',
            'monto': 4325.00,
            'cfdi_match': 747
        },
        {
            'fecha': '2025-01-27',
            'descripcion': 'COPARMEX HAISO PLASTIC',
            'monto': 1653.00,
            'cfdi_match': 761
        },
        {
            'fecha': '2025-01-28',
            'descripcion': 'CLIFTON PACKAGING 3 MESES SIN INTERESES',
            'monto': 3992.67,
            'cfdi_match': 767
        },
    ]

    # Analizar
    con_msi, sin_msi = analizar_transacciones_amex_msi(transacciones_ejemplo)

    print()
    print("=" * 80)
    print("RECOMENDACIONES:")
    print("=" * 80)
    print()

    if con_msi:
        print("⚠️  ACCIÓN REQUERIDA:")
        print()
        print("Las siguientes transacciones tienen MSI.")
        print("Debes confirmar manualmente:")
        print()
        for tx in con_msi:
            print(f"1. {tx['descripcion']}")
            print(f"   ¿Cuántos meses? {tx['meses'] or '(no detectado)'}")
            print(f"   Comando para registrar:")
            if tx.get('cfdi_match'):
                meses = tx['meses'] or 6  # Default 6 si no detectó
                print(f"   >>> registrar_pago_diferido({tx['cfdi_match']}, 'AMEX', {tx['monto']}, {meses}, '{tx['fecha']}')")
            print()

    print("💡 NOTA:")
    print("   - MSI detectado automáticamente en descripción")
    print("   - Si no aparece 'MSI' en descripción, revisar estado de cuenta PDF")
    print("   - Verificar en sección 'Compras a Meses Sin Intereses'")
    print()
