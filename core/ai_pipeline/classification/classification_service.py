"""
Classification Service - Orchestrates embeddings search + LLM classification

This module integrates:
1. Embeddings search (account_catalog.py) - to retrieve SAT account candidates
2. LLM classifier (expense_llm_classifier.py) - to choose the best SAT code
3. Company context injection - for industry-specific reasoning
4. Correction memory - for auto-apply learned patterns

This is the production-ready implementation requested in Option 2.
"""

import logging
from typing import Dict, Any, List, Optional
from core.accounting.account_catalog import retrieve_relevant_accounts
from core.ai_pipeline.classification.expense_llm_classifier import ExpenseLLMClassifier, ClassificationResult
from core.ai_pipeline.classification.family_classifier import get_family_classifier, FamilyClassificationResult
from core.ai_pipeline.classification.subfamily_classifier import SubfamilyClassifier, SubfamilyClassificationResult
from core.ai_pipeline.classification.classification_learning import get_auto_classification_from_history
from core.ai_pipeline.classification.model_selector import (
    get_model_selector,
    select_model_for_sat_account
)
from core.shared.company_context import get_company_classification_context
from config.config import config

logger = logging.getLogger(__name__)

# Import LLM retrieval service (Solution A)
try:
    from core.ai_pipeline.retrieval import retrieve_candidates_with_llm
    LLM_RETRIEVAL_AVAILABLE = True
except ImportError:
    LLM_RETRIEVAL_AVAILABLE = False
    logger.warning("LLM retrieval service not available, falling back to embeddings")


