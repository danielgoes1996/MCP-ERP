"""Utilities to fetch and retrieve account catalog entries for RAG enrichment."""

from __future__ import annotations

import json
import logging
import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import psycopg2

try:
    from sentence_transformers import SentenceTransformer
except ImportError:  # pragma: no cover - optional dependency
    SentenceTransformer = None  # type: ignore

from config.config import config
from core.text_normalizer import normalize_expense_text
from core.sat_utils import extract_family_code

logger = logging.getLogger(__name__)

EMBEDDING_MODEL_DIR = Path("data/embeddings/sat_sentence_transformer")
EMBEDDING_METADATA_PATH = Path("data/embeddings/sat_sentence_transformer_metadata.json")
CONTEXT_CACHE_PATH = Path("data/embeddings/sat_account_context.json")


def _get_db_connection() -> sqlite3.Connection:
    db_path = Path(config.UNIFIED_DB_PATH)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


@lru_cache(maxsize=1)
def _load_embedding_metadata() -> Dict[str, Any]:
    if not EMBEDDING_METADATA_PATH.exists():
        return {}
    try:
        with EMBEDDING_METADATA_PATH.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Unable to read embedding metadata: %s", exc)
        return {}


@lru_cache(maxsize=1)
def _load_context_cache() -> Dict[str, Dict[str, Any]]:
    if not CONTEXT_CACHE_PATH.exists():
        return {}
    try:
        with CONTEXT_CACHE_PATH.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            return data
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Unable to read SAT context cache: %s", exc)
    return {}


@lru_cache(maxsize=1)
def _load_sentence_model() -> Optional[SentenceTransformer]:
    if SentenceTransformer is None:
        logger.warning("sentence-transformers not installed; falling back to keyword retrieval.")
        return None

    candidates = []
    if EMBEDDING_MODEL_DIR.exists():
        candidates.append(str(EMBEDDING_MODEL_DIR))

    metadata = _load_embedding_metadata()
    model_path = metadata.get("model_path")
    if model_path:
        candidates.append(str(model_path))
    model_name = metadata.get("model_name")
    if model_name:
        candidates.append(model_name)

    # Preserve insertion order while removing duplicates
    seen = set()
    ordered_candidates = []
    for candidate in candidates:
        if candidate not in seen:
            seen.add(candidate)
            ordered_candidates.append(candidate)

    for candidate in ordered_candidates:
        try:
            model = SentenceTransformer(candidate)
            return model
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("Unable to load embedding model from %s: %s", candidate, exc)

    logger.warning("No SentenceTransformer model available for SAT embeddings.")
    return None


