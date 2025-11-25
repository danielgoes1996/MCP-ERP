"""
Classification Learning Module - Stores and retrieves validated classifications with embeddings.

This module implements a learning system that:
1. Stores human-validated classifications with semantic embeddings
2. Searches for similar past classifications using cosine similarity
3. Automatically applies learned patterns to avoid redundant LLM calls
4. Improves classification accuracy over time

The system uses pgvector for efficient similarity search and works in conjunction
with the classification_service to provide a hybrid approach:
- First check learning history (fast, cheap, accurate for known patterns)
- Then fall back to LLM (slower, expensive, but handles new cases)
"""

import logging
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from sentence_transformers import SentenceTransformer
from core.shared.db_config import get_connection

logger = logging.getLogger(__name__)

# Global model instance (loaded once on first use)
_embedding_model: Optional[SentenceTransformer] = None


def get_embedding_model() -> SentenceTransformer:
    """
    Get or initialize the embedding model (singleton pattern).

    Returns:
        SentenceTransformer model for generating 384-dim embeddings
    """
    global _embedding_model
    if _embedding_model is None:
        logger.info("Loading sentence transformer model: paraphrase-multilingual-MiniLM-L12-v2")
        _embedding_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        logger.info("Sentence transformer model loaded successfully")
    return _embedding_model


@dataclass
class LearnedClassification:
    """Result from learning history search."""
    sat_account_code: str
    sat_account_name: str
    family_code: Optional[str]
    confidence: float  # Based on cosine similarity
    source_emisor: str
    source_concepto: str
    validation_type: str  # 'human', 'auto', 'corrected'
    similarity_score: float  # Raw cosine similarity (0-1)


def generate_invoice_embedding(
    nombre_emisor: str,
    concepto: str
) -> np.ndarray:
    """
    Generate a 384-dimension embedding for an invoice.

    The embedding combines provider name and concept to capture the semantic
    meaning of the expense. Similar expenses will have similar embeddings.

    Args:
        nombre_emisor: Provider/vendor name
        concepto: Expense description/concept

    Returns:
        384-dimension numpy array
    """
    # Combine emisor + concepto for semantic representation
    text = f"{nombre_emisor} - {concepto}".strip()

    model = get_embedding_model()
    embedding = model.encode(text, convert_to_numpy=True)

    return embedding


def search_similar_classifications(
    company_id: int,
    tenant_id: int,
    nombre_emisor: str,
    concepto: str,
    top_k: int = 5,
    min_similarity: float = 0.85
) -> List[LearnedClassification]:
    """
    Search for similar past classifications using vector similarity.

    This function:
    1. Generates embedding for the invoice (emisor + concepto)
    2. Searches classification_learning_history using cosine similarity
    3. Returns top-K most similar validated classifications

    Args:
        company_id: Company ID to filter results
        tenant_id: Tenant ID to filter results
        nombre_emisor: Provider name
        concepto: Expense description
        top_k: Number of results to return (default: 5)
        min_similarity: Minimum cosine similarity threshold (default: 0.85)

    Returns:
        List of LearnedClassification objects, sorted by similarity (highest first)
    """
    try:
        # Generate embedding for this invoice
        query_embedding = generate_invoice_embedding(nombre_emisor, concepto)

        # Convert to PostgreSQL vector format
        embedding_str = f"[{','.join(str(x) for x in query_embedding)}]"

        conn = get_connection()
        cursor = conn.cursor()

        # Search using cosine distance (1 - cosine_similarity)
        # Lower distance = higher similarity
        # We use ORDER BY to get most similar first
        cursor.execute("""
            SELECT
                sat_account_code,
                sat_account_name,
                family_code,
                rfc_emisor,
                nombre_emisor,
                concepto,
                validation_type,
                1 - (embedding <=> %s::vector) as similarity
            FROM classification_learning_history
            WHERE company_id = %s
              AND tenant_id = %s
              AND embedding IS NOT NULL
              AND 1 - (embedding <=> %s::vector) >= %s
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """, (
            embedding_str,
            company_id,
            tenant_id,
            embedding_str,
            min_similarity,
            embedding_str,
            top_k
        ))

        results = []
        for row in cursor.fetchall():
            (code, name, family, rfc, emisor, concepto_src,
             validation_type, similarity) = row

            # Convert similarity to confidence (0.85-1.0 → 85-100%)
            confidence = similarity

            results.append(LearnedClassification(
                sat_account_code=code,
                sat_account_name=name,
                family_code=family,
                confidence=confidence,
                source_emisor=emisor,
                source_concepto=concepto_src,
                validation_type=validation_type,
                similarity_score=similarity
            ))

        cursor.close()
        conn.close()

        logger.info(
            f"Found {len(results)} similar classifications for '{nombre_emisor}' "
            f"with min_similarity={min_similarity}"
        )

        return results

    except Exception as e:
        logger.error(f"Error searching similar classifications: {e}", exc_info=True)
        return []


