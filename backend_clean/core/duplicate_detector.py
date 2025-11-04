"""
Duplicate Expense Detector - Usa embeddings semánticos para detectar gastos duplicados
"""

import os
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
from dataclasses import dataclass

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

logger = logging.getLogger(__name__)


@dataclass
class DuplicateMatch:
    """Representa un posible duplicado encontrado"""
    expense_id: int
    similarity_score: float
    match_reasons: List[str]
    existing_expense: Dict[str, Any]
    confidence_level: str  # 'high', 'medium', 'low'


class DuplicateDetector:
    """
    Detector de gastos duplicados usando embeddings semánticos y heurísticas
    """

    def __init__(self):
        if not OpenAI:
            logger.warning("OpenAI library not available, using basic heuristics only")
            self.client = None
        else:
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                logger.warning("OPENAI_API_KEY not configured, using basic heuristics only")
                self.client = None
            else:
                self.client = OpenAI(api_key=api_key)

        # Configuración de umbrales
        self.SIMILARITY_THRESHOLDS = {
            'high': 0.85,      # Muy probable duplicado
            'medium': 0.70,    # Posible duplicado
            'low': 0.55        # Revisión manual
        }

        # Ventana de tiempo para buscar duplicados (días)
        self.TIME_WINDOW_DAYS = 30

    def detect_duplicates(self, new_expense: Dict[str, Any], existing_expenses: List[Dict[str, Any]]) -> List[DuplicateMatch]:
        """
        Detecta posibles duplicados de un gasto nuevo comparándolo con gastos existentes

        Args:
            new_expense: El nuevo gasto a verificar
            existing_expenses: Lista de gastos existentes para comparar

        Returns:
            Lista de posibles duplicados ordenados por similitud
        """
        logger.info(f"Detecting duplicates for expense: {new_expense.get('descripcion', 'N/A')}")

        potential_duplicates = []

        # Filtrar gastos por ventana de tiempo
        filtered_expenses = self._filter_by_time_window(new_expense, existing_expenses)

        for existing_expense in filtered_expenses:
            similarity_score, match_reasons = self._calculate_similarity(new_expense, existing_expense)

            if similarity_score >= self.SIMILARITY_THRESHOLDS['low']:
                confidence_level = self._get_confidence_level(similarity_score)

                duplicate_match = DuplicateMatch(
                    expense_id=existing_expense.get('id'),
                    similarity_score=similarity_score,
                    match_reasons=match_reasons,
                    existing_expense=existing_expense,
                    confidence_level=confidence_level
                )

                potential_duplicates.append(duplicate_match)

        # Ordenar por score de similitud (mayor a menor)
        potential_duplicates.sort(key=lambda x: x.similarity_score, reverse=True)

        logger.info(f"Found {len(potential_duplicates)} potential duplicates")
        return potential_duplicates

    def _filter_by_time_window(self, new_expense: Dict[str, Any], existing_expenses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filtra gastos existentes por ventana de tiempo"""
        new_date = self._parse_date(new_expense.get('fecha_gasto'))
        if not new_date:
            new_date = datetime.now()

        time_window_start = new_date - timedelta(days=self.TIME_WINDOW_DAYS)
        time_window_end = new_date + timedelta(days=self.TIME_WINDOW_DAYS)

        filtered = []
        for expense in existing_expenses:
            expense_date = self._parse_date(expense.get('fecha_gasto'))
            if not expense_date:
                expense_date = self._parse_date(expense.get('created_at'))

            if expense_date and time_window_start <= expense_date <= time_window_end:
                filtered.append(expense)

        return filtered

    def _calculate_similarity(self, expense1: Dict[str, Any], expense2: Dict[str, Any]) -> Tuple[float, List[str]]:
        """
        Calcula la similitud entre dos gastos usando múltiples factores
        """
        scores = {}
        match_reasons = []

        # 1. Similitud semántica de descripción (40% del peso)
        desc_score = self._semantic_similarity(
            expense1.get('descripcion', ''),
            expense2.get('descripcion', '')
        )
        scores['description'] = desc_score * 0.4

        if desc_score > 0.7:
            match_reasons.append(f"Descripción muy similar ({desc_score:.2f})")
        elif desc_score > 0.5:
            match_reasons.append(f"Descripción similar ({desc_score:.2f})")

        # 2. Similitud de monto (30% del peso)
        amount_score = self._amount_similarity(
            expense1.get('monto_total', 0),
            expense2.get('monto_total', 0)
        )
        scores['amount'] = amount_score * 0.3

        if amount_score > 0.95:
            match_reasons.append("Monto exacto")
        elif amount_score > 0.8:
            match_reasons.append("Monto muy similar")

        # 3. Similitud de proveedor (20% del peso)
        provider_score = self._provider_similarity(
            expense1.get('proveedor'),
            expense2.get('proveedor')
        )
        scores['provider'] = provider_score * 0.2

        if provider_score > 0.8:
            match_reasons.append("Mismo proveedor")
        elif provider_score > 0.5:
            match_reasons.append("Proveedor similar")

        # 4. Similitud de fecha (10% del peso)
        date_score = self._date_similarity(
            expense1.get('fecha_gasto'),
            expense2.get('fecha_gasto')
        )
        scores['date'] = date_score * 0.1

        if date_score > 0.9:
            match_reasons.append("Misma fecha")
        elif date_score > 0.7:
            match_reasons.append("Fecha cercana")

        # Score total
        total_score = sum(scores.values())

        logger.debug(f"Similarity breakdown: {scores}, total: {total_score:.3f}")

        return total_score, match_reasons

    def _semantic_similarity(self, text1: str, text2: str) -> float:
        """Calcula similitud semántica usando embeddings o fallback a string similarity"""
        if not text1 or not text2:
            return 0.0

        # Si tenemos OpenAI, usar embeddings
        if self.client:
            try:
                return self._embedding_similarity(text1, text2)
            except Exception as e:
                logger.warning(f"Error with embeddings, falling back to string similarity: {e}")

        # Fallback a similitud de strings
        return self._string_similarity(text1, text2)

    def _embedding_similarity(self, text1: str, text2: str) -> float:
        """Calcula similitud usando embeddings de OpenAI"""
        try:
            # Obtener embeddings
            response1 = self.client.embeddings.create(
                model="text-embedding-3-small",
                input=text1
            )
            response2 = self.client.embeddings.create(
                model="text-embedding-3-small",
                input=text2
            )

            embedding1 = np.array(response1.data[0].embedding)
            embedding2 = np.array(response2.data[0].embedding)

            # Calcular similitud coseno
            dot_product = np.dot(embedding1, embedding2)
            norm1 = np.linalg.norm(embedding1)
            norm2 = np.linalg.norm(embedding2)

            if norm1 == 0 or norm2 == 0:
                return 0.0

            similarity = dot_product / (norm1 * norm2)
            return max(0.0, similarity)  # Asegurar que no sea negativo

        except Exception as e:
            logger.error(f"Error calculating embedding similarity: {e}")
            return self._string_similarity(text1, text2)

    def _string_similarity(self, text1: str, text2: str) -> float:
        """Fallback de similitud usando SequenceMatcher"""
        from difflib import SequenceMatcher

        # Normalizar textos
        text1_norm = text1.lower().strip()
        text2_norm = text2.lower().strip()

        return SequenceMatcher(None, text1_norm, text2_norm).ratio()

    def _amount_similarity(self, amount1: float, amount2: float) -> float:
        """Calcula similitud de montos"""
        if amount1 <= 0 or amount2 <= 0:
            return 0.0

        diff = abs(amount1 - amount2)
        max_amount = max(amount1, amount2)

        return max(0.0, 1.0 - (diff / max_amount))

    def _provider_similarity(self, provider1: Optional[Dict], provider2: Optional[Dict]) -> float:
        """Calcula similitud de proveedores"""
        if not provider1 or not provider2:
            return 0.0

        name1 = provider1.get('nombre', '') if isinstance(provider1, dict) else str(provider1)
        name2 = provider2.get('nombre', '') if isinstance(provider2, dict) else str(provider2)

        if not name1 or not name2:
            return 0.0

        return self._string_similarity(name1, name2)

    def _date_similarity(self, date1: Optional[str], date2: Optional[str]) -> float:
        """Calcula similitud de fechas"""
        parsed_date1 = self._parse_date(date1)
        parsed_date2 = self._parse_date(date2)

        if not parsed_date1 or not parsed_date2:
            return 0.5  # Neutral si no tenemos fechas

        diff_days = abs((parsed_date1 - parsed_date2).days)

        # Score decae exponencialmente con la diferencia de días
        if diff_days == 0:
            return 1.0
        elif diff_days <= 1:
            return 0.9
        elif diff_days <= 3:
            return 0.7
        elif diff_days <= 7:
            return 0.5
        else:
            return max(0.0, 0.5 - (diff_days * 0.02))

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse date string to datetime object"""
        if not date_str:
            return None

        # Convertir a string si no lo es
        date_str = str(date_str).strip()

        formats = [
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%d-%m-%Y",
            "%d/%m/%Y",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S.%fZ"
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except (ValueError, TypeError) as e:
                # Para ISO formato con microsegundos, truncar los microsegundos extra
                if 'T' in date_str and '.' in date_str and fmt == "%Y-%m-%dT%H:%M:%S.%f":
                    try:
                        # Truncar a 6 dígitos de microsegundos
                        if date_str.count('.') == 1:
                            date_part, time_part = date_str.split('.')
                            microseconds = time_part[:6]  # Solo primeros 6 dígitos
                            truncated_date = f"{date_part}.{microseconds}"
                            return datetime.strptime(truncated_date, fmt)
                    except:
                        pass
                logger.debug(f"Failed to parse '{date_str}' with format '{fmt}': {e}")
                continue

        logger.warning(f"Could not parse date: '{date_str}'")
        return None

    def _get_confidence_level(self, similarity_score: float) -> str:
        """Determina el nivel de confianza basado en el score"""
        if similarity_score >= self.SIMILARITY_THRESHOLDS['high']:
            return 'high'
        elif similarity_score >= self.SIMILARITY_THRESHOLDS['medium']:
            return 'medium'
        else:
            return 'low'

    def get_duplicate_summary(self, duplicates: List[DuplicateMatch]) -> Dict[str, Any]:
        """Genera un resumen de duplicados encontrados"""
        if not duplicates:
            return {
                'has_duplicates': False,
                'total_found': 0,
                'risk_level': 'none',
                'recommendation': 'proceed'
            }

        high_confidence = [d for d in duplicates if d.confidence_level == 'high']
        medium_confidence = [d for d in duplicates if d.confidence_level == 'medium']

        if high_confidence:
            risk_level = 'high'
            recommendation = 'block'
        elif medium_confidence:
            risk_level = 'medium'
            recommendation = 'review'
        else:
            risk_level = 'low'
            recommendation = 'warn'

        return {
            'has_duplicates': True,
            'total_found': len(duplicates),
            'high_confidence': len(high_confidence),
            'medium_confidence': len(medium_confidence),
            'low_confidence': len([d for d in duplicates if d.confidence_level == 'low']),
            'risk_level': risk_level,
            'recommendation': recommendation,
            'top_match': {
                'expense_id': duplicates[0].expense_id,
                'similarity_score': duplicates[0].similarity_score,
                'confidence_level': duplicates[0].confidence_level,
                'match_reasons': duplicates[0].match_reasons
            } if duplicates else None
        }


# Instancia global del detector
_duplicate_detector = None

def get_duplicate_detector() -> DuplicateDetector:
    """Obtener instancia global del detector de duplicados"""
    global _duplicate_detector
    if _duplicate_detector is None:
        _duplicate_detector = DuplicateDetector()
    return _duplicate_detector


def detect_expense_duplicates(new_expense: Dict[str, Any], existing_expenses: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Función helper para detectar duplicados de un gasto

    Returns:
        Diccionario con resultados de detección y recomendaciones
    """
    detector = get_duplicate_detector()
    duplicates = detector.detect_duplicates(new_expense, existing_expenses)
    summary = detector.get_duplicate_summary(duplicates)

    return {
        'summary': summary,
        'duplicates': [
            {
                'expense_id': d.expense_id,
                'similarity_score': d.similarity_score,
                'confidence_level': d.confidence_level,
                'match_reasons': d.match_reasons,
                'existing_expense': {
                    'id': d.existing_expense.get('id'),
                    'descripcion': d.existing_expense.get('descripcion'),
                    'monto_total': d.existing_expense.get('monto_total'),
                    'fecha_gasto': d.existing_expense.get('fecha_gasto'),
                    'proveedor': d.existing_expense.get('proveedor')
                }
            }
            for d in duplicates
        ]
    }