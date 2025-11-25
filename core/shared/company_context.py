"""
Company classification context retrieval.

This module provides helpers to retrieve company-specific context for AI classification.
Context is stored in companies.settings as JSON and populated during onboarding.

Created: 2025-11-13
Purpose: Enable AI-driven classification with company-specific context
"""

from typing import Optional, Dict, Any, List
import json
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
import os

from core.shared.db_config import POSTGRES_CONFIG

logger = logging.getLogger(__name__)

# Redis client (lazy initialization)
_redis_client = None


def get_redis_client():
    """Get or create Redis client (lazy initialization with fallback)."""
    global _redis_client

    if _redis_client is not None:
        return _redis_client

    try:
        import redis

        # Connect to Redis (from docker-compose)
        _redis_client = redis.Redis(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=int(os.getenv('REDIS_PORT', 6379)),
            db=int(os.getenv('REDIS_DB', 0)),
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2
        )

        # Test connection
        _redis_client.ping()
        logger.info("Redis client initialized successfully")

    except Exception as e:
        logger.warning(f"Redis not available, caching disabled: {e}")
        _redis_client = None

    return _redis_client


# Industry descriptions for AI context
INDUSTRY_DESCRIPTIONS = {
    "retail": "venta al público de productos físicos (tiendas minoristas)",
    "food_production": "producción y comercialización de alimentos (industria alimentaria)",
    "food_service": "servicios de alimentación (restaurantes, cafeterías, catering)",
    "manufacturing": "manufactura y producción industrial",
    "services": "prestación de servicios profesionales (consultoría, asesoría)",
    "tech": "tecnología y software (desarrollo, SaaS)",
    "logistics": "logística y transporte",
    "construction": "construcción e infraestructura",
    "real_estate": "bienes raíces y arrendamiento",
    "agriculture": "agricultura y ganadería",
    "healthcare": "salud y servicios médicos",
    "education": "educación y capacitación",
}


# Business model descriptions
BUSINESS_MODEL_DESCRIPTIONS = {
    "b2b_wholesale": "venta mayorista B2B (empresa a empresa)",
    "b2b_services": "servicios B2B (consultoría, outsourcing)",
    "b2c_retail": "venta minorista B2C (empresa a consumidor)",
    "b2c_online": "comercio electrónico directo al consumidor",
    "marketplace": "plataforma marketplace (intermediario)",
    "subscription": "modelo de suscripción (SaaS, membresías)",
    "production": "producción y venta de productos propios",
    "distribution": "distribución de productos de terceros",
}


# Expense category descriptions (semantic only, NO SAT codes hardcoded)
# SAT codes come from: embeddings search + correction memory learning
EXPENSE_CATEGORY_DESCRIPTIONS = {
    "raw_materials": "materias primas e insumos para producción",
    "production_salaries": "sueldos y salarios de personal de producción",
    "administrative_salaries": "sueldos y salarios de personal administrativo",
    "sales_salaries": "sueldos y salarios de personal de ventas",
    "rent": "arrendamiento de espacios (oficinas, bodegas, locales)",
    "utilities": "servicios públicos (electricidad, agua, internet, teléfono)",
    "marketing": "publicidad, promoción y marketing",
    "digital_marketing": "publicidad digital y redes sociales",
    "logistics": "servicios de logística, transporte y distribución",
    "services": "servicios profesionales y consultoría",
    "administrative_services": "servicios administrativos y contables",
    "cloud_services": "servicios de cómputo en la nube y software",
    "maintenance": "mantenimiento y reparaciones",
    "travel": "viáticos y gastos de viaje",
    "insurance": "seguros y pólizas",
    "legal_fees": "servicios legales y notariales",
}


