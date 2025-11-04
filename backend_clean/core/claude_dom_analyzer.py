"""
Claude DOM Analyzer

Reemplaza OpenAI para análisis de DOM usando Claude API.
Especializado en HTML complejo, minificado e iframes.
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Any
from dataclasses import dataclass
import requests

logger = logging.getLogger(__name__)

@dataclass
class DOMAnalysisResult:
    """Resultado del análisis DOM"""
    intent_detected: str
    confidence: float
    recommended_elements: List[Dict]
    reasoning: str
    suggested_strategy: str
    fallback_options: List[str]
    analysis_time_ms: int

@dataclass
class URLClassification:
    """Clasificación de URLs"""
    primary_url: str
    url_priority_score: float
    reasoning: str
    confidence: float
    recommended_approach: str

class ClaudeDOMAnalyzer:
    """Analizador DOM usando Claude API"""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.base_url = "https://api.anthropic.com/v1/messages"
        self.model = "claude-3-5-sonnet-20241022"

        if not self.api_key:
            logger.warning("⚠️ Anthropic API key no configurada")

    def is_available(self) -> bool:
        """Verificar si Claude está disponible"""
        return bool(self.api_key)

    async def analyze_dom_for_invoicing(self, html_content: str, url: str) -> DOMAnalysisResult:
        """Analizar DOM para detectar elementos de facturación"""

        start_time = datetime.now()

        if not self.is_available():
            # Fallback heurístico
            return self._heuristic_analysis(html_content, url, start_time)

        try:
            # Truncar HTML si es muy largo
            html_preview = html_content[:8000] if len(html_content) > 8000 else html_content

            prompt = f"""
Analiza este HTML de portal web para detectar elementos de facturación/CFDI.
URL: {url}

HTML:
{html_preview}

Por favor analiza y responde en JSON con esta estructura:
{{
    "intent_detected": "click_cta|fill_form|navigate_menu|no_invoicing_detected",
    "confidence": 0.0-1.0,
    "recommended_elements": [
        {{
            "selector": "CSS selector",
            "text": "texto del elemento",
            "type": "button|link|input|form",
            "relevance_score": 0.0-1.0,
            "reasoning": "por qué es relevante"
        }}
    ],
    "reasoning": "explicación detallada del análisis",
    "suggested_strategy": "click_cta|fill_form|navigate_menu",
    "fallback_options": ["estrategia1", "estrategia2"]
}}

Busca especialmente:
- Botones/enlaces con texto: "factura", "cfdi", "billing", "solicitar", "generar"
- Formularios para RFC/datos fiscales
- Menús de navegación con secciones de facturación
- CTAs relacionados con descargar/obtener facturas

Si el HTML está minificado o es complejo, enfócate en elementos más probables.
"""

            response = await self._call_claude_api(prompt)

            try:
                result_data = json.loads(response)
                processing_time = (datetime.now() - start_time).total_seconds() * 1000

                return DOMAnalysisResult(
                    intent_detected=result_data.get('intent_detected', 'no_invoicing_detected'),
                    confidence=result_data.get('confidence', 0.0),
                    recommended_elements=result_data.get('recommended_elements', []),
                    reasoning=result_data.get('reasoning', ''),
                    suggested_strategy=result_data.get('suggested_strategy', 'navigate_menu'),
                    fallback_options=result_data.get('fallback_options', []),
                    analysis_time_ms=int(processing_time)
                )

            except json.JSONDecodeError:
                logger.warning("⚠️ Claude response no es JSON válido, usando análisis heurístico")
                return self._heuristic_analysis(html_content, url, start_time)

        except Exception as e:
            logger.error(f"❌ Error en análisis Claude: {e}")
            return self._heuristic_analysis(html_content, url, start_time)

    async def classify_urls_for_invoicing(self, urls: List[str], merchant_name: str = "") -> Dict[str, URLClassification]:
        """Clasificar múltiples URLs por probabilidad de facturación"""

        if not self.is_available():
            return self._heuristic_url_classification(urls, merchant_name)

        try:
            urls_text = "\n".join([f"- {url}" for url in urls])

            prompt = f"""
Analiza estas URLs de un merchant llamado "{merchant_name}" y clasifícalas por probabilidad de contener funcionalidad de facturación/CFDI.

