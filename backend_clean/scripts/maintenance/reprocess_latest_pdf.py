#!/usr/bin/env python3
"""
Reprocesar el PDF más reciente (AMEX Gold) con LLM mejorado
Para obtener descripciones completas con RFC y información detallada
"""
import os
import sqlite3
from core.llm_pdf_parser import LLMPDFParser

def main():
    # PDF más reciente
    pdf_path = "./uploads/statements/9_20250928_000304_Periodo_JUL 2025 (1).pdf"

    if not os.path.exists(pdf_path):
        print(f"❌ PDF no encontrado: {pdf_path}")
        return

    print(f"🔄 Reprocesando PDF más reciente: {pdf_path}")
    print("📋 Este PDF contiene las transacciones de AMEX Gold con información completa")

    # Configurar parser LLM con API key
    api_key = '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'
    parser = LLMPDFParser(api_key=api_key)

    # Parámetros de la cuenta AMEX Gold
    account_id = 5  # AMEX Gold
    user_id = 9
    tenant_id = 3

    try:
        print("🤖 Iniciando procesamiento con LLM mejorado...")

        # Procesar PDF con LLM mejorado
        transactions, stats = parser.parse_bank_statement_with_llm(
            pdf_path, account_id, user_id, tenant_id
        )

        print(f"✅ Procesamiento completado!")
        print(f"📊 Transacciones encontradas: {len(transactions)}")
        print(f"📈 Estadísticas: {stats}")

        # Conectar a base de datos
        conn = sqlite3.connect('unified_mcp_system.db')
        cursor = conn.cursor()

        # Backup de transacciones existentes (opcional)
        print("💾 Creando respaldo de transacciones existentes...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bank_movements_backup_20250928 AS
            SELECT * FROM bank_movements
            WHERE account_id = ? AND user_id = ?
        """, (account_id, user_id))

        # Eliminar transacciones existentes de esta cuenta
        print("🗑️ Eliminando transacciones existentes...")
        cursor.execute("""
            DELETE FROM bank_movements
            WHERE account_id = ? AND user_id = ?
        """, (account_id, user_id))

        deleted_count = cursor.rowcount
        print(f"🗑️ Eliminadas {deleted_count} transacciones anteriores")

        # Insertar nuevas transacciones mejoradas
        print("💾 Insertando transacciones con descripciones mejoradas...")
        inserted_count = 0

        for txn in transactions:
            cursor.execute("""
                INSERT INTO bank_movements (
                    account_id, user_id, tenant_id, transaction_date,
                    description, amount, balance, category, movement_kind,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (
                account_id, user_id, tenant_id, txn.date,
                txn.description, txn.amount, getattr(txn, 'balance_after', None), txn.category,
                txn.movement_kind.value if txn.movement_kind else 'expense'
            ))
            inserted_count += 1

        conn.commit()
        print(f"✅ Insertadas {inserted_count} transacciones mejoradas")

        # Mostrar ejemplos de mejoras
        cursor.execute("""
            SELECT description, category, amount
            FROM bank_movements
            WHERE account_id = ? AND user_id = ?
            AND (description LIKE '%TELMEX%'
                 OR description LIKE '%OpenAI%'
                 OR description LIKE '%Office Depot%'
                 OR description LIKE '%TME840315KT6%')
            LIMIT 5
        """, (account_id, user_id))

        examples = cursor.fetchall()

        if examples:
            print("\n🎯 Ejemplos de descripciones mejoradas encontradas:")
            for desc, cat, amount in examples:
                print(f"  📝 {desc}")
                print(f"      Categoría: {cat} | Monto: ${amount}")
                print()
        else:
            print("\n📋 No se encontraron ejemplos específicos, pero todas las transacciones fueron reprocesadas con el LLM mejorado")

        # Estadísticas finales
        cursor.execute("""
            SELECT category, COUNT(*) as count
            FROM bank_movements
            WHERE account_id = ? AND user_id = ?
            GROUP BY category
            ORDER BY count DESC
        """, (account_id, user_id))

        categories = cursor.fetchall()
        print("📊 Distribución final de categorías:")
        for cat, count in categories:
            print(f"  {cat}: {count} transacciones")

        conn.close()
        print(f"\n🎉 ¡Reprocesamiento completado exitosamente!")
        print(f"🔍 Ahora tus transacciones tienen descripciones completas con RFC y detalles")

    except Exception as e:
        print(f"❌ Error durante el reprocesamiento: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()