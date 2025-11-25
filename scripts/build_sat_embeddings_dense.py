#!/usr/bin/env python3
"""
Generate dense SentenceTransformer embeddings for the SAT account catalog.

Steps performed:
1. Read SAT accounts from the SQLite catalog (code, name, description).
2. Encode the textual representation with a SentenceTransformer model.
3. Upsert the normalized embeddings into PostgreSQL (vector(N)).
4. Persist the model artifacts locally for reuse during inference.

Example usage:
    python scripts/build_sat_embeddings_dense.py \
        --sqlite unified_mcp_system.db \
        --postgres-host localhost \
        --postgres-db contaflow \
        --postgres-user danielgoes96 \
        --model sentence-transformers/all-MiniLM-L6-v2 \
        --reset-table
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

import numpy as np
import psycopg2
from psycopg2.extras import execute_batch
from sentence_transformers import SentenceTransformer

try:  # Optional env loader for local dev
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - optional dependency
    pass

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

DEFAULT_MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_MODEL_DIR = Path("data/embeddings/sat_sentence_transformer")
DEFAULT_METADATA_PATH = Path("data/embeddings/sat_sentence_transformer_metadata.json")
DEFAULT_CONTEXT_CACHE = Path("data/embeddings/sat_account_context.json")


@dataclass(frozen=True)
class AccountRow:
    code: str
    name: str
    description: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build dense embeddings for SAT account catalog.")
    parser.add_argument("--sqlite", type=Path, default=Path("unified_mcp_system.db"), help="Path to SQLite database.")
    parser.add_argument("--postgres-host", default="localhost", help="PostgreSQL host.")
    parser.add_argument("--postgres-port", default="5432", help="PostgreSQL port.")
    parser.add_argument("--postgres-db", default="contaflow", help="PostgreSQL database name.")
    parser.add_argument("--postgres-user", default=str(Path.home().name), help="PostgreSQL user.")
    parser.add_argument("--postgres-password", default="", help="PostgreSQL password (optional).")
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL_ID,
        help="SentenceTransformer model id or local path (default: sentence-transformers/all-MiniLM-L6-v2).",
    )
    parser.add_argument(
        "--model-save-path",
        type=Path,
        default=DEFAULT_MODEL_DIR,
        help="Directory to store the exported SentenceTransformer model.",
    )
    parser.add_argument("--batch-size", type=int, default=64, help="Encoding batch size.")
    parser.add_argument(
        "--reset-table",
        action="store_true",
        help="Drop and recreate sat_account_embeddings before inserting (destroys previous data).",
    )
    parser.add_argument(
        "--use-claude-context",
        action="store_true",
        help="Enrich SAT catalog entries with Claude-generated context before encoding.",
    )
    parser.add_argument(
        "--claude-model",
        default="claude-3-haiku-20240307",
        help="Claude model to use when enriching catalog context (default: claude-3-haiku-20240307).",
    )
    parser.add_argument(
        "--context-cache",
        type=Path,
        default=DEFAULT_CONTEXT_CACHE,
        help=f"Path to cache contextual descriptions (default: {DEFAULT_CONTEXT_CACHE}).",
    )
    return parser.parse_args()


def load_sat_accounts(sqlite_path: Path) -> List[AccountRow]:
    """Fetch sat_account_catalog rows from SQLite."""
    if not sqlite_path.exists():
        raise FileNotFoundError(f"SQLite database not found at {sqlite_path}")

    logger.info("Loading SAT catalog from %s", sqlite_path)
    with sqlite3.connect(str(sqlite_path)) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT code, name, COALESCE(description, '') AS description
            FROM sat_account_catalog
            ORDER BY code
            """
        )
        rows = cursor.fetchall()

    accounts = [AccountRow(row["code"], row["name"], row["description"]) for row in rows]
    logger.info("Loaded %d SAT accounts", len(accounts))
    return accounts