URLs:
{urls_text}

Responde en JSON con esta estructura:
{{
    "classifications": [
        {{
            "url": "url completa",
            "priority_score": 0.0-1.0,
            "reasoning": "explicación de por qué esta URL es probable/improbable",
            "confidence": 0.0-1.0,
            "recommended_approach": "direct_access|explore_navigation|skip"
        }}
    ],
    "recommended_order": ["url1", "url2", "url3"]
}}

Considera:
- Palabras clave: factura, cfdi, billing, cliente, portal, admin
- Paths sugestivos: /billing/, /facturas/, /cfdi/, /cliente/
- Subdominios: portal.*, cliente.*, admin.*
- Estructuras típicas de portales comerciales mexicanos

Prioriza URLs que más probablemente contengan funcionalidad de facturación.
"""

            response = await self._call_claude_api(prompt)

            try:
                result_data = json.loads(response)
                classifications = {}

                for classification in result_data.get('classifications', []):
                    url = classification.get('url', '')
                    if url:
                        classifications[url] = URLClassification(
                            primary_url=url,
                            url_priority_score=classification.get('priority_score', 0.0),
                            reasoning=classification.get('reasoning', ''),
                            confidence=classification.get('confidence', 0.0),
                            recommended_approach=classification.get('recommended_approach', 'explore_navigation')
                        )

                return classifications

            except json.JSONDecodeError:
                logger.warning("⚠️ Claude URL classification response no es JSON válido")
                return self._heuristic_url_classification(urls, merchant_name)

        except Exception as e:
            logger.error(f"❌ Error en clasificación Claude: {e}")
            return self._heuristic_url_classification(urls, merchant_name)

    async def explain_automation_failure(self, error_context: Dict[str, Any]) -> str:
        """Generar explicación humana de fallo de automatización"""

        if not self.is_available():
            return self._heuristic_error_explanation(error_context)

        try:
            error_summary = json.dumps(error_context, indent=2)

            prompt = f"""
Un sistema de automatización web falló al intentar navegar un portal de facturación.
Genera una explicación clara en español para el usuario final.

Contexto del error:
{error_summary}

Por favor proporciona:
1. Explicación simple de qué falló
2. Posibles causas (sin jerga técnica)
3. Recomendaciones para resolverlo

