#!/usr/bin/env python3
"""
Normalize ALL embeddings in the database.

The issue: Only 25 accounts had normalized embeddings after enrichment,
but the other ~1050 accounts have non-normalized embeddings, causing
incorrect cosine distance calculations in pgvector.

This script normalizes all existing embeddings without changing descriptions.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
from core.shared.db_config import get_connection

def normalize_all_embeddings():
    """Normalize all embeddings in sat_account_embeddings table."""

    conn = get_connection()
    cursor = conn.cursor()

    print("\n" + "="*100)
    print("🔧 NORMALIZING ALL EMBEDDINGS IN DATABASE")
    print("="*100)

    # Get all accounts with embeddings
    cursor.execute("""
        SELECT code, embedding
        FROM sat_account_embeddings
        WHERE embedding IS NOT NULL
    """)

    rows = cursor.fetchall()
    total = len(rows)

    print(f"\n📊 Found {total} accounts with embeddings\n")

    updated = 0
    skipped = 0

    for code, embedding in rows:
        # Convert to numpy array
        # Handle both list and string representations
        if isinstance(embedding, str):
            # Parse string representation: '[0.1,0.2,...]'
            import json
            emb_list = json.loads(embedding)
            emb_array = np.array(emb_list, dtype=np.float32)
        elif isinstance(embedding, list):
            emb_array = np.array(embedding, dtype=np.float32)
        else:
            print(f"   ⚠️  Unknown embedding type for {code}: {type(embedding)}")
            continue

        # Check if already normalized (norm ~= 1.0)
        norm = np.linalg.norm(emb_array)

        if abs(norm - 1.0) < 0.01:
            # Already normalized, skip
            skipped += 1
            if skipped % 100 == 0:
                print(f"   Skipped {skipped}/{total} (already normalized)...")
            continue

        # Normalize
        normalized = emb_array / norm

        # Update database
        try:
            cursor.execute("""
                UPDATE sat_account_embeddings
                SET embedding = %s
                WHERE code = %s
            """, (normalized.tolist(), code))

            updated += 1

            if updated % 100 == 0:
                print(f"   ✅ Normalized {updated}/{total} embeddings...")

        except Exception as e:
            print(f"   ❌ Error updating {code}: {e}")

    # Commit changes
    conn.commit()
    cursor.close()
    conn.close()

    print("\n" + "="*100)
    print("📊 RESUMEN")
    print("="*100)
    print(f"✅ Embeddings normalizados: {updated}")
    print(f"⏭️  Ya normalizados (skipped): {skipped}")
    print(f"📈 Total procesado: {total}")
    print("\n💡 Todos los embeddings ahora están normalizados para distancia coseno.\n")


if __name__ == '__main__':
    normalize_all_embeddings()
