#!/usr/bin/env python3
"""
Clasificador de Estados de Cuenta con IA
==========================================
Usa LLM (Claude/GPT) para detectar automáticamente:
- Banco
- Tipo de cuenta (credit_card, debit_card, checking, savings)
- Formato del estado de cuenta
- Metadata relevante
"""
import os
import json
import logging
from typing import Optional, Dict, Any, Tuple
from datetime import datetime
import hashlib

logger = logging.getLogger(__name__)


class AIBankClassifier:
    """
    Clasificador inteligente de estados de cuenta usando LLM

    Detecta automáticamente:
    - Banco emisor
    - Tipo de cuenta (credit_card, debit_card, checking, savings, cash)
    - Formato/layout del PDF
    - Período del estado de cuenta
    - Número de cuenta (enmascarado)
    """

    def __init__(self, use_gemini: bool = True):
        """
        Args:
            use_gemini: Si True usa Google Gemini (default), si False usa OpenAI/Claude
        """
        self.use_gemini = use_gemini
        self.cache_dir = "/tmp/bank_statement_cache"
        os.makedirs(self.cache_dir, exist_ok=True)

        # Configurar cliente LLM
        if use_gemini:
            try:
                import google.generativeai as genai
                api_key = os.getenv("GEMINI_API_KEY")
                if not api_key:
                    raise ValueError("GEMINI_API_KEY not found in environment")
                genai.configure(api_key=api_key)
                self.client = genai
                # Usar gemini-2.5-flash (producción) en lugar de 2.0-flash-exp (experimental)
                self.model = os.getenv("GEMINI_COMPLETE_MODEL", "gemini-2.5-flash")
                logger.info(f"✅ Google Gemini client initialized with model: {self.model}")
            except Exception as e:
                logger.warning(f"⚠️ Gemini not available: {e}")
                self.client = None
        else:
            # Fallback a OpenAI o Claude
            try:
                import openai
                self.client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                self.model = "gpt-4o-mini"
                self.use_gemini = False
                logger.info("✅ OpenAI client initialized (fallback)")
            except Exception as e:
                logger.warning(f"⚠️ OpenAI not available: {e}")
                try:
                    import anthropic
                    self.client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
                    self.model = "claude-3-haiku-20240307"
                    self.use_gemini = False
                    logger.info("✅ Anthropic client initialized (fallback)")
                except Exception as e2:
                    logger.warning(f"⚠️ Anthropic not available: {e2}")
                    self.client = None

    def classify_statement(
        self,
        pdf_text: str,
        file_name: str,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Clasifica un estado de cuenta usando IA

        Args:
            pdf_text: Texto extraído del PDF (primeras 3 páginas)
            file_name: Nombre del archivo
            use_cache: Si True, usa cache para archivos ya procesados

        Returns:
            Dict con clasificación:
            {
                'banco': str,
                'account_type': 'credit_card' | 'debit_card' | 'checking' | 'savings',
                'confidence': float (0.0-1.0),
                'periodo_inicio': str (YYYY-MM-DD) o None,
                'periodo_fin': str (YYYY-MM-DD) o None,
                'numero_cuenta_enmascarado': str o None,
                'formato_detectado': str,
                'metadata': dict,
                'ai_model': str,
                'cached': bool
            }
        """

        # Check cache
        if use_cache:
            cached = self._get_from_cache(pdf_text, file_name)
            if cached:
                logger.info(f"📦 Using cached classification for {file_name}")
                cached['cached'] = True
                return cached

        # Si no hay LLM disponible, usar fallback rule-based
        if not self.client:
            logger.warning("⚠️ LLM not available, using rule-based fallback")
            return self._fallback_classification(pdf_text, file_name)

        try:
            # Llamar a LLM
            logger.info(f"🤖 Calling LLM to classify {file_name}...")
            classification = self._classify_with_llm(pdf_text, file_name)

            # Guardar en cache
            if use_cache:
                self._save_to_cache(pdf_text, file_name, classification)

            classification['cached'] = False
            return classification

        except Exception as e:
            logger.error(f"❌ LLM classification failed: {e}", exc_info=True)
            logger.info("⚠️ Falling back to rule-based classification")
            return self._fallback_classification(pdf_text, file_name)

    def _classify_with_llm(self, pdf_text: str, file_name: str) -> Dict[str, Any]:
        """Clasifica usando LLM (Gemini, OpenAI o Anthropic)"""

        # Truncar texto para no gastar tokens
        text_preview = pdf_text[:4000]  # ~1000 tokens

        prompt = f"""Analiza este estado de cuenta bancario mexicano y extrae la siguiente información en formato JSON:

TEXTO DEL ESTADO DE CUENTA:
{text_preview}

Responde ÚNICAMENTE con un objeto JSON válido (sin markdown, sin explicaciones) con esta estructura:

{{
    "banco": "Nombre del banco (ej: BBVA, Santander, Inbursa, Banamex, Banorte, HSBC, Scotiabank, etc.)",
    "account_type": "credit_card | debit_card | checking | savings",
    "confidence": 0.95,
    "periodo_inicio": "YYYY-MM-DD o null",
    "periodo_fin": "YYYY-MM-DD o null",
    "numero_cuenta_enmascarado": "****1234 o null",
    "formato_detectado": "descripción breve del formato (ej: PDF estándar BBVA, Excel Inbursa, etc.)",
    "metadata": {{
        "tiene_movimientos_credito": true,
        "tiene_limite_credito": false,
        "tiene_pago_minimo": false,
        "idioma": "es"
    }}
}}

IMPORTANTE:
- "account_type" debe ser EXACTAMENTE uno de: credit_card, debit_card, checking, savings
- Para tarjetas de CRÉDITO usa "credit_card" (tienen límite de crédito, pago mínimo, fecha de corte)
- Para tarjetas de DÉBITO o cuentas de cheques usa "debit_card" o "checking" (solo tienen saldo disponible)
- "confidence" debe ser un número entre 0.0 y 1.0
- Si no puedes determinar algo, usa null
- Responde SOLO el JSON, sin texto adicional"""

        if self.use_gemini:
            # Google Gemini
            model = self.client.GenerativeModel(
                model_name=self.model,
                generation_config={
                    "temperature": 0.1,
                    "max_output_tokens": 500,
                }
            )

            response = model.generate_content(prompt)
            result_text = response.text.strip()

        elif hasattr(self.client, 'chat'):
            # OpenAI
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Eres un experto en análisis de estados de cuenta bancarios mexicanos. Respondes solo con JSON válido."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=500
            )

            result_text = response.choices[0].message.content.strip()

        else:
            # Anthropic
            response = self.client.messages.create(
                model=self.model,
                max_tokens=500,
                temperature=0.1,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            result_text = response.content[0].text.strip()

        # Parsear JSON
        # Limpiar markdown si aparece
        result_text = result_text.replace("```json", "").replace("```", "").strip()

        classification = json.loads(result_text)

        # Validar campos obligatorios
        required_fields = ['banco', 'account_type', 'confidence']
        for field in required_fields:
            if field not in classification:
                raise ValueError(f"Missing required field: {field}")

        # Validar account_type
        valid_types = ['credit_card', 'debit_card', 'checking', 'savings']
        if classification['account_type'] not in valid_types:
            logger.warning(f"⚠️ Invalid account_type: {classification['account_type']}, defaulting to 'checking'")
            classification['account_type'] = 'checking'

        # Agregar metadata
        classification['ai_model'] = self.model
        classification['classified_at'] = datetime.now().isoformat()

        logger.info(f"✅ LLM Classification: {classification['banco']} - {classification['account_type']} (confidence: {classification['confidence']:.2f})")

        return classification

    def _fallback_classification(self, pdf_text: str, file_name: str) -> Dict[str, Any]:
        """Fallback rule-based cuando LLM no disponible"""
        from .bank_detector import BankDetector

        detector = BankDetector()
        banco = detector.detect_bank_from_text(pdf_text)

        # Detectar tipo de cuenta con heurísticas
        text_upper = pdf_text.upper()
        account_type = 'checking'  # Default
        confidence = 0.5

        # Palabras clave para tarjeta de crédito
        credit_keywords = [
            'TARJETA DE CREDITO', 'TARJETA DE CRÉDITO', 'CREDIT CARD',
            'LIMITE DE CREDITO', 'LÍMITE DE CRÉDITO', 'CREDIT LIMIT',
            'PAGO MINIMO', 'PAGO MÍNIMO', 'MINIMUM PAYMENT',
            'FECHA DE CORTE', 'SALDO PARA NO GENERAR INTERESES'
        ]

        debit_keywords = [
            'TARJETA DE DEBITO', 'TARJETA DE DÉBITO', 'DEBIT CARD',
            'CUENTA DE CHEQUES', 'CHECKING ACCOUNT'
        ]

        credit_score = sum(1 for kw in credit_keywords if kw in text_upper)
        debit_score = sum(1 for kw in debit_keywords if kw in text_upper)

        if credit_score >= 2:
            account_type = 'credit_card'
            confidence = min(0.8, 0.5 + (credit_score * 0.1))
        elif debit_score >= 1:
            account_type = 'debit_card'
            confidence = min(0.7, 0.5 + (debit_score * 0.1))

        logger.info(f"📋 Rule-based Classification: {banco} - {account_type} (confidence: {confidence:.2f})")

        return {
            'banco': banco or 'Unknown',
            'account_type': account_type,
            'confidence': confidence,
            'periodo_inicio': None,
            'periodo_fin': None,
            'numero_cuenta_enmascarado': None,
            'formato_detectado': 'PDF genérico',
            'metadata': {
                'credit_score': credit_score,
                'debit_score': debit_score
            },
            'ai_model': 'rule_based_fallback',
            'classified_at': datetime.now().isoformat(),
            'cached': False
        }

    def _get_cache_key(self, pdf_text: str, file_name: str) -> str:
        """Genera cache key basado en contenido"""
        # Hash del contenido (primeros 2000 chars)
        content_hash = hashlib.sha256(pdf_text[:2000].encode()).hexdigest()[:16]
        return f"{content_hash}_{file_name}"

    def _get_from_cache(self, pdf_text: str, file_name: str) -> Optional[Dict[str, Any]]:
        """Obtiene clasificación del cache si existe"""
        cache_key = self._get_cache_key(pdf_text, file_name)
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")

        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"⚠️ Cache read failed: {e}")

        return None

    def _save_to_cache(self, pdf_text: str, file_name: str, classification: Dict[str, Any]):
        """Guarda clasificación en cache"""
        cache_key = self._get_cache_key(pdf_text, file_name)
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")

        try:
            with open(cache_file, 'w') as f:
                json.dump(classification, f, indent=2)
        except Exception as e:
            logger.warning(f"⚠️ Cache write failed: {e}")


# Función helper para uso fácil
def classify_bank_statement_with_ai(
    pdf_text: str,
    file_name: str,
    use_gemini: bool = True
) -> Dict[str, Any]:
    """
    Helper function para clasificar un estado de cuenta con IA

    Args:
        pdf_text: Texto extraído del PDF
        file_name: Nombre del archivo
        use_gemini: Si True usa Google Gemini (default), si False usa OpenAI/Claude

    Returns:
        Dict con clasificación completa

    Example:
        >>> pdf_text = extract_text_from_pdf("estado_cuenta.pdf")
        >>> result = classify_bank_statement_with_ai(pdf_text, "estado_cuenta.pdf")
        >>> print(result['banco'])  # "BBVA"
        >>> print(result['account_type'])  # "credit_card"
    """
    classifier = AIBankClassifier(use_gemini=use_gemini)
    return classifier.classify_statement(pdf_text, file_name, use_cache=True)
