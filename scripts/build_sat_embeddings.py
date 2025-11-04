#!/usr/bin/env python3
"""
Generate dense embeddings for the SAT account catalog and store them in PostgreSQL.

The script:
1. Reads `code`, `name`, `description` from the SQLite `sat_account_catalog`.
2. Builds TF-IDF features and reduces them with TruncatedSVD to obtain dense vectors.
3. Upserts the results into the PostgreSQL table `sat_account_embeddings`.

Requirements (already installed in the virtualenv):
    - scikit-learn
    - numpy
    - psycopg2-binary

Usage:
    python scripts/build_sat_embeddings.py \
        --sqlite unified_mcp_system.db \
        --postgres-host localhost \
        --postgres-db contaflow \
        --postgres-user danielgoes96
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
from pathlib import Path
from typing import Iterable, List, Sequence

import numpy as np
import psycopg2
from psycopg2.extras import execute_batch
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from joblib import dump
import unicodedata

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

EMBEDDING_DIM = 128


def load_sat_accounts(sqlite_path: Path) -> List[tuple[str, str, str]]:
    """Fetch sat_account_catalog rows from SQLite."""
    logger.info("Loading SAT catalog from %s", sqlite_path)
    with sqlite3.connect(str(sqlite_path)) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT code, name, COALESCE(description, '') AS description FROM sat_account_catalog ORDER BY code")
        rows = cursor.fetchall()

    accounts = [(row["code"], row["name"], row["description"]) for row in rows]
    logger.info("Loaded %d SAT accounts", len(accounts))
    return accounts


def _normalize_text(text: str) -> str:
    if text is None:
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    return normalized.lower()


def build_embeddings(
    accounts: Sequence[tuple[str, str, str]]
) -> tuple[np.ndarray, TfidfVectorizer, TruncatedSVD]:
    """
    Create TF-IDF features and project them to a dense embedding space using TruncatedSVD.
    Returns an array with shape (n_accounts, EMBEDDING_DIM).
    """
    logger.info("Building TF-IDF matrix and performing dimensionality reduction")
    raw_texts: List[str] = []
    for code, name, description in accounts:
        normalized_fields = [
            _normalize_text(code),
            _normalize_text(name),
            _normalize_text(description),
        ]
        text = " ".join(filter(None, normalized_fields))
        raw_texts.append(text)

    vectorizer = TfidfVectorizer(max_features=5000, stop_words=None)
    tfidf_matrix = vectorizer.fit_transform(raw_texts)
    print(f"TF-IDF shape: {tfidf_matrix.shape}", flush=True)

    n_features = tfidf_matrix.shape[1]
    n_components = min(32, n_features - 1) if n_features > 1 else 1
    svd = TruncatedSVD(n_components=n_components, n_iter=5, random_state=42)
    print("Running SVD...", flush=True)
    reduced = svd.fit_transform(tfidf_matrix)
    print("SVD listo", flush=True)

    # Normalize to unit length to make cosine similarity meaningful
    norms = np.linalg.norm(reduced, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    normalized = reduced / norms

    logger.info("Generated embeddings with shape %s", normalized.shape)
    return normalized, vectorizer, svd


def format_vector(values: Iterable[float]) -> str:
    """Convert an iterable of floats into the pgvector textual representation."""
    return "[" + ",".join(f"{value:.6f}" for value in values) + "]"


def upsert_embeddings(
    postgres_dsn: str,
    accounts: Sequence[tuple[str, str, str]],
    embeddings: np.ndarray,
) -> None:
    """Insert or update embeddings inside PostgreSQL."""
    logger.info("Upserting embeddings into PostgreSQL")
    insert_sql = """
        INSERT INTO sat_account_embeddings (code, name, description, embedding, search_vector, created_at)
        VALUES (%s, %s, %s, %s::vector, to_tsvector('spanish'::regconfig, %s), NOW())
        ON CONFLICT (code) DO UPDATE
        SET name = EXCLUDED.name,
            description = EXCLUDED.description,
            embedding = EXCLUDED.embedding,
            search_vector = EXCLUDED.search_vector,
            created_at = NOW();
    """

    payload = []
    for (code, name, description), vector in zip(accounts, embeddings):
        vector_str = format_vector(vector)
        search_text = " ".join(
            filter(
                None,
                [
                    _normalize_text(code),
                    _normalize_text(name),
                    _normalize_text(description),
                ],
            )
        )
        payload.append((code, name, description, vector_str, search_text))

    with psycopg2.connect(postgres_dsn) as conn:
        with conn.cursor() as cur:
            execute_batch(cur, insert_sql, payload, page_size=500)
        conn.commit()

    logger.info("Upserted %d embeddings", len(payload))


def create_indexes(postgres_dsn: str) -> None:
    """Create recommended indexes for pgvector search."""
    logger.info("Ensuring pgvector indexes exist")
    create_index_sql = """
        CREATE INDEX IF NOT EXISTS idx_sat_embeddings_vector
            ON sat_account_embeddings USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100);
    """
    create_search_index_sql = """
        CREATE INDEX IF NOT EXISTS idx_sat_embeddings_search
            ON sat_account_embeddings USING gin (search_vector);
    """

    with psycopg2.connect(postgres_dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(create_index_sql)
            cur.execute(create_search_index_sql)
        conn.commit()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build embeddings for SAT account catalog.")
    parser.add_argument("--sqlite", type=Path, default=Path("unified_mcp_system.db"), help="Path to SQLite database.")
    parser.add_argument("--postgres-host", default="localhost")
    parser.add_argument("--postgres-port", default="5432")
    parser.add_argument("--postgres-db", default="contaflow")
    parser.add_argument("--postgres-user", default=str(Path.home().name))
    parser.add_argument("--postgres-password", default="", help="Optional password for PostgreSQL.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.sqlite.exists():
        raise SystemExit(f"SQLite database not found at {args.sqlite}")

    accounts = load_sat_accounts(args.sqlite)
    if not accounts:
        raise SystemExit("No accounts found in sat_account_catalog; aborting.")

    embeddings, vectorizer, svd = build_embeddings(accounts)

    # Persist preprocessing artifacts for runtime queries
    artifacts_dir = Path("data/embeddings")
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    dump(vectorizer, artifacts_dir / "sat_tfidf.joblib")
    dump(svd, artifacts_dir / "sat_svd.joblib")
    logger.info("Stored preprocessing artifacts under %s", artifacts_dir)

    password_part = f" password={args.postgres_password}" if args.postgres_password else ""
    dsn = f"host={args.postgres_host} port={args.postgres_port} dbname={args.postgres_db} user={args.postgres_user}{password_part}"

    upsert_embeddings(dsn, accounts, embeddings)
    create_indexes(dsn)

    logger.info("All done!")


if __name__ == "__main__":
    main()
