#!/usr/bin/env python3
"""
Aplicar descripciones enriquecidas al catálogo SAT y regenerar embeddings.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import yaml
from sentence_transformers import SentenceTransformer
from core.shared.db_config import get_connection


def load_enriched_descriptions(yaml_path: str) -> dict:
    """Load enriched descriptions from YAML file."""
    with open(yaml_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    return data


def apply_descriptions(descriptions: dict):
    """Apply enriched descriptions to database and regenerate embeddings."""

    conn = get_connection()
    cursor = conn.cursor()

    # Load embedding model
    print("\n🤖 Cargando modelo de embeddings...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    print("✅ Modelo cargado\n")

    print("="*100)
    print("📝 APLICANDO DESCRIPCIONES ENRIQUECIDAS")
    print("="*100)

    updated_count = 0
    failed_count = 0

    for code, data in descriptions.items():
        if not isinstance(data, dict) or 'description' not in data:
            continue

        enriched_desc = data['description']

        # Check if account exists
        cursor.execute(
            "SELECT name FROM sat_account_embeddings WHERE code = %s",
            (code,)
        )
        result = cursor.fetchone()

        if not result:
            print(f"⚠️  Cuenta {code} no existe en la base de datos")
            failed_count += 1
            continue

        account_name = result[0]

        # Generate new embedding for enriched description
        # Combine name + enriched description for better context
        full_text = f"{account_name}. {enriched_desc}"
        # IMPORTANT: normalize_embeddings=True to match metadata and enable cosine similarity
        embedding = model.encode(full_text, normalize_embeddings=True)

        # Update database
        try:
            cursor.execute(
                """
                UPDATE sat_account_embeddings
                SET description = %s,
                    embedding = %s
                WHERE code = %s
                """,
                (enriched_desc, embedding.tolist(), code)
            )

            updated_count += 1
            print(f"✅ {code:<10} {account_name[:50]}")
            print(f"   Descripción: {enriched_desc[:80]}...")

        except Exception as e:
            print(f"❌ Error actualizando {code}: {e}")
            failed_count += 1

    # Commit changes
    conn.commit()
    cursor.close()
    conn.close()

    print("\n" + "="*100)
    print("📊 RESUMEN")
    print("="*100)
    print(f"✅ Cuentas actualizadas: {updated_count}")
    print(f"❌ Errores: {failed_count}")
    print(f"📈 Total procesado: {updated_count + failed_count}")

    print("\n💡 Las descripciones han sido aplicadas y los embeddings regenerados.")
    print("   Ahora las búsquedas deberían tener mucho mejor precisión semántica.\n")


def main():
    print("\n" + "="*100)
    print("🔧 ENRIQUECIMIENTO DEL CATÁLOGO SAT")
    print("="*100)

    yaml_path = '/Users/danielgoes96/Desktop/mcp-server/data/sat_enriched_descriptions.yaml'

    print(f"\n📂 Cargando descripciones desde: {yaml_path}")

    try:
        descriptions = load_enriched_descriptions(yaml_path)
        print(f"✅ Cargadas {len(descriptions)} descripciones enriquecidas\n")

        apply_descriptions(descriptions)

    except FileNotFoundError:
        print(f"❌ Error: No se encontró el archivo {yaml_path}")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