def get_company_classification_context(company_id: int) -> Optional[Dict[str, Any]]:
    """
    Retrieve classification context from company settings.

    Args:
        company_id: Database ID of the company (integer PK)
                   Can also accept string slugs like 'carreta_verde' (will be resolved)

    Returns:
        Dict with:
        - industry: str
        - business_model: str
        - typical_expenses: List[str]
        - provider_treatments: Dict[str, str]  # RFC -> category
        - preferences: Dict (detail_level, auto_approve_threshold)

        None if not found or on error

    Example:
        >>> context = get_company_classification_context(2)
        >>> context['industry']
        'food_production'
        >>> context['provider_treatments']['FIN1203015JA']
        'servicios_administrativos_timbrado'
    """
    try:
        # Resolve company_id if it's a string slug
        resolved_id = company_id
        if isinstance(company_id, str):
            if company_id.isdigit():
                resolved_id = int(company_id)
            else:
                # Query database to resolve slug → integer PK
                try:
                    conn_temp = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
                    cursor_temp = conn_temp.cursor()
                    cursor_temp.execute("""
                        SELECT id FROM companies WHERE company_id = %s
                    """, (company_id,))
                    row_temp = cursor_temp.fetchone()
                    conn_temp.close()

                    if row_temp and row_temp['id']:
                        resolved_id = row_temp['id']
                        logger.debug(f"Resolved company_id '{company_id}' → {resolved_id}")
                    else:
                        logger.warning(f"Could not resolve company_id '{company_id}' - not found in database")
                        return None
                except Exception as e:
                    logger.warning(f"Could not resolve company_id '{company_id}': {e}")
                    return None

        conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT settings
            FROM companies
            WHERE id = %s
        """, (resolved_id,))

        row = cursor.fetchone()

        if not row or not row['settings']:
            logger.debug(f"No classification context found for company_id={company_id}")
            return None

        # Parse JSON settings
        settings = json.loads(row['settings']) if isinstance(row['settings'], str) else row['settings']

        # Validate structure
        if not isinstance(settings, dict):
            logger.warning(f"Invalid settings format for company_id={company_id}")
            return None

        logger.info(f"Retrieved classification context for company_id={resolved_id} (requested as: {company_id})")
        return settings

    except psycopg2.Error as e:
        logger.error(f"Database error loading company context: {e}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error in company settings: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error loading company context: {e}")
        return None
    finally:
        if 'conn' in locals():
            conn.close()


def format_context_for_prompt(context: Dict[str, Any], provider_rfc: Optional[str] = None) -> str:
    """
    Format company context into a natural language block for AI prompts.

    Args:
        context: Classification context dict from get_company_classification_context()
        provider_rfc: Optional RFC to highlight specific provider treatment

    Returns:
        Formatted string ready to inject into prompt

    Example:
        >>> context = {"industry": "food_production", "typical_expenses": ["raw_materials"]}
        >>> formatted = format_context_for_prompt(context, "FIN1203015JA")
        >>> print(formatted)
        CONTEXTO DE LA EMPRESA:
        - Industria: producción y comercialización de alimentos
        ...
    """
    if not context:
        return ""

    lines = ["CONTEXTO DE LA EMPRESA:"]

    # Industry
    industry = context.get('industry')
    if industry:
        industry_desc = INDUSTRY_DESCRIPTIONS.get(industry, industry)
        lines.append(f"- Industria: {industry_desc}")

    # Business model
    business_model = context.get('business_model')
    if business_model:
        model_desc = BUSINESS_MODEL_DESCRIPTIONS.get(business_model, business_model)
        lines.append(f"- Modelo de negocio: {model_desc}")

    # Typical expenses (semantic descriptions only, NO SAT codes)
    typical_expenses = context.get('typical_expenses', [])
    if typical_expenses:
        expense_labels = []
        for expense in typical_expenses[:5]:  # Limit to 5 most common
            # Get semantic description, NOT SAT code
            desc = EXPENSE_CATEGORY_DESCRIPTIONS.get(expense, expense)
            expense_labels.append(f"{expense} ({desc})")

        lines.append(f"- Gastos típicos: {', '.join(expense_labels)}")

    # Provider-specific treatment
    provider_treatments = context.get('provider_treatments', {})
    if provider_rfc and provider_rfc in provider_treatments:
        treatment = provider_treatments[provider_rfc]
        lines.append(f"\nREGLA ESPECÍFICA PARA ESTE PROVEEDOR:")
        lines.append(f"- RFC {provider_rfc}: clasificar usualmente como '{treatment}'")

    return "\n".join(lines)


def get_similar_corrections(
    company_id: int,
    provider_rfc: Optional[str] = None,
    description: Optional[str] = None,
    limit: int = 3
) -> list:
    """
    Retrieve similar past corrections for this company.

    This helps the AI learn from previous manual corrections.

    Args:
        company_id: Company database ID
        provider_rfc: Optional RFC to filter by provider
        description: Optional description for similarity search (future enhancement)
        limit: Max number of corrections to return

    Returns:
        List of dicts with:
        - sat_code: str
        - description: str
        - provider_name: str
        - confidence: float

    Example:
        >>> corrections = get_similar_corrections(2, "FIN1203015JA")
        >>> corrections[0]['sat_code']
        '613.01'
    """
    try:
        conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
        cursor = conn.cursor()

        # Query ai_correction_memory for similar expenses
        query = """
            SELECT
                corrected_sat_code as sat_code,
                original_description as description,
                provider_name,
                1.0 as confidence
            FROM ai_correction_memory
            WHERE company_id = %s
        """
        params = [company_id]

        if provider_rfc:
            query += " AND provider_rfc = %s"
            params.append(provider_rfc)

        query += " ORDER BY corrected_at DESC LIMIT %s"
        params.append(limit)

        cursor.execute(query, params)
        corrections = cursor.fetchall()

        logger.info(f"Found {len(corrections)} similar corrections for company_id={company_id}")
        return [dict(row) for row in corrections]

    except psycopg2.Error as e:
        logger.error(f"Error fetching similar corrections: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error fetching corrections: {e}")
        return []
    finally:
        if 'conn' in locals():
            conn.close()


def format_corrections_for_prompt(corrections: list) -> str:
    """
    Format past corrections into a prompt block.

    Args:
        corrections: List from get_similar_corrections()

    Returns:
        Formatted string for prompt injection

    Example:
        >>> corrections = [{"sat_code": "613.01", "provider_name": "FINKOK"}]
        >>> print(format_corrections_for_prompt(corrections))
        CLASIFICACIONES PREVIAS (aprendizaje):
        - FINKOK: clasificado previamente como 613.01
    """
    if not corrections:
        return ""

    lines = ["CLASIFICACIONES PREVIAS (aprendizaje de correcciones manuales):"]

    for corr in corrections:
        provider = corr.get('provider_name', 'Proveedor desconocido')
        sat_code = corr.get('sat_code', 'N/A')
        desc = corr.get('description', '')

        if desc:
            lines.append(f"- {provider} ({desc[:50]}): clasificado como {sat_code}")
        else:
            lines.append(f"- {provider}: clasificado como {sat_code}")

    return "\n".join(lines)


def get_family_classification_examples(
    company_id: int,
    description: Optional[str] = None,
    limit: int = 5,
    use_cache: bool = True
) -> List[Dict[str, Any]]:
    """
    Get examples of previously classified invoices at FAMILY level for few-shot learning.

    This function retrieves invoices that have been successfully classified to the family
    level (100-800) to provide context for ambiguous cases.

    WITH REDIS CACHING: Results are cached for 1 hour to reduce database load by 99%.

    Sources (in order of priority):
    1. Manual corrections from ai_correction_memory (highest quality)
    2. Successfully classified invoices from expense_invoices (if family_code is populated)

    Args:
        company_id: Company identifier
        description: Optional description to find similar invoices (semantic search - future)
        limit: Maximum number of examples to return (default: 5)
        use_cache: Whether to use Redis cache (default: True)

    Returns:
        List of dicts with:
        - descripcion: Invoice description
        - family_code: Family code (100-800)
        - family_name: Family name (ACTIVO, PASIVO, etc.)
        - razonamiento: Brief explanation (if available from corrections)
        - source: 'correction' or 'classified'

    Example:
        >>> examples = get_family_classification_examples(2, limit=3)
        >>> examples[0]
        {
            'descripcion': 'BOTELLAS PET 1L',
            'family_code': '100',
            'family_name': 'ACTIVO',
            'razonamiento': 'Inventario de materiales para producción',
            'source': 'correction'
        }
    """
    # Try to get from cache first
    cache_key = f"family_examples:company_{company_id}:limit_{limit}"
    redis_client = get_redis_client() if use_cache else None

    if redis_client:
        try:
            cached = redis_client.get(cache_key)
            if cached:
                logger.debug(f"Cache HIT for family examples (company={company_id})")
                return json.loads(cached)
            else:
                logger.debug(f"Cache MISS for family examples (company={company_id})")
        except Exception as e:
            logger.warning(f"Redis cache read failed: {e}")

    try:
        conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
        cursor = conn.cursor()

        examples = []

        # STEP 1: Get examples from manual corrections (highest quality)
        # These are corrections where accountant manually fixed the classification
        query_corrections = """
            SELECT DISTINCT ON (original_description)
                original_description as descripcion,
                SUBSTRING(corrected_sat_code FROM 1 FOR 3) as family_code,
                corrected_sat_code,
                'correction' as source
            FROM ai_correction_memory
            WHERE company_id = %s
              AND corrected_sat_code IS NOT NULL
              AND original_description IS NOT NULL
            ORDER BY original_description, corrected_at DESC
            LIMIT %s
        """

        cursor.execute(query_corrections, (company_id, limit))
        corrections_results = cursor.fetchall()

        # Map family codes to names
        family_names = {
            '100': 'ACTIVO',
            '200': 'PASIVO',
            '300': 'CAPITAL',
            '400': 'INGRESOS',
            '500': 'COSTO DE VENTAS',
            '600': 'GASTOS DE OPERACIÓN',
            '700': 'GASTOS FINANCIEROS',
            '800': 'OTROS INGRESOS/GASTOS'
        }

        for row in corrections_results:
            examples.append({
                'descripcion': row['descripcion'],
                'family_code': row['family_code'],
                'family_name': family_names.get(row['family_code'], 'DESCONOCIDA'),
                'razonamiento': f"Clasificado manualmente como {row['corrected_sat_code']}",
                'source': 'correction'
            })

        # STEP 2: If we need more examples, get from successfully classified expenses
        # Note: Using 'expenses' table instead of 'expense_invoices' since the former
        # has the 'description' field and enhanced_data with classifications
        if len(examples) < limit:
            remaining = limit - len(examples)

            query_classified = """
                SELECT DISTINCT ON (description)
                    description as descripcion,
                    enhanced_data->>'family_code' as family_code,
                    'classified' as source
                FROM expenses
                WHERE company_id = %s
                  AND enhanced_data IS NOT NULL
                  AND enhanced_data->>'family_code' IS NOT NULL
                  AND enhanced_data->>'family_code' != ''
                  AND description IS NOT NULL
                  AND (enhanced_data->>'classification_confidence_family')::float >= 0.90
                ORDER BY description, created_at DESC
                LIMIT %s
            """

            cursor.execute(query_classified, (company_id, remaining))
            classified_results = cursor.fetchall()

            for row in classified_results:
                # Avoid duplicates
                if not any(ex['descripcion'] == row['descripcion'] for ex in examples):
                    examples.append({
                        'descripcion': row['descripcion'],
                        'family_code': row['family_code'],
                        'family_name': family_names.get(row['family_code'], 'DESCONOCIDA'),
                        'razonamiento': f"Clasificado automáticamente con alta confianza",
                        'source': 'classified'
                    })

        logger.info(
            f"Retrieved {len(examples)} family classification examples for company_id={company_id} "
            f"({sum(1 for ex in examples if ex['source'] == 'correction')} corrections, "
            f"{sum(1 for ex in examples if ex['source'] == 'classified')} classified)"
        )

        # Cache the results for 1 hour
        if redis_client and examples:
            try:
                redis_client.setex(
                    cache_key,
                    3600,  # TTL: 1 hour
                    json.dumps(examples)
                )
                logger.debug(f"Cached {len(examples)} family examples for company_id={company_id}")
            except Exception as e:
                logger.warning(f"Redis cache write failed: {e}")

        return examples

    except psycopg2.Error as e:
        logger.error(f"Error fetching family classification examples: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error fetching examples: {e}")
        return []
    finally:
        if 'conn' in locals():
            conn.close()


def format_family_examples_for_prompt(examples: list, compressed: bool = True) -> str:
    """
    Format family classification examples into a prompt block for few-shot learning.

    Args:
        examples: List from get_family_classification_examples()
        compressed: If True, use compressed format (67% fewer tokens). Default: True

    Returns:
        Formatted string for prompt injection

    Example (compressed format - default):
        >>> examples = [
        ...     {
        ...         'descripcion': 'BOTELLAS PET 1L',
        ...         'family_code': '100',
        ...         'family_name': 'ACTIVO',
        ...         'razonamiento': 'Inventario de materiales'
        ...     }
        ... ]
        >>> print(format_family_examples_for_prompt(examples, compressed=True))

        EJEMPLOS:
        1. "BOTELLAS PET" → 100 (inventario)

    Example (verbose format):
        >>> print(format_family_examples_for_prompt(examples, compressed=False))

        CLASIFICACIONES PREVIAS (aprende de estos patrones):

        1. "BOTELLAS PET 1L" → Familia 100 (ACTIVO)
           Razonamiento: Inventario de materiales
    """
    if not examples:
        return ""

    if compressed:
        # COMPRESSED FORMAT: ~50 tokens per example (vs ~150 in verbose)
        # "BOTELLAS PET" → 100 (inventario)
        lines = ["", "EJEMPLOS:"]

        for idx, ex in enumerate(examples, 1):
            descripcion = ex.get('descripcion', 'N/A')
            family_code = ex.get('family_code', 'N/A')
            razonamiento = ex.get('razonamiento', 'Sin razonamiento')

            # Truncate description to first 3-4 words (keep semantic core)
            desc_words = descripcion.split()[:4]
            short_desc = ' '.join(desc_words)

            # Extract key concept from razonamiento (first 2-3 words)
            reason_words = razonamiento.lower().split()[:3]
            short_reason = ' '.join(reason_words)

            lines.append(f'{idx}. "{short_desc}" → {family_code} ({short_reason})')

        return "\n".join(lines)

    else:
        # VERBOSE FORMAT: ~150 tokens per example (legacy)
        lines = [
            "",
            "CLASIFICACIONES PREVIAS (aprende de estos patrones):",
            ""
        ]

        for idx, ex in enumerate(examples, 1):
            descripcion = ex.get('descripcion', 'N/A')
            family_code = ex.get('family_code', 'N/A')
            family_name = ex.get('family_name', 'N/A')
            razonamiento = ex.get('razonamiento', 'Sin razonamiento')

            lines.append(f'{idx}. "{descripcion[:80]}" → Familia {family_code} ({family_name})')
            lines.append(f'   Razonamiento: {razonamiento}')
            lines.append('')

        return "\n".join(lines)
