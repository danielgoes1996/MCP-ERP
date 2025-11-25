"""
Script para guardar usando el JSON que ya extrajimos
"""

import os
import sys
import json
from datetime import datetime, date

sys.path.insert(0, os.path.dirname(__file__))

import psycopg2
from psycopg2.extras import RealDictCursor

# Configuración PostgreSQL
POSTGRES_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "127.0.0.1"),
    "port": int(os.getenv("POSTGRES_PORT", 5433)),
    "database": os.getenv("POSTGRES_DB", "mcp_system"),
    "user": os.getenv("POSTGRES_USER", "mcp_user"),
    "password": os.getenv("POSTGRES_PASSWORD", "changeme")
}

def main():
    print("\n" + "="*80)
    print("💾 GUARDANDO ESTADO DE CUENTA EN POSTGRESQL")
    print("="*80 + "\n")

    # Leer JSON que ya extrajimos
    with open("gemini_response.txt", "r") as f:
        response_text = f.read()

    # Limpiar markdown
    if "```json" in response_text:
        start = response_text.find("```json") + 7
        end = response_text.find("```", start)
        response_text = response_text[start:end].strip()

    # Parsear JSON
    data = json.loads(response_text)

    print("✅ JSON parseado exitosamente")
    print(f"   Banco: {data['bank_info']['bank_name']}")
    print(f"   Transacciones: {len(data['transactions'])}")

    # Conectar a PostgreSQL
    print("\n🔍 Conectando a PostgreSQL...")
    conn = psycopg2.connect(**POSTGRES_CONFIG)
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    print("✅ Conexión exitosa\n")

    # Configuración
    account_id = 1
    company_id = 2  # Usar company existente "Default Company"
    tenant_id = 2   # Usar tenant existente "Default Tenant"

    try:
        # PASO 0: Crear payment_account si no existe
        print("🏦 Verificando payment_account...")

        cursor.execute("SELECT id FROM payment_accounts WHERE id = %s", (account_id,))
        account_exists = cursor.fetchone()

        if not account_exists:
            print(f"   Cuenta {account_id} no existe, creándola...")

            cursor.execute("""
                INSERT INTO payment_accounts (
                    id, company_id, tenant_id,
                    account_name, bank_name, account_type,
                    status, currency,
                    created_at, updated_at
                ) VALUES (
                    %s, %s, %s,
                    %s, %s, %s,
                    'active', 'MXN',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """, (
                account_id, company_id, tenant_id,
                'Cuenta Inbursa Empresarial', 'Inbursa', 'checking'
            ))

            print(f"✅ Cuenta {account_id} creada")
        else:
            print(f"✅ Cuenta {account_id} ya existe")

        # PASO 1: Insertar bank_statement
        print("\n📋 Insertando statement...")

        bank_info = data['bank_info']
        summary = data['summary']

        # Calcular totales
        total_credits = sum(tx['amount'] for tx in data['transactions'] if tx['amount'] > 0)
        total_debits = abs(sum(tx['amount'] for tx in data['transactions'] if tx['amount'] < 0))

        cursor.execute("""
            INSERT INTO bank_statements (
                account_id, company_id, tenant_id,
                file_name, file_path, file_type,
                period_start, period_end,
                opening_balance, closing_balance,
                total_credits, total_debits,
                transaction_count,
                parsing_status,
                created_at, updated_at
            ) VALUES (
                %s, %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s,
                %s, %s,
                %s,
                %s,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            RETURNING id
        """, (
            account_id, company_id, tenant_id,
            'Periodo_ENE 2025.pdf', '~/Downloads/Periodo_ENE 2025.pdf', 'pdf',
            bank_info['period_start'], bank_info['period_end'],
            summary['opening_balance'], summary['closing_balance'],
            total_credits, total_debits,
            len(data['transactions']),
            'completed'
        ))

        statement_id = cursor.fetchone()['id']

        print(f"✅ Statement guardado con ID: {statement_id}")

        # PASO 2: Insertar transacciones
        print(f"\n📋 Insertando {len(data['transactions'])} transacciones...")

        for i, tx in enumerate(data['transactions'], 1):
            # Parsear fecha
            tx_date = datetime.strptime(tx['date'], '%Y-%m-%d').date()

            cursor.execute("""
                INSERT INTO bank_transactions (
                    statement_id, account_id, company_id, tenant_id,
                    transaction_date, description, amount,
                    transaction_type, balance, reference,
                    msi_candidate, msi_months, msi_confidence,
                    created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """, (
                statement_id, account_id, company_id, tenant_id,
                tx_date, tx['description'], tx['amount'],
                tx['type'], None, None,  # balance y reference no disponibles
                False, None, 0.0  # MSI detection viene después
            ))

            if i % 10 == 0:
                print(f"   Guardadas {i}/{len(data['transactions'])} transacciones...")

        print(f"✅ {len(data['transactions'])} transacciones guardadas")

        # Commit
        conn.commit()

        print("\n" + "="*80)
        print("✅ TODO GUARDADO EXITOSAMENTE")
        print("="*80 + "\n")

        # Verificar
        cursor.execute("""
            SELECT
                id, file_name, period_start, period_end,
                opening_balance, closing_balance,
                total_credits, total_debits,
                transaction_count
            FROM bank_statements
            WHERE id = %s
        """, (statement_id,))

        statement = cursor.fetchone()

        print("📋 STATEMENT GUARDADO:")
        print(f"   ID: {statement['id']}")
        print(f"   Archivo: {statement['file_name']}")
        print(f"   Período: {statement['period_start']} → {statement['period_end']}")
        print(f"   Saldo inicial: ${statement['opening_balance']:,.2f}")
        print(f"   Saldo final: ${statement['closing_balance']:,.2f}")
        print(f"   Total créditos: ${statement['total_credits']:,.2f}")
        print(f"   Total débitos: ${statement['total_debits']:,.2f}")
        print(f"   Transacciones: {statement['transaction_count']}")

        # Resumen por tipo
        cursor.execute("""
            SELECT
                transaction_type,
                COUNT(*) as count,
                SUM(amount) as total
            FROM bank_transactions
            WHERE statement_id = %s
            GROUP BY transaction_type
        """, (statement_id,))

        summary_db = cursor.fetchall()

        print(f"\n📊 TRANSACCIONES POR TIPO:")
        for row in summary_db:
            tipo_emoji = "💰" if row['transaction_type'] == 'credit' else "💸"
            print(f"   {tipo_emoji} {row['transaction_type'].title()}: {row['count']} transacciones (${abs(row['total']):,.2f})")

        # Primeras 5
        cursor.execute("""
            SELECT
                id, transaction_date, description, amount, transaction_type
            FROM bank_transactions
            WHERE statement_id = %s
            ORDER BY transaction_date, id
            LIMIT 5
        """, (statement_id,))

        txs = cursor.fetchall()

        print(f"\n📋 PRIMERAS 5 TRANSACCIONES:")
        for tx in txs:
            print(f"   {tx['id']}. {tx['transaction_date']} | ${tx['amount']:>10,.2f} | {tx['description'][:60]}")

        print(f"\n🎯 QUERIES PARA VERIFICAR:")
        print(f"   SELECT * FROM bank_statements WHERE id = {statement_id};")
        print(f"   SELECT * FROM bank_transactions WHERE statement_id = {statement_id} ORDER BY transaction_date;")
        print(f"   SELECT COUNT(*) FROM bank_transactions WHERE statement_id = {statement_id};")

    except Exception as e:
        conn.rollback()
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cursor.close()
        conn.close()

    print("\n")


if __name__ == "__main__":
    main()
