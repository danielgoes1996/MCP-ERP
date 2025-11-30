"""
Módulo para evaluar similitud entre conceptos de tickets y facturas

Utiliza un enfoque híbrido:
1. Keyword overlap (Jaccard similarity) - Nivel 1 (rápido)
2. Sequence similarity (SequenceMatcher) - Nivel 1 (rápido)
3. Semantic similarity (Gemini LLM) - Nivel 2 (preciso, solo para casos ambiguos)
"""

from typing import List, Dict, Optional, Tuple
from difflib import SequenceMatcher
import re
import logging
import os
import time
from functools import lru_cache
import hashlib

logger = logging.getLogger(__name__)

# Lazy import Gemini (solo si se usa)
_gemini_client = None

def _get_gemini_client():
    """Get or create Gemini client (lazy initialization)"""
    global _gemini_client
    if _gemini_client is None:
        try:
            import google.generativeai as genai
            api_key = os.getenv('GEMINI_API_KEY')
            if not api_key:
                logger.warning("GEMINI_API_KEY not set - semantic similarity disabled")
                return None
            genai.configure(api_key=api_key)
            _gemini_client = genai.GenerativeModel('gemini-2.5-flash')  # Latest Flash model
            logger.info("Gemini client initialized successfully")
        except ImportError:
            logger.warning("google-generativeai not installed - semantic similarity disabled")
            return None
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}")
            return None
    return _gemini_client


