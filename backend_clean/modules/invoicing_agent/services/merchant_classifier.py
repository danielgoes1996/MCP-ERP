"""
Merchant Classifier - Sistema inteligente de clasificación de merchants.

Combina heurísticas rápidas con embeddings semánticos para identificación robusta.
Incluye sistema de confianza y fallback humano.
"""

import asyncio
import logging
import os
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Dict, Any, List, Optional
import hashlib

logger = logging.getLogger(__name__)


class ClassificationMethod(Enum):
    """Métodos de clasificación disponibles."""
    REGEX_PATTERNS = "regex_patterns"
    KEYWORD_MATCHING = "keyword_matching"
    SEMANTIC_EMBEDDINGS = "semantic_embeddings"
    MACHINE_LEARNING = "machine_learning"
    HUMAN_REVIEW = "human_review"


@dataclass
class MerchantMatch:
    """Resultado de clasificación de merchant."""
    merchant_id: str
    merchant_name: str
    confidence: float
    method: ClassificationMethod
    matched_patterns: List[str]
    rfc: Optional[str] = None
    portal_url: Optional[str] = None
    metadata: Dict[str, Any] = None
    processing_time: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['method'] = self.method.value
        return result


class MerchantClassifier(ABC):
    """Interfaz abstracta para clasificadores de merchants."""

    @abstractmethod
    async def classify(self, text: str) -> Optional[MerchantMatch]:
        """Clasificar texto y devolver merchant identificado."""

    @abstractmethod
    def get_confidence_threshold(self) -> float:
        """Umbral mínimo de confianza para este clasificador."""


