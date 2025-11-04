"""
Expense Enhancer - Usa LLM para mejorar descripciones y mapear campos de gastos
"""

import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional
import json

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

logger = logging.getLogger(__name__)


class ExpenseEnhancer:
    """
    Clase para mejorar gastos usando LLM antes de enviarlos a Odoo
    """

    def __init__(self):
        if not OpenAI:
            raise ImportError("OpenAI library not installed")

        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY not configured")

        self.client = OpenAI(api_key=api_key)

        # Mapeo de categorías de Carreta Verde
        self.categories = {
            'alimentos': ['comida', 'restaurante', 'almuerzo', 'desayuno', 'cena', 'café', 'lunch'],
            'transporte': ['gasolina', 'combustible', 'taxi', 'uber', 'transporte', 'viaje', 'kilometraje'],
            'hospedaje': ['hotel', 'alojamiento', 'hospedaje', 'estancia'],
            'comunicacion': ['telefono', 'internet', 'celular', 'comunicacion'],
            'materiales': ['oficina', 'suministros', 'materiales', 'papeleria'],
            'marketing': ['publicidad', 'promocion', 'marketing', 'cliente', 'adquisicion'],
            'capacitacion': ['curso', 'entrenamiento', 'capacitacion', 'seminario'],
            'representacion': ['representacion', 'atencion', 'cliente', 'reunion']
        }

        # Empleados conocidos de Carreta Verde
        self.employees = {
            'daniel': 'Daniel Gómez',
            'daniel gomez': 'Daniel Gómez',
            'daniel gómez': 'Daniel Gómez',
            'usuario voz': 'Daniel Gómez'  # Default para voz
        }

    def enhance_expense(self, raw_transcript: str, amount: float) -> Dict[str, Any]:
        """
        Mejora un gasto usando LLM para generar descripción profesional y mapear campos

        Args:
            raw_transcript: Transcripción original de voz
            amount: Monto del gasto

        Returns:
            Dict con campos mejorados para Odoo
        """
        try:
            logger.info(f"Mejorando gasto: {raw_transcript} - ${amount}")

            # Usar LLM para analizar y mejorar
            enhanced_data = self._analyze_with_llm(raw_transcript, amount)

            # Mapear campos para Odoo
            odoo_expense = self._map_to_odoo_fields(enhanced_data, amount)

            logger.info(f"Gasto mejorado exitosamente: {odoo_expense['name']}")
            return odoo_expense

        except Exception as e:
            logger.error(f"Error mejorando gasto: {e}")
            # Fallback básico
            return self._create_basic_expense(raw_transcript, amount)

    def _analyze_with_llm(self, transcript: str, amount: float) -> Dict[str, Any]:
        """
        Usa OpenAI para analizar el gasto y extraer información estructurada
        """

        prompt = f"""
Analiza el siguiente gasto de empresa y extrae información estructurada:

TRANSCRIPCIÓN: "{transcript}"
MONTO: ${amount}

Extrae y mejora la siguiente información:

1. DESCRIPCIÓN PROFESIONAL: Reescribe en formato profesional para contabilidad
2. CATEGORÍA: Clasifica en una de estas categorías:
   - alimentos (restaurantes, comidas)
   - transporte (gasolina, taxi, viajes)
   - hospedaje (hoteles)
   - comunicacion (teléfono, internet)
   - materiales (oficina, suministros)
   - marketing (publicidad, clientes)
   - capacitacion (cursos, entrenamientos)
   - representacion (atención a clientes)

3. EMPLEADO: Identifica el empleado (si se menciona)
4. PROVEEDOR: Identifica el proveedor/establecimiento
5. PROPÓSITO COMERCIAL: Explica el propósito de negocio
6. INCLUYE_IMPUESTOS: true/false si probablemente incluye IVA

Responde SOLO en formato JSON:
{{
    "descripcion_profesional": "descripción clara y profesional",
    "categoria": "categoria_detectada",
    "empleado": "nombre_empleado_o_null",
    "proveedor": "nombre_proveedor_o_null",
    "proposito_comercial": "explicación del propósito de negocio",
    "incluye_impuestos": true_o_false,
    "confianza": 0.95
}}
"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Eres un asistente contable experto que analiza gastos empresariales y los categoriza profesionalmente."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=500
            )

            content = response.choices[0].message.content.strip()

            # Extraer JSON de la respuesta
            if content.startswith('```json'):
                content = content[7:-3]
            elif content.startswith('```'):
                content = content[3:-3]

            return json.loads(content)

        except Exception as e:
            logger.error(f"Error en análisis LLM: {e}")
            # Fallback con análisis básico
            return self._basic_analysis(transcript, amount)

    def _basic_analysis(self, transcript: str, amount: float) -> Dict[str, Any]:
        """
        Análisis básico sin LLM como fallback
        """
        transcript_lower = transcript.lower()

        # Detectar categoría básica
        categoria = 'materiales'  # default
        for cat, keywords in self.categories.items():
            if any(keyword in transcript_lower for keyword in keywords):
                categoria = cat
                break

        # Detectar empleado
        empleado = None
        for name_variant, full_name in self.employees.items():
            if name_variant.lower() in transcript_lower:
                empleado = full_name
                break

        return {
            "descripcion_profesional": transcript.capitalize(),
            "categoria": categoria,
            "empleado": empleado,
            "proveedor": None,
            "proposito_comercial": "Gasto operacional de empresa",
            "incluye_impuestos": True,
            "confianza": 0.7
        }

    def _map_to_odoo_fields(self, enhanced_data: Dict[str, Any], amount: float) -> Dict[str, Any]:
        """
        Mapea los datos mejorados a campos de Odoo hr.expense
        """

        # Calcular impuestos si es necesario
        if enhanced_data.get('incluye_impuestos', True):
            # Asumir IVA 16% incluido en México
            base_amount = amount / 1.16
            tax_amount = amount - base_amount
        else:
            base_amount = amount
            tax_amount = 0

        # Determinar quién paga
        payment_mode = 'own_account'  # Empleado paga (a reembolsar)
        if amount > 2000:  # Gastos grandes probablemente los paga la empresa
            payment_mode = 'company_account'

        # Mapear empleado
        employee_name = enhanced_data.get('empleado', 'Daniel Gómez')

        expense_data = {
            'name': enhanced_data['descripcion_profesional'],
            'description': f"{enhanced_data['proposito_comercial']}\n\nTranscripción original: {enhanced_data.get('transcript_original', '')}",
            'total_amount': float(amount),
            'price_unit': float(base_amount),
            'quantity': 1.0,
            'date': datetime.now().strftime('%Y-%m-%d'),
            'payment_mode': payment_mode,
            # Removido: 'reference', 'tax_ids', 'analytic_distribution', 'company_id' - no existen o causan errores
        }

        # Agregar información adicional en notas
        if enhanced_data.get('proveedor'):
            expense_data['description'] += f"\nProveedor: {enhanced_data['proveedor']}"

        if enhanced_data.get('categoria'):
            expense_data['description'] += f"\nCategoría: {enhanced_data['categoria']}"

        return expense_data

    def _create_basic_expense(self, transcript: str, amount: float) -> Dict[str, Any]:
        """
        Crea un gasto básico como fallback
        """
        return {
            'name': transcript.capitalize(),
            'description': f"Gasto registrado por voz\n\nTranscripción: {transcript}",
            'total_amount': float(amount),
            'price_unit': float(amount),
            'quantity': 1.0,
            'date': datetime.now().strftime('%Y-%m-%d'),
            'payment_mode': 'own_account'
        }


# Instancia global
expense_enhancer = None

def get_expense_enhancer() -> ExpenseEnhancer:
    """
    Obtiene o crea la instancia global del enhancer
    """
    global expense_enhancer
    if expense_enhancer is None:
        expense_enhancer = ExpenseEnhancer()
    return expense_enhancer


def enhance_expense_from_voice(transcript: str, amount: float) -> Dict[str, Any]:
    """
    Función de conveniencia para mejorar un gasto desde voz
    """
    try:
        enhancer = get_expense_enhancer()
        return enhancer.enhance_expense(transcript, amount)
    except Exception as e:
        logger.error(f"Error en enhance_expense_from_voice: {e}")
        # Fallback básico
        return {
            'name': transcript.capitalize(),
            'description': f"Gasto registrado por voz: {transcript}",
            'total_amount': float(amount),
            'price_unit': float(amount),
            'quantity': 1.0,
            'date': datetime.now().strftime('%Y-%m-%d'),
            'payment_mode': 'own_account'
        }