def _load_claude_client() -> Optional["anthropic.Anthropic"]:
    """Instantiate an Anthropic client when credentials and SDK are available."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY no configurada; se omite enriquecimiento contextual con Claude.")
        return None

    try:
        import anthropic
    except ImportError:  # pragma: no cover - optional dependency
        logger.warning("anthropic SDK no instalado. Ejecuta `pip install anthropic` para habilitar Claude.")
        return None

    try:
        return anthropic.Anthropic(api_key=api_key)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("No se pudo inicializar cliente de Claude: %s", exc)
        return None


def _sanitize_context(text: str) -> str:
    normalized = (text or "").strip()
    if not normalized:
        return ""
    return " ".join(normalized.split())


def _generate_context_with_claude(
    client: "anthropic.Anthropic",
    model: str,
    account: AccountRow,
) -> Optional[str]:
    """Ask Claude to provide a short contextual description for the SAT account."""
    try:
        prompt = (
            "Explica en máximo 2 oraciones cuándo se usa la cuenta contable del SAT.\n"
            "Incluye ejemplos concretos en México (proveedores, conceptos, escenarios) "
            "y resume el tipo de gasto que cubre.\n\n"
            f"Cuenta: {account.code} {account.name}\n"
            f"Descripción SAT oficial: {account.description or 'N/A'}"
        )
        response = client.messages.create(
            model=model,
            max_tokens=250,
            temperature=0.2,
            system=(
                "Eres un contador certificado en México. "
                "Describe con precisión en qué casos se utiliza la cuenta contable proporcionada. "
                "Evita viñetas; responde en texto corrido."
            ),
            messages=[
                {"role": "user", "content": prompt},
            ],
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Claude falló generando contexto para %s: %s", account.code, exc)
        return None

    parts = []
    for block in response.content:
        block_text = getattr(block, "text", "")
        if isinstance(block_text, str):
            parts.append(block_text)
    return _sanitize_context(" ".join(parts))


def _load_context_cache(cache_path: Path) -> Dict[str, Dict[str, str]]:
    if not cache_path.exists():
        return {}
    try:
        with cache_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            return data
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("No se pudo leer cache de contexto %s: %s", cache_path, exc)
    return {}


def _persist_context_cache(cache_path: Path, cache: Dict[str, Dict[str, str]]) -> None:
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with cache_path.open("w", encoding="utf-8") as fh:
            json.dump(cache, fh, indent=2, ensure_ascii=False)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("No se pudo guardar cache de contexto %s: %s", cache_path, exc)


def build_context_map(
    accounts: Sequence[AccountRow],
    use_claude: bool,
    claude_model: str,
    cache_path: Path,
) -> Dict[str, str]:
    """
    Return a mapping code -> contextual description, optionally asking Claude for missing entries.
    """
    context_cache = _load_context_cache(cache_path)
    enriched_context: Dict[str, str] = {}

    if not use_claude:
        # Return any cached context we may already have (useful for deterministic runs)
        for account in accounts:
            cached = context_cache.get(account.code, {}).get("context")
            if cached:
                enriched_context[account.code] = cached
        return enriched_context

    client = _load_claude_client()
    if not client:
        for account in accounts:
            cached = context_cache.get(account.code, {}).get("context")
            if cached:
                enriched_context[account.code] = cached
        return enriched_context

    cache_updated = False
    for account in accounts:
        cache_entry = context_cache.get(account.code)
        if cache_entry and cache_entry.get("context"):
            enriched_context[account.code] = cache_entry["context"]
            continue

        context = _generate_context_with_claude(client, claude_model, account)
        time.sleep(0.6)  # throttle Claude requests to stay below rate limits
        if not context:
            continue

        timestamp = datetime.utcnow().isoformat()
        context_cache[account.code] = {
            "context": context,
            "model": claude_model,
            "generated_at": timestamp,
        }
        enriched_context[account.code] = context
        cache_updated = True

    if cache_updated:
        _persist_context_cache(cache_path, context_cache)

    return enriched_context


def _normalize_text(value: str) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", value)
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    return normalized.lower()


def build_text_payloads(
    accounts: Sequence[AccountRow],
    context_map: Optional[Dict[str, str]] = None,
) -> List[str]:
    """Concatenate and normalize relevant fields (including optional Claude context) for encoding."""
    payloads: List[str] = []
    for account in accounts:
        contextual_notes = ""
        if context_map:
            contextual_notes = context_map.get(account.code, "")
        normalized_fields = [
            _normalize_text(account.code),
            _normalize_text(account.name),
            _normalize_text(account.description),
            _normalize_text(contextual_notes),
        ]
        payloads.append(" ".join(filter(None, normalized_fields)))
    return payloads


def load_model(model_id_or_path: str) -> SentenceTransformer:
    """Load a SentenceTransformer model from Hugging Face or a local directory."""
    resolved_path = Path(model_id_or_path)
    if resolved_path.exists():
        logger.info("Loading SentenceTransformer model from local path: %s", resolved_path)
        return SentenceTransformer(str(resolved_path))

    logger.info("Downloading SentenceTransformer model: %s", model_id_or_path)
    return SentenceTransformer(model_id_or_path)


def encode_accounts(
    model: SentenceTransformer,
    payloads: Sequence[str],
    batch_size: int,
) -> np.ndarray:
    """Generate normalized dense embeddings."""
    embeddings = model.encode(
        list(payloads),
        batch_size=batch_size,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=True,
    )
    if embeddings.ndim != 2:
        raise ValueError(f"Expected 2D embeddings but received shape {embeddings.shape}")
    return embeddings.astype(np.float32)


def ensure_embeddings_table(dsn: str, dim: int, reset_table: bool) -> None:
    """Create or reset the sat_account_embeddings table with the right vector dimension."""
    drop_sql = "DROP TABLE IF EXISTS sat_account_embeddings;"
    create_extension_sql = "CREATE EXTENSION IF NOT EXISTS vector;"
    create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS sat_account_embeddings (
            code TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            embedding vector({dim}) NOT NULL,
            search_vector tsvector,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """
    alter_sql = f"ALTER TABLE sat_account_embeddings ALTER COLUMN embedding TYPE vector({dim});"

    with psycopg2.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(create_extension_sql)
            if reset_table:
                logger.info("Dropping sat_account_embeddings table before recreation")
                cur.execute(drop_sql)
            cur.execute(create_table_sql)
            try:
                cur.execute(alter_sql)
            except psycopg2.Error as exc:  # pragma: no cover - defensive
                logger.warning("Unable to alter embedding dimension: %s", exc)
                conn.rollback()
                conn.commit()
                with conn.cursor() as retry_cur:
                    retry_cur.execute(create_table_sql)
        conn.commit()