Responde en texto plano, máximo 200 palabras, tono profesional pero accesible.
"""

            explanation = await self._call_claude_api(prompt)
            return explanation.strip()

        except Exception as e:
            logger.error(f"❌ Error generando explicación: {e}")
            return self._heuristic_error_explanation(error_context)

    async def _call_claude_api(self, prompt: str) -> str:
        """Llamar a Claude API"""

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01"
        }

        payload = {
            "model": self.model,
            "max_tokens": 2000,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }

        response = requests.post(
            self.base_url,
            headers=headers,
            json=payload,
            timeout=30
        )

        if response.status_code != 200:
            raise Exception(f"Claude API error: {response.status_code} - {response.text}")

        result = response.json()

        if "content" in result and len(result["content"]) > 0:
            return result["content"][0]["text"]
        else:
            raise Exception("Claude API returned empty response")

    def _heuristic_analysis(self, html_content: str, url: str, start_time: datetime) -> DOMAnalysisResult:
        """Análisis heurístico como fallback"""

        logger.info("🔄 Usando análisis heurístico (Claude no disponible)")

        # Palabras clave para facturación
        invoice_keywords = [
            'factura', 'cfdi', 'billing', 'invoice', 'solicitar',
            'generar', 'descargar', 'obtener', 'emitir', 'fiscal'
        ]

        html_lower = html_content.lower()
        found_keywords = [kw for kw in invoice_keywords if kw in html_lower]

        # Scoring simple
        score = len(found_keywords) / len(invoice_keywords) if invoice_keywords else 0

        # Determinar intent
        if score > 0.3:
            intent = "click_cta" if any(word in html_lower for word in ['solicitar', 'generar', 'obtener']) else "navigate_menu"
        else:
            intent = "no_invoicing_detected"

        processing_time = (datetime.now() - start_time).total_seconds() * 1000

        return DOMAnalysisResult(
            intent_detected=intent,
            confidence=min(score + 0.1, 0.8),  # Confianza limitada para heurística
            recommended_elements=[],
            reasoning=f"Análisis heurístico: encontradas {len(found_keywords)} palabras clave relacionadas",
            suggested_strategy=intent if intent != "no_invoicing_detected" else "navigate_menu",
            fallback_options=["click_cta", "navigate_menu", "fill_form"],
            analysis_time_ms=int(processing_time)
        )

    def _heuristic_url_classification(self, urls: List[str], merchant_name: str) -> Dict[str, URLClassification]:
        """Clasificación heurística de URLs"""

        classifications = {}

        for url in urls:
            url_lower = url.lower()

            # Scoring basado en palabras clave en URL
            score = 0.0
            reasoning = "Análisis heurístico: "

            if any(word in url_lower for word in ['factura', 'cfdi', 'billing']):
                score += 0.4
                reasoning += "contiene palabras clave de facturación, "

            if any(word in url_lower for word in ['cliente', 'portal', 'admin']):
                score += 0.3
                reasoning += "contiene indicadores de portal, "

            if any(path in url_lower for path in ['/billing/', '/facturas/', '/cfdi/']):
                score += 0.3
                reasoning += "path sugiere funcionalidad de facturación, "

            # Penalizar URLs de descarga de apps
            if any(word in url_lower for word in ['download', 'app-descarga', 'mobile']):
                score = max(0, score - 0.5)
                reasoning += "penalizada por ser URL de descarga, "

            reasoning = reasoning.rstrip(", ")

            classifications[url] = URLClassification(
                primary_url=url,
                url_priority_score=min(score, 1.0),
                reasoning=reasoning,
                confidence=0.7,  # Confianza fija para heurística
                recommended_approach="explore_navigation" if score > 0.3 else "skip"
            )

        return classifications

    def _heuristic_error_explanation(self, error_context: Dict[str, Any]) -> str:
        """Explicación heurística de errores"""

        error_type = error_context.get('error_type', 'unknown')

        explanations = {
            'timeout': 'El portal tardó demasiado en responder. Puede estar experimentando lentitud temporal.',
            'element_not_found': 'No se encontraron los elementos esperados en la página. El portal podría haber cambiado su diseño.',
            'no_invoicing_detected': 'No se detectaron opciones de facturación en el portal. Puede requerir navegación manual.',
            'captcha_detected': 'El portal requiere verificación de captcha que debe completarse manualmente.',
            'authentication_required': 'El portal requiere inicio de sesión antes de acceder a la facturación.'
        }

        return explanations.get(error_type,
            'Se encontró un problema técnico durante la navegación automática. '
            'Se recomienda intentar manualmente o contactar al portal.')

# Funciones de conveniencia
def create_claude_analyzer(api_key: str = None) -> ClaudeDOMAnalyzer:
    """Factory para crear analizador Claude"""
    return ClaudeDOMAnalyzer(api_key)

# Función de migración desde OpenAI
async def migrate_from_openai_analysis(html_content: str, url: str, openai_function_name: str = "") -> DOMAnalysisResult:
    """Migrar desde análisis OpenAI a Claude"""

    analyzer = create_claude_analyzer()

    if analyzer.is_available():
        logger.info("🔄 Migrando análisis de OpenAI a Claude")
        return await analyzer.analyze_dom_for_invoicing(html_content, url)
    else:
        logger.warning("⚠️ Claude no disponible, usando análisis heurístico")
        return analyzer._heuristic_analysis(html_content, url, datetime.now())

async def claude_classify_urls(urls: List[str], merchant_name: str = "") -> Dict[str, Any]:
    """Función compatible con interfaz OpenAI existente"""

    analyzer = create_claude_analyzer()
    classifications = await analyzer.classify_urls_for_invoicing(urls, merchant_name)

    # Convertir a formato compatible
    sorted_urls = sorted(
        classifications.items(),
        key=lambda x: x[1].url_priority_score,
        reverse=True
    )

    return {
        "classifications": classifications,
        "recommended_order": [url for url, _ in sorted_urls],
        "primary_recommendation": sorted_urls[0][0] if sorted_urls else urls[0] if urls else "",
        "confidence": sum(c.confidence for c in classifications.values()) / len(classifications) if classifications else 0.0,
        "service": "claude"
    }