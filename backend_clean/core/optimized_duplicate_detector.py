"""
Optimized Duplicate Expense Detector - Versión mejorada con cache y batch processing
"""

import os
import logging
import hashlib
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
from dataclasses import dataclass
from functools import lru_cache

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
    processing_time_ms: Optional[int] = None


class OptimizedDuplicateDetector:
    """
    Detector optimizado de gastos duplicados con cache y batch processing
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

        # Cache para embeddings (en memoria)
        self._embedding_cache = {}
        self._cache_hits = 0
        self._cache_misses = 0

        # Configuración optimizada
        self.config = {
            'similarity_thresholds': {
                'high': 0.85,
                'medium': 0.70,
                'low': 0.55
            },
            'weights': {
                'description': 0.4,
                'amount': 0.3,
                'provider': 0.2,
                'date': 0.1
            },
            'time_window_days': 30,
            'max_comparisons': 100,  # Límite para performance
            'cache_ttl_hours': 24,   # TTL del cache
            'batch_size': 10         # Para batch embeddings
        }

    def detect_duplicates(self, new_expense: Dict[str, Any],
                         existing_expenses: List[Dict[str, Any]],
                         custom_config: Optional[Dict[str, Any]] = None) -> List[DuplicateMatch]:
        """
        Detecta posibles duplicados con optimizaciones de performance
        """
        start_time = time.time()

        # Aplicar configuración personalizada si se provee
        if custom_config:
            config = {**self.config, **custom_config}
        else:
            config = self.config

        logger.info(f"Detecting duplicates for expense: {new_expense.get('description', 'N/A')}")

        potential_duplicates = []

        # 1. Filtrar por ventana de tiempo y límite de comparaciones
        filtered_expenses = self._filter_and_limit_expenses(new_expense, existing_expenses, config)

        if not filtered_expenses:
            return []

        # 2. Pre-calcular embeddings en batch si es necesario
        self._precompute_embeddings_batch(new_expense, filtered_expenses)

        # 2.5. Extraer características ML si están habilitadas
        if config.get('extract_ml_features', True):
            self._extract_ml_features(new_expense)

        # 3. Calcular similitudes
        for existing_expense in filtered_expenses:
            similarity_score, match_reasons = self._calculate_similarity_optimized(
                new_expense, existing_expense, config
            )

            if similarity_score >= config['similarity_thresholds']['low']:
                confidence_level = self._get_confidence_level(similarity_score, config)

                processing_time = int((time.time() - start_time) * 1000)

                duplicate_match = DuplicateMatch(
                    expense_id=existing_expense.get('id'),
                    similarity_score=similarity_score,
                    match_reasons=match_reasons,
                    existing_expense=existing_expense,
                    confidence_level=confidence_level,
                    processing_time_ms=processing_time
                )

                potential_duplicates.append(duplicate_match)

        # Ordenar por score de similitud (mayor a menor)
        potential_duplicates.sort(key=lambda x: x.similarity_score, reverse=True)

        total_time = int((time.time() - start_time) * 1000)
        cache_hit_rate = self._cache_hits / (self._cache_hits + self._cache_misses) if (self._cache_hits + self._cache_misses) > 0 else 0

        logger.info(f"Found {len(potential_duplicates)} potential duplicates in {total_time}ms (cache hit rate: {cache_hit_rate:.2%})")
        return potential_duplicates

    def _filter_and_limit_expenses(self, new_expense: Dict[str, Any],
                                 existing_expenses: List[Dict[str, Any]],
                                 config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Filtra y limita gastos para optimizar performance"""
        new_date = self._parse_date(new_expense.get('date'))
        if not new_date:
            new_date = datetime.now()

        time_window_start = new_date - timedelta(days=config['time_window_days'])
        time_window_end = new_date + timedelta(days=config['time_window_days'])

        # Filtrar por fecha y ordenar por relevancia
        filtered = []
        for expense in existing_expenses:
            expense_date = self._parse_date(expense.get('date'))
            if not expense_date:
                expense_date = self._parse_date(expense.get('created_at'))

            if expense_date and time_window_start <= expense_date <= time_window_end:
                # Agregar score de relevancia basado en proximidad temporal
                days_diff = abs((expense_date - new_date).days)
                relevance_score = max(0, 1.0 - (days_diff / config['time_window_days']))
                expense['_relevance_score'] = relevance_score
                filtered.append(expense)

        # Ordenar por relevancia y limitar
        filtered.sort(key=lambda x: x.get('_relevance_score', 0), reverse=True)
        return filtered[:config['max_comparisons']]

    def _precompute_embeddings_batch(self, new_expense: Dict[str, Any],
                                   filtered_expenses: List[Dict[str, Any]]):
        """Pre-computa embeddings en batch para mejor performance"""
        if not self.client:
            return

        texts_to_embed = []
        texts_map = {}

        # Agregar texto del nuevo gasto
        new_text = new_expense.get('description', '')
        if new_text and not self._get_cached_embedding(new_text):
            texts_to_embed.append(new_text)
            texts_map[new_text] = 'new'

        # Agregar textos de gastos existentes
        for expense in filtered_expenses:
            text = expense.get('description', '')
            if text and not self._get_cached_embedding(text):
                texts_to_embed.append(text)
                texts_map[text] = expense.get('id')

        if not texts_to_embed:
            return

        # Procesar en batches
        batch_size = self.config['batch_size']
        for i in range(0, len(texts_to_embed), batch_size):
            batch = texts_to_embed[i:i + batch_size]
            try:
                self._batch_embed_and_cache(batch)
            except Exception as e:
                logger.warning(f"Batch embedding failed: {e}")

    def _batch_embed_and_cache(self, texts: List[str]):
        """Obtiene embeddings en batch y los cachea"""
        if not self.client or not texts:
            return

        try:
            response = self.client.embeddings.create(
                model="text-embedding-3-small",
                input=texts
            )

            for i, text in enumerate(texts):
                if i < len(response.data):
                    embedding = response.data[i].embedding
                    self._cache_embedding(text, embedding)

        except Exception as e:
            logger.error(f"Batch embedding error: {e}")

    def _get_cached_embedding(self, text: str) -> Optional[List[float]]:
        """Obtiene embedding del cache"""
        text_hash = self._get_text_hash(text)

        if text_hash in self._embedding_cache:
            cached_data = self._embedding_cache[text_hash]
            # Verificar TTL
            if time.time() - cached_data['timestamp'] < (self.config['cache_ttl_hours'] * 3600):
                self._cache_hits += 1
                return cached_data['embedding']
            else:
                # Limpiar entrada expirada
                del self._embedding_cache[text_hash]

        self._cache_misses += 1
        return None

    def _cache_embedding(self, text: str, embedding: List[float]):
        """Cachea un embedding"""
        text_hash = self._get_text_hash(text)
        self._embedding_cache[text_hash] = {
            'embedding': embedding,
            'timestamp': time.time()
        }

    def _get_text_hash(self, text: str) -> str:
        """Genera hash único para texto (para usar como clave de cache)"""
        return hashlib.md5(text.lower().strip().encode()).hexdigest()

    def _calculate_similarity_optimized(self, expense1: Dict[str, Any],
                                     expense2: Dict[str, Any],
                                     config: Dict[str, Any]) -> Tuple[float, List[str]]:
        """Versión optimizada de cálculo de similitud"""
        scores = {}
        match_reasons = []
        weights = config['weights']

        # 1. Similitud semántica de descripción
        desc_score = self._semantic_similarity_optimized(
            expense1.get('description', ''),
            expense2.get('description', '')
        )
        scores['description'] = desc_score * weights['description']

        if desc_score > 0.7:
            match_reasons.append(f"Descripción muy similar ({desc_score:.2f})")
        elif desc_score > 0.5:
            match_reasons.append(f"Descripción similar ({desc_score:.2f})")

        # 2. Similitud de monto
        amount_score = self._amount_similarity(
            expense1.get('amount', 0),
            expense2.get('amount', 0)
        )
        scores['amount'] = amount_score * weights['amount']

        if amount_score > 0.95:
            match_reasons.append("Monto exacto")
        elif amount_score > 0.8:
            match_reasons.append("Monto muy similar")

        # 3. Similitud de proveedor
        provider_score = self._provider_similarity(
            expense1.get('merchant_name'),
            expense2.get('merchant_name')
        )
        scores['provider'] = provider_score * weights['provider']

        if provider_score > 0.8:
            match_reasons.append("Mismo proveedor")
        elif provider_score > 0.5:
            match_reasons.append("Proveedor similar")

        # 4. Similitud de fecha
        date_score = self._date_similarity(
            expense1.get('date'),
            expense2.get('date')
        )
        scores['date'] = date_score * weights['date']

        if date_score > 0.9:
            match_reasons.append("Misma fecha")
        elif date_score > 0.7:
            match_reasons.append("Fecha cercana")

        total_score = sum(scores.values())
        return total_score, match_reasons

    def _semantic_similarity_optimized(self, text1: str, text2: str) -> float:
        """Versión optimizada con cache de similitud semántica"""
        if not text1 or not text2:
            return 0.0

        # Primero intentar con embeddings cacheados
        if self.client:
            try:
                embedding1 = self._get_cached_embedding(text1)
                embedding2 = self._get_cached_embedding(text2)

                if embedding1 and embedding2:
                    return self._cosine_similarity(embedding1, embedding2)

            except Exception as e:
                logger.warning(f"Error with cached embeddings: {e}")

        # Fallback a similitud de strings (más rápido)
        return self._string_similarity_optimized(text1, text2)

    def _cosine_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """Calcula similitud coseno entre embeddings"""
        try:
            arr1 = np.array(embedding1)
            arr2 = np.array(embedding2)

            dot_product = np.dot(arr1, arr2)
            norm1 = np.linalg.norm(arr1)
            norm2 = np.linalg.norm(arr2)

            if norm1 == 0 or norm2 == 0:
                return 0.0

            similarity = dot_product / (norm1 * norm2)
            return max(0.0, similarity)

        except Exception as e:
            logger.error(f"Error calculating cosine similarity: {e}")
            return 0.0

    @lru_cache(maxsize=1000)
    def _string_similarity_optimized(self, text1: str, text2: str) -> float:
        """Versión optimizada y cacheada de similitud de strings"""
        from difflib import SequenceMatcher

        # Normalizar textos
        text1_norm = text1.lower().strip()
        text2_norm = text2.lower().strip()

        # Comparación rápida para casos obvios
        if text1_norm == text2_norm:
            return 1.0

        if not text1_norm or not text2_norm:
            return 0.0

        # Usar SequenceMatcher optimizado
        return SequenceMatcher(None, text1_norm, text2_norm).ratio()

    def _amount_similarity(self, amount1: float, amount2: float) -> float:
        """Calcula similitud de montos"""
        if amount1 <= 0 or amount2 <= 0:
            return 0.0

        diff = abs(amount1 - amount2)
        max_amount = max(amount1, amount2)

        return max(0.0, 1.0 - (diff / max_amount))

    def _provider_similarity(self, provider1: Optional[str], provider2: Optional[str]) -> float:
        """Calcula similitud de proveedores"""
        if not provider1 or not provider2:
            return 0.0

        return self._string_similarity_optimized(provider1, provider2)

    def _date_similarity(self, date1: Optional[str], date2: Optional[str]) -> float:
        """Calcula similitud de fechas"""
        parsed_date1 = self._parse_date(date1)
        parsed_date2 = self._parse_date(date2)

        if not parsed_date1 or not parsed_date2:
            return 0.5

        diff_days = abs((parsed_date1 - parsed_date2).days)

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

    @lru_cache(maxsize=500)
    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Versión cacheada de parseo de fechas"""
        if not date_str:
            return None

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
            except (ValueError, TypeError):
                continue

        return None

    def _get_confidence_level(self, similarity_score: float, config: Dict[str, Any]) -> str:
        """Determina nivel de confianza"""
        thresholds = config['similarity_thresholds']

        if similarity_score >= thresholds['high']:
            return 'high'
        elif similarity_score >= thresholds['medium']:
            return 'medium'
        else:
            return 'low'

    def get_duplicate_summary(self, duplicates: List[DuplicateMatch]) -> Dict[str, Any]:
        """Genera resumen de duplicados con métricas de performance"""
        if not duplicates:
            return {
                'has_duplicates': False,
                'total_found': 0,
                'risk_level': 'none',
                'recommendation': 'proceed',
                'avg_processing_time_ms': 0
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

        # Calcular tiempo promedio de procesamiento
        processing_times = [d.processing_time_ms for d in duplicates if d.processing_time_ms]
        avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0

        return {
            'has_duplicates': True,
            'total_found': len(duplicates),
            'high_confidence': len(high_confidence),
            'medium_confidence': len(medium_confidence),
            'low_confidence': len([d for d in duplicates if d.confidence_level == 'low']),
            'risk_level': risk_level,
            'recommendation': recommendation,
            'avg_processing_time_ms': int(avg_processing_time),
            'cache_hit_rate': self._cache_hits / (self._cache_hits + self._cache_misses) if (self._cache_hits + self._cache_misses) > 0 else 0,
            'top_match': {
                'expense_id': duplicates[0].expense_id,
                'similarity_score': duplicates[0].similarity_score,
                'confidence_level': duplicates[0].confidence_level,
                'match_reasons': duplicates[0].match_reasons
            } if duplicates else None
        }

    def _extract_ml_features(self, expense: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extrae características ML del gasto"""
        try:
            from .ml_feature_extractor import extract_expense_features
            return extract_expense_features(expense)
        except ImportError as e:
            logger.warning(f"ML feature extractor not available: {e}")
            return None
        except Exception as e:
            logger.error(f"Error extracting ML features: {e}")
            return None

    def clear_cache(self):
        """Limpia el cache de embeddings"""
        self._embedding_cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0

    def get_cache_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del cache"""
        total_requests = self._cache_hits + self._cache_misses
        hit_rate = self._cache_hits / total_requests if total_requests > 0 else 0

        return {
            'cache_size': len(self._embedding_cache),
            'cache_hits': self._cache_hits,
            'cache_misses': self._cache_misses,
            'hit_rate': hit_rate,
            'total_requests': total_requests
        }


# Factory functions
_optimized_detector = None

def get_optimized_detector() -> OptimizedDuplicateDetector:
    """Obtener instancia global del detector optimizado"""
    global _optimized_detector
    if _optimized_detector is None:
        _optimized_detector = OptimizedDuplicateDetector()
    return _optimized_detector


def detect_expense_duplicates_optimized(new_expense: Dict[str, Any],
                                      existing_expenses: List[Dict[str, Any]],
                                      custom_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Función helper optimizada para detectar duplicados
    """
    detector = get_optimized_detector()
    duplicates = detector.detect_duplicates(new_expense, existing_expenses, custom_config)
    summary = detector.get_duplicate_summary(duplicates)

    # Extraer ML features del nuevo gasto si está configurado
    ml_features = None
    if custom_config is None or custom_config.get('extract_ml_features', True):
        try:
            from .ml_feature_extractor import extract_expense_features
            ml_features = extract_expense_features(new_expense)
        except Exception as e:
            logger.warning(f"Could not extract ML features: {e}")

    return {
        'summary': summary,
        'ml_features': ml_features,
        'duplicates': [
            {
                'expense_id': d.expense_id,
                'similarity_score': d.similarity_score,
                'confidence_level': d.confidence_level,
                'match_reasons': d.match_reasons,
                'processing_time_ms': d.processing_time_ms,
                'existing_expense': {
                    'id': d.existing_expense.get('id'),
                    'description': d.existing_expense.get('description'),
                    'amount': d.existing_expense.get('amount'),
                    'date': d.existing_expense.get('date'),
                    'merchant_name': d.existing_expense.get('merchant_name')
                }
            }
            for d in duplicates
        ],
        'cache_stats': detector.get_cache_stats()
    }