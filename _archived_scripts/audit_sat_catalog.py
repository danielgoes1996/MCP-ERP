#!/usr/bin/env python3
"""
Auditoría del catálogo SAT para identificar cuentas que necesitan enriquecimiento.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from core.shared.db_config import get_connection


def audit_catalog():
    """Audit SAT catalog descriptions."""

    conn = get_connection()
    cursor = conn.cursor()

    print("\n" + "="*100)
    print("📊 AUDITORÍA DEL CATÁLOGO SAT")
    print("="*100)

    # Count total accounts
    cursor.execute("SELECT COUNT(*) FROM sat_account_embeddings")
    total_accounts = cursor.fetchone()[0]

    print(f"\n📋 Total de cuentas: {total_accounts}")

    # Count by account type
    cursor.execute("""
        SELECT
            CASE
                WHEN LENGTH(code) = 3 THEN 'Familia'
                WHEN LENGTH(code) = 3 THEN 'Subfamilia'
                WHEN code ~ '^[0-9]{3}\\.[0-9]{2}$' THEN 'Cuenta específica'
                ELSE 'Otro'
            END as tipo,
            COUNT(*) as count
        FROM sat_account_embeddings
        GROUP BY tipo
        ORDER BY count DESC
    """)

    print("\n📊 Distribución por tipo:")
    for tipo, count in cursor.fetchall():
        print(f"   {tipo}: {count}")

    # Check description quality
    print("\n" + "="*100)
    print("📝 CALIDAD DE DESCRIPCIONES")
    print("="*100)

    # Accounts with no description or description == name
    cursor.execute("""
        SELECT COUNT(*)
        FROM sat_account_embeddings
        WHERE description IS NULL OR description = '' OR description = name
    """)
    no_desc = cursor.fetchone()[0]

    print(f"\n⚠️  Cuentas sin descripción única: {no_desc} ({no_desc/total_accounts*100:.1f}%)")

    # Accounts with good descriptions
    cursor.execute("""
        SELECT COUNT(*)
        FROM sat_account_embeddings
        WHERE description IS NOT NULL
          AND description != ''
          AND description != name
          AND LENGTH(description) > LENGTH(name)
    """)
    good_desc = cursor.fetchone()[0]

    print(f"✅ Cuentas con descripción enriquecida: {good_desc} ({good_desc/total_accounts*100:.1f}%)")

    # Sample accounts that need enrichment
    print("\n" + "="*100)
    print("🔍 MUESTRA DE CUENTAS QUE NECESITAN ENRIQUECIMIENTO")
    print("="*100)

    # Get specific accounts (XXX.XX) with no good description
    cursor.execute("""
        SELECT code, name, description
        FROM sat_account_embeddings
        WHERE code ~ '^[0-9]{3}\\.[0-9]{2}$'
          AND (description IS NULL OR description = '' OR description = name)
        ORDER BY code
        LIMIT 20
    """)

    print("\nPrimeras 20 cuentas específicas sin descripción:")
    for code, name, description in cursor.fetchall():
        print(f"   {code:<10} {name[:60]}")
        if description and description != name:
            print(f"              Desc: {description[:60]}")

    # Check families in our test invoices
    print("\n" + "="*100)
    print("🎯 FAMILIAS RELEVANTES PARA NUESTRAS FACTURAS DE PRUEBA")
    print("="*100)

    relevant_families = ['100', '600', '601', '602', '603', '115', '120', '164', '171']

    for family_code in relevant_families:
        cursor.execute("""
            SELECT code, name, description
            FROM sat_account_embeddings
            WHERE code LIKE %s
              AND code ~ '^[0-9]{3}\\.[0-9]{2}$'
            ORDER BY code
            LIMIT 5
        """, (f"{family_code[:3]}%",))

        results = cursor.fetchall()
        if results:
            print(f"\n📂 Familia {family_code}:")
            for code, name, description in results:
                has_desc = "✅" if (description and description != name and len(description) > len(name)) else "❌"
                print(f"   {has_desc} {code:<10} {name[:50]}")

    # Check which accounts are most commonly searched
    print("\n" + "="*100)
    print("🔥 ANÁLISIS DE USO (basado en clasificaciones anteriores)")
    print("="*100)

    # This would need classification_logs table, but for now just show structure
    cursor.execute("""
        SELECT code, name, description,
               LENGTH(description) as desc_length,
               LENGTH(name) as name_length
        FROM sat_account_embeddings
        WHERE code ~ '^[0-9]{3}\\.[0-9]{2}$'
        ORDER BY code
        LIMIT 10
    """)

    print("\nEstructura actual de primeras 10 cuentas:")
    print(f"{'Code':<10} {'Name Length':<15} {'Desc Length':<15} {'Has Enrichment'}")
    print("-" * 60)
    for code, name, description, desc_len, name_len in cursor.fetchall():
        has_enrichment = "✅" if (desc_len and desc_len > name_len) else "❌"
        print(f"{code:<10} {name_len:<15} {desc_len or 0:<15} {has_enrichment}")

    cursor.close()
    conn.close()

    print("\n" + "="*100)
    print("💡 RECOMENDACIONES")
    print("="*100)

    print(f"""
Prioridades de enriquecimiento:

1. 🎯 ALTA PRIORIDAD (Familias 600, 100):
   - Gastos de operación (600.XX)
   - Activos (100.XX)
   - Estas aparecen más frecuentemente en facturas

2. 🔍 ESTRATEGIA:
   - Agregar ejemplos concretos a descripciones (ej: "602.84 Fletes y acarreos: Transporte de mercancías, envíos, logística, almacenamiento, courier")
   - Incluir sinónimos y términos relacionados
   - Agregar contexto de industria cuando sea relevante

3. 📝 IMPLEMENTACIÓN:
   - Crear archivo YAML/JSON con descripciones enriquecidas
   - Script para actualizar base de datos
   - Regenerar embeddings después de actualización
    """)

    print("="*100 + "\n")


if __name__ == '__main__':
    audit_catalog()
