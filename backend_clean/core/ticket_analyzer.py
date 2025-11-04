"""
Servicio de análisis automático de tickets usando Claude como LLM principal con OpenAI como fallback.
Extrae el nombre del comercio y categoriza el tipo de gasto.
"""

import json
import logging
import os
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass

# Importar Claude como LLM principal
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

# OpenAI como fallback
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# Importar sistema de fallbacks robusto
try:
    from core.robust_fallback_system import try_llm_analysis_with_fallbacks, fallback_system
    FALLBACK_SYSTEM_AVAILABLE = True
except ImportError:
    FALLBACK_SYSTEM_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class TicketAnalysis:
    """Resultado del análisis de un ticket"""
    merchant_name: str
    category: str
    confidence: float
    subcategory: Optional[str] = None
    raw_analysis: Optional[Dict] = None
    facturacion_urls: Optional[List[Dict]] = None


class TicketAnalyzer:
    """
    Analizador inteligente de tickets usando Claude como LLM principal y OpenAI como fallback
    """

    def __init__(self):
        self.claude_client = None
        self.openai_client = None
        self._initialize_llm_clients()

        # Categorías predefinidas para gastos empresariales
        self.categories = {
            "alimentacion": ["restaurante", "comida", "café", "bar", "catering"],
            "transporte": ["gasolina", "taxi", "uber", "metro", "autobús", "estacionamiento"],
            "oficina": ["papelería", "suministros", "equipo", "software", "internet"],
            "viajes": ["hotel", "hospedaje", "vuelo", "tren", "rental"],
            "entretenimiento": ["cine", "teatro", "eventos", "recreación"],
            "salud": ["farmacia", "médico", "dentista", "laboratorio"],
            "servicios": ["limpieza", "seguridad", "mantenimiento", "reparación"],
            "marketing": ["publicidad", "promoción", "eventos", "diseño"],
            "tecnologia": ["software", "hardware", "desarrollo", "hosting"],
            "capacitacion": ["cursos", "seminarios", "libros", "educación"],
            "otros": ["misceláneos", "varios", "general"]
        }

    def _initialize_llm_clients(self):
        """Inicializar clientes de Claude y OpenAI"""
        # Inicializar Claude como principal
        if ANTHROPIC_AVAILABLE:
            claude_key = os.getenv("ANTHROPIC_API_KEY")
            if claude_key:
                try:
                    self.claude_client = anthropic.Anthropic(api_key=claude_key)
                    logger.info("🤖 Cliente Claude inicializado como LLM principal")
                except Exception as e:
                    logger.error(f"Error inicializando Claude: {e}")
            else:
                logger.warning("ANTHROPIC_API_KEY no configurada")
        else:
            logger.warning("Anthropic no instalado - instala con: pip install anthropic")

        # Inicializar OpenAI como fallback
        if OPENAI_AVAILABLE:
            openai_key = os.getenv("OPENAI_API_KEY")
            if openai_key:
                try:
                    self.openai_client = True  # Indicar que tenemos API key
                    logger.info("🔄 Cliente OpenAI inicializado como fallback")
                except Exception as e:
                    logger.error(f"Error inicializando OpenAI: {e}")
            else:
                logger.warning("OPENAI_API_KEY no configurada")
        else:
            logger.warning("OpenAI no instalado")

    async def analyze_ticket(self, ticket_text: str) -> TicketAnalysis:
        """
        Analizar un ticket para extraer merchant y categoría

        Args:
            ticket_text: Texto extraído del ticket por OCR

        Returns:
            TicketAnalysis con merchant_name, category y confidence
        """

        if not self.claude_client and not self.openai_client:
            logger.warning("No hay LLM disponible, usando análisis básico")
            return self._basic_analysis(ticket_text)

        try:
            # Crear prompt optimizado para análisis de tickets mexicanos
            prompt = self._create_analysis_prompt(ticket_text)

            # Intentar Claude primero, luego OpenAI como fallback
            response = await self._call_llm_with_fallback(prompt)

            # Parsear respuesta
            analysis = self._parse_llm_response(response)

            logger.info(f"Ticket analizado: {analysis.merchant_name} - {analysis.category}")
            return analysis

        except Exception as e:
            logger.error(f"Error en análisis de ticket: {e}")
            return self._basic_analysis(ticket_text)

    def _create_analysis_prompt(self, ticket_text: str) -> str:
        """Crear prompt optimizado para análisis de tickets"""

        categories_list = ", ".join(self.categories.keys())

        prompt = """
Analiza este ticket de compra mexicano y extrae la información solicitada.

TICKET:
""" + ticket_text + """

INSTRUCCIONES:
1. Identifica el NOMBRE DEL COMERCIO/EMPRESA (el más específico y reconocible)
2. Clasifica el TIPO DE GASTO según estas categorías: """ + categories_list + """
3. Asigna un nivel de CONFIANZA (0.0 a 1.0)
4. Sugiere URLs de FACTURACIÓN basándote en el merchant detectado

REGLAS:
- Para el merchant: usa el nombre comercial más conocido (ej: "OXXO", "Walmart", "Soriana")
- Para categoría: considera QUÉ se compró, no solo DÓNDE
- Si es un supermercado con comida preparada → "alimentacion"
- Si es gasolina → "transporte"
- Si son suministros de oficina → "oficina"

IMPORTANTE: SOLO sugiere URLs que aparecen LITERALMENTE en el texto del ticket.
NO inventes URLs. Si no hay URLs de facturación en el texto, devuelve una lista vacía.

FORMATO DE RESPUESTA (JSON):
{
    "merchant_name": "Nombre del comercio",
    "category": "categoria_del_gasto",
    "confidence": 0.95,
    "subcategory": "subcategoría opcional",
    "reasoning": "breve explicación",
    "facturacion_urls": [
        {
            "url": "URL_EXACTA_DEL_TEXTO",
            "confidence": 0.95,
            "method": "texto_ticket"
        }
    ]
}

EJEMPLOS:
- Si el texto dice "facture en factura.oxxo.com" → {"merchant_name": "OXXO", "category": "alimentacion", "confidence": 0.9, "facturacion_urls": [{"url": "factura.oxxo.com", "confidence": 0.95, "method": "texto_ticket"}]}
- Si el texto dice "facturacion.inforest.com.mx" → {"merchant_name": "Merchant Name", "category": "alimentacion", "confidence": 0.9, "facturacion_urls": [{"url": "facturacion.inforest.com.mx", "confidence": 0.95, "method": "texto_ticket"}]}
- Si NO hay URLs en el texto → {"merchant_name": "Merchant Name", "category": "alimentacion", "confidence": 0.9, "facturacion_urls": []}

Responde SOLO con el JSON, sin texto adicional:
"""

        return prompt

    async def _call_llm_with_fallback(self, prompt: str) -> str:
        """Llamar a Claude primero, OpenAI como fallback"""

        # Intentar Claude primero
        if self.claude_client:
            try:
                logger.info("🤖 Llamando a Claude para análisis de ticket")
                response = await self._call_claude(prompt)
                logger.info("✅ Claude respondió exitosamente")
                return response
            except Exception as e:
                logger.warning(f"❌ Claude falló, intentando OpenAI: {e}")

        # Fallback a OpenAI
        if self.openai_client:
            try:
                logger.info("🔄 Usando OpenAI como fallback")
                response = await self._call_openai(prompt)
                logger.info("✅ OpenAI respondió exitosamente")
                return response
            except Exception as e:
                logger.error(f"❌ OpenAI también falló: {e}")
                raise

        raise Exception("No hay LLM disponible")

    async def _call_claude(self, prompt: str) -> str:
        """Llamar a Claude API"""
        try:
            message = self.claude_client.messages.create(
                model="claude-3-haiku-20240307",  # Modelo más barato y rápido
                max_tokens=1000,
                temperature=0.3,
                system="Eres un experto analizando tickets de compra mexicanos para categorización de gastos empresariales. Responde siempre en formato JSON válido.",
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            result = message.content[0].text.strip()
            logger.info(f"Claude response: {result[:200]}...")
            return result

        except Exception as e:
            logger.error(f"Error llamando Claude API: {e}")
            raise

    async def _call_openai(self, prompt: str) -> str:
        """Llamar a OpenAI API (fallback)"""

        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

            response = await client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "Eres un experto analizando tickets de compra mexicanos para categorización de gastos empresariales. Responde siempre en formato JSON válido."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,  # Baja temperatura para respuestas más consistentes
                max_tokens=800,
                timeout=10
            )

            result = response.choices[0].message.content.strip()
            logger.info(f"OpenAI response: {result[:200]}...")
            return result

        except Exception as e:
            logger.error(f"Error llamando OpenAI API: {e}")
            raise

    def _parse_llm_response(self, response: str) -> TicketAnalysis:
        """Parsear respuesta JSON del LLM (Claude u OpenAI)"""

        try:
            # Limpiar respuesta por si tiene texto extra
            response = response.strip()
            if response.startswith("```json"):
                response = response.replace("```json", "").replace("```", "")

            data = json.loads(response)

            return TicketAnalysis(
                merchant_name=data.get("merchant_name", "Comercio Desconocido"),
                category=data.get("category", "otros"),
                confidence=float(data.get("confidence", 0.5)),
                subcategory=data.get("subcategory"),
                raw_analysis=data,
                facturacion_urls=data.get("facturacion_urls", [])
            )

        except json.JSONDecodeError as e:
            logger.error(f"Error parseando JSON del LLM: {e}, respuesta: {response}")
            # Intentar extracción manual
            return self._manual_parse(response)

        except Exception as e:
            logger.error(f"Error general parseando respuesta: {e}")
            return TicketAnalysis(
                merchant_name="Error de Análisis",
                category="otros",
                confidence=0.0,
                facturacion_urls=[]
            )

    def _manual_parse(self, response: str) -> TicketAnalysis:
        """Intento de parseo manual si falla JSON"""

        merchant = "Comercio Desconocido"
        category = "otros"
        confidence = 0.3

        # Buscar patrones comunes
        response_lower = response.lower()

        # Merchants comunes
        if "oxxo" in response_lower:
            merchant = "OXXO"
        elif "walmart" in response_lower:
            merchant = "Walmart"
        elif "soriana" in response_lower:
            merchant = "Soriana"
        elif "pemex" in response_lower:
            merchant = "Pemex"
        elif "costco" in response_lower:
            merchant = "Costco"

        # Categorías por palabras clave
        if any(word in response_lower for word in ["comida", "restaurante", "alimentacion"]):
            category = "alimentacion"
        elif any(word in response_lower for word in ["gasolina", "transporte"]):
            category = "transporte"
        elif any(word in response_lower for word in ["oficina", "papeleria"]):
            category = "oficina"

        return TicketAnalysis(
            merchant_name=merchant,
            category=category,
            confidence=confidence,
            facturacion_urls=[]
        )

    def _basic_analysis(self, ticket_text: str) -> TicketAnalysis:
        """Análisis básico sin OpenAI"""

        text_lower = ticket_text.lower()

        # Detectar merchants comunes por palabras clave
        merchant = "Comercio Desconocido"
        category = "otros"
        confidence = 0.6

        # Merchants
        if "oxxo" in text_lower:
            merchant = "OXXO"
            category = "alimentacion"  # OXXO normalmente es comida/bebidas
        elif "walmart" in text_lower:
            merchant = "Walmart"
            category = "alimentacion"  # Supermercado
        elif "soriana" in text_lower:
            merchant = "Soriana"
            category = "alimentacion"
        elif "costco" in text_lower:
            merchant = "Costco"
            category = "alimentacion"
        elif "pemex" in text_lower:
            merchant = "Pemex"
            category = "transporte"
        elif "home depot" in text_lower:
            merchant = "Home Depot"
            category = "oficina"
        elif any(word in text_lower for word in ["restaurant", "rest ", "cafe", "bar"]):
            merchant = "Restaurante"
            category = "alimentacion"

        # Ajustar categoría según productos
        if any(word in text_lower for word in ["gasolina", "magna", "premium"]):
            category = "transporte"
        elif any(word in text_lower for word in ["oficina", "papel", "pluma", "folder"]):
            category = "oficina"

        return TicketAnalysis(
            merchant_name=merchant,
            category=category,
            confidence=confidence,
            facturacion_urls=[]
        )

    def get_category_display_name(self, category: str) -> str:
        """Obtener nombre de categoría para mostrar"""

        display_names = {
            "alimentacion": "🍽️ Alimentación",
            "transporte": "🚗 Transporte",
            "oficina": "🏢 Oficina",
            "viajes": "✈️ Viajes",
            "entretenimiento": "🎭 Entretenimiento",
            "salud": "🏥 Salud",
            "servicios": "🔧 Servicios",
            "marketing": "📢 Marketing",
            "tecnologia": "💻 Tecnología",
            "capacitacion": "📚 Capacitación",
            "otros": "📦 Otros"
        }

        return display_names.get(category, f"📦 {category.title()}")


