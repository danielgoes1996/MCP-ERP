"""
Script para guardar el estado de cuenta en PostgreSQL
"""

import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from core.ai_pipeline.ai_bank_orchestrator import get_ai_orchestrator

def main():
    print("\n" + "="*80)
    print("💾 GUARDANDO ESTADO DE CUENTA EN POSTGRESQL")
    print("="*80 + "\n")

    # Configuración
    pdf_path = os.path.expanduser("~/Downloads/Periodo_ENE 2025.pdf")

    # Datos de la cuenta (ajusta según tu configuración)
    account_id = 1        # ID de payment_accounts
    company_id = 1        # ID de tu empresa
    user_id = 1           # ID del usuario
    tenant_id = "pollenbeemx"  # Tu tenant

    print(f"📄 Archivo: {pdf_path}")
    print(f"🏢 Company: {company_id}")
    print(f"👤 User: {user_id}")
    print(f"🏦 Account: {account_id}")
    print(f"🏷️  Tenant: {tenant_id}")

    # Verificar conexión PostgreSQL
    print("\n🔍 Verificando conexión a PostgreSQL...")

    import psycopg2
    from psycopg2.extras import RealDictCursor

    POSTGRES_CONFIG = {
        "host": os.getenv("POSTGRES_HOST", "127.0.0.1"),
        "port": int(os.getenv("POSTGRES_PORT", 5433)),
        "database": os.getenv("POSTGRES_DB", "mcp_system"),
        "user": os.getenv("POSTGRES_USER", "mcp_user"),
        "password": os.getenv("POSTGRES_PASSWORD", "changeme")
    }

    try:
        conn = psycopg2.connect(**POSTGRES_CONFIG)
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Verificar que existen las tablas
        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name IN ('bank_statements', 'bank_transactions', 'payment_accounts')
        """)

        tables = [row['table_name'] for row in cursor.fetchall()]

        print(f"✅ Conexión exitosa a PostgreSQL")
        print(f"✅ Tablas encontradas: {', '.join(tables)}")

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"❌ Error conectando a PostgreSQL: {e}")
        print("\n⚠️  Asegúrate que PostgreSQL esté corriendo:")
        print("   docker ps | grep postgres")
        print("   o")
        print("   brew services list | grep postgres")
        return

    # Obtener orchestrator
    print("\n🤖 Iniciando AI Bank Orchestrator...")

    try:
        orchestrator = get_ai_orchestrator()

        # Procesar y guardar
        print("\n🚀 Procesando estado de cuenta con AI...\n")

        result = orchestrator.process_bank_statement(
            pdf_path=pdf_path,
            account_id=account_id,
            company_id=company_id,
            user_id=user_id,
            tenant_id=tenant_id
        )

        # Mostrar resultados
        print("\n" + "="*80)
        print("📊 RESULTADOS DEL GUARDADO")
        print("="*80 + "\n")

        if result.success:
            print("✅ GUARDADO EXITOSO\n")

            print("📋 STATEMENT GUARDADO:")
            print(f"   ID: {result.statement_id}")
            print(f"   Archivo: Periodo_ENE 2025.pdf")
            print(f"   Período: {result.statement_data.period_start} → {result.statement_data.period_end}")
            print(f"   Banco: {result.statement_data.bank_name}")
            print(f"   Tipo: {result.statement_data.account_type}")

            print(f"\n💰 SALDOS GUARDADOS:")
            print(f"   Saldo inicial: ${result.statement_data.opening_balance:,.2f}")
            print(f"   Saldo final:   ${result.statement_data.closing_balance:,.2f}")
            print(f"   Total créditos: ${result.statement_data.total_credits:,.2f}")
            print(f"   Total débitos:  ${result.statement_data.total_debits:,.2f}")

            print(f"\n📋 TRANSACCIONES GUARDADAS:")
            print(f"   Total: {result.transactions_created} registros")

            if result.msi_matches:
                print(f"\n💳 MSI DETECTADOS:")
                print(f"   Total: {len(result.msi_matches)} matches")
                for i, match in enumerate(result.msi_matches, 1):
                    print(f"   {i}. TX #{match.transaction_id} ↔ Invoice #{match.invoice_id}")
                    print(f"      {match.msi_months} meses × ${match.monthly_amount:,.2f} = ${match.total_amount:,.2f}")
                    print(f"      Confianza: {match.confidence:.2%}")

            print(f"\n⚙️  METADATA:")
            print(f"   Método: {result.metadata.get('parsing_method')}")
            print(f"   Modelo: {result.metadata.get('model')}")
            print(f"   Confianza: {result.metadata.get('confidence', 0):.2%}")
            print(f"   Tiempo: {result.processing_time_seconds:.2f}s")

            # Verificar en BD
            print("\n" + "="*80)
            print("🔍 VERIFICACIÓN EN BASE DE DATOS")
            print("="*80 + "\n")

            conn = psycopg2.connect(**POSTGRES_CONFIG)
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            # Ver statement
            cursor.execute("""
                SELECT
                    id, file_name, period_start, period_end,
                    opening_balance, closing_balance,
                    total_credits, total_debits,
                    transaction_count, ai_confidence
                FROM bank_statements
                WHERE id = %s
            """, (result.statement_id,))

            statement = cursor.fetchone()

            if statement:
                print("✅ Statement en BD:")
                print(f"   ID: {statement['id']}")
                print(f"   Archivo: {statement['file_name']}")
                print(f"   Saldos: ${statement['opening_balance']:,.2f} → ${statement['closing_balance']:,.2f}")
                print(f"   Transacciones: {statement['transaction_count']}")
                print(f"   Confianza: {statement['ai_confidence']:.2%}")

            # Contar transacciones
            cursor.execute("""
                SELECT
                    transaction_type,
                    COUNT(*) as count,
                    SUM(amount) as total
                FROM bank_transactions
                WHERE statement_id = %s
                GROUP BY transaction_type
            """, (result.statement_id,))

            summary = cursor.fetchall()

            print(f"\n✅ Transacciones en BD:")
            for row in summary:
                tipo_emoji = "💰" if row['transaction_type'] == 'credit' else "💸"
                print(f"   {tipo_emoji} {row['transaction_type'].title()}: {row['count']} transacciones (${abs(row['total']):,.2f})")

            # Primeras 5 transacciones
            cursor.execute("""
                SELECT
                    id, transaction_date, description, amount, transaction_type
                FROM bank_transactions
                WHERE statement_id = %s
                ORDER BY transaction_date, id
                LIMIT 5
            """, (result.statement_id,))

            transactions = cursor.fetchall()

            print(f"\n✅ Primeras 5 transacciones:")
            for tx in transactions:
                print(f"   {tx['id']}. {tx['transaction_date']} | ${tx['amount']:>10,.2f} | {tx['description'][:50]}")

            cursor.close()
            conn.close()

            print("\n" + "="*80)
            print("✅ TODO GUARDADO EXITOSAMENTE EN POSTGRESQL")
            print("="*80)

            print(f"\n🎯 SIGUIENTE PASO:")
            print(f"   Ver en BD:")
            print(f"   SELECT * FROM bank_statements WHERE id = {result.statement_id};")
            print(f"   SELECT * FROM bank_transactions WHERE statement_id = {result.statement_id};")

        else:
            print(f"❌ ERROR EN GUARDADO: {result.error}")
            print(f"\n⚠️  El sistema intentó usar fallback tradicional")

    except Exception as e:
        print(f"❌ Error en procesamiento: {e}")
        import traceback
        traceback.print_exc()

    print("\n")


if __name__ == "__main__":
    main()