def normalize_text(text: str) -> str:
    """
    Normalizar texto para comparación

    - Convierte a minúsculas
    - Remueve acentos
    - Remueve caracteres especiales
    - Normaliza espacios
    """
    if not text:
        return ""

    # Minúsculas
    text = text.lower()

    # Remover acentos comunes en español
    replacements = {
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
        'ñ': 'n', 'ü': 'u'
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    # Remover caracteres especiales (mantener números y letras)
    text = re.sub(r'[^a-z0-9\s]', ' ', text)

    # Normalizar espacios múltiples
    text = re.sub(r'\s+', ' ', text).strip()

    return text


def extract_keywords(text: str, remove_stopwords: bool = True) -> set:
    """
    Extraer palabras clave de un texto

    Args:
        text: Texto a procesar
        remove_stopwords: Si se deben remover palabras comunes

    Returns:
        Set de palabras clave
    """
    # Stopwords comunes en español (palabras sin significado semántico)
    stopwords = {
        'de', 'del', 'la', 'el', 'los', 'las', 'un', 'una', 'unos', 'unas',
        'sin', 'con', 'para', 'por', 'en', 'a', 'y', 'o'
    }

    normalized = normalize_text(text)
    words = set(normalized.split())

    if remove_stopwords:
        words = words - stopwords

    return words


def keyword_similarity(text1: str, text2: str) -> float:
    """
    Calcular similitud basada en overlap de keywords (Jaccard similarity)

    Fórmula: |A ∩ B| / |A ∪ B|

    Args:
        text1: Primer texto (ej: "MAGNA 40 LITROS")
        text2: Segundo texto (ej: "Combustible Magna sin plomo")

    Returns:
        Score de 0.0 a 1.0

    Example:
        >>> keyword_similarity("MAGNA 40 LITROS", "Combustible Magna sin plomo")
        0.5  # {"magna", "40", "litros"} ∩ {"combustible", "magna", "sin", "plomo"}
    """
    kw1 = extract_keywords(text1)
    kw2 = extract_keywords(text2)

    if not kw1 or not kw2:
        return 0.0

    intersection = len(kw1 & kw2)
    union = len(kw1 | kw2)

    return intersection / union if union > 0 else 0.0


def sequence_similarity(text1: str, text2: str) -> float:
    """
    Calcular similitud basada en secuencia de caracteres (Levenshtein-like)

    Usa difflib.SequenceMatcher que implementa algoritmo similar a Levenshtein
    pero más eficiente para textos largos.

    Args:
        text1: Primer texto
        text2: Segundo texto

    Returns:
        Score de 0.0 a 1.0

    Example:
        >>> sequence_similarity("DIESEL 50L", "DIESEL 50 LITROS")
        0.85  # Muy similar en secuencia
    """
    norm1 = normalize_text(text1)
    norm2 = normalize_text(text2)

    if not norm1 or not norm2:
        return 0.0

    return SequenceMatcher(None, norm1, norm2).ratio()


def number_overlap(text1: str, text2: str) -> float:
    """
    Calcular overlap de números (útil para cantidades)

    Example:
        >>> number_overlap("40 LITROS", "Combustible 40 Litros")
        1.0  # "40" aparece en ambos
    """
    # Extraer todos los números (enteros y decimales)
    nums1 = set(re.findall(r'\d+\.?\d*', text1))
    nums2 = set(re.findall(r'\d+\.?\d*', text2))

    if not nums1 or not nums2:
        return 0.0

    intersection = len(nums1 & nums2)
    union = len(nums1 | nums2)

    return intersection / union if union > 0 else 0.0


@lru_cache(maxsize=1000)
def _gemini_semantic_similarity_cached(text1_hash: str, text2_hash: str, text1: str, text2: str) -> Optional[float]:
    """
    Calcular similitud semántica usando Gemini LLM (con cache)

    Cache basado en hashes de los textos para evitar llamadas repetidas
    """
    client = _get_gemini_client()
    if client is None:
        return None

    try:
        prompt = f"""Evalúa si estos dos conceptos de productos/servicios son equivalentes o muy similares.
Considera sinónimos, abreviaciones y variaciones comunes en español.

Concepto 1 (del ticket): {text1}
Concepto 2 (de la factura): {text2}

Responde SOLO con un número de 0 a 100, donde:
- 100 = Exactamente el mismo producto/servicio
- 80-99 = Muy similar, probablemente el mismo
- 50-79 = Similar, podría ser el mismo
- 20-49 = Algo relacionado pero diferente
- 0-19 = Completamente diferente

Score (solo el número):"""

        response = client.generate_content(prompt)
        result_text = response.text.strip()

        # Extraer número del response (por si incluye texto extra)
        import re
        match = re.search(r'\d+', result_text)
        if match:
            score = int(match.group())
            score = max(0, min(100, score))  # Clamp 0-100
            logger.info(f"Gemini semantic similarity: '{text1}' vs '{text2}' → {score}/100")
            return score / 100.0  # Retornar 0-1
        else:
            logger.warning(f"Gemini returned non-numeric response: {result_text}")
            return None

    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        return None


def gemini_semantic_similarity(text1: str, text2: str) -> Optional[float]:
    """
    Wrapper para _gemini_semantic_similarity_cached que genera hashes

    Args:
        text1: Primer texto
        text2: Segundo texto

    Returns:
        Score de 0.0 a 1.0, o None si Gemini no está disponible

    Example:
        >>> gemini_semantic_similarity("MAGNA 40 LITROS", "Combustible Magna sin plomo")
        0.85  # Gemini entiende que son similares
    """
    # Generar hashes para cache
    text1_hash = hashlib.md5(text1.encode()).hexdigest()
    text2_hash = hashlib.md5(text2.encode()).hexdigest()

    return _gemini_semantic_similarity_cached(text1_hash, text2_hash, text1, text2)


def calculate_concept_similarity(
    ticket_concept: str,
    invoice_concept: str,
    weights: Optional[Dict[str, float]] = None
) -> float:
    """
    Calcular similitud combinada entre dos conceptos

    Args:
        ticket_concept: Concepto del ticket (ej: "MAGNA 40 LITROS")
        invoice_concept: Concepto de la factura (ej: "Combustible Magna sin plomo")
        weights: Pesos personalizados (default: keyword=0.3, sequence=0.5, numbers=0.2)

    Returns:
        Score de 0.0 a 1.0
    """
    if weights is None:
        weights = {
            'keyword': 0.3,
            'sequence': 0.5,
            'numbers': 0.2
        }

    # Calcular componentes
    kw_score = keyword_similarity(ticket_concept, invoice_concept)
    seq_score = sequence_similarity(ticket_concept, invoice_concept)
    num_score = number_overlap(ticket_concept, invoice_concept)

    # Score ponderado
    combined = (
        kw_score * weights['keyword'] +
        seq_score * weights['sequence'] +
        num_score * weights['numbers']
    )

    logger.debug(f"Concept similarity: '{ticket_concept}' vs '{invoice_concept}'")
    logger.debug(f"  - Keyword: {kw_score:.2f}")
    logger.debug(f"  - Sequence: {seq_score:.2f}")
    logger.debug(f"  - Numbers: {num_score:.2f}")
    logger.debug(f"  - Combined: {combined:.2f}")

    return combined


def calculate_concept_match_score(
    ticket_concepts: List[str],
    invoice_concepts: List[Dict],
    threshold: float = 0.5
) -> int:
    """
    Calcular score de matching entre conceptos de ticket y factura

    Compara TODOS los conceptos del ticket con TODOS los de la factura
    y retorna el score MÁS ALTO encontrado.

    Args:
        ticket_concepts: Lista de conceptos del ticket
            Ejemplo: ["MAGNA 40 LITROS"]
        invoice_concepts: Lista de conceptos de la factura (objetos con 'descripcion')
            Ejemplo: [{"descripcion": "Combustible Magna sin plomo", "cantidad": "40"}]
        threshold: Umbral mínimo de similitud (default: 0.5)

    Returns:
        Score de 0 a 100
        - 0: Sin similitud
        - 100: Conceptos idénticos

    Examples:
        >>> calculate_concept_match_score(
        ...     ["MAGNA 40 LITROS"],
        ...     [{"descripcion": "Combustible Magna sin plomo"}]
        ... )
        65  # Similitud media-alta

        >>> calculate_concept_match_score(
        ...     ["DIESEL 50 LITROS"],
        ...     [{"descripcion": "DIESEL 50 LITROS"}]
        ... )
        100  # Match perfecto
    """
    if not ticket_concepts or not invoice_concepts:
        logger.debug("No concepts to compare")
        return 0

    max_similarity = 0.0
    best_match = None

    for ticket_concept in ticket_concepts:
        for invoice_concept_obj in invoice_concepts:
            # Extraer descripción del concepto de factura
            invoice_concept = invoice_concept_obj.get('descripcion', '')
            if not invoice_concept:
                continue

            # Calcular similitud
            similarity = calculate_concept_similarity(ticket_concept, invoice_concept)

            # Guardar el mejor match
            if similarity > max_similarity:
                max_similarity = similarity
                best_match = (ticket_concept, invoice_concept)

    # Convertir a score de 0-100
    score = int(max_similarity * 100)

    if best_match:
        logger.info(
            f"Best concept match (score={score}): "
            f"'{best_match[0]}' <-> '{best_match[1]}'"
        )

    return score


def interpret_concept_score(score: int) -> str:
    """
    Interpretar score de concepto en categoría de confianza

    Args:
        score: Score de 0 a 100

    Returns:
        'high', 'medium', 'low', 'none'
    """
    if score >= 70:
        return 'high'
    elif score >= 50:
        return 'medium'
    elif score >= 30:
        return 'low'
    else:
        return 'none'


def hybrid_concept_similarity(
    ticket_concept: str,
    invoice_concept: str,
    use_gemini: bool = True
) -> Tuple[float, str]:
    """
    Sistema HÍBRIDO: String matching + Gemini LLM

    Estrategia:
    1. Siempre calcular string similarity primero (rápido, gratis)
    2. Si score es claro (>70 o <30) → usar string score
    3. Si score es ambiguo (30-70) → usar Gemini para desambiguar

    Args:
        ticket_concept: Concepto del ticket
        invoice_concept: Concepto de la factura
        use_gemini: Si se debe usar Gemini para casos ambiguos (default: True)

    Returns:
        Tuple de (score 0-1, method_used)

    Examples:
        >>> hybrid_concept_similarity("DIESEL 50L", "DIESEL 50 LITROS")
        (1.0, 'string_match')  # Claro, no necesita Gemini

        >>> hybrid_concept_similarity("MAGNA", "Combustible sin plomo")
        (0.75, 'gemini')  # Ambiguo, usa Gemini
    """
    # Paso 1: String matching (siempre primero)
    string_score = calculate_concept_similarity(ticket_concept, invoice_concept)

    # Caso claro: Alta similitud
    if string_score >= 0.70:
        logger.debug(f"High string similarity ({string_score:.2f}) - skipping Gemini")
        return string_score, 'string_match'

    # Caso claro: Baja similitud
    if string_score < 0.30:
        logger.debug(f"Low string similarity ({string_score:.2f}) - skipping Gemini")
        return string_score, 'string_match'

    # Caso ambiguo (30-70): Usar Gemini si está disponible
    if not use_gemini:
        logger.debug("Gemini disabled - using string score")
        return string_score, 'string_match'

    gemini_score = gemini_semantic_similarity(ticket_concept, invoice_concept)

    if gemini_score is None:
        # Gemini no disponible → fallback a string score
        logger.debug("Gemini unavailable - using string score")
        return string_score, 'string_fallback'

    # Combinar scores: 30% string + 70% Gemini
    # (Gemini tiene más peso porque es más preciso semánticamente)
    combined_score = (string_score * 0.3) + (gemini_score * 0.7)

    logger.info(
        f"Hybrid match: '{ticket_concept}' vs '{invoice_concept}' → "
        f"string={string_score:.2f}, gemini={gemini_score:.2f}, combined={combined_score:.2f}"
    )

    return combined_score, 'hybrid_gemini'


def calculate_concept_match_score_hybrid(
    ticket_concepts: List[str],
    invoice_concepts: List[Dict],
    use_gemini: bool = True
) -> Tuple[int, Dict[str, any]]:
    """
    Versión HÍBRIDA de calculate_concept_match_score

    Usa string matching + Gemini para mayor precisión en casos ambiguos.

    Args:
        ticket_concepts: Lista de conceptos del ticket
        invoice_concepts: Lista de conceptos de la factura
        use_gemini: Si se debe usar Gemini (default: True)

    Returns:
        Tuple de (score 0-100, metadata dict)

    Metadata incluye:
        - best_match: (ticket_concept, invoice_concept)
        - method_used: 'string_match', 'hybrid_gemini', 'string_fallback'
        - string_score: Score de string matching
        - gemini_score: Score de Gemini (si se usó)
        - gemini_calls: Número de llamadas a Gemini realizadas
    """
    if not ticket_concepts or not invoice_concepts:
        return 0, {'method_used': 'none', 'gemini_calls': 0}

    max_similarity = 0.0
    best_match = None
    method_used = 'string_match'
    gemini_calls = 0
    string_score_best = 0.0
    gemini_score_best = None

    for ticket_concept in ticket_concepts:
        for invoice_concept_obj in invoice_concepts:
            invoice_concept = invoice_concept_obj.get('descripcion', '')
            if not invoice_concept:
                continue

            # Usar híbrido
            similarity, method = hybrid_concept_similarity(
                ticket_concept,
                invoice_concept,
                use_gemini=use_gemini
            )

            if 'gemini' in method:
                gemini_calls += 1

            # Guardar el mejor match
            if similarity > max_similarity:
                max_similarity = similarity
                best_match = (ticket_concept, invoice_concept)
                method_used = method

                # Guardar scores individuales para el mejor match
                string_score_best = calculate_concept_similarity(ticket_concept, invoice_concept)
                if 'gemini' in method:
                    gemini_score_best = gemini_semantic_similarity(ticket_concept, invoice_concept)

    score = int(max_similarity * 100)

    metadata = {
        'best_match': best_match,
        'method_used': method_used,
        'string_score': int(string_score_best * 100) if string_score_best else None,
        'gemini_score': int(gemini_score_best * 100) if gemini_score_best else None,
        'gemini_calls': gemini_calls
    }

    if best_match:
        logger.info(
            f"Best hybrid match (score={score}, method={method_used}): "
            f"'{best_match[0]}' <-> '{best_match[1]}'"
        )

    return score, metadata


# Ejemplos de uso y tests
if __name__ == "__main__":
    # Test 1: Gasolina Pemex
    print("\n=== Test 1: Gasolina Pemex ===")
    ticket = "MAGNA 40 LITROS"
    invoice = "Combustible Magna sin plomo"
    score = calculate_concept_match_score(
        [ticket],
        [{"descripcion": invoice}]
    )
    print(f"Score: {score}/100 - Confianza: {interpret_concept_score(score)}")

    # Test 2: Match perfecto
    print("\n=== Test 2: Match Perfecto ===")
    ticket = "DIESEL 50 LITROS"
    invoice = "DIESEL 50 LITROS"
    score = calculate_concept_match_score(
        [ticket],
        [{"descripcion": invoice}]
    )
    print(f"Score: {score}/100 - Confianza: {interpret_concept_score(score)}")

    # Test 3: Oxxo - Sin match
    print("\n=== Test 3: Sin Match ===")
    ticket = "SANDWICH JAMON"
    invoice = "Servicio de consultoría"
    score = calculate_concept_match_score(
        [ticket],
        [{"descripcion": invoice}]
    )
    print(f"Score: {score}/100 - Confianza: {interpret_concept_score(score)}")

    # Test 4: Múltiples conceptos
    print("\n=== Test 4: Múltiples Conceptos ===")
    tickets = ["COCA COLA 600ML", "SANDWICH JAMON"]
    invoices = [
        {"descripcion": "Refresco Coca Cola 600ml"},
        {"descripcion": "Alimentos preparados - Sandwich"}
    ]
    score = calculate_concept_match_score(tickets, invoices)
    print(f"Score: {score}/100 - Confianza: {interpret_concept_score(score)}")
