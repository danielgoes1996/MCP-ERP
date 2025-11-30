"""Ticket OCR extraction powered by Gemini 2.5 Flash.

This parser extracts key information from ticket images/PDFs to facilitate
invoice-to-expense matching. It focuses on extracting:

1. Product/service concepts (for semantic matching)
2. Merchant information (RFC, name)
3. Transaction details (total, date, folio)
4. Invoice portal URL (if present)

Created: 2025-11-25
Purpose: Async ticket processing with concept similarity matching
"""

from __future__ import annotations

import json
import logging
import os
import re
from functools import lru_cache
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TicketParserError(RuntimeError):
    """Raised when ticket parsing fails."""


class TicketParserNotConfigured(TicketParserError):
    """Raised when Gemini API key is not configured."""


# Lazy initialization for Gemini client
_gemini_client = None


def _get_gemini_client():
    """Get or initialize Gemini client with lazy loading."""
    global _gemini_client
    if _gemini_client is None:
        try:
            import google.generativeai as genai

            api_key = os.getenv('GEMINI_API_KEY')
            if not api_key:
                raise TicketParserNotConfigured("GEMINI_API_KEY not configured")

            genai.configure(api_key=api_key)
            _gemini_client = genai.GenerativeModel('gemini-2.5-flash')
            logger.info("Gemini client initialized successfully for ticket parsing")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}")
            raise TicketParserNotConfigured(f"Gemini initialization failed: {e}")

    return _gemini_client


def build_ticket_prompt(ocr_text: str) -> str:
    """Generate the prompt for Gemini to extract ticket data.

    Args:
        ocr_text: Raw OCR text extracted from ticket image/PDF

    Returns:
        Formatted prompt for Gemini
    """

    prompt = f"""Analiza el siguiente texto extraído de un ticket de compra mexicano y extrae la información clave.
Responde ÚNICAMENTE con un JSON válido en el siguiente formato:

{{
  "merchant_name": "string | null",           // Nombre del comercio
  "merchant_rfc": "string | null",            // RFC del emisor (formato AAA######XXX o AAAA######XXX)
  "folio": "string | null",                   // Número de folio/ticket
  "fecha": "YYYY-MM-DD | null",               // Fecha de la compra
  "total": number | null,                     // Monto total
  "subtotal": number | null,                  // Subtotal antes de impuestos
  "iva": number | null,                       // Monto de IVA
  "forma_pago": "string | null",              // Forma de pago (efectivo, tarjeta, etc)
  "conceptos": [                              // Lista de productos/servicios
    {{
      "descripcion": "string",                // Descripción del producto/servicio
      "cantidad": number | null,              // Cantidad
      "precio_unitario": number | null,       // Precio unitario
      "importe": number | null                // Importe total del concepto
    }}
  ],
  "invoice_portal_url": "string | null",      // URL del portal de facturación (si existe)
  "invoice_portal_hint": "string | null",     // Texto que indica cómo facturar
  "extraction_confidence": "high|medium|low"  // Nivel de confianza de la extracción
}}

REGLAS IMPORTANTES:
1. **Conceptos**: Extrae TODOS los productos/servicios mencionados. Si hay descripciones vagas como "PRODUCTO" o "ARTICULO", incluye la cantidad y precio como contexto.

2. **RFC**: Busca patrones como "RFC: XXX######XXX" o similar. Si no encuentras RFC explícito, retorna null.

3. **URL de Facturación**: Busca URLs que contengan palabras como "factura", "facturacion", "cfdi", "invoice" o dominios conocidos de facturación.

4. **Fechas**: Extrae la fecha de compra en formato YYYY-MM-DD. Si solo aparece DD/MM/YYYY, conviértelo.

5. **Números**: Limpia los números eliminando símbolos de moneda ($, MXN) y comas. Usa punto decimal.

6. **Confianza**:
   - "high": RFC + total + conceptos claros encontrados
   - "medium": Total + conceptos encontrados, pero falta RFC o conceptos vagos
   - "low": Información parcial o ambigua

7. **JSON válido**: No agregues comentarios, explicaciones ni markdown. Solo el JSON.

TEXTO DEL TICKET:
{ocr_text}

JSON de respuesta:"""

    return prompt


def parse_ticket_text(ocr_text: str, max_retries: int = 2) -> Dict[str, Any]:
    """Parse ticket OCR text using Gemini 2.5 Flash.

    Args:
        ocr_text: Raw OCR text from ticket image/PDF
        max_retries: Number of retry attempts for transient errors

    Returns:
        Dictionary with extracted ticket data

    Raises:
        TicketParserError: If parsing fails after retries
        TicketParserNotConfigured: If Gemini API key not configured
    """

    if not ocr_text or not ocr_text.strip():
        raise TicketParserError("Empty OCR text provided")

    client = _get_gemini_client()
    prompt = build_ticket_prompt(ocr_text)

    last_exception = None

    for attempt in range(max_retries):
        try:
            response = client.generate_content(prompt)

            if not response or not response.text:
                raise TicketParserError("Empty response from Gemini")

            # Clean response (remove markdown code fences if present)
            raw_text = response.text.strip()
            json_text = _clean_json_response(raw_text)

            # Parse JSON
            parsed_data = json.loads(json_text)

            # Validate required structure
            if not isinstance(parsed_data, dict):
                raise TicketParserError("Gemini returned non-dict response")

            # Add metadata
            parsed_data['extraction_model'] = 'gemini-2.5-flash'
            parsed_data['extraction_method'] = 'gemini_ticket_parser'

            logger.info(
                f"Successfully parsed ticket: merchant={parsed_data.get('merchant_name')}, "
                f"total={parsed_data.get('total')}, "
                f"concepts={len(parsed_data.get('conceptos', []))}, "
                f"confidence={parsed_data.get('extraction_confidence')}"
            )

            return parsed_data

        except json.JSONDecodeError as e:
            last_exception = e
            logger.warning(f"Attempt {attempt + 1}/{max_retries} - Invalid JSON from Gemini: {e}")
            if attempt < max_retries - 1:
                continue
            raise TicketParserError(f"Gemini returned invalid JSON: {e}") from e

        except Exception as e:
            last_exception = e
            logger.warning(f"Attempt {attempt + 1}/{max_retries} - Gemini API error: {e}")
            if attempt < max_retries - 1:
                continue
            raise TicketParserError(f"Failed to parse ticket: {e}") from e

    # Should not reach here, but handle just in case
    raise TicketParserError(f"Failed after {max_retries} attempts") from last_exception