@lru_cache(maxsize=1)
def _load_sat_accounts() -> List[Dict[str, Any]]:
    accounts: List[Dict[str, Any]] = []
    try:
        with _get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT code, name, description
                FROM sat_account_catalog
                ORDER BY code
                """
            )
            rows = cursor.fetchall()
            for row in rows:
                accounts.append({
                    "code": row["code"],
                    "name": row["name"],
                    "description": row["description"],
                })
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.debug("Unable to load sat_account_catalog: %s", exc)

    if not accounts:
        # fallback minimal catalog
        accounts = [
            {"code": "601", "name": "Gastos generales", "description": "Gastos de operación distintos a viáticos"},
            {"code": "603", "name": "Gastos de ventas", "description": "Publicidad, marketing, comisiones"},
            {"code": "605", "name": "Gastos de administración", "description": "Servicios administrativos, oficinas"},
            {"code": "607", "name": "Gastos financieros", "description": "Intereses, comisiones bancarias"},
            {"code": "609", "name": "Gastos por viáticos", "description": "Viáticos, alimentos y hospedaje"},
            {"code": "611", "name": "Servicios profesionales", "description": "Honorarios y consultoría"},
        ]

    return accounts


def get_context_snippets(codes: Iterable[str], limit: int = 5) -> Dict[str, str]:
    """
    Return contextual descriptions for the provided SAT codes using the cached Claude output.
    """
    cache = _load_context_cache()
    snippets: Dict[str, str] = {}
    for code in codes:
        normalized_code = code or ""
        if normalized_code in snippets:
            continue
        entry = cache.get(normalized_code) or cache.get(normalized_code.split(".", 1)[0])
        if entry and isinstance(entry, dict):
            context = entry.get("context")
            if context:
                snippets[normalized_code] = context
        if len(snippets) >= limit:
            break
    return snippets


def _tokenize(text: str) -> List[str]:
    separators = " ,.;:-_()/\n\t"
    tokens: List[str] = []
    current = []
    for char in text.lower():
        if char in separators:
            if current:
                tokens.append("".join(current))
                current = []
        else:
            current.append(char)
    if current:
        tokens.append("".join(current))
    return tokens


def _score_account(account: Dict[str, Any], terms: Iterable[str]) -> Tuple[int, float]:
    """Return (match_count, token_ratio) for ranking purposes."""
    text = f"{account.get('code', '')} {account.get('name', '')} {account.get('description', '')}".lower()
    tokens = set(_tokenize(text))
    matches = 0
    for term in terms:
        if term and term in text:
            matches += 2  # full string inclusion
        if term in tokens:
            matches += 3
    token_ratio = len(tokens) / (len(tokens) + 50)
    return matches, token_ratio


def _retrieve_with_local_catalog(
    expense_payload: Dict[str, Any],
    top_k: int,
    family_filter: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    candidate_accounts = _load_sat_accounts()
    if not candidate_accounts:
        return []

    query_terms: List[str] = []
    fields = [
        expense_payload.get("descripcion"),
        expense_payload.get("categoria"),
        expense_payload.get("categoria_semantica"),
        expense_payload.get("categoria_contable"),
        expense_payload.get("notas"),
        expense_payload.get("comentarios"),
    ]

    metadata = expense_payload.get("metadata")
    if isinstance(metadata, dict):
        fields.extend([
            metadata.get("descripcion_contable"),
            metadata.get("categoria_contable"),
            metadata.get("categoria_semantica"),
            metadata.get("observaciones"),
        ])

    for field in fields:
        if not field:
            continue
        for token in _tokenize(str(field)):
            if len(token) > 2:
                query_terms.append(token)

    if not query_terms:
        # default broad query
        query_terms = ["gastos", "generales"]

    # Expand tokens with contextual aliases to improve recall (e.g. viaticos ↔ hospedaje)
    expanded_terms: List[str] = []
    seen_terms = set()

    def _add_term(term: str) -> None:
        normalized = term.strip().lower()
        if normalized and normalized not in seen_terms:
            expanded_terms.append(normalized)
            seen_terms.add(normalized)

    for original_term in list(query_terms):
        _add_term(original_term)
        lookup_key = _normalize_text(original_term) or original_term.strip().lower()
        alias_terms = KEYWORD_ALIASES.get(lookup_key) or KEYWORD_ALIASES.get(original_term.strip().lower())
        if alias_terms:
            for alias in alias_terms:
                _add_term(alias)

    if expanded_terms:
        query_terms = expanded_terms

    scored = []
    for account in candidate_accounts:
        score = _score_account(account, query_terms)
        scored.append((score, account))

    scored.sort(key=lambda item: item[0], reverse=True)

    top_accounts = []
    for (score_tuple, account) in scored:
        family_hint = extract_family_code(account.get("code"))
        if family_filter and family_hint not in family_filter:
            continue
        top_accounts.append({
            "code": account.get("code"),
            "name": account.get("name"),
            "description": account.get("description"),
            "family_hint": family_hint,
            "version_tag": None,
            "score": score_tuple[0],
        })
        if len(top_accounts) >= top_k:
            break

    return top_accounts


def _normalize_text(value: Optional[str]) -> str:
    return normalize_expense_text(value or "")


KEYWORD_ALIASES = {
    "laptop": ["equipo computo", "computo", "activo fijo", "seccion 156"],
    "macbook": ["equipo computo", "computo", "activo fijo", "seccion 156"],
    "computadora": ["equipo computo", "computo", "activo fijo", "seccion 156"],
    "computador": ["equipo computo", "computo", "activo fijo"],
    "equipo de computo": ["equipo computo", "activo fijo"],
    "equipo computo": ["equipo computo", "activo fijo"],
    "tecnologia": ["equipo computo", "computo"],
    "activo fijo": ["activo fijo", "seccion 156"],
    "hotel": ["hospedaje", "alojamiento", "viaticos", "viajes"],
    "hoteles": ["hospedaje", "hotel", "alojamiento", "viaticos", "viajes"],
    "hospedaje": ["hotel", "alojamiento", "viaticos", "viajes"],
    "alojamiento": ["hospedaje", "hotel", "viaticos", "viajes"],
    "viaticos": ["viatico", "hospedaje", "hotel", "viaje", "viajes"],
    "viatico": ["viaticos", "hospedaje", "hotel", "viaje"],
    "viaje": ["viaticos", "viajes", "hospedaje", "hotel"],
    "viajes": ["viaticos", "viaje", "hospedaje", "hotel"],
    "estancia": ["hospedaje", "hotel", "alojamiento"],
}


def _build_query_embedding(expense_payload: Dict[str, Any]) -> Optional[np.ndarray]:
    model = _load_sentence_model()
    if model is None:
        return None

    fields = [
        expense_payload.get("descripcion"),
        expense_payload.get("categoria"),
        expense_payload.get("categoria_semantica"),
        expense_payload.get("categoria_contable"),
        expense_payload.get("notas"),
        expense_payload.get("comentarios"),
    ]

    metadata = expense_payload.get("metadata")
    if isinstance(metadata, dict):
        fields.extend([
            metadata.get("descripcion_contable"),
            metadata.get("categoria_contable"),
            metadata.get("categoria_semantica"),
            metadata.get("observaciones"),
        ])

    normalized_fields = [_normalize_text(str(field)) for field in fields if field]
    text_lower = " ".join(normalized_fields)
    for keyword, aliases in KEYWORD_ALIASES.items():
        if keyword in text_lower:
            normalized_fields.extend(aliases)
    text = " ".join(filter(None, normalized_fields)).strip()
    if not text:
        return None

    metadata = _load_embedding_metadata()
    normalize_embeddings = bool(metadata.get("normalize_embeddings", True))

    try:
        vector = model.encode(
            [text],
            convert_to_numpy=True,
            normalize_embeddings=normalize_embeddings,
        )
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Unable to encode query embedding: %s", exc)
        return None

    if isinstance(vector, np.ndarray):
        if vector.ndim == 2:
            vector = vector[0]
    else:
        vector = np.asarray(vector)

    if vector.ndim != 1:
        logger.warning("Unexpected embedding shape for query: %s", vector.shape)
        return None

    if not normalize_embeddings:
        norm = np.linalg.norm(vector)
        if norm == 0:
            return None
        vector = vector / norm

    declared_dim = metadata.get("embedding_dimension")
    if declared_dim and len(vector) != declared_dim:
        logger.warning(
            "Query embedding dimension (%s) does not match metadata (%s).",
            len(vector),
            declared_dim,
        )

    return vector.astype(np.float32)


def _get_pg_connection():
    password_part = f" password={config.PG_PASSWORD}" if config.PG_PASSWORD else ""
    dsn = f"host={config.PG_HOST} port={config.PG_PORT} dbname={config.PG_DB} user={config.PG_USER}{password_part}"
    return psycopg2.connect(dsn)


def _vector_to_pgtext(vector: np.ndarray) -> str:
    return "[" + ",".join(f"{value:.6f}" for value in vector) + "]"


def _retrieve_with_pgvector(
    expense_payload: Dict[str, Any],
    top_k: int,
    family_filter: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    query_vector = _build_query_embedding(expense_payload)
    if query_vector is None:
        return []

    vector_str = _vector_to_pgtext(query_vector)
    search_components = [
        _normalize_text(expense_payload.get("descripcion")),
        _normalize_text(expense_payload.get("categoria")),
        _normalize_text(expense_payload.get("categoria_contable")),
        _normalize_text(expense_payload.get("categoria_semantica")),
    ]
    combined_search = " ".join(filter(None, search_components))
    for keyword, aliases in KEYWORD_ALIASES.items():
        if keyword in combined_search:
            search_components.extend(aliases)
    search_text = " ".join(filter(None, search_components))

    filters: List[str] = []
    params: List[Any] = [vector_str, search_text]
    version_tag = getattr(config, "SAT_EMBEDDING_VERSION", None)
    if version_tag:
        filters.append("version_tag = %s")
        params.append(version_tag)
    if family_filter:
        filters.append("family_hint = ANY(%s)")
        params.append(list(family_filter))

    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    sql = f"""
        SELECT
            code,
            name,
            description,
            family_hint,
            version_tag,
            embedding <-> %s::vector AS distance,
            ts_rank(search_vector, plainto_tsquery('spanish'::regconfig, %s::text)) AS ts_rank
        FROM sat_account_embeddings
        {where_clause}
        ORDER BY distance ASC, ts_rank DESC
        LIMIT %s;
    """
    params.append(top_k)

    try:
        with _get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
    except Exception as exc:
        logger.warning("pgvector retrieval failed: %s", exc)
        return []

    results: List[Dict[str, Any]] = []
    for code, name, description, family_hint, version_tag_value, distance, ts_rank in rows:
        score = max(0.0, 1.0 - float(distance)) if distance is not None else 0.0
        results.append(
            {
                "code": code,
                "name": name,
                "description": description,
                "family_hint": family_hint,
                "version_tag": version_tag_value,
                "score": score,
                "distance": float(distance) if distance is not None else None,
                "ts_rank": float(ts_rank) if ts_rank is not None else None,
            }
        )

    return results


def retrieve_relevant_accounts(
    expense_payload: Dict[str, Any],
    top_k: int = 5,
    family_filter: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Return top_k SAT accounts relevant to the manual expense payload.

    Uses PostgreSQL pgvector when available; falls back to the legacy
    token-based scorer otherwise.
    """

    if config.USE_PG_VECTOR:
        results = _retrieve_with_pgvector(expense_payload, top_k, family_filter=family_filter)
        if results:
            return results

    return _retrieve_with_local_catalog(expense_payload, top_k, family_filter=family_filter)
