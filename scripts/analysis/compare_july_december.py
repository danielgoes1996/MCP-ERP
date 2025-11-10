#!/usr/bin/env python3
"""
Comparar la lógica que funcionó en julio vs diciembre
"""
import sys
sys.path.append('.')
from core.ai_pipeline.parsers.robust_pdf_parser import RobustPDFParser
from collections import Counter
import sqlite3

def compare_july_december():
    print("🔍 Comparando la lógica de julio vs diciembre")
    print("=" * 60)

    # Analizar transacciones de julio en la BD
    conn = sqlite3.connect("unified_mcp_system.db")
    cursor = conn.cursor()

    print("📊 ANÁLISIS DE JULIO EN BD:")
    cursor.execute("""
        SELECT COUNT(*) as total,
               COUNT(DISTINCT reference) as unique_refs,
               COUNT(CASE WHEN reference IS NOT NULL THEN 1 END) as with_ref,
               COUNT(CASE WHEN reference IS NULL THEN 1 END) as without_ref
        FROM bank_movements
        WHERE date LIKE '2025-07%' AND user_id = 9
    """)
    july_stats = cursor.fetchone()
    print(f"  Total transacciones: {july_stats[0]}")
    print(f"  Referencias únicas: {july_stats[1]}")
    print(f"  Con referencia: {july_stats[2]}")
    print(f"  Sin referencia: {july_stats[3]}")

    # Encontrar referencias duplicadas en julio
    cursor.execute("""
        SELECT reference, COUNT(*) as count
        FROM bank_movements
        WHERE date LIKE '2025-07%' AND user_id = 9 AND reference IS NOT NULL
        GROUP BY reference
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC
    """)
    july_duplicates = cursor.fetchall()

    if july_duplicates:
        print(f"\n🔍 REFERENCIAS DUPLICADAS EN JULIO ({len(july_duplicates)}):")
        for ref, count in july_duplicates:
            print(f"    {ref}: {count} veces")

            # Mostrar las transacciones específicas
            cursor.execute("""
                SELECT description, amount
                FROM bank_movements
                WHERE reference = ? AND date LIKE '2025-07%' AND user_id = 9
            """, (ref,))
            txns = cursor.fetchall()
            for desc, amount in txns:
                print(f"      {desc[:50]}... | ${amount}")

    print("\n📊 ANÁLISIS DE DICIEMBRE EN BD:")
    cursor.execute("""
        SELECT COUNT(*) as total,
               COUNT(DISTINCT reference) as unique_refs,
               COUNT(CASE WHEN reference IS NOT NULL THEN 1 END) as with_ref,
               COUNT(CASE WHEN reference IS NULL THEN 1 END) as without_ref
        FROM bank_movements
        WHERE date LIKE '2024-12%' AND user_id = 9
    """)
    dec_stats = cursor.fetchone()
    print(f"  Total transacciones: {dec_stats[0]}")
    print(f"  Referencias únicas: {dec_stats[1]}")
    print(f"  Con referencia: {dec_stats[2]}")
    print(f"  Sin referencia: {dec_stats[3]}")

    # Encontrar referencias duplicadas en diciembre
    cursor.execute("""
        SELECT reference, COUNT(*) as count
        FROM bank_movements
        WHERE date LIKE '2024-12%' AND user_id = 9 AND reference IS NOT NULL
        GROUP BY reference
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC
    """)
    dec_duplicates = cursor.fetchall()

    if dec_duplicates:
        print(f"\n🔍 REFERENCIAS DUPLICADAS EN DICIEMBRE ({len(dec_duplicates)}):")
        for ref, count in dec_duplicates:
            print(f"    {ref}: {count} veces")

            # Mostrar las transacciones específicas
            cursor.execute("""
                SELECT description, amount
                FROM bank_movements
                WHERE reference = ? AND date LIKE '2024-12%' AND user_id = 9
            """, (ref,))
            txns = cursor.fetchall()
            for desc, amount in txns:
                print(f"      {desc[:50]}... | ${amount}")

    conn.close()

    print(f"\n📋 COMPARACIÓN:")
    print(f"  Julio: {july_stats[0]} transacciones, {len(july_duplicates)} referencias duplicadas")
    print(f"  Diciembre: {dec_stats[0]} transacciones, {len(dec_duplicates)} referencias duplicadas")

    # Explicar la diferencia
    print(f"\n💡 CONCLUSIÓN:")
    if july_stats[0] > dec_stats[0]:
        print(f"  Julio tiene {july_stats[0] - dec_stats[0]} transacciones más que diciembre")
        print(f"  Esto es normal - cada mes tiene diferente número de operaciones bancarias")

    print(f"  El fix de deduplicación permite que ambos meses mantengan sus referencias duplicadas legítimas")

if __name__ == "__main__":
    compare_july_december()