def format_vector(values: Iterable[float]) -> str:
    """Convert an iterable of floats into the pgvector textual representation."""
    return "[" + ",".join(f"{value:.6f}" for value in values) + "]"


def upsert_embeddings(
    dsn: str,
    accounts: Sequence[AccountRow],
    embeddings: np.ndarray,
    context_map: Optional[Dict[str, str]] = None,
) -> None:
    """Insert or update embeddings inside PostgreSQL."""
    insert_sql = """
        INSERT INTO sat_account_embeddings (code, name, description, embedding, search_vector, family_hint, created_at)
        VALUES (%s, %s, %s, %s::vector, to_tsvector('spanish'::regconfig, %s), %s, NOW())
        ON CONFLICT (code) DO UPDATE
        SET name = EXCLUDED.name,
            description = EXCLUDED.description,
            embedding = EXCLUDED.embedding,
            search_vector = EXCLUDED.search_vector,
            family_hint = EXCLUDED.family_hint,
            created_at = NOW();
    """

    payload = []
    for account, vector in zip(accounts, embeddings):
        context_fragment = ""
        if context_map:
            context_fragment = context_map.get(account.code, "")
        search_text = " ".join(
            filter(
                None,
                [
                    _normalize_text(account.code),
                    _normalize_text(account.name),
                    _normalize_text(account.description),
                    _normalize_text(context_fragment),
                ],
            )
        )
        # Extract family hint from code (first 3 digits for level 1, or extract from dotted codes)
        family_hint = account.code.split('.')[0] if '.' in account.code else account.code[:3]
        payload.append((account.code, account.name, account.description, format_vector(vector), search_text, family_hint))

    logger.info("Upserting %d embeddings into PostgreSQL", len(payload))
    with psycopg2.connect(dsn) as conn:
        with conn.cursor() as cur:
            execute_batch(cur, insert_sql, payload, page_size=500)
        conn.commit()


