"""
Depreciation Rate Service - RAG-based fiscal regulation retrieval

This service determines depreciation rates for fixed assets using:
1. Semantic search over LISR Article 34 (Mexican tax law)
2. Vector embeddings for regulation matching
3. Structured data extraction for rates and legal basis

Author: System
Date: 2025-11-28
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict
import psycopg2
from psycopg2.extras import RealDictCursor
from sentence_transformers import SentenceTransformer
import numpy as np

logger = logging.getLogger(__name__)

@dataclass
class DepreciationRate:
    """
    Depreciation rate with fiscal and accounting treatments.

    Attributes:
        Fiscal rates (for SAT tax returns):
            annual_rate_fiscal: Annual percentage (e.g., 30.0 for 30%)
            years_fiscal: Useful life in years (e.g., 3.33)
            months_fiscal: Useful life in months (e.g., 40)

        Accounting rates (for financial statements):
            annual_rate_accounting: Annual percentage per NIF/company policy
            years_accounting: Accounting useful life
            months_accounting: Accounting months

        Legal basis:
            law_code: "LISR", "CFF", etc.
            article: Article number
            section: Fraction, paragraph, etc.
            article_text: Full legal text
            effective_date: When regulation became effective
            dof_url: Official source URL

        Context:
            asset_type: Internal type (equipo_computo, vehiculos, etc.)
            applies_to: List of asset descriptions
            reasoning: Explanation of why this rate applies
            confidence: Match confidence (0.0-1.0)
    """

    # Fiscal rates (LISR)
    annual_rate_fiscal: float
    years_fiscal: float
    months_fiscal: int

    # Accounting rates (NIF/Company policy)
    annual_rate_accounting: float
    years_accounting: float
    months_accounting: int

    # Legal basis
    law_code: str
    article: str
    section: str
    article_text: str
    effective_date: str
    dof_url: str

    # Context and reasoning
    asset_type: str
    applies_to: List[str]
    reasoning: str
    confidence: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


class DepreciationRateService:
    """
    Service for determining depreciation rates using RAG over fiscal regulations.

    Uses semantic search to find the most relevant LISR Article 34 provision
    and extracts structured depreciation data with legal backing.
    """

    def __init__(self, db_config: Optional[Dict[str, Any]] = None):
        """
        Initialize service with embeddings model and database config.

        Args:
            db_config: PostgreSQL connection config (uses default if None)
        """
        # Initialize sentence transformer for embeddings
        # Using multilingual model for Spanish fiscal text
        self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

        # Database config
        if db_config is None:
            from core.shared.db_config import POSTGRES_CONFIG
            self.db_config = POSTGRES_CONFIG
        else:
            self.db_config = db_config

        logger.info("DepreciationRateService initialized with multilingual embeddings model")

    def _get_connection(self):
        """Get PostgreSQL connection"""
        try:
            conn = psycopg2.connect(**self.db_config)
            return conn
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise

    def get_depreciation_rate(
        self,
        asset_description: str,
        sat_account_code: Optional[str] = None,
        sat_product_code: Optional[str] = None,
        amount: Optional[float] = None,
        provider_name: Optional[str] = None
    ) -> Optional[DepreciationRate]:
        """
        Determine depreciation rate using RAG over fiscal regulations.

        Process:
        1. Build enriched search query from asset context
        2. Generate embedding and search fiscal_regulations table
        3. Retrieve top matches with similarity scores
        4. Extract structured depreciation data
        5. Apply accounting policy adjustments if needed
        6. Return DepreciationRate with legal basis

        Args:
            asset_description: "Laptop Dell Precision 5570"
            sat_account_code: "156.01" (Equipo de cómputo)
            sat_product_code: "43211500" (Computadoras portátiles)
            amount: 50000.0
            provider_name: "Dell México"

        Returns:
            DepreciationRate with fiscal/accounting rates and legal basis
            None if service fails (falls back to default)

        Example:
            >>> service = DepreciationRateService()
            >>> rate = service.get_depreciation_rate(
            ...     asset_description="Laptop HP EliteBook",
            ...     sat_account_code="156.01"
            ... )
            >>> print(rate.annual_rate_fiscal)  # 30.0
            >>> print(rate.article)  # "34"
            >>> print(rate.section)  # "Fracción V"
        """
        try:
            # 1. Build enriched search query
            search_query = self._build_search_query(
                asset_description,
                sat_account_code,
                sat_product_code
            )

            logger.info(f"Searching depreciation rate for: {search_query}")

            # 2. Generate embedding
            query_embedding = self.model.encode(search_query)

            # 3. Semantic search in fiscal_regulations
            candidates = self._search_regulations(query_embedding)

            if not candidates:
                logger.warning(f"No fiscal regulations found for: {search_query}")
                return self._get_default_rate()

            # 4. Select best match
            best_match = candidates[0]
            similarity = best_match['similarity']

            logger.info(
                f"Best match: {best_match['law_code']} Art. {best_match['article_number']} "
                f"{best_match['section']} (similarity: {similarity:.2%})"
            )

            # 5. Extract structured data
            data = best_match['structured_data']

            # 6. Determine accounting rate (may differ from fiscal)
            accounting_rate, accounting_years, accounting_months = self._determine_accounting_rate(
                fiscal_rate=data['depreciation_rate_annual'],
                fiscal_years=data['depreciation_years'],
                asset_type=data.get('asset_type'),
                sat_account_code=sat_account_code,
                amount=amount
            )

            # 7. Build result
            result = DepreciationRate(
                # Fiscal (LISR)
                annual_rate_fiscal=data['depreciation_rate_annual'],
                years_fiscal=data['depreciation_years'],
                months_fiscal=data['depreciation_months'],

                # Accounting (NIF/Policy)
                annual_rate_accounting=accounting_rate,
                years_accounting=accounting_years,
                months_accounting=accounting_months,

                # Legal basis
                law_code=best_match['law_code'],
                article=best_match['article_number'],
                section=best_match['section'],
                article_text=best_match['content'],
                effective_date=str(best_match['effective_date']),
                dof_url=best_match['source_url'] or "https://www.diputados.gob.mx/LeyesBiblio/pdf/LISR.pdf",

                # Context
                asset_type=data.get('asset_type', 'unknown'),
                applies_to=data.get('applies_to', []),
                reasoning=self._build_reasoning(best_match, data, similarity, accounting_years != data['depreciation_years']),
                confidence=float(similarity)
            )

            logger.info(
                f"Depreciation rate determined: {result.annual_rate_fiscal}% fiscal "
                f"({result.years_fiscal} years), {result.annual_rate_accounting}% accounting "
                f"({result.years_accounting} years)"
            )

            return result

        except Exception as e:
            logger.error(f"Error determining depreciation rate: {e}", exc_info=True)
            return self._get_default_rate()

    def _build_search_query(
        self,
        asset_description: str,
        sat_account_code: Optional[str],
        sat_product_code: Optional[str]
    ) -> str:
        """
        Build enriched search query for semantic matching.

        Combines asset description with contextual keywords from SAT codes.
        """
        query_parts = [asset_description]

        # Add SAT account family context
        if sat_account_code:
            family = sat_account_code.split('.')[0]
            context_map = {
                "156": "equipo de cómputo procesamiento datos computadora laptop servidor",
                "155": "mobiliario equipo oficina muebles escritorio silla archivero",
                "154": "vehículos automotores transporte automóvil camioneta camión",
                "153": "maquinaria equipo industrial producción manufactura",
                "118": "activos intangibles software licencias derechos",
                "152": "edificios construcciones inmuebles",
                "151": "terrenos predios"
            }
            if family in context_map:
                query_parts.append(context_map[family])

        # Add SAT product code context (if available)
        if sat_product_code:
            # First 2 digits indicate major category
            prefix = sat_product_code[:2]
            product_context_map = {
                "43": "equipo cómputo electrónico tecnología",
                "25": "vehículos transporte automotor",
                "56": "mobiliario oficina muebles",
                "44": "equipo oficina comunicación",
                "31": "equipo industrial manufactura maquinaria"
            }
            if prefix in product_context_map:
                query_parts.append(product_context_map[prefix])

        return " ".join(query_parts)

    def _search_regulations(self, query_embedding: np.ndarray) -> List[Dict[str, Any]]:
        """
        Search fiscal_regulations using vector similarity.

        Returns top 3 candidates with similarity scores.
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            # Convert numpy array to list for psycopg2
            embedding_list = query_embedding.tolist()

            # Vector similarity search
            cursor.execute("""
                SELECT
                    id,
                    law_code,
                    article_number,
                    section,
                    title,
                    content,
                    structured_data,
                    asset_categories,
                    effective_date,
                    source_url,
                    1 - (content_embedding <=> %s::vector) as similarity
                FROM fiscal_regulations
                WHERE regulation_type = 'depreciation'
                  AND status = 'active'
                ORDER BY content_embedding <=> %s::vector
                LIMIT 3
            """, (embedding_list, embedding_list))

            results = cursor.fetchall()
            cursor.close()

            return results

        finally:
            conn.close()

    def _determine_accounting_rate(
        self,
        fiscal_rate: float,
        fiscal_years: float,
        asset_type: Optional[str],
        sat_account_code: Optional[str],
        amount: Optional[float]
    ) -> Tuple[float, float, int]:
        """
        Determine accounting depreciation rate (may differ from fiscal).

        Companies often use different rates for:
        - Financial statements (NIF - generally longer lives)
        - Tax returns (LISR - faster depreciation for tax benefits)

        This creates deferred tax assets/liabilities (ISR diferido).

        Returns:
            (annual_rate, years, months)
        """
        # Default: use same as fiscal
        accounting_rate = fiscal_rate
        accounting_years = fiscal_years
        accounting_months = int(fiscal_years * 12)

        # Policy: Extend useful life for certain asset types (conservative accounting)
        if asset_type == 'equipo_computo' or (sat_account_code and sat_account_code.startswith('156')):
            # Fiscal: 30% (3.33 years)
            # Accounting: 20% (5 years) - more conservative
            accounting_years = 5.0
            accounting_months = 60
            accounting_rate = 100.0 / accounting_years  # 20%

        elif asset_type == 'vehiculos' or (sat_account_code and sat_account_code.startswith('154')):
            # Fiscal: 25% (4 years)
            # Accounting: 20% (5 years)
            accounting_years = 5.0
            accounting_months = 60
            accounting_rate = 20.0

        return accounting_rate, accounting_years, accounting_months

    def _build_reasoning(
        self,
        regulation: Dict[str, Any],
        structured_data: Dict[str, Any],
        similarity: float,
        has_fiscal_accounting_diff: bool
    ) -> str:
        """Build human-readable reasoning for the depreciation rate"""
        reasoning_parts = [
            f"Según {regulation['law_code']} Artículo {regulation['article_number']} "
            f"{regulation['section']}: {regulation['title']}."
        ]

        reasoning_parts.append(
            f"Aplica tasa fiscal de {structured_data['depreciation_rate_annual']}% anual "
            f"({structured_data['depreciation_years']} años, {structured_data['depreciation_months']} meses)."
        )

        if has_fiscal_accounting_diff:
            reasoning_parts.append(
                "Nota: La tasa contable difiere de la fiscal según políticas NIF "
                "(genera ISR diferido)."
            )

        reasoning_parts.append(f"Confianza de coincidencia semántica: {similarity:.2%}.")

        return " ".join(reasoning_parts)

    def _get_default_rate(self) -> DepreciationRate:
        """
        Default depreciation rate when no match found.

        Uses LISR Article 34 Fraction XIII: 10% for general machinery/equipment.
        """
        return DepreciationRate(
            # Fiscal
            annual_rate_fiscal=10.0,
            years_fiscal=10.0,
            months_fiscal=120,

            # Accounting (same as fiscal for default)
            annual_rate_accounting=10.0,
            years_accounting=10.0,
            months_accounting=120,

            # Legal basis
            law_code="LISR",
            article="34",
            section="Fracción XIII",
            article_text=(
                "Tratándose de maquinaria y equipo distintos de los señalados en las "
                "fracciones anteriores, 10%."
            ),
            effective_date="2014-01-01",
            dof_url="https://www.diputados.gob.mx/LeyesBiblio/pdf/LISR.pdf",

            # Context
            asset_type="maquinaria_general",
            applies_to=["Maquinaria y equipo no especificado en otras fracciones"],
            reasoning=(
                "Tasa por defecto según LISR Art. 34 Fracción XIII: 10% anual para "
                "maquinaria y equipo en general (no se encontró coincidencia específica)."
            ),
            confidence=0.5
        )


# Singleton instance
_depreciation_service: Optional[DepreciationRateService] = None

def get_depreciation_rate_service() -> DepreciationRateService:
    """
    Get singleton instance of DepreciationRateService.

    Returns:
        Initialized DepreciationRateService instance
    """
    global _depreciation_service
    if _depreciation_service is None:
        _depreciation_service = DepreciationRateService()
    return _depreciation_service
