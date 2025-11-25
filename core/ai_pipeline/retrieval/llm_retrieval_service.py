"""
LLM-Based Retrieval Service for Phase 2B (Solution A)

Replaces TF-IDF/embeddings with Claude Haiku LLM for candidate selection.

Advantages:
- Uses ALL context: provider name, ClaveProdServ, Phase 2A reasoning
- Semantic understanding (ODOO → software, not "plan" → retirement)
- Fast implementation (1 day vs 2-3 weeks for embeddings)
- Cost-effective: ~$0.001 per invoice

Disadvantages:
- Higher cost at scale (>10,000 invoices/month)
- Slower than embeddings (500ms vs 50ms)
- Not ideal for real-time batch processing

Use cases:
- Immediate accuracy improvement (20-40%)
- Baseline for comparing against embeddings
- Production use until embeddings are ready
"""

import logging
import json
from typing import Dict, Any, List, Optional
from anthropic import Anthropic

from core.shared.db_config import get_connection
from core.sat_catalog_service import get_sat_name

logger = logging.getLogger(__name__)


class LLMRetrievalService:
    """
    LLM-based candidate retrieval for Phase 2B.

    Uses Claude Haiku to intelligently select top candidates from a subfamily.
    """

    def __init__(self, model: str = "claude-sonnet-4-5-20250929"):
        """
        Initialize LLM retrieval service.

        Args:
            model: Claude model to use (default: Sonnet 4.5 for better reasoning/consistency)
        """
        self.client = Anthropic()
        self.model = model

    def retrieve_candidates(
        self,
        subfamily_code: str,
        subfamily_name: str,
        invoice_context: Dict[str, Any],
        phase2a_reasoning: Optional[str] = None,
        top_k: int = 15
    ) -> List[Dict[str, Any]]:
        """
        Retrieve top K candidates using LLM intelligence.

        Args:
            subfamily_code: Subfamily from Phase 2A (e.g., "602")
            subfamily_name: Subfamily name (e.g., "Gastos de administración")
            invoice_context: Full invoice context with provider, ClaveProdServ, etc.
            phase2a_reasoning: Reasoning from Phase 2A for threading
            top_k: Number of candidates to return (default: 15)

        Returns:
            List of candidate accounts in format:
            [
                {
                    "code": "602.84",
                    "name": "Gastos de tecnología",
                    "description": "...",
                    "family_hint": "602",
                    "score": 0.95,
                    "llm_reasoning": "..."
                },
                ...
            ]
        """
        try:
            # 1. Query ALL accounts in the subfamily from database
            all_accounts = self._query_subfamily_accounts(subfamily_code)

            if not all_accounts:
                logger.warning(
                    f"No accounts found for subfamily {subfamily_code}, "
                    f"falling back to broader query"
                )
                # Fallback: query family instead
                family_code = subfamily_code[0] + "00"
                all_accounts = self._query_family_accounts(family_code)

            if not all_accounts:
                logger.error(f"No accounts found for family {subfamily_code[0]}00")
                return []

            logger.info(
                f"LLM Retrieval: Found {len(all_accounts)} accounts in subfamily {subfamily_code}"
            )

            # 2. Build enriched context for LLM
            enriched_context = self._build_enriched_context(
                invoice_context,
                subfamily_code,
                subfamily_name,
                phase2a_reasoning
            )

            # 3. Call LLM to select top candidates
            selected_candidates = self._llm_select_candidates(
                enriched_context,
                all_accounts,
                top_k
            )

            logger.info(
                f"LLM Retrieval: Selected {len(selected_candidates)} candidates. "
                f"Top: {selected_candidates[0]['code']} - {selected_candidates[0]['name']}"
            )

            return selected_candidates

        except Exception as e:
            logger.error(f"LLM retrieval failed: {e}", exc_info=True)
            return []

    def _query_subfamily_accounts(self, subfamily_code: str) -> List[Dict[str, Any]]:
        """
        Query all accounts in a subfamily from PostgreSQL.

        Args:
            subfamily_code: 3-digit subfamily code (e.g., "602")

        Returns:
            List of accounts with code, name, description
        """
        try:
            conn = get_connection(dict_cursor=True)
            cursor = conn.cursor()

            # Query accounts starting with subfamily code (e.g., 602.XX)
            cursor.execute("""
                SELECT code, name, description
                FROM sat_account_embeddings
                WHERE code LIKE %s
                ORDER BY code
            """, (f"{subfamily_code}.%",))

            accounts = []
            for row in cursor.fetchall():
                accounts.append({
                    'code': row['code'],
                    'name': row['name'],
                    'description': row.get('description', '')
                })

            cursor.close()
            conn.close()

            return accounts

        except Exception as e:
            logger.error(f"Database query failed for subfamily {subfamily_code}: {e}")
            return []

    def _query_family_accounts(self, family_code: str) -> List[Dict[str, Any]]:
        """
        Query all accounts in a family from PostgreSQL (fallback).

        Args:
            family_code: 3-digit family code (e.g., "600")

        Returns:
            List of accounts with code, name, description
        """
        try:
            conn = get_connection(dict_cursor=True)
            cursor = conn.cursor()

            # Query accounts in family range (e.g., 600-699)
            cursor.execute("""
                SELECT code, name, description
                FROM sat_account_embeddings
                WHERE family_hint = %s
                ORDER BY code
                LIMIT 200
            """, (family_code,))

            accounts = []
            for row in cursor.fetchall():
                accounts.append({
                    'code': row['code'],
                    'name': row['name'],
                    'description': row.get('description', '')
                })

            cursor.close()
            conn.close()

            return accounts

        except Exception as e:
            logger.error(f"Database query failed for family {family_code}: {e}")
            return []

    def _build_enriched_context(
        self,
        invoice_context: Dict[str, Any],
        subfamily_code: str,
        subfamily_name: str,
        phase2a_reasoning: Optional[str]
    ) -> Dict[str, Any]:
        """
        Build enriched context for LLM including ALL available metadata.

        This is the key advantage over TF-IDF: we can use EVERYTHING.
        """
        # Extract invoice fields
        provider_name = invoice_context.get('provider_name', 'N/A')
        provider_rfc = invoice_context.get('provider_rfc', 'N/A')
        description = invoice_context.get('description', 'N/A')
        clave_prod_serv = invoice_context.get('clave_prod_serv', 'N/A')
        amount = invoice_context.get('amount', 0)
        uso_cfdi = invoice_context.get('uso_cfdi', 'N/A')
        payment_method = invoice_context.get('payment_method', 'N/A')

        # Get SAT catalog name for ClaveProdServ
        sat_name = None
        if clave_prod_serv and clave_prod_serv != 'N/A':
            sat_name = get_sat_name(clave_prod_serv)

        # Build enriched text
        enriched_text = f"Proveedor: {provider_name}"

        if provider_rfc and provider_rfc != 'N/A':
            enriched_text += f" (RFC: {provider_rfc})"

        enriched_text += f"\nDescripción: {description}"

        if clave_prod_serv and clave_prod_serv != 'N/A':
            enriched_text += f"\nClave SAT: {clave_prod_serv}"
            if sat_name:
                enriched_text += f" ({sat_name})"

        enriched_text += f"\nMonto: ${amount:,.2f} MXN"

        if uso_cfdi and uso_cfdi != 'N/A':
            enriched_text += f"\nUsoCFDI: {uso_cfdi}"

        if payment_method and payment_method != 'N/A':
            enriched_text += f"\nForma de pago: {payment_method}"

        # Add Phase 2A threading
        if phase2a_reasoning:
            enriched_text += f"\n\nRazonamiento Fase 2A:\n{phase2a_reasoning}"

        return {
            'enriched_text': enriched_text,
            'subfamily_code': subfamily_code,
            'subfamily_name': subfamily_name,
            'provider_name': provider_name,
            'clave_prod_serv': clave_prod_serv,
            'sat_name': sat_name,
            'description': description,
        }

    def _llm_select_candidates(
        self,
        enriched_context: Dict[str, Any],
        all_accounts: List[Dict[str, Any]],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """
        Use Claude Haiku to intelligently select top K candidates.

        This is where the magic happens: LLM understands context.
        """
        # Build account list for LLM
        account_list_text = ""
        for i, account in enumerate(all_accounts, 1):
            account_list_text += f"\n{i}. {account['code']} - {account['name']}"
            if account.get('description'):
                account_list_text += f"\n   {account['description'][:100]}"

        # Build prompt
        prompt = f"""Eres un contador experto mexicano. Analiza esta factura y selecciona las {top_k} cuentas SAT MÁS RELEVANTES de la subfamilia {enriched_context['subfamily_code']} ({enriched_context['subfamily_name']}).

FACTURA:
{enriched_context['enriched_text']}

CUENTAS DISPONIBLES en subfamilia {enriched_context['subfamily_code']}:
{account_list_text}

INSTRUCCIONES:
1. Analiza el proveedor, descripción, ClaveProdServ y razonamiento de Fase 2A
2. Selecciona las {top_k} cuentas MÁS RELEVANTES (ordenadas de más a menos relevante)
3. Explica brevemente POR QUÉ cada cuenta es relevante

EJEMPLOS DE RAZONAMIENTO CORRECTO:
- ODOO TECHNOLOGIES + ClaveSAT 81112500 (software) → Cuenta de tecnología/software, NO jubilación
- AMAZON WEB SERVICES + Storage → Cuenta de tecnología/hosting, NO almacenamiento físico
- PASE + Recarga → Cuenta de casetas/peajes, NO recarga celular

RESPONDE EN JSON:
{{
  "selected_accounts": [
    {{
      "code": "602.84",
      "rank": 1,
      "relevance_score": 0.95,
      "reasoning": "Por qué es la más relevante (1-2 oraciones)"
    }},
    ...
  ],
  "selection_methodology": "Explicación general de cómo seleccionaste (2-3 oraciones)"
}}

IMPORTANTE:
- Usa TODO el contexto (proveedor + ClaveProdServ + razonamiento)
- NO te dejes engañar por coincidencias léxicas ("plan" → "plan de jubilación")
- Entiende el TIPO DE NEGOCIO del proveedor"""

        try:
            # Call Claude Haiku
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                temperature=0.0,  # Deterministic for consistency
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            # Parse JSON response
            response_text = response.content[0].text.strip()

            # Extract JSON from markdown code blocks if present
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            result = json.loads(response_text)

            # Transform to expected format
            selected_candidates = []
            for item in result.get('selected_accounts', [])[:top_k]:
                code = item.get('code')

                # Find account in original list
                account = next((a for a in all_accounts if a['code'] == code), None)

                if account:
                    selected_candidates.append({
                        'code': code,
                        'name': account['name'],
                        'description': account.get('description', ''),
                        'family_hint': code.split('.')[0] if '.' in code else code[:3],
                        'score': item.get('relevance_score', 0.9),
                        'llm_reasoning': item.get('reasoning', ''),
                        'rank': item.get('rank', 0)
                    })

            # Log methodology for debugging
            methodology = result.get('selection_methodology', '')
            if methodology:
                logger.info(f"LLM Selection Methodology: {methodology}")

            return selected_candidates

        except Exception as e:
            logger.error(f"LLM candidate selection failed: {e}", exc_info=True)

            # Fallback: return first top_k accounts with low scores
            fallback = []
            for account in all_accounts[:top_k]:
                fallback.append({
                    'code': account['code'],
                    'name': account['name'],
                    'description': account.get('description', ''),
                    'family_hint': account['code'].split('.')[0] if '.' in account['code'] else account['code'][:3],
                    'score': 0.5,  # Low score to indicate fallback
                    'llm_reasoning': 'Fallback: LLM selection failed'
                })

            return fallback


def retrieve_candidates_with_llm(
    subfamily_code: str,
    subfamily_name: str,
    invoice_context: Dict[str, Any],
    phase2a_reasoning: Optional[str] = None,
    top_k: int = 15
) -> List[Dict[str, Any]]:
    """
    Convenience function to retrieve candidates using LLM.

    Args:
        subfamily_code: Subfamily from Phase 2A (e.g., "602")
        subfamily_name: Subfamily name (e.g., "Gastos de administración")
        invoice_context: Full invoice context
        phase2a_reasoning: Reasoning from Phase 2A
        top_k: Number of candidates to return

    Returns:
        List of candidate accounts
    """
    service = LLMRetrievalService()
    return service.retrieve_candidates(
        subfamily_code=subfamily_code,
        subfamily_name=subfamily_name,
        invoice_context=invoice_context,
        phase2a_reasoning=phase2a_reasoning,
        top_k=top_k
    )


__all__ = ['LLMRetrievalService', 'retrieve_candidates_with_llm']