def create_indexes(dsn: str) -> None:
    """Ensure pgvector/GiN indexes exist for fast similarity + text search."""
    vector_index_sql = """
        CREATE INDEX IF NOT EXISTS idx_sat_embeddings_vector
            ON sat_account_embeddings USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100);
    """
    search_index_sql = """
        CREATE INDEX IF NOT EXISTS idx_sat_embeddings_search
            ON sat_account_embeddings USING gin (search_vector);
    """

    with psycopg2.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(vector_index_sql)
            cur.execute(search_index_sql)
        conn.commit()


def persist_model_artifacts(model: SentenceTransformer, save_path: Path, metadata_path: Path, metadata: dict) -> None:
    """Persist the SentenceTransformer model and metadata for inference-time reuse."""
    save_path.mkdir(parents=True, exist_ok=True)
    logger.info("Saving SentenceTransformer model to %s", save_path)
    model.save(str(save_path))

    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Writing metadata to %s", metadata_path)
    with metadata_path.open("w", encoding="utf-8") as fh:
        json.dump(metadata, fh, indent=2, ensure_ascii=False)


def build_postgres_dsn(args: argparse.Namespace) -> str:
    password_part = f" password={args.postgres_password}" if args.postgres_password else ""
    dsn = (
        f"host={args.postgres_host} port={args.postgres_port} "
        f"dbname={args.postgres_db} user={args.postgres_user}{password_part}"
    )
    return dsn


def main() -> None:
    args = parse_args()

    accounts = load_sat_accounts(args.sqlite)
    if not accounts:
        raise SystemExit("No accounts found in sat_account_catalog; aborting.")

    context_map = build_context_map(
        accounts,
        use_claude=args.use_claude_context,
        claude_model=args.claude_model,
        cache_path=args.context_cache,
    )
    if context_map:
        logger.info("Contexto enriquecido disponible para %d cuentas SAT.", len(context_map))
    elif args.use_claude_context:
        logger.warning("No se generó contexto enriquecido; se continuará con el texto básico.")

    model = load_model(args.model)
    payloads = build_text_payloads(accounts, context_map=context_map)
    embeddings = encode_accounts(model, payloads, batch_size=args.batch_size)

    dsn = build_postgres_dsn(args)
    ensure_embeddings_table(dsn, dim=embeddings.shape[1], reset_table=args.reset_table)
    upsert_embeddings(dsn, accounts, embeddings, context_map=context_map)
    create_indexes(dsn)

    metadata = {
        "model_name": args.model,
        "embedding_dimension": int(embeddings.shape[1]),
        "normalize_embeddings": True,
        "model_path": str(args.model_save_path),
        "uses_claude_context": bool(context_map),
        "claude_model": args.claude_model if context_map else None,
        "context_cache": str(args.context_cache),
        "context_generated_at": datetime.utcnow().isoformat() if context_map else None,
    }
    persist_model_artifacts(model, args.model_save_path, DEFAULT_METADATA_PATH, metadata)

    logger.info("All done! Generated %d embeddings with dimension %d.", len(accounts), embeddings.shape[1])


if __name__ == "__main__":
    main()