class ClassificationService:
    """
    Production-ready classification service with embeddings integration.

    Flow:
    1. Build expense snapshot from parsed_data
    2. Retrieve SAT account candidates via embeddings search
    3. Check correction memory for auto-apply patterns
    4. If no auto-apply → Call LLM classifier with company context
    5. Return classification result
    """

    def __init__(self):
        # Don't initialize classifier here - we'll create it with the right model for each request
        self.family_classifier = get_family_classifier()  # Always uses Haiku (cheap for simple task)
        self.subfamily_classifier = SubfamilyClassifier()  # Phase 2A: Subfamily classification
        self.model_selector = get_model_selector()  # Adaptive selector for SAT classification

    def classify_invoice(
        self,
        session_id: str,
        company_id: int,
        parsed_data: Dict[str, Any],
        top_k: int = 10
    ) -> Optional[ClassificationResult]:
        """
        Classify an invoice using embeddings + LLM.

        Args:
            session_id: Invoice session ID
            company_id: Company ID (integer)
            parsed_data: Parsed CFDI data from universal_invoice_engine
            top_k: Number of candidate SAT accounts to retrieve

        Returns:
            ClassificationResult with SAT code, confidence, explanation
            None if classification failed
        """
        try:
            # 1. Build expense snapshot from parsed_data
            snapshot = self._build_expense_snapshot(company_id, parsed_data)

            if not snapshot:
                logger.warning(f"Session {session_id}: Cannot build expense snapshot from parsed_data")
                return None

            # 2. LEARNING PHASE: Check if we've seen this before (fastest, cheapest, most accurate)
            # Before doing any expensive operations (family classification, embeddings, LLM),
            # check if we have a high-confidence match in our learning history
            tenant_id = parsed_data.get('tenant_id') or parsed_data.get('receptor', {}).get('tenant_id', 1)
            nombre_emisor = snapshot.get('provider_name', '')
            concepto = snapshot.get('description', '')

            if nombre_emisor and concepto:
                logger.info(f"Session {session_id}: Checking learning history for auto-classification")
                learned_match = get_auto_classification_from_history(
                    company_id=company_id,
                    tenant_id=tenant_id,
                    nombre_emisor=nombre_emisor,
                    concepto=concepto,
                    min_confidence=0.92  # 92% similarity required for auto-apply
                )

                if learned_match:
                    # We found a high-confidence match! Skip LLM entirely
                    logger.info(
                        f"Session {session_id}: AUTO-APPLIED from learning history: "
                        f"{learned_match.sat_account_code} - {learned_match.sat_account_name} "
                        f"(similarity: {learned_match.similarity_score:.2%}, source: {learned_match.validation_type})"
                    )

                    # Return immediately with learned classification
                    result = ClassificationResult(
                        sat_account_code=learned_match.sat_account_code,
                        sat_account_name=learned_match.sat_account_name,
                        family_code=learned_match.family_code,
                        confidence_sat=learned_match.confidence,
                        confidence_family=1.0,  # We know the family from the account code
                        model_version='learning-history',
                        explanation_short=f"Auto-aplicado por historial de aprendizaje (similitud: {learned_match.similarity_score:.0%})",
                        explanation_detail=(
                            f"Esta clasificación fue aplicada automáticamente basándose en un caso similar previo:\n"
                            f"- Proveedor similar: {learned_match.source_emisor}\n"
                            f"- Concepto similar: {learned_match.source_concepto}\n"
                            f"- Similitud semántica: {learned_match.similarity_score:.2%}\n"
                            f"- Fuente de validación: {learned_match.validation_type}\n\n"
                            f"Esta clasificación fue validada previamente y se aplicó automáticamente "
                            f"para ahorrar tiempo y mantener consistencia."
                        ),
                        alternative_candidates=[],
                        metadata={
                            'auto_applied': True,
                            'learning_similarity': learned_match.similarity_score,
                            'learning_source': learned_match.validation_type,
                            'source_emisor': learned_match.source_emisor,
                            'source_concepto': learned_match.source_concepto
                        }
                    )
                    return result
                else:
                    logger.info(f"Session {session_id}: No high-confidence match in learning history, proceeding with LLM classification")

            # 3. HIERARCHICAL PHASE 1: Classify to family level (100-800)
            # This narrows down the search space for embeddings + LLM
            family_result = None
            try:
                logger.info(f"Session {session_id}: Running hierarchical family classification (Phase 1)")

                # Build invoice data for family classifier
                # NEW: Use enriched multi-concept description for better LLM context
                enriched_desc_parts = []
                all_conceptos = snapshot.get('all_conceptos', [])

                if all_conceptos and len(all_conceptos) > 0:
                    # Primary concept (highest amount)
                    primary = all_conceptos[0]
                    primary_desc = primary.get('descripcion', '')
                    primary_sat = primary.get('sat_name', '')
                    primary_pct = primary.get('percentage', 0)

                    if primary_desc:
                        if primary_sat:
                            enriched_desc_parts.append(f"{primary_desc} ({primary_pct:.1f}% - {primary_sat})")
                        else:
                            enriched_desc_parts.append(f"{primary_desc} ({primary_pct:.1f}%)")

                    # Additional concepts if any
                    if len(all_conceptos) > 1:
                        additional_descs = []
                        for concepto in all_conceptos[1:]:
                            desc = concepto.get('descripcion', '')
                            pct = concepto.get('percentage', 0)
                            if desc:
                                if pct >= 5.0:
                                    additional_descs.append(f"{desc} ({pct:.1f}%)")
                                else:
                                    additional_descs.append(desc)

                        if additional_descs:
                            enriched_desc_parts.append(f"Adicionales: {', '.join(additional_descs)}")

                # Combine or fallback to original
                enriched_description = ' | '.join(enriched_desc_parts) if enriched_desc_parts else snapshot['description']

                invoice_data_for_family = {
                    'descripcion': enriched_description,
                    'proveedor': snapshot['provider_name'],
                    'rfc_proveedor': snapshot.get('provider_rfc', ''),
                    'clave_prod_serv': snapshot.get('clave_prod_serv', ''),
                    'monto': snapshot['amount'],
                    'uso_cfdi': snapshot.get('uso_cfdi', ''),
                    'metodo_pago': snapshot.get('payment_type', ''),  # NEW: Add payment method for Phase 2A
                    'forma_pago': snapshot.get('payment_method', ''),
                }

                family_result = self.family_classifier.classify(
                    invoice_data=invoice_data_for_family,
                    company_id=company_id,
                    tenant_id=None
                )

                logger.info(
                    f"Session {session_id}: Family classification → {family_result.familia_codigo} "
                    f"({family_result.familia_nombre}) - Confidence: {family_result.confianza:.2%}"
                )

                if family_result.override_uso_cfdi:
                    logger.warning(
                        f"Session {session_id}: UsoCFDI override detected - "
                        f"Reason: {family_result.override_razon}"
                    )

            except Exception as e:
                logger.warning(f"Session {session_id}: Family classification failed: {e}, using default families")
                family_result = None

            # 3.5. HIERARCHICAL PHASE 2A: Classify to subfamily level (601, 602, 603...)
            # This further narrows down the search space from family (600) to subfamily (603)
            # Provides 96% candidate reduction for embedding search
            subfamily_result = None
            try:
                if family_result and family_result.confianza >= 0.80:
                    logger.info(f"Session {session_id}: Running hierarchical subfamily classification (Phase 2A)")

                    # Load company context for Phase 2A (reuse from family classifier if available)
                    company_context = None
                    try:
                        company_context = get_company_classification_context(company_id)
                        if company_context:
                            industry_desc = company_context.get('industry_description') or company_context.get('industry', 'N/A')
                            logger.info(f"Session {session_id}: Loaded company context for Phase 2A: {industry_desc}")
                    except Exception as e:
                        logger.warning(f"Session {session_id}: Could not load company context for Phase 2A: {e}")

                    # Log enriched description for Phase 2A
                    logger.info(
                        f"Session {session_id}: Phase 2A INPUT → Descripción: '{invoice_data_for_family['descripcion']}'"
                    )

                    subfamily_result = self.subfamily_classifier.classify(
                        invoice_data=invoice_data_for_family,
                        family_code=family_result.familia_codigo,
                        family_name=family_result.familia_nombre,
                        family_confidence=family_result.confianza,
                        family_reasoning=family_result.razonamiento_principal,  # NEW: Pass Phase 1 reasoning for continuity
                        company_context=company_context,  # NEW: Pass company context
                    )

                    logger.info(
                        f"Session {session_id}: Subfamily classification → {subfamily_result.subfamily_code} "
                        f"({subfamily_result.subfamily_name}) - Confidence: {subfamily_result.confidence:.2%}"
                    )

                    if subfamily_result.requires_human_review:
                        logger.warning(
                            f"Session {session_id}: Subfamily classification has low confidence - "
                            f"requires human review"
                        )
                else:
                    logger.info(
                        f"Session {session_id}: Skipping subfamily classification - "
                        f"family confidence too low or not available"
                    )

            except Exception as e:
                logger.warning(f"Session {session_id}: Subfamily classification failed: {e}, proceeding without it")
                subfamily_result = None

            # 4. PHASE 2B: Retrieve SAT account candidates
            # Two strategies available:
            # - Solution A (LLM): Intelligent retrieval using Claude Haiku (fast, accurate, ~$0.001/invoice)
            # - Solution B (Embeddings): Semantic search using sentence-transformers (scalable, free after setup)

            # Check if we should use LLM retrieval (Solution A)
            use_llm_retrieval = (
                config.USE_LLM_RETRIEVAL and
                LLM_RETRIEVAL_AVAILABLE and
                subfamily_result and
                subfamily_result.confidence >= 0.85
            )

            if use_llm_retrieval:
                # SOLUTION A: LLM-based intelligent retrieval
                logger.info(
                    f"Session {session_id}: Using LLM-based retrieval (Solution A) for subfamily "
                    f"{subfamily_result.subfamily_code} ({subfamily_result.subfamily_name})"
                )

                candidates_raw = retrieve_candidates_with_llm(
                    subfamily_code=subfamily_result.subfamily_code,
                    subfamily_name=subfamily_result.subfamily_name,
                    invoice_context=snapshot,
                    phase2a_reasoning=subfamily_result.reasoning,
                    top_k=top_k
                )

                filtering_method = 'llm_intelligent_retrieval'
                filter_used = subfamily_result.subfamily_code

                if not candidates_raw:
                    logger.warning(
                        f"Session {session_id}: LLM retrieval failed, falling back to embeddings"
                    )
                    use_llm_retrieval = False  # Trigger fallback below

            if not use_llm_retrieval:
                # SOLUTION B (CURRENT): Embedding-based retrieval (fallback or default)
                # Build payload for embeddings search
                expense_payload = self._build_embeddings_payload(snapshot)

                # Determine filtering strategy based on Phase 1/2A results
                if subfamily_result and subfamily_result.confidence >= 0.85:
                    # BEST CASE: Use Phase 2A subfamily classification for precise filtering
                    family_filter = [subfamily_result.subfamily_code]
                    logger.info(
                        f"Session {session_id}: Using hierarchical SUBFAMILY filter (Phase 2A) → "
                        f"{subfamily_result.subfamily_code} ({subfamily_result.subfamily_name})"
                    )
                    filtering_method = 'hierarchical_subfamily_based'
                    filter_used = subfamily_result.subfamily_code
                elif family_result and family_result.confianza >= 0.80:
                    # GOOD: Use Phase 1 family classification to filter by subfamilies
                    family_filter = self._get_subfamilies_for_family(family_result.familia_codigo)
                    logger.info(
                        f"Session {session_id}: Using hierarchical FAMILY filter (Phase 1) → "
                        f"{family_result.familia_codigo} (subfamilies: {len(family_filter)})"
                    )
                    filtering_method = 'hierarchical_family_based'
                    filter_used = family_result.familia_codigo
                else:
                    # FALLBACK: use dynamic filter across multiple families
                    family_filter = self._get_default_family_filter()
                    logger.info(
                        f"Session {session_id}: Using dynamic fallback filter "
                        f"({len(family_filter)} subfamilies from families 100, 500, 600)"
                    )
                    filtering_method = 'dynamic_fallback'
                    filter_used = None

                candidates_raw = retrieve_relevant_accounts(
                    expense_payload=expense_payload,
                    top_k=top_k,
                    family_filter=family_filter
                )

            if not candidates_raw:
                logger.warning(f"Session {session_id}: No SAT account candidates found")
                return None

            # Transform candidates to format expected by LLM classifier
            # Classifier expects: code, name, family_hint, score, description
            candidates = self._transform_candidates(candidates_raw)

            logger.info(
                f"Session {session_id}: Retrieved {len(candidates)} candidates. "
                f"Top candidate: {candidates[0]['code']} - {candidates[0]['name']} (score: {candidates[0]['score']:.2f})"
            )

            # Track Phase 2A (Subfamily) and Phase 2B (Filtering) metadata for observability
            # Note: filtering_method and filter_used are already set in Phase 2B logic above
            phase2a_metadata = {
                'subfamily_code': subfamily_result.subfamily_code if subfamily_result else None,
                'subfamily_name': subfamily_result.subfamily_name if subfamily_result else None,
                'confidence': subfamily_result.confidence if subfamily_result else None,  # Changed from 'subfamily_confidence' to 'confidence' for consistency
                'requires_human_review': subfamily_result.requires_human_review if subfamily_result else None,
                'shortlist_size': subfamily_result.shortlist_size if subfamily_result else None,
                'reasoning': subfamily_result.reasoning if subfamily_result else None,  # NEW: LLM reasoning
                'alternative_subfamilies': subfamily_result.alternative_subfamilies if subfamily_result else None,  # NEW: Alternatives considered
            } if subfamily_result else None

            phase2b_metadata = {
                'filtering_method': filtering_method,
                'filter_used': filter_used,
                'candidates_before': top_k,
                'candidates_filtered': len(candidates),
                'reduction_percentage': ((top_k - len(candidates)) / top_k * 100) if top_k > 0 else 0,
                'sample_candidates': [
                    {'code': c['code'], 'name': c['name'], 'score': c['score']}
                    for c in candidates[:5]
                ] if candidates else []
            }

            # 5. MODEL SELECTION: Using Haiku for SAT classification (temporary - Sonnet not available)
            # Adaptive selection disabled temporarily for testing
            selected_model = "claude-3-5-haiku-20241022"
            selection_reason = "Testing mode: Using Haiku temporarily (Sonnet not available)"

            logger.info(
                f"Session {session_id}: Model selected for SAT classification: HAIKU (temporary)"
            )

            # 6. Call LLM classifier with selected model
            # Pass hierarchical family result to LLM for hard constraint enforcement
            classifier = ExpenseLLMClassifier(model=selected_model)
            result = classifier.classify(
                snapshot,
                candidates,
                hierarchical_family=family_result.familia_codigo if family_result and family_result.confianza >= 0.80 else None,
                subfamily_reasoning=subfamily_result.reasoning if subfamily_result else None
            )

            # Track Phase 3 metadata for observability
            phase3_metadata = {
                'model_used': selected_model,
                'top_k_considered': len(candidates),
                'tokens_used': getattr(result, 'tokens_used', None),
                'top_candidates': [
                    {
                        'code': c['code'],
                        'name': c['name'],
                        'score': c.get('score', 0),
                        'family_hint': c.get('family_hint', '')
                    }
                    for c in candidates[:10]  # Top 10 candidates evaluated
                ],
                'reasoning': getattr(result, 'explanation_short', None),
                'hierarchical_family_constraint': family_result.familia_codigo if family_result and family_result.confianza >= 0.80 else None
            }

            # 7. Attach hierarchical phase 1, 2, 3 metadata + model selection metadata to result
            if family_result:
                result.hierarchical_phase1 = {
                    'family_code': family_result.familia_codigo,
                    'family_name': family_result.familia_nombre,
                    'confidence': family_result.confianza,
                    'reasoning': family_result.razonamiento_principal,  # Phase 1 reasoning for threading to Phase 2A
                    'override_uso_cfdi': family_result.override_uso_cfdi,
                    'override_reason': family_result.override_razon,
                    'uso_cfdi_declared': snapshot.get('uso_cfdi'),
                    'requires_human_review': family_result.requiere_revision_humana,
                }

            # Attach Phase 2A metadata (subfamily classification)
            if phase2a_metadata:
                result.hierarchical_phase2a = phase2a_metadata

            # Attach Phase 2B metadata (account filtering)
            result.hierarchical_phase2b = phase2b_metadata

            # Attach Phase 3 metadata (specific account selection)
            result.hierarchical_phase3 = phase3_metadata

            # Attach model selection metadata
            if not hasattr(result, 'metadata'):
                result.metadata = {}
            result.metadata['selected_model'] = selected_model
            result.metadata['model_selection_reason'] = selection_reason

            logger.info(
                f"Session {session_id}: Classification result: {result.sat_account_code} "
                f"(confidence: {result.confidence_sat:.2%})"
            )

            return result

        except Exception as e:
            logger.error(f"Session {session_id}: Classification failed: {e}", exc_info=True)
            return None

    def _build_expense_snapshot(self, company_id: int, parsed_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Build expense snapshot from parsed CFDI data.

        This is the format expected by ExpenseLLMClassifier.classify()

        When invoice has multiple concepts, uses the one with highest amount
        as the primary classification target (e.g., for PASE invoices with
        "RECARGA IDMX" $336 + "COMISION" $8.62, we classify based on the toll).
        """
        if not parsed_data:
            return None

        emisor = parsed_data.get('emisor', {})
        conceptos = parsed_data.get('conceptos', [])
        total_factura = float(parsed_data.get('total', 0))

        # MEJORA: Use concept with highest amount, not just first one
        # This handles invoices like PASE that mix different expense types
        concepto = None
        if conceptos:
            if len(conceptos) == 1:
                concepto = conceptos[0]
            else:
                # Multiple concepts: choose the one with highest amount
                concepto = max(conceptos, key=lambda c: float(c.get('importe', 0)))
                logger.info(f"Invoice has {len(conceptos)} concepts, using highest amount: "
                           f"{concepto.get('descripcion', 'N/A')} (${concepto.get('importe', 0)})")

        if not concepto:
            concepto = {}

        # NEW: Process ALL concepts for enriched embedding payload
        # Calculate percentage and enrich each concept
        all_conceptos_enriched = []
        for c in conceptos:
            importe = float(c.get('importe', 0))
            percentage = (importe / total_factura * 100) if total_factura > 0 else 0

            # Get SAT name for this concept's clave_prod_serv
            clave = c.get('clave_prod_serv')
            sat_name = None
            if clave:
                from core.sat_catalog_service import get_sat_name
                sat_name = get_sat_name(clave)

            all_conceptos_enriched.append({
                'descripcion': c.get('descripcion', ''),
                'importe': importe,
                'percentage': percentage,
                'clave_prod_serv': clave,
                'sat_name': sat_name,
                'cantidad': c.get('cantidad', 1),
                'unidad': c.get('unidad', ''),
            })

        # Sort by importe descending (highest first)
        all_conceptos_enriched.sort(key=lambda x: x['importe'], reverse=True)

        # Extract key fields from primary concept
        description = concepto.get('descripcion', '')
        provider_name = emisor.get('nombre', '')
        provider_rfc = emisor.get('rfc', '')
        clave_prod_serv = concepto.get('clave_prod_serv')
        amount = total_factura

        # Extract UsoCFDI from receptor node (critical for classification validation)
        receptor = parsed_data.get('receptor', {})
        uso_cfdi = receptor.get('uso_cfdi') or parsed_data.get('uso_cfdi')

        if not description and not provider_name:
            logger.warning(f"Company {company_id}: Missing both description and provider_name")
            return None

        # NEW: Detect invoice direction (RECIBIDA vs EMITIDA) for proper classification
        # This is CRITICAL for material purchases: RECIBIDA = Inventory (115), EMITIDA = Cost of Sales (500)
        receptor_rfc = receptor.get('rfc', '')
        receptor_nombre = receptor.get('nombre', '')

        # ENRICH: Add SAT catalog name to description for better LLM classification
        enriched_description = description
        if clave_prod_serv:
            from core.sat_catalog_service import get_sat_name
            sat_name = get_sat_name(clave_prod_serv)
            if sat_name:
                enriched_description = f"{description} | Servicio SAT: {sat_name}"

        snapshot = {
            'company_id': company_id,
            'description': enriched_description,
            'descripcion_original': enriched_description,  # FIX: LLM expects this field name
            'provider_name': provider_name,
            'provider_rfc': provider_rfc,
            'clave_prod_serv': clave_prod_serv,
            'amount': amount,
            'uso_cfdi': uso_cfdi,  # NEW: UsoCFDI for validation against company context
            # Optional fields for better classification
            'payment_method': parsed_data.get('forma_pago'),
            'payment_type': parsed_data.get('metodo_pago'),
            'currency': parsed_data.get('moneda', 'MXN'),
            # NEW: Invoice direction context (CRITICAL for inventory vs cost of sales)
            'receptor_rfc': receptor_rfc,
            'receptor_nombre': receptor_nombre,
            'emisor_rfc': provider_rfc,  # Alias for consistency
            'emisor_nombre': provider_name,  # Alias for consistency
            # NEW: ALL concepts enriched for multi-concept embedding payload
            'all_conceptos': all_conceptos_enriched,
            'num_conceptos': len(all_conceptos_enriched),
        }

        return snapshot

    def _build_embeddings_payload(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build ENRICHED payload for embeddings search from expense snapshot.

        NEW: Multi-concept payload that includes ALL invoice concepts while
        maintaining weight/priority for the primary (highest amount) concept.

        This solves the "semantic signal loss" problem where invoices with multiple
        concepts lost valuable context by only using the highest-amount concept.
        """
        description_parts = []

        # Get all concepts (already sorted by importe descending)
        all_conceptos = snapshot.get('all_conceptos', [])
        num_conceptos = snapshot.get('num_conceptos', 0)

        if all_conceptos and len(all_conceptos) > 0:
            # PRIMARY CONCEPT (highest amount) - Give it prominence
            primary = all_conceptos[0]
            primary_desc = primary.get('descripcion', '')
            primary_sat = primary.get('sat_name', '')
            primary_pct = primary.get('percentage', 0)

            if primary_desc:
                if primary_sat:
                    description_parts.append(
                        f"Principal: {primary_desc} ({primary_pct:.1f}% - {primary_sat})"
                    )
                else:
                    description_parts.append(f"Principal: {primary_desc} ({primary_pct:.1f}%)")

            # ADDITIONAL CONCEPTS - Add for semantic richness
            if len(all_conceptos) > 1:
                additional_descs = []
                for concepto in all_conceptos[1:]:
                    desc = concepto.get('descripcion', '')
                    pct = concepto.get('percentage', 0)
                    if desc:
                        # Include percentage if significant (>5%)
                        if pct >= 5.0:
                            additional_descs.append(f"{desc} ({pct:.1f}%)")
                        else:
                            additional_descs.append(desc)

                if additional_descs:
                    description_parts.append(f"Adicionales: {' + '.join(additional_descs)}")

        else:
            # Fallback to old behavior if no all_conceptos available
            raw_description = snapshot.get('description', '')
            if raw_description:
                description_parts.append(raw_description)

        # Provider name (critical context)
        if snapshot.get('provider_name'):
            description_parts.append(f"Proveedor: {snapshot['provider_name']}")

        # Combine into rich description
        descripcion = " | ".join(description_parts) if description_parts else "compra de bienes o servicios"

        # Build metadata for additional context
        metadata = {}

        # Include primary clave_prod_serv for boost scoring
        if snapshot.get('clave_prod_serv'):
            metadata['clave_prod_serv'] = snapshot['clave_prod_serv']

        if snapshot.get('provider_rfc'):
            metadata['provider_rfc'] = snapshot['provider_rfc']

        if snapshot.get('amount'):
            metadata['amount'] = snapshot['amount']

        # NEW: Include number of concepts for debugging
        if num_conceptos > 0:
            metadata['num_conceptos'] = num_conceptos

        payload = {
            'descripcion': descripcion,
            'metadata': metadata
        }

        # Add optional fields if available
        if snapshot.get('payment_method'):
            payload['notas'] = f"Forma de pago: {snapshot['payment_method']}"

        return payload

    def _transform_candidates(self, candidates_raw: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Transform embeddings search results to format expected by LLM classifier.

        Input (from retrieve_relevant_accounts):
        {
            "code": "613.01",
            "name": "Servicios administrativos",
            "description": "...",
            "family_hint": "613",
            "score": 0.92,
            "version_tag": "v1.0",
            "distance": 0.08  # optional, pgvector only
        }

        Output (for ExpenseLLMClassifier):
        {
            "code": "613.01",
            "name": "Servicios administrativos",
            "family_hint": "613",
            "score": 0.92,
            "description": "..."
        }
        """
        transformed = []

        for raw in candidates_raw:
            transformed.append({
                'code': raw.get('code'),
                'name': raw.get('name'),
                'family_hint': raw.get('family_hint'),
                'score': raw.get('score', 0.0),
                'description': raw.get('description', '')
            })

        return transformed

    def _get_subfamilies_for_family(self, family_code: str) -> List[str]:
        """
        Map family code (100-800) to list of relevant subfamily codes.

        This mapping is based on the SAT account catalog structure.
        For received invoices (company is buying), we focus on:
        - Family 100 (Activo) → Fixed assets, intangibles
        - Family 500 (Costo de Ventas) → Production costs
        - Family 600 (Gastos de Operación) → Operating expenses

        Returns:
            List of subfamily codes (e.g., ['151', '152', ...] for family 100)
        """
        # Mapping: family_code → list of subfamilies
        FAMILY_TO_SUBFAMILIES = {
            # Family 100: ACTIVO (Assets)
            '100': [
                '151',  # Terrenos
                '152',  # Edificios
                '153',  # Maquinaria y equipo
                '154',  # Vehículos
                '155',  # Mobiliario y equipo de oficina
                '156',  # Equipo de cómputo
                '157',  # Equipo de comunicación
                '158',  # Activos biológicos
                '118',  # Activos intangibles
                '183',  # Gastos amortizables
                '184',  # Gastos diferidos
                '115',  # Inventario (sometimes treated as asset)
            ],

            # Family 500: COSTO DE VENTAS (Cost of Sales)
            '500': [
                '501',  # Costo de venta y/o servicio
                '502',  # Compras (purchases)
                '503',  # Devoluciones y bonificaciones
                '504',  # Otras cuentas de costos
                '505',  # Gastos de fabricación
            ],

            # Family 600: GASTOS DE OPERACIÓN (Operating Expenses)
            '600': [
                '601',  # Gastos de venta
                '602',  # Gastos de administración
                '603',  # Gastos de fabricación indirectos
                '604',  # Gastos financieros
                '605',  # Otros gastos
                '606',  # Pérdida en venta de activos
                '607',  # Gastos extraordinarios
                '608',  # Impuestos y derechos
                '609',  # Participación de utilidades
                '611',  # Depreciación y amortización
                '612',  # Servicios
                '613',  # Suministros y gastos
                '614',  # Arrendamientos
            ],

            # Family 200: PASIVO (Liabilities) - rare for received invoices
            '200': [],

            # Family 300: CAPITAL CONTABLE (Equity) - rare for received invoices
            '300': [],

            # Family 400: INGRESOS (Income) - NEVER for received invoices
            '400': [],

            # Family 700: RESULTADO INTEGRAL (Comprehensive Income) - rare
            '700': [],

            # Family 800: CUENTAS DE ORDEN (Memorandum Accounts) - rare
            '800': [],
        }

        subfamilies = FAMILY_TO_SUBFAMILIES.get(family_code, [])

        if not subfamilies:
            logger.warning(
                f"No subfamilies mapped for family {family_code}, "
                f"falling back to default families"
            )

        return subfamilies

    def _get_default_family_filter(self) -> List[str]:
        """
        Get default family filter for received invoices (facturas recibidas).

        Dynamically generated from FAMILY_TO_SUBFAMILIES to avoid hardcoding.
        """
        # Common families for received invoices (purchases/expenses/investments)
        common_families = ['100', '500', '600']  # Activos, Costos, Gastos

        subfamilies = []
        for family_code in common_families:
            subfamilies.extend(self._get_subfamilies_for_family(family_code))

        # Remove duplicates
        return list(set(subfamilies))


def classify_invoice_session(
    session_id: str,
    company_id: int,
    parsed_data: Dict[str, Any],
    top_k: int = 10
) -> Optional[Dict[str, Any]]:
    """
    Convenience function to classify an invoice and return classification dict.

    This is the function that should be called from universal_invoice_engine_system.py
    or from API endpoints.

    Args:
        session_id: Invoice session ID
        company_id: Company ID (integer)
        parsed_data: Parsed CFDI data from universal_invoice_engine
        top_k: Number of candidate SAT accounts to retrieve

    Returns:
        Classification dict ready for database storage:
        {
            'sat_account_code': '613.01',
            'family_code': '613',
            'confidence_sat': 0.92,
            'confidence_family': 0.95,
            'model_version': 'claude-sonnet-4.5',
            'explanation_short': '...',
            'explanation_detail': '...',
            'status': 'pending'
        }

        None if classification failed
    """
    service = ClassificationService()

    result = service.classify_invoice(
        session_id=session_id,
        company_id=company_id,
        parsed_data=parsed_data,
        top_k=top_k
    )

    if not result:
        return None

    # Look up SAT account name from catalog to avoid AI hallucinations
    sat_account_name = None
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        from config.config import config

        conn = psycopg2.connect(
            host=config.PG_HOST,
            port=config.PG_PORT,
            database=config.PG_DB,
            user=config.PG_USER,
            password=config.PG_PASSWORD
        )
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("""
            SELECT name FROM sat_account_embeddings
            WHERE code = %s
            LIMIT 1
        """, (result.sat_account_code,))

        row = cursor.fetchone()
        if row:
            sat_account_name = row['name']
            logger.info(f"Looked up SAT account name for {result.sat_account_code}: {sat_account_name}")
        else:
            logger.warning(f"SAT code {result.sat_account_code} not found in catalog")
            sat_account_name = result.sat_account_code  # Fallback to code if not found

        conn.close()
    except Exception as e:
        logger.error(f"Error looking up SAT account name: {e}")
        sat_account_name = result.sat_account_code  # Fallback to code on error

    # Convert ClassificationResult to dict for database storage
    classification_dict = {
        'sat_account_code': result.sat_account_code,
        'sat_account_name': sat_account_name,  # Add the official name from catalog
        'family_code': result.family_code,
        'confidence_sat': result.confidence_sat,
        'confidence_family': result.confidence_family,
        'model_version': result.model_version,
        'explanation_short': result.explanation_short,
        'explanation_detail': result.explanation_detail,
        'status': 'pending',  # Always start as pending, needs accountant confirmation
        'alternative_candidates': result.alternative_candidates,  # Add alternatives for UI dropdown
        'metadata': {
            'session_id': session_id,
            'company_id': company_id,
            'candidates_count': top_k,
            'hierarchical_phase1': getattr(result, 'hierarchical_phase1', None),
            'hierarchical_phase2a': getattr(result, 'hierarchical_phase2a', None),
            'hierarchical_phase2b': getattr(result, 'hierarchical_phase2b', None),
            'hierarchical_phase3': getattr(result, 'hierarchical_phase3', None)
        }
    }

    return classification_dict
