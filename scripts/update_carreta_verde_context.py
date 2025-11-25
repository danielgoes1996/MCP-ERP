#!/usr/bin/env python3
"""
Update Carreta Verde company context with business model and typical expenses.

This enables the AI classifier to understand that Carreta Verde is a honey
production/packaging business, so labels from GARIN ETIQUETAS should be
classified as packaging materials (115 Inventario or 502 Compras), NOT
office supplies (613.01 Papelería).
"""

import json
import psycopg2
from core.shared.db_config import POSTGRES_CONFIG

# Define Carreta Verde context
CARRETA_VERDE_CONTEXT = {
    "industry": "food_production",
    "industry_description": "Producción y comercialización de miel de abeja",
    "business_model": "production",
    "business_model_description": "Producción, envasado y distribución de miel",

    # Typical expenses for a honey production business
    "typical_expenses": [
        "raw_materials",  # Miel a granel
        "packaging_materials",  # Envases, etiquetas, tapas
        "utilities",  # Electricidad, agua
        "logistics",  # Transporte, distribución
        "administrative_services",  # Contabilidad, legal
    ],

    # Provider-specific treatments
    # This tells the AI how to classify invoices from specific providers
    "provider_treatments": {
        "GET130827SN7": "packaging_materials_labels"  # GARIN ETIQUETAS
    },

    # Classification preferences
    "preferences": {
        "detail_level": "high",  # Request detailed explanations from AI
        "auto_approve_threshold": 0.90  # Auto-approve at 90% confidence
    }
}

def main():
    print("=" * 80)
    print("UPDATE CARRETA VERDE COMPANY CONTEXT")
    print("=" * 80)

    conn = None
    try:
        # Connect to database
        print("\n1. Connecting to PostgreSQL...")
        conn = psycopg2.connect(**POSTGRES_CONFIG)
        cursor = conn.cursor()
        print("   ✓ Connected")

        # Update company settings
        print("\n2. Updating Carreta Verde company context...")
        settings_json = json.dumps(CARRETA_VERDE_CONTEXT)

        cursor.execute("""
            UPDATE companies
            SET settings = %s
            WHERE company_id = 'carreta_verde'
            RETURNING id, name, company_id
        """, (settings_json,))

        result = cursor.fetchone()

        if result:
            company_id, name, company_id_slug = result
            print(f"   ✓ Updated company: {name} (id={company_id}, slug={company_id_slug})")

            # Verify update
            cursor.execute("""
                SELECT settings
                FROM companies
                WHERE company_id = 'carreta_verde'
            """)

            row = cursor.fetchone()
            if row:
                settings = json.loads(row[0]) if row[0] else {}
                print("\n3. Verified configuration:")
                print(f"   - Industry: {settings.get('industry')} - {settings.get('industry_description')}")
                print(f"   - Business model: {settings.get('business_model')} - {settings.get('business_model_description')}")
                print(f"   - Typical expenses: {', '.join(settings.get('typical_expenses', []))}")
                print(f"   - Provider treatments:")
                for rfc, treatment in settings.get('provider_treatments', {}).items():
                    print(f"     • {rfc}: {treatment}")
                print(f"   - Preferences: {settings.get('preferences')}")
        else:
            print("   ✗ No company found with company_id='carreta_verde'")
            return

        # Commit changes
        conn.commit()
        print("\n✓ Company context updated successfully!")

        print("\n" + "=" * 80)
        print("NEXT STEPS:")
        print("=" * 80)
        print("1. The AI classifier will now inject this context into prompts")
        print("2. Labels from GARIN ETIQUETAS should classify as packaging materials")
        print("3. UsoCFDI=G03 contradictions will be detected and overridden")
        print("4. Test by reclassifying the GARIN ETIQUETAS invoice")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    main()
