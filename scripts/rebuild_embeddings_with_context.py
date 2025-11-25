#!/usr/bin/env python3
"""
Regenerate SAT account embeddings WITH Claude context enrichment.

This script:
1. Reads SAT accounts from PostgreSQL (sat_account_embeddings table)
2. Loads cached Claude context from sat_account_context.json
3. Generates embeddings using SentenceTransformer with enriched text
4. Updates embeddings in PostgreSQL

Usage:
    python3 scripts/rebuild_embeddings_with_context.py
"""

import sys
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import psycopg2
from psycopg2.extras import execute_batch
from sentence_transformers import SentenceTransformer

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.shared.db_config import POSTGRES_CONFIG

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

CONTEXT_CACHE_PATH = Path("data/embeddings/sat_account_context.json")
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def load_context_cache() -> Dict[str, Dict]:
    """Load Claude-generated context from cache."""
    if not CONTEXT_CACHE_PATH.exists():
        logger.warning(f"Context cache not found at {CONTEXT_CACHE_PATH}")
        return {}
    
    with open(CONTEXT_CACHE_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    logger.info(f"Loaded context for {len(data)} accounts from cache")
    return data


def build_enriched_text(code: str, name: str, description: str, context: Optional[str]) -> str:
    """
    Build enriched text for embedding generation.
    
    Similar to how queries are enriched in _build_embeddings_payload().
    """
    parts = []
    
    # 1. Code and name (always include)
    parts.append(f"{code} {name}")
    
    # 2. Description (if available)
    if description and description.strip():
        parts.append(description.strip())
    
    # 3. Claude context (if available) - THIS IS THE KEY ENRICHMENT
    if context and context.strip():
        parts.append(context.strip())
    
    return " | ".join(parts)


def fetch_accounts_from_db() -> List[tuple]:
    """Fetch all accounts from PostgreSQL."""
    conn = psycopg2.connect(**POSTGRES_CONFIG)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT code, name, COALESCE(description, '') as description
        FROM sat_account_embeddings
        ORDER BY code
    """)
    
    accounts = cursor.fetchall()
    cursor.close()
    conn.close()
    
    logger.info(f"Loaded {len(accounts)} accounts from PostgreSQL")
    return accounts


def generate_embeddings_batch(
    model: SentenceTransformer,
    accounts: List[tuple],
    context_cache: Dict
) -> List[tuple]:
    """
    Generate embeddings for all accounts with context enrichment.
    
    Returns: List of (code, embedding_vector) tuples
    """
    enriched_texts = []
    codes = []
    
    for code, name, description in accounts:
        # Get Claude context if available
        context_entry = context_cache.get(code, {})
        context = context_entry.get('context', '')
        
        # Build enriched text
        enriched_text = build_enriched_text(code, name, description, context)
        enriched_texts.append(enriched_text)
        codes.append(code)
    
    # Log sample
    logger.info(f"Sample enriched text for {codes[0]}:")
    logger.info(f"  {enriched_texts[0][:200]}...")
    
    # Generate embeddings
    logger.info(f"Encoding {len(enriched_texts)} texts with {MODEL_NAME}...")
    embeddings = model.encode(
        enriched_texts,
        convert_to_numpy=True,
        normalize_embeddings=True,  # IMPORTANT: normalize for cosine similarity
        show_progress_bar=True,
        batch_size=64
    )
    
    logger.info(f"Generated {len(embeddings)} embeddings of shape {embeddings.shape}")
    
    # Verify normalization
    norms = np.linalg.norm(embeddings, axis=1)
    logger.info(f"Embedding norms: mean={norms.mean():.4f}, std={norms.std():.4f}")
    
    return list(zip(codes, embeddings))


def update_embeddings_in_db(embeddings_data: List[tuple]) -> None:
    """Update embeddings in PostgreSQL."""
    conn = psycopg2.connect(**POSTGRES_CONFIG)
    cursor = conn.cursor()
    
    logger.info(f"Updating {len(embeddings_data)} embeddings in database...")
    
    # Prepare batch update data
    update_data = []
    for code, embedding in embeddings_data:
        # Convert numpy array to pgvector format
        vector_str = "[" + ",".join(f"{val:.6f}" for val in embedding) + "]"
        update_data.append((vector_str, code))
    
    # Batch update
    execute_batch(
        cursor,
        """
        UPDATE sat_account_embeddings
        SET embedding = %s::vector
        WHERE code = %s
        """,
        update_data,
        page_size=100
    )
    
    conn.commit()
    logger.info(f"✅ Updated {cursor.rowcount} embeddings")
    
    cursor.close()
    conn.close()


def main():
    print("=" * 100)
    print("REGENERATING SAT ACCOUNT EMBEDDINGS WITH CONTEXT ENRICHMENT")
    print("=" * 100)
    print()
    
    # 1. Load context cache
    context_cache = load_context_cache()
    
    # 2. Fetch accounts from database
    accounts = fetch_accounts_from_db()
    
    # 3. Load SentenceTransformer model
    logger.info(f"Loading model: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)
    
    # 4. Generate embeddings with enrichment
    embeddings_data = generate_embeddings_batch(model, accounts, context_cache)
    
    # 5. Update database
    update_embeddings_in_db(embeddings_data)
    
    print()
    print("=" * 100)
    print("✅ EMBEDDINGS REGENERATED SUCCESSFULLY")
    print("=" * 100)
    print()
    print("Next steps:")
    print("  1. Run test_3_invoices.py to validate classification")
    print("  2. Check that combustibles accounts now appear in top results")
    print()


if __name__ == "__main__":
    main()