class RegexPatternClassifier(MerchantClassifier):
    """Clasificador basado en patrones regex - rápido y preciso."""

    def __init__(self):
        # Configuración de merchants con patrones específicos
        self.merchant_patterns = {
            'GASOLINERIA_LITRO_MIL': {
                'rfc': 'GLM090710TVO',
                'portal': 'https://factura.litromil.com.mx',  # Portal genérico
                'patterns': [
                    r'GASOLINERIA.*LITRO.*MIL',
                    r'LITRO.*MIL',
                    r'GLM090710TVO',  # RFC específico
                    r'CLAVE.*CLIENTE.*PEMEX.*0000115287',  # Clave específica del ticket real
                    r'LIBRAMIENTO.*SUR.*PONIENTE'  # Dirección específica
                ],
                'negative_patterns': []
            },
            'PEMEX': {
                'rfc': 'PEP970814SF3',
                'portal': 'https://factura.pemex.com',
                'patterns': [
                    r'PEMEX',
                    r'GASOLINERA.*PEMEX',
                    r'ESTACIÓN.*DE.*SERVICIO.*PEMEX',
                    r'PETRÓLEOS.*MEXICANOS',
                    r'PEP\d{6}[A-Z0-9]{3}',  # RFC pattern
                    r'CLAVE.*CLIENTE.*PEMEX'
                ],
                'negative_patterns': [r'LITRO.*MIL']  # No confundir con Litro Mil
            },
            'SHELL': {
                'rfc': 'SHE850912XY4',
                'portal': 'https://factura.shell.com.mx',
                'patterns': [
                    r'SHELL',
                    r'SHELL.*ESTACIÓN',
                    r'COMBUSTIBLES.*SHELL',
                    r'SHELL.*GASOLINERA'
                ],
                'negative_patterns': []
            },
            'OXXO': {
                'rfc': 'OXX970814HS9',
                'portal': 'https://factura.oxxo.com',
                'patterns': [
                    r'OXXO',
                    r'CADENA.*COMERCIAL.*OXXO',
                    r'OXXO.*TIENDA',
                    r'OXX\d{6}[A-Z0-9]{3}'
                ],
                'negative_patterns': []
            },
            'WALMART': {
                'rfc': 'WAL9709244W4',
                'portal': 'https://factura.walmart.com.mx',
                'patterns': [
                    r'WALMART',
                    r'WAL-?MART',
                    r'SUPERCENTER',
                    r'WALMART.*SUPERCENTER'
                ],
                'negative_patterns': []
            },
            'COSTCO': {
                'rfc': 'COS050815PE4',
                'portal': 'https://facturaelectronica.costco.com.mx',
                'patterns': [
                    r'COSTCO',
                    r'COSTCO.*WHOLESALE',
                    r'WHOLESALE.*COSTCO'
                ],
                'negative_patterns': []
            },
            'SORIANA': {
                'rfc': 'SOR810511HN9',
                'portal': 'https://facturacion.soriana.com',
                'patterns': [
                    r'SORIANA',
                    r'HIPER.*SORIANA',
                    r'MEGA.*SORIANA',
                    r'TIENDA.*SORIANA'
                ],
                'negative_patterns': [
                    r'GASOLINERA',  # Evitar confundir gasolineras con Soriana
                    r'PEMEX',
                    r'SHELL'
                ]
            },
            'HOME_DEPOT': {
                'rfc': 'HDM930228Q90',
                'portal': 'https://homedepot.com.mx/facturacion',
                'patterns': [
                    r'HOME.*DEPOT',
                    r'THE.*HOME.*DEPOT',
                    r'HOMEDEPOT'
                ],
                'negative_patterns': []
            },
            'CHEDRAUI': {
                'rfc': 'CCH850701TN7',
                'portal': 'https://factura.chedraui.com.mx',
                'patterns': [
                    r'CHEDRAUI',
                    r'SUPER.*CHE',
                    r'TIENDAS.*CHEDRAUI'
                ],
                'negative_patterns': []
            },
            '7_ELEVEN': {
                'rfc': 'SEL991209KE7',
                'portal': 'https://facturacion.7-eleven.com.mx',
                'patterns': [
                    r'7-?ELEVEN',
                    r'SEVEN.*ELEVEN',
                    r'7.*11'
                ],
                'negative_patterns': []
            }
        }

    def get_confidence_threshold(self) -> float:
        return 0.85

    async def classify(self, text: str) -> Optional[MerchantMatch]:
        start_time = time.time()
        text_upper = text.upper()

        best_match = None
        highest_confidence = 0.0

        for merchant_id, config in self.merchant_patterns.items():
            matched_patterns = []
            confidence = 0.0

            # Verificar patrones negativos primero
            negative_match = False
            for negative_pattern in config.get('negative_patterns', []):
                if re.search(negative_pattern, text_upper, re.IGNORECASE):
                    negative_match = True
                    break

            if negative_match:
                continue

            # Verificar patrones positivos
            for pattern in config['patterns']:
                matches = re.findall(pattern, text_upper, re.IGNORECASE)
                if matches:
                    matched_patterns.extend([pattern])

                    # Calcular confianza basada en tipo de patrón
                    if 'RFC' in pattern or r'\d{6}' in pattern:
                        confidence += 0.4  # RFC es muy específico
                    elif len(pattern) > 10:
                        confidence += 0.3  # Patrones largos son más específicos
                    else:
                        confidence += 0.2  # Patrones básicos

            # Bonus por múltiples matches
            if len(matched_patterns) > 1:
                confidence += 0.1 * (len(matched_patterns) - 1)

            # Normalizar confianza
            confidence = min(confidence, 1.0)

            if confidence > highest_confidence and confidence >= self.get_confidence_threshold():
                highest_confidence = confidence
                best_match = MerchantMatch(
                    merchant_id=merchant_id,
                    merchant_name=merchant_id.replace('_', ' ').title(),
                    confidence=confidence,
                    method=ClassificationMethod.REGEX_PATTERNS,
                    matched_patterns=matched_patterns,
                    rfc=config.get('rfc'),
                    portal_url=config.get('portal'),
                    metadata={'total_patterns': len(config['patterns'])},
                    processing_time=time.time() - start_time
                )

        return best_match