# Función de conveniencia para usar desde otros módulos
async def analyze_ticket_content(ticket_text: str) -> TicketAnalysis:
    """
    Función principal para analizar contenido de tickets con fallbacks robustos.

    Args:
        ticket_text: Texto extraído del ticket

    Returns:
        TicketAnalysis con merchant y categoría
    """
    # Intentar con sistema de fallbacks si está disponible
    if False:  # FALLBACK_SYSTEM_AVAILABLE - Temporalmente deshabilitado
        try:
            # Usar sistema de fallbacks robusto
            analyzer = TicketAnalyzer()
            prompt = analyzer._create_analysis_prompt(ticket_text)

            result = await try_llm_analysis_with_fallbacks(ticket_text, prompt)

            if result.success:
                if isinstance(result.result, dict):
                    # Resultado del análisis básico
                    analysis_data = result.result
                else:
                    # Resultado de OpenAI (string JSON)
                    analysis_data = json.loads(result.result)

                return TicketAnalysis(
                    merchant_name=analysis_data.get("merchant_name", "Unknown"),
                    category=analysis_data.get("category", "otros"),
                    confidence=analysis_data.get("confidence", 0.5),
                    facturacion_urls=analysis_data.get("facturacion_urls", []),
                    raw_analysis={"method": "fallback_system", "service": result.service_used}
                )
            else:
                logger.warning(f"Fallback system failed: {result.error}")
        except Exception as e:
            logger.warning(f"Error in fallback system: {e}")

    # Fallback al método tradicional
    analyzer = TicketAnalyzer()
    return await analyzer.analyze_ticket(ticket_text)