def save_validated_classification(
    company_id: int,
    tenant_id: int,
    session_id: str,
    rfc_emisor: str,
    nombre_emisor: str,
    concepto: str,
    total: float,
    uso_cfdi: str,
    sat_account_code: str,
    sat_account_name: str,
    family_code: Optional[str],
    validation_type: str,  # 'human', 'auto', 'corrected'
    validated_by: Optional[str] = None,
    original_llm_prediction: Optional[str] = None,
    original_llm_confidence: Optional[float] = None
) -> bool:
    """
    Save a validated classification to the learning history.

    This function:
    1. Generates embedding for emisor + concepto
    2. Stores classification with metadata
    3. Allows system to learn from corrections

    Args:
        company_id: Company ID
        tenant_id: Tenant ID
        session_id: Invoice session ID
        rfc_emisor: Provider RFC
        nombre_emisor: Provider name
        concepto: Expense description
        total: Invoice amount
        uso_cfdi: CFDI usage code
        sat_account_code: Validated SAT account code
        sat_account_name: SAT account name
        family_code: SAT family code (e.g., '610')
        validation_type: 'human' (user correction), 'auto' (high confidence), 'corrected' (LLM override)
        validated_by: User ID or system identifier
        original_llm_prediction: Original LLM prediction (if corrected)
        original_llm_confidence: Original LLM confidence (if corrected)

    Returns:
        True if saved successfully, False otherwise
    """
    try:
        # Generate embedding
        embedding = generate_invoice_embedding(nombre_emisor, concepto)
        embedding_str = f"[{','.join(str(x) for x in embedding)}]"

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO classification_learning_history (
                company_id,
                tenant_id,
                session_id,
                rfc_emisor,
                nombre_emisor,
                concepto,
                total,
                uso_cfdi,
                embedding,
                sat_account_code,
                sat_account_name,
                family_code,
                validation_type,
                validated_by,
                original_llm_prediction,
                original_llm_confidence
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s::vector,
                %s, %s, %s, %s, %s, %s, %s
            )
        """, (
            company_id,
            tenant_id,
            session_id,
            rfc_emisor,
            nombre_emisor,
            concepto,
            total,
            uso_cfdi,
            embedding_str,
            sat_account_code,
            sat_account_name,
            family_code,
            validation_type,
            validated_by,
            original_llm_prediction,
            original_llm_confidence
        ))

        conn.commit()
        cursor.close()
        conn.close()

        logger.info(
            f"Saved {validation_type} classification: '{nombre_emisor}' → "
            f"{sat_account_code} ({sat_account_name})"
        )

        return True

    except Exception as e:
        logger.error(f"Error saving validated classification: {e}", exc_info=True)
        return False


def get_auto_classification_from_history(
    company_id: int,
    tenant_id: int,
    nombre_emisor: str,
    concepto: str,
    min_confidence: float = 0.92
) -> Optional[LearnedClassification]:
    """
    Attempt to auto-classify based on learning history.

    This is the main entry point for the classification service.
    If we find a very similar past classification (similarity >= min_confidence),
    we can skip the LLM call entirely.

    Args:
        company_id: Company ID
        tenant_id: Tenant ID
        nombre_emisor: Provider name
        concepto: Expense description
        min_confidence: Minimum similarity to auto-apply (default: 0.92 = 92%)

    Returns:
        LearnedClassification if found with high confidence, None otherwise
    """
    results = search_similar_classifications(
        company_id=company_id,
        tenant_id=tenant_id,
        nombre_emisor=nombre_emisor,
        concepto=concepto,
        top_k=1,
        min_similarity=min_confidence
    )

    if results and len(results) > 0:
        best_match = results[0]
        logger.info(
            f"AUTO-APPLY from learning history: '{nombre_emisor}' → "
            f"{best_match.sat_account_code} (similarity: {best_match.similarity_score:.2%})"
        )
        return best_match

    logger.debug(
        f"No high-confidence match in learning history for '{nombre_emisor}' "
        f"(threshold: {min_confidence:.0%})"
    )
    return None


def get_learning_statistics(
    company_id: int,
    tenant_id: int
) -> Dict[str, Any]:
    """
    Get statistics about the learning history.

    Args:
        company_id: Company ID
        tenant_id: Tenant ID

    Returns:
        Dictionary with statistics:
        - total_validations: Total number of validated classifications
        - by_type: Breakdown by validation_type
        - top_providers: Most frequently learned providers
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Total validations
        cursor.execute("""
            SELECT COUNT(*) FROM classification_learning_history
            WHERE company_id = %s AND tenant_id = %s
        """, (company_id, tenant_id))
        total = cursor.fetchone()[0]

        # By validation type
        cursor.execute("""
            SELECT validation_type, COUNT(*)
            FROM classification_learning_history
            WHERE company_id = %s AND tenant_id = %s
            GROUP BY validation_type
        """, (company_id, tenant_id))
        by_type = dict(cursor.fetchall())

        # Top providers
        cursor.execute("""
            SELECT nombre_emisor, COUNT(*) as cnt
            FROM classification_learning_history
            WHERE company_id = %s AND tenant_id = %s
            GROUP BY nombre_emisor
            ORDER BY cnt DESC
            LIMIT 10
        """, (company_id, tenant_id))
        top_providers = cursor.fetchall()

        cursor.close()
        conn.close()

        return {
            'total_validations': total,
            'by_type': by_type,
            'top_providers': [(name, count) for name, count in top_providers]
        }

    except Exception as e:
        logger.error(f"Error getting learning statistics: {e}", exc_info=True)
        return {
            'total_validations': 0,
            'by_type': {},
            'top_providers': []
        }
