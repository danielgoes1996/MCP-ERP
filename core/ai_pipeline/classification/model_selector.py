#!/usr/bin/env python3
"""
Sistema de selección adaptativa de modelos LLM para clasificación.

Este módulo determina dinámicamente qué modelo Claude usar (Haiku vs Sonnet)
basándose en la complejidad del caso, optimizando costo vs precisión.
"""

import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ModelRecommendation:
    """Recomendación de modelo con justificación."""
    model_name: str
    reason: str
    complexity_score: float
    estimated_cost: float


class AdaptiveModelSelector:
    """
    Selector adaptativo de modelos Claude para clasificación.

    Estrategia:
    - Haiku 3.5: Casos simples y claros (70-80% de facturas)
    - Sonnet 3.5: Casos complejos, ambiguos o críticos (20-30%)
    """

    # Configuración de modelos
    MODELS = {
        'haiku': {
            'name': 'claude-3-5-haiku-20241022',
            'cost_per_call': 0.008,  # Promedio estimado
            'best_for': 'Casos simples con candidato claro'
        },
        'sonnet': {
            'name': 'claude-3-5-sonnet-20241022',
            'cost_per_call': 0.020,  # Promedio estimado
            'best_for': 'Casos complejos o ambiguos'
        }
    }

    # Umbrales de decisión
    THRESHOLDS = {
        'high_confidence_similarity': 0.90,  # Candidato muy claro
        'ambiguous_similarity_gap': 0.05,    # Gap mínimo entre top-2
        'multi_concept_threshold': 2,        # Múltiples conceptos
        'high_amount_threshold': 50000,      # Monto alto (MXN)
        'short_description_length': 3        # Descripción muy corta (ambigua)
    }

    def __init__(self):
        self.usage_stats = {
            'haiku_count': 0,
            'sonnet_count': 0,
            'total_cost': 0.0
        }

    def select_model_for_family_classification(self) -> ModelRecommendation:
        """
        Selecciona modelo para clasificación de familia (Nivel 2).

        Siempre usa Haiku porque:
        - Solo 8 opciones (100, 200, 300, 400, 500, 600, 700, 800)
        - Tarea de clasificación directa
        - Errores no son fatales (Nivel 3 puede refinar)
        """
        self.usage_stats['haiku_count'] += 1

        return ModelRecommendation(
            model_name=self.MODELS['haiku']['name'],
            reason="Clasificación de familia: tarea simple (8 opciones)",
            complexity_score=0.2,
            estimated_cost=0.003
        )

    def select_model_for_sat_classification(
        self,
        top_candidates: list,
        invoice_data: dict,
        provider_correction_history: Optional[Dict[str, int]] = None
    ) -> ModelRecommendation:
        """
        Selecciona modelo para clasificación SAT (Nivel 3).

        Args:
            top_candidates: Top-K cuentas SAT candidatas con similarity scores
            invoice_data: Datos de la factura (descripción, monto, etc.)
            provider_correction_history: Historial de correcciones por proveedor

        Returns:
            ModelRecommendation con modelo seleccionado y justificación
        """
        complexity_factors = self._assess_complexity(
            top_candidates,
            invoice_data,
            provider_correction_history
        )

        complexity_score = complexity_factors['total_score']
        reasons = complexity_factors['reasons']

        # DECISIÓN: Haiku vs Sonnet
        if complexity_score < 0.5:
            # CASO SIMPLE → HAIKU
            selected = 'haiku'
            self.usage_stats['haiku_count'] += 1

            reason = f"Caso simple (score: {complexity_score:.2f}): {', '.join(reasons[:2])}"

        else:
            # CASO COMPLEJO → SONNET
            selected = 'sonnet'
            self.usage_stats['sonnet_count'] += 1

            reason = f"Caso complejo (score: {complexity_score:.2f}): {', '.join(reasons)}"

        model_config = self.MODELS[selected]
        self.usage_stats['total_cost'] += model_config['cost_per_call']

        logger.info(
            f"Model selected: {selected.upper()} "
            f"(complexity: {complexity_score:.2f}, reason: {reason})"
        )

        return ModelRecommendation(
            model_name=model_config['name'],
            reason=reason,
            complexity_score=complexity_score,
            estimated_cost=model_config['cost_per_call']
        )

    def _assess_complexity(
        self,
        top_candidates: list,
        invoice_data: dict,
        provider_correction_history: Optional[Dict[str, int]]
    ) -> Dict[str, Any]:
        """
        Evalúa la complejidad del caso de clasificación.

        Returns:
            Dict con score total y lista de razones
        """
        score = 0.0
        reasons = []

        # FACTOR 1: Similitud del top candidate
        if top_candidates and len(top_candidates) > 0:
            top1_similarity = top_candidates[0].get('similarity', 0.0)

            if top1_similarity > self.THRESHOLDS['high_confidence_similarity']:
                # Candidato muy claro → Baja complejidad
                score += 0.0
                reasons.append(f"Top candidato claro ({top1_similarity:.0%})")
            else:
                # Candidato no tan claro → Alta complejidad
                score += 0.4
                reasons.append(f"Top candidato ambiguo ({top1_similarity:.0%})")

        # FACTOR 2: Gap entre top-2 candidatos
        if top_candidates and len(top_candidates) >= 2:
            top1_similarity = top_candidates[0].get('similarity', 0.0)
            top2_similarity = top_candidates[1].get('similarity', 0.0)
            gap = top1_similarity - top2_similarity

            if gap < self.THRESHOLDS['ambiguous_similarity_gap']:
                # Múltiples candidatos similares → Alta complejidad
                score += 0.3
                reasons.append(f"Gap pequeño entre candidatos ({gap:.0%})")

        # FACTOR 3: Descripción multi-concepto
        description = invoice_data.get('description', '')
        concept_count = description.count(',') + description.count(' y ')

        if concept_count >= self.THRESHOLDS['multi_concept_threshold']:
            # Múltiples conceptos → Alta complejidad
            score += 0.3
            reasons.append(f"Múltiples conceptos ({concept_count + 1})")

        # FACTOR 4: Descripción muy corta (ambigua)
        description_word_count = len(description.split())
        if description_word_count < self.THRESHOLDS['short_description_length']:
            # Descripción corta → Alta complejidad
            score += 0.2
            reasons.append(f"Descripción corta ({description_word_count} palabras)")

        # FACTOR 5: Monto alto (impacto contable)
        amount = invoice_data.get('amount', 0.0) or invoice_data.get('total', 0.0)
        if amount > self.THRESHOLDS['high_amount_threshold']:
            # Monto alto → Alta complejidad (requiere precisión)
            score += 0.4
            reasons.append(f"Monto alto (${amount:,.0f})")

        # FACTOR 6: Historial de correcciones del proveedor
        if provider_correction_history:
            provider_name = invoice_data.get('provider_name', '')
            correction_count = provider_correction_history.get(provider_name, 0)

            if correction_count >= 2:
                # Proveedor difícil → Alta complejidad
                score += 0.5
                reasons.append(f"Proveedor corregido {correction_count} veces")

        # FACTOR 7: Primera clasificación de este proveedor
        # (sin historial de aprendizaje, requiere LLM potente)
        # Este factor se evalúa ANTES en classification_service.py
        # Si llega aquí es porque NO hay match en learning history

        return {
            'total_score': min(score, 1.0),  # Cap at 1.0
            'reasons': reasons
        }

    def get_usage_stats(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas de uso de modelos.

        Returns:
            Dict con contadores y costos
        """
        total_calls = self.usage_stats['haiku_count'] + self.usage_stats['sonnet_count']

        if total_calls == 0:
            return {
                'total_calls': 0,
                'haiku_usage': 0.0,
                'sonnet_usage': 0.0,
                'total_cost': 0.0,
                'avg_cost_per_call': 0.0
            }

        return {
            'total_calls': total_calls,
            'haiku_count': self.usage_stats['haiku_count'],
            'sonnet_count': self.usage_stats['sonnet_count'],
            'haiku_usage': self.usage_stats['haiku_count'] / total_calls,
            'sonnet_usage': self.usage_stats['sonnet_count'] / total_calls,
            'total_cost': self.usage_stats['total_cost'],
            'avg_cost_per_call': self.usage_stats['total_cost'] / total_calls
        }


# Instancia global del selector
_model_selector = AdaptiveModelSelector()


def get_model_selector() -> AdaptiveModelSelector:
    """Obtiene la instancia global del selector de modelos."""
    return _model_selector


def select_model_for_family() -> str:
    """
    Atajo para obtener modelo de clasificación de familia.

    Returns:
        Nombre del modelo Claude (siempre Haiku)
    """
    recommendation = _model_selector.select_model_for_family_classification()
    return recommendation.model_name


def select_model_for_sat_account(
    top_candidates: list,
    invoice_data: dict,
    provider_correction_history: Optional[Dict[str, int]] = None
) -> tuple[str, str]:
    """
    Atajo para obtener modelo de clasificación SAT.

    Returns:
        Tupla (model_name, reason)
    """
    recommendation = _model_selector.select_model_for_sat_classification(
        top_candidates,
        invoice_data,
        provider_correction_history
    )
    return recommendation.model_name, recommendation.reason