if __name__ == "__main__":
    # Test del analizador
    import asyncio

    async def test_analyzer():
        """Test del analizador de tickets"""

        print("🧪 PROBANDO ANALIZADOR DE TICKETS")
        print("="*50)

        # Tickets de prueba
        test_tickets = [
            "OXXO TIENDA #1234\nCOCA COLA 600ML $18.50\nSABRITAS $15.00\nTOTAL: $33.50",
            "PEMEX ESTACION 5678\nMAGNA $500.00\nTOTAL: $500.00",
            "WALMART SUPERCENTER\nLECHE LALA $28.50\nPAN BIMBO $35.00\nTOTAL: $63.50",
            "RESTAURANTE LA CASA\nFILETE $193.00\nQUESADILLAS $90.00\nTOTAL: $283.00"
        ]

        analyzer = TicketAnalyzer()

        for i, ticket in enumerate(test_tickets, 1):
            print(f"\n📋 TICKET {i}:")
            print(f"Texto: {ticket[:50]}...")

            analysis = await analyzer.analyze_ticket(ticket)

            print(f"🏪 Merchant: {analysis.merchant_name}")
            print(f"📂 Categoría: {analyzer.get_category_display_name(analysis.category)}")
            print(f"📊 Confianza: {analysis.confidence:.1%}")

        print(f"\n✅ Análisis completado")

    # Ejecutar test
    asyncio.run(test_analyzer())