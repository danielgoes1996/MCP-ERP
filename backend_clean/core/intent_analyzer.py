"""
Intent Analyzer - Sistema de análisis de intenciones para detectar gastos en mensajes
"""

import os
import logging
import json
import re
from datetime import datetime
from typing import Dict, Any, List
from dataclasses import dataclass

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

logger = logging.getLogger(__name__)


@dataclass
class ExpenseIntent:
    """Representa una intención de gasto detectada"""
    is_expense: bool
    confidence: float
    extracted_data: Dict[str, Any]
    reasoning: str
    original_text: str
    source: str  # 'whatsapp', 'email', 'sms', etc.


class IntentAnalyzer:
    """
    Analizador de intenciones para detectar gastos en mensajes de texto
    usando OpenAI GPT para análisis contextual
    """

    def __init__(self):
        if not OpenAI:
            logger.warning("OpenAI library not available, using rule-based intent analysis")
            self.client = None
        else:
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                logger.warning("OPENAI_API_KEY not configured, using rule-based intent analysis")
                self.client = None
            else:
                self.client = OpenAI(api_key=api_key)

        # Patrones de gastos en español
        self.EXPENSE_PATTERNS = {
            'explicit_expense': [
                r'gasté?\s+\$?(\d+(?:\.\d{2})?)',
                r'pagué?\s+\$?(\d+(?:\.\d{2})?)',
                r'compré?\s+.*\$?(\d+(?:\.\d{2})?)',
                r'cuesta\s+\$?(\d+(?:\.\d{2})?)',
                r'costó\s+\$?(\d+(?:\.\d{2})?)',
                r'factura\s+.*\$?(\d+(?:\.\d{2})?)',
                r'recibo\s+.*\$?(\d+(?:\.\d{2})?)',
            ],
            'expense_keywords': [
                'compra', 'gasto', 'pago', 'factura', 'recibo', 'ticket',
                'combustible', 'gasolina', 'comida', 'almuerzo', 'cena',
                'transporte', 'uber', 'taxi', 'hotel', 'restaurante',
                'oficina', 'suministros', 'licencia', 'suscripción',
                'servicio', 'reparación', 'mantenimiento'
            ],
            'amount_patterns': [
                r'\$(\d+(?:\.\d{2})?)',
                r'(\d+(?:\.\d{2})?)\s*pesos',
                r'(\d+(?:\.\d{2})?)\s*mxn',
                r'(\d+(?:\.\d{2})?)\s*dlls?',
                r'(\d+(?:\.\d{2})?)\s*usd',
            ],
            'vendor_indicators': [
                r'en\s+(\w+(?:\s+\w+)*)',
                r'de\s+(\w+(?:\s+\w+)*)',
                r'con\s+(\w+(?:\s+\w+)*)',
                r'@(\w+)',
                r'#(\w+)',
            ]
        }

        # Categorías automáticas basadas en keywords
        self.AUTO_CATEGORIES = {
            'combustible': ['gasolina', 'diesel', 'combustible', 'pemex', 'shell', 'bp'],
            'alimentos': ['comida', 'almuerzo', 'desayuno', 'cena', 'restaurante', 'starbucks', 'mcdonalds'],
            'transporte': ['uber', 'taxi', 'transporte', 'vuelo', 'avion', 'autobus', 'metro'],
            'hospedaje': ['hotel', 'hospedaje', 'alojamiento', 'airbnb', 'booking'],
            'tecnologia': ['licencia', 'software', 'suscripción', 'microsoft', 'adobe', 'google'],
            'oficina': ['papeleria', 'oficina', 'suministros', 'office depot', 'materiales'],
            'servicios': ['internet', 'telefono', 'luz', 'agua', 'electricidad', 'servicio'],
            'marketing': ['publicidad', 'marketing', 'facebook', 'google ads', 'instagram']
        }

    def analyze_intent(self, text: str, source: str = 'unknown', metadata: Dict[str, Any] = None) -> ExpenseIntent:
        """
        Analiza un mensaje de texto para detectar intenciones de gasto

        Args:
            text: Texto del mensaje
            source: Fuente del mensaje ('whatsapp', 'email', etc.)
            metadata: Metadatos adicionales (remitente, fecha, etc.)

        Returns:
            ExpenseIntent con la evaluación del mensaje
        """

        if self.client:
            return self._analyze_with_llm(text, source, metadata)
        else:
            return self._analyze_with_rules(text, source, metadata)

    def _analyze_with_llm(self, text: str, source: str, metadata: Dict[str, Any] = None) -> ExpenseIntent:
        """Análisis usando OpenAI LLM"""

        try:
            # Crear prompt estructurado para detección de gastos
            prompt = self._create_expense_detection_prompt(text, source, metadata)

            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Eres un experto en detección de gastos empresariales en mensajes de texto. Analiza el contexto y determina si el mensaje contiene información sobre un gasto."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=600
            )

            result_text = response.choices[0].message.content.strip()
            return self._parse_llm_intent_response(result_text, text, source)

        except Exception as e:
            logger.error(f"Error in LLM intent analysis: {e}")
            # Fallback a reglas básicas
            return self._analyze_with_rules(text, source, metadata)

    def _create_expense_detection_prompt(self, text: str, source: str, metadata: Dict[str, Any] = None) -> str:
        """Crear prompt para detección de gastos"""

        prompt = f"""
ANÁLISIS DE INTENCIÓN DE GASTO EN MENSAJE

TEXTO A ANALIZAR: "{text}"
FUENTE: {source}
METADATOS: {json.dumps(metadata or {}, ensure_ascii=False)}

CONTEXTO:
Estás analizando mensajes que podrían contener información sobre gastos empresariales.
Los mensajes pueden venir de WhatsApp, correo electrónico, SMS, etc.

TIPOS DE GASTOS A DETECTAR:
- Compras explícitas ("compré...", "gasté...", "pagué...")
- Facturas y recibos ("factura de...", "recibo por...")
- Servicios contratados ("suscripción", "licencia", "servicio")
- Gastos de viaje (combustible, hotel, transporte)
- Comidas de negocios (restaurantes, almuerzos corporativos)
- Suministros de oficina
- Gastos de tecnología

INFORMACIÓN A EXTRAER:
- Descripción del gasto
- Monto (en pesos mexicanos, dólares, etc.)
- Proveedor/comercio
- Categoría probable
- Fecha (si se menciona)
- Método de pago (si se menciona)

RESPUESTA EN FORMATO JSON:
{{
    "is_expense": true/false,
    "confidence": 0.85,
    "reasoning": "explicación clara de por qué es o no es un gasto",
    "extracted_data": {{
        "descripcion": "descripción del gasto detectado",
        "monto": 0.00,
        "moneda": "MXN",
        "proveedor": "nombre del proveedor",
        "categoria": "categoría sugerida",
        "fecha_probable": "YYYY-MM-DD",
        "metodo_pago": "efectivo/tarjeta/transferencia",
        "keywords_encontradas": ["palabra1", "palabra2"]
    }}
}}

INSTRUCCIONES:
1. Si NO es claramente un gasto, marca is_expense: false
2. Solo marca is_expense: true si hay evidencia clara de transacción monetaria
3. La confianza debe reflejar qué tan seguro estás
4. Extrae todos los datos posibles, incluso si algunos quedan como null
5. Sé conservador: es mejor no detectar un gasto que crear falsos positivos
"""

        return prompt

    def _parse_llm_intent_response(self, response_text: str, original_text: str, source: str) -> ExpenseIntent:
        """Parsear respuesta JSON del LLM"""

        try:
            # Extraer JSON de la respuesta
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())

                return ExpenseIntent(
                    is_expense=result.get('is_expense', False),
                    confidence=result.get('confidence', 0.5),
                    extracted_data=result.get('extracted_data', {}),
                    reasoning=result.get('reasoning', 'Análisis LLM completado'),
                    original_text=original_text,
                    source=source
                )
            else:
                raise ValueError("No JSON found in LLM response")

        except Exception as e:
            logger.error(f"Error parsing LLM intent response: {e}")
            # Fallback con datos básicos
            return ExpenseIntent(
                is_expense=False,
                confidence=0.1,
                extracted_data={},
                reasoning=f'Error parseando respuesta LLM: {str(e)}',
                original_text=original_text,
                source=source
            )

    def _analyze_with_rules(self, text: str, source: str, metadata: Dict[str, Any] = None) -> ExpenseIntent:
        """Análisis usando reglas básicas como fallback"""

        text_lower = text.lower()

        # Buscar patrones explícitos de gasto
        explicit_matches = []
        for pattern in self.EXPENSE_PATTERNS['explicit_expense']:
            matches = re.findall(pattern, text_lower, re.IGNORECASE)
            explicit_matches.extend(matches)

        # Buscar keywords de gasto
        keyword_matches = []
        for keyword in self.EXPENSE_PATTERNS['expense_keywords']:
            if keyword in text_lower:
                keyword_matches.append(keyword)

        # Buscar montos
        amounts = []
        for pattern in self.EXPENSE_PATTERNS['amount_patterns']:
            matches = re.findall(pattern, text_lower, re.IGNORECASE)
            amounts.extend([float(m) for m in matches if m])

        # Buscar proveedores
        vendors = []
        for pattern in self.EXPENSE_PATTERNS['vendor_indicators']:
            matches = re.findall(pattern, text, re.IGNORECASE)
            vendors.extend(matches)

        # Determinar si es un gasto
        is_expense = False
        confidence = 0.0
        reasoning = ""

        if explicit_matches and amounts:
            is_expense = True
            confidence = 0.9
            reasoning = f"Patrón explícito de gasto encontrado: {explicit_matches[0]} con monto {amounts[0]}"
        elif keyword_matches and amounts:
            is_expense = True
            confidence = 0.7
            reasoning = f"Keywords de gasto ({', '.join(keyword_matches)}) con monto detectado"
        elif len(keyword_matches) >= 2:
            is_expense = True
            confidence = 0.5
            reasoning = f"Múltiples keywords de gasto: {', '.join(keyword_matches)}"
        else:
            reasoning = "No se detectaron patrones claros de gasto"

        # Extraer datos
        extracted_data = {}
        if is_expense:
            extracted_data = {
                "descripcion": self._extract_description(text, keyword_matches),
                "monto": amounts[0] if amounts else None,
                "moneda": "MXN",  # Asumir MXN por defecto
                "proveedor": vendors[0] if vendors else None,
                "categoria": self._auto_categorize(text_lower),
                "fecha_probable": datetime.now().strftime('%Y-%m-%d'),
                "keywords_encontradas": keyword_matches
            }

        return ExpenseIntent(
            is_expense=is_expense,
            confidence=confidence,
            extracted_data=extracted_data,
            reasoning=reasoning,
            original_text=text,
            source=source
        )

    def _extract_description(self, text: str, keywords: List[str]) -> str:
        """Extraer descripción del gasto"""
        # Tomar las primeras 100 caracteres o hasta el primer punto
        desc = text[:100]
        if '.' in desc:
            desc = desc[:desc.index('.')]
        return desc.strip()

    def _auto_categorize(self, text_lower: str) -> str:
        """Categorización automática basada en keywords"""
        for category, keywords in self.AUTO_CATEGORIES.items():
            if any(keyword in text_lower for keyword in keywords):
                return category
        return 'oficina'  # Categoría por defecto

    def batch_analyze_messages(self, messages: List[Dict[str, Any]]) -> List[ExpenseIntent]:
        """
        Analizar múltiples mensajes en lote

        Args:
            messages: Lista de mensajes con formato:
                [{"text": "...", "source": "...", "metadata": {...}}, ...]

        Returns:
            Lista de ExpenseIntent para cada mensaje
        """
        results = []
        for msg in messages:
            try:
                intent = self.analyze_intent(
                    text=msg.get('text', ''),
                    source=msg.get('source', 'unknown'),
                    metadata=msg.get('metadata', {})
                )
                results.append(intent)
            except Exception as e:
                logger.error(f"Error analyzing message: {e}")
                results.append(ExpenseIntent(
                    is_expense=False,
                    confidence=0.0,
                    extracted_data={},
                    reasoning=f'Error en análisis: {str(e)}',
                    original_text=msg.get('text', ''),
                    source=msg.get('source', 'unknown')
                ))
        return results

    def get_expense_statistics(self, intents: List[ExpenseIntent]) -> Dict[str, Any]:
        """Obtener estadísticas de los análisis realizados"""

        total_messages = len(intents)
        detected_expenses = [i for i in intents if i.is_expense]

        stats = {
            'total_messages': total_messages,
            'detected_expenses': len(detected_expenses),
            'detection_rate': len(detected_expenses) / total_messages if total_messages > 0 else 0,
            'average_confidence': sum(i.confidence for i in detected_expenses) / len(detected_expenses) if detected_expenses else 0,
            'by_source': {},
            'by_category': {},
            'total_amount': 0
        }

        # Estadísticas por fuente
        for intent in intents:
            source = intent.source
            stats['by_source'][source] = stats['by_source'].get(source, 0) + 1

        # Estadísticas por categoría y montos
        for intent in detected_expenses:
            category = intent.extracted_data.get('categoria', 'sin_categoria')
            stats['by_category'][category] = stats['by_category'].get(category, 0) + 1

            amount = intent.extracted_data.get('monto', 0)
            if amount:
                stats['total_amount'] += amount

        return stats


# Instancia global del analizador
_intent_analyzer = None

def get_intent_analyzer() -> IntentAnalyzer:
    """Obtener instancia global del analizador de intenciones"""
    global _intent_analyzer
    if _intent_analyzer is None:
        _intent_analyzer = IntentAnalyzer()
    return _intent_analyzer


def analyze_message_intent(text: str, source: str = 'unknown', metadata: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Función helper para analizar intención de gasto en un mensaje

    Returns:
        Diccionario con el análisis de intención
    """
    analyzer = get_intent_analyzer()
    intent = analyzer.analyze_intent(text, source, metadata)

    return {
        'is_expense': intent.is_expense,
        'confidence': intent.confidence,
        'extracted_data': intent.extracted_data,
        'reasoning': intent.reasoning,
        'original_text': intent.original_text,
        'source': intent.source,
        'analysis_method': 'llm' if analyzer.client else 'rules'
    }