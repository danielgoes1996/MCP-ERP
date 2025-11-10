"""
Category Predictor - Usa LLM contextual para predecir categorías de gastos
"""

import os
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

logger = logging.getLogger(__name__)


@dataclass
class CategoryPrediction:
    """Representa una predicción de categoría"""
    category: str
    confidence: float
    reasoning: str
    alternatives: List[Dict[str, Any]]


class CategoryPredictor:
    """
    Predictor inteligente de categorías usando LLM con contexto empresarial
    """

    def __init__(self):
        if not OpenAI:
            logger.warning("OpenAI library not available, using fallback category prediction")
            self.client = None
        else:
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                logger.warning("OPENAI_API_KEY not configured, using fallback category prediction")
                self.client = None
            else:
                self.client = OpenAI(api_key=api_key)

        # Catálogo de categorías empresariales estándar
        self.BUSINESS_CATEGORIES = {
            'combustible': {
                'keywords': ['gasolina', 'combustible', 'pemex', 'shell', 'bp', 'total', 'diesel'],
                'providers': ['pemex', 'shell', 'bp', 'total', 'gas'],
                'description': 'Gastos de combustible y lubricantes para vehículos'
            },
            'alimentos': {
                'keywords': ['restaurante', 'comida', 'almuerzo', 'desayuno', 'cena', 'café', 'lunch', 'food'],
                'providers': ['mcdonalds', 'subway', 'starbucks', 'dominos'],
                'description': 'Gastos en alimentos y bebidas para el personal'
            },
            'transporte': {
                'keywords': ['uber', 'taxi', 'transporte', 'viaje', 'avion', 'autobus', 'metro'],
                'providers': ['uber', 'cabify', 'aeromexico', 'volaris', 'ado'],
                'description': 'Gastos de transporte y viajes de negocio'
            },
            'hospedaje': {
                'keywords': ['hotel', 'hospedaje', 'alojamiento', 'estancia', 'booking'],
                'providers': ['marriott', 'hilton', 'city express', 'booking', 'airbnb'],
                'description': 'Gastos de hospedaje en viajes de negocio'
            },
            'oficina': {
                'keywords': ['papeleria', 'oficina', 'suministros', 'materiales', 'impresora', 'papel'],
                'providers': ['office depot', 'walmart', 'costco', 'staples'],
                'description': 'Suministros y materiales de oficina'
            },
            'tecnologia': {
                'keywords': ['software', 'licencia', 'microsoft', 'adobe', 'google', 'zoom', 'slack'],
                'providers': ['microsoft', 'adobe', 'google', 'zoom', 'slack', 'aws'],
                'description': 'Software, licencias y servicios tecnológicos'
            },
            'servicios': {
                'keywords': ['internet', 'telefono', 'celular', 'comunicacion', 'luz', 'agua', 'electricidad'],
                'providers': ['telmex', 'telcel', 'cfe', 'izzi', 'totalplay'],
                'description': 'Servicios básicos y comunicaciones'
            },
            'marketing': {
                'keywords': ['publicidad', 'marketing', 'promocion', 'facebook', 'google ads', 'instagram'],
                'providers': ['facebook', 'google', 'instagram', 'linkedin'],
                'description': 'Gastos de marketing y publicidad'
            },
            'honorarios': {
                'keywords': ['consultor', 'asesor', 'profesional', 'servicio', 'honorarios'],
                'providers': ['despacho', 'consultoria'],
                'description': 'Honorarios a profesionales independientes'
            },
            'capacitacion': {
                'keywords': ['curso', 'capacitacion', 'entrenamiento', 'seminario', 'certificacion'],
                'providers': ['udemy', 'coursera', 'platzi'],
                'description': 'Cursos y capacitación del personal'
            }
        }

    def predict_category(self,
                        description: str,
                        amount: float = None,
                        provider_name: str = None,
                        expense_history: List[Dict[str, Any]] = None) -> CategoryPrediction:
        """
        Predice la categoría de un gasto usando LLM con contexto empresarial

        Args:
            description: Descripción del gasto
            amount: Monto del gasto (opcional)
            provider_name: Nombre del proveedor (opcional)
            expense_history: Historial de gastos para contexto (opcional)

        Returns:
            CategoryPrediction con la categoría sugerida y alternativas
        """

        if self.client:
            return self._predict_with_llm(description, amount, provider_name, expense_history)
        else:
            return self._predict_with_rules(description, amount, provider_name)

    def _predict_with_llm(self,
                         description: str,
                         amount: float = None,
                         provider_name: str = None,
                         expense_history: List[Dict[str, Any]] = None) -> CategoryPrediction:
        """Predicción usando LLM con contexto empresarial"""

        try:
            # Construir contexto para el LLM
            context = self._build_context(description, amount, provider_name, expense_history)

            # Crear prompt estructurado
            prompt = self._create_prediction_prompt(context)

            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Eres un experto en categorización de gastos empresariales. Analiza el contexto y predice la categoría más apropiada."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # Baja temperatura para consistencia
                max_tokens=500
            )

            result_text = response.choices[0].message.content.strip()

            # Parsear respuesta del LLM
            return self._parse_llm_response(result_text)

        except Exception as e:
            logger.error(f"Error in LLM category prediction: {e}")
            # Fallback a reglas básicas
            return self._predict_with_rules(description, amount, provider_name)

    def _build_context(self,
                      description: str,
                      amount: float = None,
                      provider_name: str = None,
                      expense_history: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Construye contexto para el LLM"""

        context = {
            'gasto_actual': {
                'descripcion': description,
                'monto': amount,
                'proveedor': provider_name
            },
            'categorias_disponibles': list(self.BUSINESS_CATEGORIES.keys()),
            'definiciones_categorias': {
                cat: info['description']
                for cat, info in self.BUSINESS_CATEGORIES.items()
            }
        }

        # Agregar patrones del historial si está disponible
        if expense_history:
            context['patrones_historicos'] = self._analyze_expense_patterns(expense_history)

        # Agregar información de proveedor conocido
        if provider_name:
            matching_category = self._find_provider_category(provider_name)
            if matching_category:
                context['proveedor_conocido'] = {
                    'categoria_usual': matching_category,
                    'confianza': 'alta'
                }

        return context

    def _create_prediction_prompt(self, context: Dict[str, Any]) -> str:
        """Crea el prompt estructurado para el LLM"""

        prompt = f"""
ANÁLISIS DE CATEGORIZACIÓN DE GASTO EMPRESARIAL

GASTO A CATEGORIZAR:
- Descripción: "{context['gasto_actual']['descripcion']}"
- Monto: ${context['gasto_actual']['monto'] or 'N/A'}
- Proveedor: {context['gasto_actual']['proveedor'] or 'N/A'}

CATEGORÍAS DISPONIBLES:
"""

        for category, definition in context['definiciones_categorias'].items():
            prompt += f"- {category}: {definition}\n"

        if 'proveedor_conocido' in context:
            prompt += f"""
PROVEEDOR CONOCIDO:
- Este proveedor típicamente se clasifica como: {context['proveedor_conocido']['categoria_usual']}
"""

        if 'patrones_historicos' in context:
            prompt += f"""
PATRONES HISTÓRICOS DEL USUARIO:
- Categorías más frecuentes: {', '.join(context['patrones_historicos']['top_categories'])}
- Proveedores recurrentes: {', '.join(context['patrones_historicos']['frequent_providers'])}
"""

        prompt += """
INSTRUCCIONES:
1. Analiza la descripción, monto y proveedor del gasto
2. Considera los patrones históricos del usuario
3. Determina la categoría más apropiada
4. Proporciona 2-3 alternativas si hay ambigüedad
5. Explica tu razonamiento

RESPUESTA EN FORMATO JSON:
{
    "categoria_principal": "categoria_elegida",
    "confianza": 0.85,
    "razonamiento": "explicación de por qué elegiste esta categoría",
    "alternativas": [
        {"categoria": "segunda_opcion", "confianza": 0.60, "razon": "explicación"},
        {"categoria": "tercera_opcion", "confianza": 0.30, "razon": "explicación"}
    ]
}
"""

        return prompt

    def _parse_llm_response(self, response_text: str) -> CategoryPrediction:
        """Parsea la respuesta JSON del LLM"""

        try:
            # Intentar extraer JSON de la respuesta
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())

                return CategoryPrediction(
                    category=result.get('categoria_principal', 'oficina'),
                    confidence=result.get('confianza', 0.5),
                    reasoning=result.get('razonamiento', 'Predicción basada en análisis LLM'),
                    alternatives=result.get('alternativas', [])
                )
            else:
                raise ValueError("No JSON found in response")

        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")
            # Fallback parsing
            return CategoryPrediction(
                category='oficina',
                confidence=0.3,
                reasoning='Error parseando respuesta LLM, usando categoría por defecto',
                alternatives=[]
            )

    def _predict_with_rules(self,
                           description: str,
                           amount: float = None,
                           provider_name: str = None) -> CategoryPrediction:
        """Predicción usando reglas básicas como fallback"""

        description_lower = description.lower()
        provider_lower = (provider_name or '').lower()

        # Buscar por proveedor primero
        for category, info in self.BUSINESS_CATEGORIES.items():
            for provider in info['providers']:
                if provider in provider_lower:
                    return CategoryPrediction(
                        category=category,
                        confidence=0.85,
                        reasoning=f'Proveedor "{provider_name}" típicamente asociado con {category}',
                        alternatives=[]
                    )

        # Buscar por keywords en descripción
        category_scores = {}
        for category, info in self.BUSINESS_CATEGORIES.items():
            score = 0
            matched_keywords = []

            for keyword in info['keywords']:
                if keyword in description_lower:
                    score += 1
                    matched_keywords.append(keyword)

            if score > 0:
                category_scores[category] = {
                    'score': score,
                    'keywords': matched_keywords
                }

        if category_scores:
            # Ordenar por score
            best_category = max(category_scores.keys(), key=lambda k: category_scores[k]['score'])
            best_score = category_scores[best_category]['score']
            matched_words = category_scores[best_category]['keywords']

            confidence = min(0.9, 0.5 + (best_score * 0.2))

            # Crear alternativas
            alternatives = []
            for cat, data in category_scores.items():
                if cat != best_category and data['score'] >= best_score * 0.5:
                    alternatives.append({
                        'categoria': cat,
                        'confianza': min(0.8, confidence * 0.8),
                        'razon': f'Keywords encontradas: {", ".join(data["keywords"])}'
                    })

            return CategoryPrediction(
                category=best_category,
                confidence=confidence,
                reasoning=f'Keywords encontradas: {", ".join(matched_words)}',
                alternatives=alternatives[:2]  # Solo top 2 alternativas
            )

        # Si no hay coincidencias, usar categoría por defecto
        return CategoryPrediction(
            category='oficina',
            confidence=0.3,
            reasoning='No se encontraron keywords específicas, usando categoría por defecto',
            alternatives=[
                {'categoria': 'servicios', 'confianza': 0.25, 'razon': 'Alternativa general'},
                {'categoria': 'alimentos', 'confianza': 0.20, 'razon': 'Alternativa común'}
            ]
        )

    def _analyze_expense_patterns(self, expense_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analiza patrones en el historial de gastos"""

        if not expense_history:
            return {'top_categories': [], 'frequent_providers': []}

        # Contar categorías
        category_counts = {}
        provider_counts = {}

        for expense in expense_history[-50:]:  # Solo últimos 50 gastos
            category = expense.get('categoria')
            if category:
                category_counts[category] = category_counts.get(category, 0) + 1

            provider = expense.get('proveedor')
            if provider and isinstance(provider, dict):
                name = provider.get('nombre', '')
            elif provider:
                name = str(provider)
            else:
                name = ''

            if name:
                provider_counts[name] = provider_counts.get(name, 0) + 1

        # Top categorías y proveedores
        top_categories = sorted(category_counts.keys(),
                               key=lambda k: category_counts[k],
                               reverse=True)[:5]

        frequent_providers = sorted(provider_counts.keys(),
                                   key=lambda k: provider_counts[k],
                                   reverse=True)[:5]

        return {
            'top_categories': top_categories,
            'frequent_providers': frequent_providers,
            'category_distribution': category_counts,
            'provider_distribution': provider_counts
        }

    def _find_provider_category(self, provider_name: str) -> Optional[str]:
        """Encuentra la categoría típica de un proveedor conocido"""

        provider_lower = provider_name.lower()

        for category, info in self.BUSINESS_CATEGORIES.items():
            for known_provider in info['providers']:
                if known_provider in provider_lower or provider_lower in known_provider:
                    return category

        return None

    def get_category_suggestions(self, partial_input: str) -> List[Dict[str, Any]]:
        """Obtiene sugerencias de categorías para autocompletado"""

        if not partial_input:
            # Retornar categorías más comunes
            return [
                {'category': cat, 'description': info['description']}
                for cat, info in list(self.BUSINESS_CATEGORIES.items())[:5]
            ]

        partial_lower = partial_input.lower()
        suggestions = []

        for category, info in self.BUSINESS_CATEGORIES.items():
            if (partial_lower in category.lower() or
                any(partial_lower in keyword for keyword in info['keywords'])):
                suggestions.append({
                    'category': category,
                    'description': info['description']
                })

        return suggestions[:8]  # Máximo 8 sugerencias


# Instancia global del predictor
_category_predictor = None

def get_category_predictor() -> CategoryPredictor:
    """Obtener instancia global del predictor de categorías"""
    global _category_predictor
    if _category_predictor is None:
        _category_predictor = CategoryPredictor()
    return _category_predictor


def predict_expense_category(description: str,
                           amount: float = None,
                           provider_name: str = None,
                           expense_history: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Función helper para predecir categoría de un gasto

    Returns:
        Diccionario con predicción y alternativas
    """
    predictor = get_category_predictor()
    prediction = predictor.predict_category(description, amount, provider_name, expense_history)

    return {
        'categoria_sugerida': prediction.category,
        'confianza': prediction.confidence,
        'razonamiento': prediction.reasoning,
        'alternativas': prediction.alternatives,
        'metodo_prediccion': 'llm' if predictor.client else 'rules'
    }