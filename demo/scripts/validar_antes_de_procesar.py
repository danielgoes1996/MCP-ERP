#!/usr/bin/env python3
"""
Script de validación que se debe ejecutar ANTES de procesar un nuevo estado de cuenta
Valida esquema de BD, conexión, y genera checklist de preparación

USO:
    python3 validar_antes_de_procesar.py
"""

import sys
sys.path.append('/Users/danielgoes96/Desktop/mcp-server')

from core.shared.db_config import (
    get_connection,
    validate_column_exists,
    get_table_columns,
    TABLE_SCHEMAS,
    POSTGRES_CONFIG
)


def validar_conexion():
    """Validar que la conexión a BD funciona"""
    print("1️⃣  VALIDANDO CONEXIÓN A BASE DE DATOS...")
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT version()")
        version = cursor.fetchone()[0]
        print(f"   ✅ Conexión exitosa")
        print(f"   📦 PostgreSQL: {version.split(',')[0]}")
        print(f"   🏠 Host: {POSTGRES_CONFIG['host']}:{POSTGRES_CONFIG['port']}")
        print(f"   💾 Database: {POSTGRES_CONFIG['database']}")
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"   ❌ Error de conexión: {e}")
        return False


def validar_esquema_tablas():
    """Validar que las tablas tienen las columnas esperadas"""
    print("\n2️⃣  VALIDANDO ESQUEMA DE TABLAS...")

    errores = []
    conn = get_connection()
    cursor = conn.cursor()

    for table, expected_columns in TABLE_SCHEMAS.items():
        print(f"\n   📋 Tabla: {table}")

        # Obtener columnas reales de la BD
        cursor.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = %s
            ORDER BY ordinal_position
        """, (table,))

        real_columns = {row[0]: row[1] for row in cursor.fetchall()}

        if not real_columns:
            print(f"      ❌ Tabla {table} NO EXISTE en la base de datos")
            errores.append(f"Tabla {table} no existe")
            continue

        # Validar columnas críticas
        columnas_criticas = {
            'expense_invoices': [
                'id', 'nombre_emisor', 'total', 'fecha_emision',
                'linked_expense_id', 'match_method', 'match_confidence'
            ],
            'bank_transactions': [
                'id', 'description', 'amount', 'transaction_date',
                'reconciled_invoice_id', 'match_confidence'
            ]
        }

        for col in columnas_criticas.get(table, []):
            if col in real_columns:
                print(f"      ✅ {col} ({real_columns[col]})")
            else:
                print(f"      ❌ {col} NO EXISTE")
                errores.append(f"{table}.{col} no existe")

    cursor.close()
    conn.close()

    if errores:
        print(f"\n   ❌ Se encontraron {len(errores)} errores:")
        for error in errores:
            print(f"      - {error}")
        return False
    else:
        print("\n   ✅ Todas las columnas críticas existen")
        return True


def validar_datos_mes(año: int, mes: int):
    """Validar datos existentes del mes"""
    print(f"\n3️⃣  VALIDANDO DATOS EXISTENTES - {mes:02d}/{año}...")

    conn = get_connection()
    cursor = conn.cursor()

    # CFDIs del mes
    cursor.execute("""
        SELECT
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE linked_expense_id IS NOT NULL) as conciliados,
            SUM(total) as monto_total
        FROM expense_invoices
        WHERE EXTRACT(YEAR FROM fecha_emision) = %s
        AND EXTRACT(MONTH FROM fecha_emision) = %s
        AND tipo_comprobante = 'I'
    """, (año, mes))

    cfdi_data = cursor.fetchone()
    total_cfdis, conciliados, monto_total = cfdi_data

    print(f"   📄 CFDIs encontrados: {total_cfdis or 0}")
    if total_cfdis:
        print(f"      ✓ Conciliados: {conciliados or 0} ({(conciliados or 0) / total_cfdis * 100:.1f}%)")
        print(f"      ✓ Pendientes: {(total_cfdis or 0) - (conciliados or 0)}")
        print(f"      💰 Monto total: ${monto_total or 0:,.2f}")

    # Transacciones bancarias del mes
    cursor.execute("""
        SELECT COUNT(*)
        FROM bank_transactions
        WHERE EXTRACT(YEAR FROM transaction_date) = %s
        AND EXTRACT(MONTH FROM transaction_date) = %s
    """, (año, mes))

    bank_count = cursor.fetchone()[0]
    print(f"   🏦 Transacciones bancarias: {bank_count or 0}")

    cursor.close()
    conn.close()

    return True


def generar_checklist():
    """Generar checklist de preparación"""
    print("\n4️⃣  CHECKLIST DE PREPARACIÓN:")
    print("""
   📝 Antes de procesar un nuevo estado de cuenta:

   [ ] 1. Validar que este script corre sin errores
   [ ] 2. Tener el archivo PDF del estado de cuenta listo
   [ ] 3. Verificar el mes/año del estado de cuenta
   [ ] 4. Decidir tipo: 'banco' o 'amex'
   [ ] 5. Si es banco: verificar que las transacciones se guardan en bank_transactions
   [ ] 6. Si es AMEX: las transacciones NO se guardan en BD (solo conciliación)
   [ ] 7. Hacer backup de la BD antes de procesar (opcional pero recomendado)

   🚀 Comando para procesar:

   # Banco:
   python3 procesar_estado_cuenta_generico.py --tipo banco --mes 2 --año 2025 --archivo "/path/to/estado.pdf"

   # AMEX:
   python3 procesar_estado_cuenta_generico.py --tipo amex --mes 2 --año 2025 --archivo "/path/to/amex.pdf"

   ⚠️  IMPORTANTE:
   - El script automáticamente truncará campos largos (match_method a 100 caracteres)
   - Usará linked_expense_id = -1 para pagos AMEX
   - Usará linked_expense_id > 0 para pagos banco
   - NO sobrescribirá conciliaciones existentes
    """)


def main():
    print("=" * 80)
    print("VALIDACIÓN PRE-PROCESAMIENTO DE ESTADO DE CUENTA")
    print("=" * 80)
    print()

    # Ejecutar validaciones
    check1 = validar_conexion()
    check2 = validar_esquema_tablas()

    # Validar mes actual (enero 2025 por defecto)
    validar_datos_mes(2025, 1)

    # Generar checklist
    generar_checklist()

    # Resultado final
    print("\n" + "=" * 80)
    if check1 and check2:
        print("✅ SISTEMA LISTO PARA PROCESAR NUEVOS ESTADOS DE CUENTA")
    else:
        print("❌ ENCONTRADOS ERRORES - CORREGIR ANTES DE PROCESAR")
    print("=" * 80)


if __name__ == "__main__":
    main()