def _clean_json_response(raw_text: str) -> str:
    """Extract clean JSON from Gemini response.

    Gemini may wrap JSON in markdown code fences. This strips them.

    Args:
        raw_text: Raw response text from Gemini

    Returns:
        Clean JSON string

    Raises:
        ValueError: If no valid JSON found in response
    """

    text = raw_text.strip()

    if not text:
        raise ValueError("Empty response from Gemini")

    # Remove markdown code fences if present
    if "```" in text:
        if "```json" in text.lower():
            parts = text.lower().split("```json", 1)[1].split("```", 1)
            text = parts[0]
        else:
            text = text.split("```", 1)[1].split("```", 1)[0]

    text = text.strip()

    # Find JSON object start
    start = text.find("{")
    if start == -1:
        raise ValueError("No JSON object found in response")

    # Find matching closing brace
    brace_count = 0
    end_index = None

    for i, char in enumerate(text[start:], start=start):
        if char == "{":
            brace_count += 1
        elif char == "}":
            brace_count -= 1
            if brace_count == 0:
                end_index = i + 1
                break

    if end_index is None:
        raise ValueError("Unclosed JSON object in response")

    return text[start:end_index]


def extract_ticket_concepts(parsed_ticket: Dict[str, Any]) -> List[str]:
    """Extract concept descriptions from parsed ticket for matching.

    This creates a simplified list of product/service descriptions suitable
    for concept similarity matching with invoice line items.

    Args:
        parsed_ticket: Output from parse_ticket_text()

    Returns:
        List of concept description strings
    """

    concepts = []

    for concepto in parsed_ticket.get('conceptos', []):
        descripcion = concepto.get('descripcion', '').strip()
        if not descripcion:
            continue

        # Enrich description with quantity if available
        cantidad = concepto.get('cantidad')
        if cantidad and cantidad > 1:
            # e.g., "COCA COLA 600ML" → "COCA COLA 600ML (2 unidades)"
            descripcion = f"{descripcion} ({cantidad} unidades)"

        concepts.append(descripcion)

    return concepts


def format_ticket_for_storage(parsed_ticket: Dict[str, Any]) -> Dict[str, Any]:
    """Format parsed ticket data for storage in manual_expenses table.

    Args:
        parsed_ticket: Output from parse_ticket_text()

    Returns:
        Dictionary formatted for ticket_extracted_data JSONB field
    """

    return {
        'merchant_name': parsed_ticket.get('merchant_name'),
        'merchant_rfc': parsed_ticket.get('merchant_rfc'),
        'folio': parsed_ticket.get('folio'),
        'fecha': parsed_ticket.get('fecha'),
        'total': parsed_ticket.get('total'),
        'subtotal': parsed_ticket.get('subtotal'),
        'iva': parsed_ticket.get('iva'),
        'forma_pago': parsed_ticket.get('forma_pago'),
        'conceptos': parsed_ticket.get('conceptos', []),
        'invoice_portal_url': parsed_ticket.get('invoice_portal_url'),
        'invoice_portal_hint': parsed_ticket.get('invoice_portal_hint'),
        'extraction_confidence': parsed_ticket.get('extraction_confidence', 'low'),
        'extraction_model': parsed_ticket.get('extraction_model', 'gemini-2.5-flash'),
        'extraction_method': parsed_ticket.get('extraction_method', 'gemini_ticket_parser'),
    }


# ===========================
# DIRECT USAGE EXAMPLES
# ===========================

def _example_usage():
    """Example usage of the ticket parser (for testing/documentation)."""

    sample_ocr = """
    OXXO
    RFC: OXX830110P45
    Av. Reforma 123, CDMX

    TICKET: 0012345
    FECHA: 25/11/2025

    COCA COLA 600ML       $18.00
    SABRITAS ORIGINAL     $15.50
    PAN BIMBO BLANCO      $32.00

    SUBTOTAL:             $65.50
    IVA 16%:              $10.48
    TOTAL:                $75.98

    FORMA PAGO: EFECTIVO

    ¿Necesitas factura?
    Visita: www.oxxo.com/facturacion
    """

    try:
        parsed = parse_ticket_text(sample_ocr)
        concepts = extract_ticket_concepts(parsed)
        storage_data = format_ticket_for_storage(parsed)

        print("✅ Parsed ticket:")
        print(json.dumps(parsed, indent=2, ensure_ascii=False))
        print("\n✅ Extracted concepts:")
        print(concepts)
        print("\n✅ Storage format:")
        print(json.dumps(storage_data, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"❌ Error: {e}")


__all__ = [
    'parse_ticket_text',
    'extract_ticket_concepts',
    'format_ticket_for_storage',
    'build_ticket_prompt',
    'TicketParserError',
    'TicketParserNotConfigured',
]


if __name__ == '__main__':
    # Run example if executed directly
    _example_usage()