class SemanticEmbeddingClassifier(MerchantClassifier):
    """Clasificador basado en embeddings semánticos - robusto a variaciones."""

    def __init__(self):
        # Embeddings pre-calculados de merchants conocidos
        self.merchant_embeddings = {}
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.cohere_api_key = os.getenv("COHERE_API_KEY")

        # Merchants con sus descripciones características
        self.merchant_descriptions = {
            'PEMEX': [
                "gasolinera pemex estación de servicio combustible magna premium diesel",
                "petróleos mexicanos gasolina litros precio por litro",
                "clave cliente pemex estación servicio automotriz"
            ],
            'SHELL': [
                "shell gasolinera combustibles estación servicio",
                "shell v-power premium gasolina diesel",
                "shell station fuel gas station"
            ],
            'OXXO': [
                "oxxo tienda conveniencia refrescos bebidas comida",
                "cadena comercial oxxo productos básicos",
                "oxxo store convenience snacks drinks"
            ],
            'WALMART': [
                "walmart supercenter tienda departamental",
                "wal mart supermercado productos hogar",
                "walmart grocery food household items"
            ],
            'COSTCO': [
                "costco wholesale mayoreo membresía",
                "costco almacén productos granel",
                "costco wholesale club bulk products"
            ],
            'SORIANA': [
                "soriana supermercado tienda abarrotes",
                "hiper soriana mega soriana productos",
                "soriana grocery supermarket food"
            ]
        }

    def get_confidence_threshold(self) -> float:
        return 0.75

    async def classify(self, text: str) -> Optional[MerchantMatch]:
        """Clasificar usando embeddings semánticos."""
        start_time = time.time()

        if not (self.openai_api_key or self.cohere_api_key):
            return None

        try:
            # Obtener embedding del texto de entrada
            input_embedding = await self._get_embedding(text)
            if not input_embedding:
                return None

            best_match = None
            highest_similarity = 0.0

            # Comparar con embeddings de merchants conocidos
            for merchant_id, descriptions in self.merchant_descriptions.items():
                max_similarity = 0.0

                for description in descriptions:
                    merchant_embedding = await self._get_embedding(description)
                    if merchant_embedding:
                        similarity = self._cosine_similarity(input_embedding, merchant_embedding)
                        max_similarity = max(max_similarity, similarity)

                if max_similarity > highest_similarity and max_similarity >= self.get_confidence_threshold():
                    highest_similarity = max_similarity
                    best_match = MerchantMatch(
                        merchant_id=merchant_id,
                        merchant_name=merchant_id.replace('_', ' ').title(),
                        confidence=max_similarity,
                        method=ClassificationMethod.SEMANTIC_EMBEDDINGS,
                        matched_patterns=[f"similarity_{max_similarity:.3f}"],
                        metadata={'embedding_model': 'openai' if self.openai_api_key else 'cohere'},
                        processing_time=time.time() - start_time
                    )

            return best_match

        except Exception as e:
            logger.error(f"Error en clasificación semántica: {e}")
            return None

    async def _get_embedding(self, text: str) -> Optional[List[float]]:
        """Obtener embedding de texto usando OpenAI o Cohere."""
        try:
            if self.openai_api_key:
                return await self._get_openai_embedding(text)
            elif self.cohere_api_key:
                return await self._get_cohere_embedding(text)
        except Exception as e:
            logger.error(f"Error obteniendo embedding: {e}")
            return None

    async def _get_openai_embedding(self, text: str) -> Optional[List[float]]:
        """Obtener embedding usando OpenAI."""
        try:
            import aiohttp

            url = "https://api.openai.com/v1/embeddings"
            headers = {
                "Authorization": f"Bearer {self.openai_api_key}",
                "Content-Type": "application/json"
            }
            data = {
                "input": text,
                "model": "text-embedding-ada-002"
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result["data"][0]["embedding"]
            return None

        except Exception as e:
            logger.error(f"Error con OpenAI embedding: {e}")
            return None

    async def _get_cohere_embedding(self, text: str) -> Optional[List[float]]:
        """Obtener embedding usando Cohere."""
        try:
            import aiohttp

            url = "https://api.cohere.ai/v1/embed"
            headers = {
                "Authorization": f"Bearer {self.cohere_api_key}",
                "Content-Type": "application/json"
            }
            data = {
                "texts": [text],
                "model": "embed-multilingual-v2.0"
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result["embeddings"][0]
            return None

        except Exception as e:
            logger.error(f"Error con Cohere embedding: {e}")
            return None

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calcular similitud coseno entre dos vectores."""
        try:
            import math

            dot_product = sum(a * b for a, b in zip(vec1, vec2))
            magnitude1 = math.sqrt(sum(a * a for a in vec1))
            magnitude2 = math.sqrt(sum(a * a for a in vec2))

            if magnitude1 == 0 or magnitude2 == 0:
                return 0.0

            return dot_product / (magnitude1 * magnitude2)

        except Exception:
            return 0.0


class HybridMerchantClassifier:
    """
    Clasificador híbrido que combina múltiples métodos.

    Estrategia:
    1. Primero regex rápido (alta precisión)
    2. Si no hay match, usar embeddings semánticos
    3. Si confianza es baja, marcar para revisión humana
    """

    def __init__(self):
        self.regex_classifier = RegexPatternClassifier()
        self.semantic_classifier = SemanticEmbeddingClassifier()
        self.min_confidence_for_auto = 0.8
        self.cache: Dict[str, MerchantMatch] = {}
        self.max_cache_size = 500

        # Métricas
        self.metrics = {
            "total_classifications": 0,
            "regex_matches": 0,
            "semantic_matches": 0,
            "human_review_required": 0,
            "cache_hits": 0,
            "average_processing_time": 0.0
        }

    async def classify_merchant(self, text: str, use_cache: bool = True) -> MerchantMatch:
        """
        Clasificar merchant usando estrategia híbrida.

        Args:
            text: Texto extraído del ticket
            use_cache: Si usar cache de resultados

        Returns:
            Resultado de clasificación con nivel de confianza
        """
        start_time = time.time()

        # Verificar cache
        cache_key = hashlib.md5(text.encode()).hexdigest()[:16]
        if use_cache and cache_key in self.cache:
            self.metrics["cache_hits"] += 1
            return self.cache[cache_key]

        self.metrics["total_classifications"] += 1

        # Paso 1: Intentar regex patterns (rápido y preciso)
        regex_result = await self.regex_classifier.classify(text)
        if regex_result and regex_result.confidence >= self.min_confidence_for_auto:
            self.metrics["regex_matches"] += 1
            self._cache_result(cache_key, regex_result)
            self._update_processing_time(time.time() - start_time)
            return regex_result

        # Paso 2: Intentar embeddings semánticos (más robusto)
        semantic_result = await self.semantic_classifier.classify(text)
        if semantic_result and semantic_result.confidence >= self.min_confidence_for_auto:
            self.metrics["semantic_matches"] += 1
            self._cache_result(cache_key, semantic_result)
            self._update_processing_time(time.time() - start_time)
            return semantic_result

        # Paso 3: Confianza baja - requiere revisión humana
        self.metrics["human_review_required"] += 1

        # Usar el mejor resultado disponible pero marcarlo para revisión
        best_result = regex_result or semantic_result

        if best_result:
            # Marcar para revisión humana
            best_result.method = ClassificationMethod.HUMAN_REVIEW
            best_result.metadata = {
                **(best_result.metadata or {}),
                "requires_human_review": True,
                "low_confidence_reason": f"Confidence {best_result.confidence:.3f} below threshold {self.min_confidence_for_auto}"
            }
        else:
            # No se pudo identificar - crear resultado para revisión manual
            best_result = MerchantMatch(
                merchant_id="UNKNOWN",
                merchant_name="Desconocido",
                confidence=0.0,
                method=ClassificationMethod.HUMAN_REVIEW,
                matched_patterns=[],
                metadata={
                    "requires_human_review": True,
                    "reason": "No se pudo identificar automáticamente",
                    "text_preview": text[:100]
                },
                processing_time=time.time() - start_time
            )

        self._cache_result(cache_key, best_result)
        self._update_processing_time(time.time() - start_time)
        return best_result

    def _cache_result(self, key: str, result: MerchantMatch):
        """Guardar resultado en cache con límite de tamaño."""
        if len(self.cache) >= self.max_cache_size:
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
        self.cache[key] = result

    def _update_processing_time(self, processing_time: float):
        """Actualizar promedio de tiempo de procesamiento."""
        total = self.metrics["total_classifications"]
        current_avg = self.metrics["average_processing_time"]
        self.metrics["average_processing_time"] = (
            (current_avg * (total - 1) + processing_time) / total
        )

    def get_metrics(self) -> Dict[str, Any]:
        """Obtener métricas del clasificador."""
        total = max(self.metrics["total_classifications"], 1)
        return {
            **self.metrics,
            "cache_size": len(self.cache),
            "cache_hit_rate": self.metrics["cache_hits"] / total,
            "regex_match_rate": self.metrics["regex_matches"] / total,
            "semantic_match_rate": self.metrics["semantic_matches"] / total,
            "human_review_rate": self.metrics["human_review_required"] / total
        }

    def add_manual_classification(self, text: str, merchant_id: str, merchant_name: str):
        """
        Agregar clasificación manual para mejorar el sistema.

        Args:
            text: Texto original
            merchant_id: ID del merchant correcto
            merchant_name: Nombre del merchant
        """
        cache_key = hashlib.md5(text.encode()).hexdigest()[:16]
        manual_result = MerchantMatch(
            merchant_id=merchant_id,
            merchant_name=merchant_name,
            confidence=1.0,
            method=ClassificationMethod.HUMAN_REVIEW,
            matched_patterns=["manual_classification"],
            metadata={"manually_verified": True}
        )
        self._cache_result(cache_key, manual_result)
        logger.info(f"Clasificación manual agregada: {merchant_name}")


# Instancia global
merchant_classifier = HybridMerchantClassifier()


# Función de conveniencia
async def classify_merchant(text: str) -> MerchantMatch:
    """
    Función simple para clasificar merchant.

    Args:
        text: Texto extraído del ticket

    Returns:
        Resultado de clasificación
    """
    return await merchant_classifier.classify_merchant(text)


if __name__ == "__main__":
    # Test del clasificador
    async def test_classifier():
        test_texts = [
            "GASOLINERA PEMEX #1234\nRFC: PEP970814SF3\nESTACIÓN DE SERVICIO",
            "SHELL ESTACIÓN 567\nCOMBUSTIBLES\nPREMIUM 18.2 LTS",
            "OXXO TIENDA #1234\nCadena Comercial OXXO\nCoca Cola 600ml",
            "WALMART SUPERCENTER\nNo. Tienda: 2612\nLeche 1L",
            "TIENDA DESCONOCIDA\nCompra varios productos\nTotal: $150.00"
        ]

        print("=== Test Merchant Classifier ===")
        for i, text in enumerate(test_texts, 1):
            print(f"\n--- Test {i} ---")
            print(f"Texto: {text[:50]}...")

            result = await classify_merchant(text)
            print(f"Merchant: {result.merchant_name}")
            print(f"Confianza: {result.confidence:.3f}")
            print(f"Método: {result.method.value}")
            print(f"Patterns: {result.matched_patterns}")
            if result.metadata:
                print(f"Metadata: {result.metadata}")

        # Mostrar métricas
        print("\n=== Métricas ===")
        metrics = merchant_classifier.get_metrics()
        for key, value in metrics.items():
            print(f"{key}: {value}")

    asyncio.run(test_classifier())