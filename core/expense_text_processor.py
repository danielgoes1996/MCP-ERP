"""
Procesador de texto para gastos usando LLM
Extrae información estructurada de texto libre usando Claude
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

def process_expense_text_with_llm(text: str) -> Dict[str, Any]:
    """
    Procesa texto de gasto usando Claude para extraer información estructurada.

    Args:
        text: Texto libre describiendo un gasto

    Returns:
        Dict con campos extraídos: proveedor, monto, categoría, método de pago, etc.
    """

    # Primero intentar con reglas simples para casos obvios
    result = extract_basic_info(text)

    # Si faltan campos importantes, usar LLM
    if not all([result.get('monto_total'), result.get('descripcion')]):
        return result

    # Si falta proveedor, categoría o método de pago, usar LLM
    if not all([result.get('proveedor'), result.get('categoria'), result.get('metodo_pago')]):
        try:
            llm_result = call_claude_for_expense_parsing(text)
            # Merge LLM results with basic extraction
            for key, value in llm_result.items():
                if value and not result.get(key):
                    result[key] = value
        except Exception as e:
            logger.warning(f"LLM processing failed, using basic extraction: {e}")

    # Agregar fecha actual si no se especificó
    if not result.get('fecha_gasto'):
        result['fecha_gasto'] = datetime.now().strftime('%Y-%m-%d')

    return result


def extract_basic_info(text: str) -> Dict[str, Any]:
    """Extrae información básica usando reglas simples"""
    import re

    result = {
        'descripcion': text.strip(),
        'fecha_gasto': datetime.now().strftime('%Y-%m-%d')
    }

    # Extraer monto
    monto_patterns = [
        r'(\d+(?:[.,]\d+)?)\s*(?:mil\s*)?(?:pesos?|peso|mx|mxn|\$)',
        r'\$\s*(\d+(?:[.,]\d+)?)',
        r'(?:de|por|cuesta|vale|monto|total)\s+(\d+(?:[.,]\d+)?)\s*(?:pesos?|peso)?'
    ]

    for pattern in monto_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            amount = float(match.group(1).replace(',', '.'))
            if 'mil' in text.lower():
                amount *= 1000
            result['monto_total'] = amount
            break

    # Detectar método de pago básico
    text_lower = text.lower()
    if 'efectivo' in text_lower:
        result['metodo_pago'] = 'efectivo'
    elif 'debito' in text_lower or 'débito' in text_lower:
        result['metodo_pago'] = 'tarjeta_debito'
    elif 'credito' in text_lower or 'crédito' in text_lower:
        result['metodo_pago'] = 'tarjeta_credito'
    elif 'transferencia' in text_lower:
        result['metodo_pago'] = 'transferencia'

    return result


def call_claude_for_expense_parsing(text: str) -> Dict[str, Any]:
    """
    Llama a Claude para extraer información estructurada del texto del gasto.
    """
    try:
        import anthropic

        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            logger.warning("ANTHROPIC_API_KEY not set, skipping LLM processing")
            return {}

        client = anthropic.Anthropic(api_key=api_key)

        prompt = f"""Analiza el siguiente texto de un gasto y extrae la información estructurada.

Texto del gasto: "{text}"

Extrae los siguientes campos si están presentes o se pueden inferir:
- proveedor: nombre del comercio o proveedor (ej: CFE, Pemex, Oxxo)
- categoria: categoría del gasto (usa estas opciones: transporte, alimentacion, servicios, oficina, mantenimiento, tecnologia, gastos_generales)
- metodo_pago: forma de pago (opciones: efectivo, tarjeta_credito, tarjeta_debito, transferencia)
- banco: si se menciona un banco, extraerlo (ej: BBVA, Santander, Banamex, Inbursa)
- monto_total: monto numérico
- descripcion_normalizada: descripción clara y concisa del gasto
- se_va_a_facturar: booleano, true si se menciona que "se va a facturar" o "con factura", false si dice "sin factura" o "no se factura", null si no se menciona

Para categorías, usa esta guía:
- servicios: luz (CFE), agua, gas, internet, teléfono
- transporte: gasolina, taxi, uber, estacionamiento
- alimentacion: comida, restaurante, despensa
- oficina: papelería, material de oficina
- mantenimiento: reparaciones, limpieza
- tecnologia: software, hardware, equipos
- gastos_generales: otros gastos no clasificados

IMPORTANTE:
- Si dice "tarjeta de crédito" o "credito", metodo_pago debe ser "tarjeta_credito"
- Si dice "tarjeta de débito" o "debito", metodo_pago debe ser "tarjeta_debito"
- Si menciona "se va a facturar" o "con factura", se_va_a_facturar debe ser true
- Si menciona un banco específico (BBVA, Santander, etc), incluirlo en el campo banco

Responde SOLO con un JSON válido, sin explicaciones adicionales.
"""

        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=500,
            temperature=0.1,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        # Extraer JSON de la respuesta
        response_text = response.content[0].text.strip()

        # Intentar parsear como JSON
        try:
            # Buscar JSON en la respuesta
            if '{' in response_text:
                json_start = response_text.index('{')
                json_end = response_text.rindex('}') + 1
                json_text = response_text[json_start:json_end]
                return json.loads(json_text)
        except (ValueError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to parse LLM response as JSON: {e}")
            return {}

    except ImportError:
        logger.warning("anthropic package not installed")
        return {}
    except Exception as e:
        logger.error(f"Error calling Claude: {e}")
        return {}


def get_sat_codes_for_category(categoria: str) -> Dict[str, str]:
    """
    Devuelve códigos SAT apropiados para la categoría.
    """
    sat_mappings = {
        'servicios': {
            'sat_account_code': '631.01',  # Gastos de servicios básicos
            'sat_product_service_code': '83111603'  # Servicios de utilities
        },
        'transporte': {
            'sat_account_code': '603.04',  # Combustibles y lubricantes
            'sat_product_service_code': '15111501'  # Gasolina
        },
        'alimentacion': {
            'sat_account_code': '611.03',  # Gastos de representación
            'sat_product_service_code': '90101501'  # Servicios de restaurante
        },
        'oficina': {
            'sat_account_code': '603.01',  # Papelería y artículos de oficina
            'sat_product_service_code': '14111500'  # Papel
        },
        'mantenimiento': {
            'sat_account_code': '615.01',  # Gastos de mantenimiento
            'sat_product_service_code': '72101500'  # Servicios de mantenimiento
        },
        'tecnologia': {
            'sat_account_code': '603.02',  # Gastos de tecnología
            'sat_product_service_code': '43211500'  # Computadoras
        },
        'gastos_generales': {
            'sat_account_code': '611.02',  # Gastos generales
            'sat_product_service_code': '84111506'  # Servicios administrativos
        }
    }

    return sat_mappings.get(categoria, sat_mappings['gastos_generales'])