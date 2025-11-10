"""
Embedding-based Matcher for Bank Reconciliation

Uses local sentence transformers to find semantic similarity between
transaction descriptions and invoice names.

Advantages over LLM approach:
- 100x faster (milliseconds vs seconds)
- 100x cheaper (free vs API costs)
- Deterministic (same input = same output)
- Scalable (handles millions of transactions)
- Private (no data leaves the server)
"""

import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


@dataclass
class EmbeddingMatch:
    """Result of embedding-based matching"""
    transaction_id: int
    invoice_id: int
    transaction_description: str
    invoice_name: str
    similarity_score: float  # 0.0 - 1.0
    confidence: str  # "high", "medium", "low"
    amount_diff: float
    days_diff: int


class EmbeddingMatcher:
    """
    Fast semantic matching using sentence embeddings
    """

    def __init__(self, model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"):
        """
        Initialize the matcher with a pre-trained model

        Args:
            model_name: Sentence transformer model to use
                       Default is multilingual model that works great for Spanish
        """
        print(f"🔧 Loading embedding model: {model_name}")
        self.model = SentenceTransformer(model_name)
        print(f"✅ Model loaded successfully")

        # Cache for embeddings
        self._tx_embeddings = {}
        self._invoice_embeddings = {}

    def _normalize_text(self, text: str) -> str:
        """
        Normalize text for better matching

        Args:
            text: Input text

        Returns:
            Normalized text
        """
        # Convert to uppercase
        text = text.upper()

        # Remove common payment processors that add noise
        noise_words = [
            "STRIPE *", "STR*", "PAYPAL*", "APPLE.COM/BILL",
            ".COM", "WWW.", "MX", "US", "ECOM"
        ]

        for noise in noise_words:
            text = text.replace(noise, " ")

        # Remove extra whitespace
        text = " ".join(text.split())

        return text

    def _get_embedding(self, text: str, cache: dict, key: any) -> np.ndarray:
        """
        Get embedding for text with caching

        Args:
            text: Text to embed
            cache: Cache dictionary
            key: Cache key

        Returns:
            Embedding vector
        """
        if key not in cache:
            normalized = self._normalize_text(text)
            cache[key] = self.model.encode([normalized])[0]

        return cache[key]

    def match_batch(
        self,
        transactions: List[Dict],
        invoices: List[Dict],
        min_similarity: float = 0.7,
        max_amount_diff: float = 50.0,
        max_days_diff: int = 10
    ) -> List[EmbeddingMatch]:
        """
        Find matches using semantic similarity

        Args:
            transactions: List of {id, description, amount, date}
            invoices: List of {id, nombre_emisor, total, fecha}
            min_similarity: Minimum cosine similarity (0.7 = 70%)
            max_amount_diff: Maximum amount difference in pesos
            max_days_diff: Maximum days difference

        Returns:
            List of EmbeddingMatch objects
        """
        if not transactions or not invoices:
            return []

        print(f"\n🔍 Matching {len(transactions)} transactions vs {len(invoices)} invoices...")

        # Generate embeddings for all transactions
        tx_embeddings = []
        for tx in transactions:
            emb = self._get_embedding(tx["description"], self._tx_embeddings, tx["id"])
            tx_embeddings.append(emb)

        # Generate embeddings for all invoices
        inv_embeddings = []
        for inv in invoices:
            emb = self._get_embedding(inv["nombre_emisor"], self._invoice_embeddings, inv["id"])
            inv_embeddings.append(emb)

        # Convert to numpy arrays
        tx_embeddings = np.array(tx_embeddings)
        inv_embeddings = np.array(inv_embeddings)

        # Calculate cosine similarity matrix
        # Shape: (num_transactions, num_invoices)
        similarity_matrix = cosine_similarity(tx_embeddings, inv_embeddings)

        matches = []

        # For each transaction, find best matching invoice
        for tx_idx, tx in enumerate(transactions):
            # Get similarities for this transaction
            similarities = similarity_matrix[tx_idx]

            # Find best match
            best_inv_idx = np.argmax(similarities)
            best_similarity = similarities[best_inv_idx]

            # Check if similarity is above threshold
            if best_similarity < min_similarity:
                continue

            inv = invoices[best_inv_idx]

            # Calculate amount and date differences
            from datetime import datetime

            amount_diff = abs(abs(float(tx["amount"])) - float(inv["total"]))

            tx_date = datetime.strptime(str(tx["date"]), "%Y-%m-%d").date()
            inv_date = datetime.strptime(str(inv["fecha"]), "%Y-%m-%d").date()
            days_diff = abs((tx_date - inv_date).days)

            # Check constraints
            if amount_diff > max_amount_diff:
                continue

            if days_diff > max_days_diff:
                continue

            # Determine confidence level
            confidence = self._calculate_confidence(
                best_similarity, amount_diff, days_diff
            )

            matches.append(EmbeddingMatch(
                transaction_id=tx["id"],
                invoice_id=inv["id"],
                transaction_description=tx["description"],
                invoice_name=inv["nombre_emisor"],
                similarity_score=best_similarity,
                confidence=confidence,
                amount_diff=amount_diff,
                days_diff=days_diff
            ))

        # Sort by similarity score (best first)
        matches.sort(key=lambda m: m.similarity_score, reverse=True)

        print(f"✅ Found {len(matches)} matches")

        return matches

    def _calculate_confidence(
        self,
        similarity: float,
        amount_diff: float,
        days_diff: int
    ) -> str:
        """
        Calculate confidence level based on similarity and differences

        Args:
            similarity: Cosine similarity (0-1)
            amount_diff: Amount difference in pesos
            days_diff: Days difference

        Returns:
            Confidence level: "high", "medium", or "low"
        """
        # High confidence: very similar text, small differences
        if similarity >= 0.85 and amount_diff <= 5 and days_diff <= 2:
            return "high"

        # Medium confidence: similar text, acceptable differences
        if similarity >= 0.75 and amount_diff <= 20 and days_diff <= 5:
            return "medium"

        # Low confidence: moderate similarity
        return "low"

    def clear_cache(self):
        """Clear embedding cache"""
        self._tx_embeddings.clear()
        self._invoice_embeddings.clear()
        print("🗑️  Embedding cache cleared")


def get_embedding_matcher() -> EmbeddingMatcher:
    """
    Factory function to get the matcher

    Returns:
        Initialized EmbeddingMatcher
    """
    return EmbeddingMatcher()


# Example usage
if __name__ == "__main__":
    # Test with sample data
    matcher = EmbeddingMatcher()

    transactions = [
        {
            "id": 1,
            "description": "STRIPE *ODOO TECHNOLOG MX",
            "amount": -535.92,
            "date": "2025-01-11"
        },
        {
            "id": 2,
            "description": "GO GASOLINERO BERISA MX",
            "amount": -1250.00,
            "date": "2025-01-16"
        },
        {
            "id": 3,
            "description": "DISTRIB CRISTAL PREZ MX",
            "amount": -8090.01,
            "date": "2025-01-08"
        }
    ]

    invoices = [
        {
            "id": 101,
            "nombre_emisor": "ODOO TECHNOLOGIES SA DE CV",
            "total": 535.92,
            "fecha": "2025-01-10"
        },
        {
            "id": 102,
            "nombre_emisor": "GRUPO GASOLINERO BERISA",
            "total": 1238.44,
            "fecha": "2025-01-17"
        },
        {
            "id": 103,
            "nombre_emisor": "DISTRIBUIDORA PREZ SA DE CV",
            "total": 8090.01,
            "fecha": "2025-01-07"
        }
    ]

    print("\n" + "="*80)
    print("🧪 EMBEDDING MATCHER - TEST")
    print("="*80 + "\n")

    matches = matcher.match_batch(transactions, invoices, min_similarity=0.7)

    print(f"\nFound {len(matches)} matches:\n")

    for match in matches:
        print(f"✓ TX-{match.transaction_id}: {match.transaction_description}")
        print(f"  ↔ CFDI-{match.invoice_id}: {match.invoice_name}")
        print(f"  Similarity: {match.similarity_score:.2%} | Confidence: {match.confidence}")
        print(f"  Diff: ${match.amount_diff:.2f} ({match.days_diff} days)")
        print()
