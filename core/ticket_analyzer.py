"""
Servicio de análisis automático de tickets usando OpenAI
Extrae el nombre del comercio y categoriza el tipo de gasto
"""

import json
import logging
import os
from typing import Dict, Optional, Tuple
import openai
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TicketAnalysis:
    """Resultado del análisis de un ticket"""
    merchant_name: str
    category: str
    confidence: float
    subcategory: Optional[str] = None
    raw_analysis: Optional[Dict] = None


class TicketAnalyzer:
    """
    Analizador inteligente de tickets usando OpenAI GPT
    """

    def __init__(self):
        self.client = None
        self._initialize_openai()

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

    def _initialize_openai(self):
        """Inicializar cliente de OpenAI"""
        try:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                logger.warning("OPENAI_API_KEY no configurada")
                return

            self.client = True  # Indicar que tenemos API key
            logger.info("Cliente OpenAI inicializado correctamente")

        except Exception as e:
            logger.error(f"Error inicializando OpenAI: {e}")
            self.client = None

    async def analyze_ticket(self, ticket_text: str) -> TicketAnalysis:
        """
        Analizar un ticket para extraer merchant y categoría

        Args:
            ticket_text: Texto extraído del ticket por OCR

        Returns:
            TicketAnalysis con merchant_name, category y confidence
        """

        if not self.client:
            logger.warning("Cliente OpenAI no disponible, usando análisis básico")
            return self._basic_analysis(ticket_text)

        try:
            # Crear prompt optimizado para análisis de tickets mexicanos
            prompt = self._create_analysis_prompt(ticket_text)

            # Llamar a OpenAI
            response = await self._call_openai(prompt)

            # Parsear respuesta
            analysis = self._parse_openai_response(response)

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

REGLAS:
- Para el merchant: usa el nombre comercial más conocido (ej: "OXXO", "Walmart", "Soriana")
- Para categoría: considera QUÉ se compró, no solo DÓNDE
- Si es un supermercado con comida preparada → "alimentacion"
- Si es gasolina → "transporte"
- Si son suministros de oficina → "oficina"

FORMATO DE RESPUESTA (JSON):
{
    "merchant_name": "Nombre del comercio",
    "category": "categoria_del_gasto",
    "confidence": 0.95,
    "subcategory": "subcategoría opcional",
    "reasoning": "breve explicación"
}

EJEMPLOS:
- OXXO con comida → {"merchant_name": "OXXO", "category": "alimentacion", "confidence": 0.9}
- Pemex gasolina → {"merchant_name": "Pemex", "category": "transporte", "confidence": 0.95}
- Office Depot → {"merchant_name": "Office Depot", "category": "oficina", "confidence": 0.9}

Responde SOLO con el JSON, sin texto adicional:
"""

        return prompt

    async def _call_openai(self, prompt: str) -> str:
        """Llamar a OpenAI API"""

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
                max_tokens=200,
                timeout=10
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"Error llamando OpenAI API: {e}")
            raise

    def _parse_openai_response(self, response: str) -> TicketAnalysis:
        """Parsear respuesta JSON de OpenAI"""

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
                raw_analysis=data
            )

        except json.JSONDecodeError as e:
            logger.error(f"Error parseando JSON de OpenAI: {e}, respuesta: {response}")
            # Intentar extracción manual
            return self._manual_parse(response)

        except Exception as e:
            logger.error(f"Error general parseando respuesta: {e}")
            return TicketAnalysis(
                merchant_name="Error de Análisis",
                category="otros",
                confidence=0.0
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
            confidence=confidence
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
            confidence=confidence
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
    Función principal para analizar contenido de tickets

    Args:
        ticket_text: Texto extraído del ticket

    Returns:
        TicketAnalysis con merchant y categoría
    """
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