#!/usr/bin/env python3
"""
Revisar Estructura de Base de Datos
====================================
Analiza las tablas payment_accounts y bank_statements
para determinar dónde agregar clasificación de tipo de cuenta.
"""

import psycopg2
from psycopg2.extras import RealDictCursor

POSTGRES_CONFIG = {
    "host": "127.0.0.1",
    "port": 5433,
    "database": "mcp_system",
    "user": "mcp_user",
    "password": "changeme"
}

def main():
    conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
    cursor = conn.cursor()

    print("=" * 100)
    print("📊 REVISIÓN DE ESTRUCTURA DE BASE DE DATOS")
    print("=" * 100)

    # 1. Estructura de payment_accounts
    print("\n\n1️⃣  TABLA: payment_accounts")
    print("-" * 100)

    cursor.execute("""
        SELECT
            column_name,
            data_type,
            character_maximum_length,
            is_nullable,
            column_default
        FROM information_schema.columns
        WHERE table_name = 'payment_accounts'
        ORDER BY ordinal_position;
    """)

    columns = cursor.fetchall()

    print(f"\n{'Columna':<30} {'Tipo':<20} {'Nullable':<10} {'Default':<30}")
    print("-" * 100)
    for col in columns:
        col_name = col['column_name']
        data_type = col['data_type']
        if col['character_maximum_length']:
            data_type += f"({col['character_maximum_length']})"
        nullable = "YES" if col['is_nullable'] == 'YES' else "NO"
        default = str(col['column_default'] or '')[:30]
        print(f"{col_name:<30} {data_type:<20} {nullable:<10} {default:<30}")

    # 2. Datos de ejemplo de payment_accounts
    print("\n\n2️⃣  DATOS DE EJEMPLO: payment_accounts")
    print("-" * 100)

    cursor.execute("""
        SELECT id, account_name, bank_name, account_number, account_type,
               company_id, tenant_id, status
        FROM payment_accounts
        LIMIT 5;
    """)

    accounts = cursor.fetchall()

    if accounts:
        print(f"\n{'ID':<6} {'Nombre Cuenta':<30} {'Banco':<20} {'Tipo':<20} {'Status':<10}")
        print("-" * 100)
        for acc in accounts:
            print(f"{acc['id']:<6} {str(acc['account_name'])[:28]:<30} "
                  f"{str(acc['bank_name'] or 'N/A')[:18]:<20} "
                  f"{str(acc['account_type'] or 'N/A')[:18]:<20} "
                  f"{str(acc['status']):<10}")
    else:
        print("No hay cuentas registradas")

    # 3. Estructura de bank_statements
    print("\n\n3️⃣  TABLA: bank_statements")
    print("-" * 100)

    cursor.execute("""
        SELECT
            column_name,
            data_type,
            character_maximum_length,
            is_nullable,
            column_default
        FROM information_schema.columns
        WHERE table_name = 'bank_statements'
        ORDER BY ordinal_position;
    """)

    columns = cursor.fetchall()

    print(f"\n{'Columna':<30} {'Tipo':<20} {'Nullable':<10} {'Default':<30}")
    print("-" * 100)
    for col in columns:
        col_name = col['column_name']
        data_type = col['data_type']
        if col['character_maximum_length']:
            data_type += f"({col['character_maximum_length']})"
        nullable = "YES" if col['is_nullable'] == 'YES' else "NO"
        default = str(col['column_default'] or '')[:30]
        print(f"{col_name:<30} {data_type:<20} {nullable:<10} {default:<30}")

    # 4. Datos de ejemplo de bank_statements
    print("\n\n4️⃣  DATOS DE EJEMPLO: bank_statements")
    print("-" * 100)

    cursor.execute("""
        SELECT id, account_id, file_name, file_type, parsing_status,
               period_start, period_end, created_at
        FROM bank_statements
        ORDER BY created_at DESC
        LIMIT 5;
    """)

    statements = cursor.fetchall()

    if statements:
        print(f"\n{'ID':<6} {'Account ID':<12} {'Archivo':<40} {'Status':<15}")
        print("-" * 100)
        for stmt in statements:
            print(f"{stmt['id']:<6} {stmt['account_id']:<12} "
                  f"{str(stmt['file_name'])[:38]:<40} "
                  f"{stmt['parsing_status']:<15}")
    else:
        print("No hay estados de cuenta registrados")

    # 5. Relación entre bank_statements y payment_accounts
    print("\n\n5️⃣  RELACIÓN: bank_statements ↔ payment_accounts")
    print("-" * 100)

    cursor.execute("""
        SELECT
            bs.id as statement_id,
            bs.file_name,
            pa.id as account_id,
            pa.account_name,
            pa.bank_name
        FROM bank_statements bs
        JOIN payment_accounts pa ON bs.account_id = pa.id
        LIMIT 5;
    """)

    relations = cursor.fetchall()

    if relations:
        print(f"\n{'Statement ID':<15} {'Archivo':<30} {'Cuenta':<30} {'Banco':<20}")
        print("-" * 100)
        for rel in relations:
            print(f"{rel['statement_id']:<15} {str(rel['file_name'])[:28]:<30} "
                  f"{str(rel['account_name'])[:28]:<30} "
                  f"{str(rel['bank_name'] or 'N/A')[:18]:<20}")
    else:
        print("No hay relaciones encontradas")

    # 6. Verificar si existe campo account_type
    print("\n\n6️⃣  VERIFICACIÓN: ¿Existe campo 'account_type'?")
    print("-" * 100)

    cursor.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'payment_accounts'
        AND column_name LIKE '%type%';
    """)

    type_columns = cursor.fetchall()

    if type_columns:
        print("\n✅ Campos relacionados con 'type' encontrados:")
        for col in type_columns:
            print(f"   - {col['column_name']}")
    else:
        print("\n❌ NO existe campo 'account_type' o similar en payment_accounts")
        print("   → NECESARIO CREAR este campo para clasificar:")
        print("      • Tarjeta de Crédito (para detectar MSI)")
        print("      • Tarjeta de Débito (sin MSI)")
        print("      • Cuenta de Cheques (sin MSI)")

    # 7. Verificar bank_transactions
    print("\n\n7️⃣  TABLA: bank_transactions")
    print("-" * 100)

    cursor.execute("""
        SELECT
            column_name,
            data_type
        FROM information_schema.columns
        WHERE table_name = 'bank_transactions'
        ORDER BY ordinal_position;
    """)

    columns = cursor.fetchall()

    if columns:
        print(f"\n{'Columna':<30} {'Tipo':<20}")
        print("-" * 50)
        for col in columns:
            print(f"{col['column_name']:<30} {col['data_type']:<20}")
    else:
        print("Tabla bank_transactions no existe")

    print("\n\n" + "=" * 100)
    print("✅ REVISIÓN COMPLETA")
    print("=" * 100)

    conn.close()

if __name__ == "__main__":
    main()
