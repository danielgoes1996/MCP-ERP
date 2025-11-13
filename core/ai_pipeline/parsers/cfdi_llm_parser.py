"""CFDI extraction helpers powered by Claude Haiku.

Provides a thin wrapper around the Anthropic Messages API to transform a CFDI
XML document into a structured JSON payload ready for persistence and UI use.
"""

from __future__ import annotations

import json
import logging
import os
import textwrap
import time
from typing import Any, Dict, Optional

import requests


logger = logging.getLogger(__name__)


class CFDILLMError(RuntimeError):
    """Raised when the LLM based extraction fails."""


class CFDILLMNotConfigured(CFDILLMError):
    """Raised when the Anthropic API key is not configured."""


DEFAULT_MODEL = os.getenv("CFDI_LLM_MODEL", "claude-3-haiku-20240307")
ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"


def _clean_json_response(raw_text: str) -> str:
    """Extract a JSON object from an LLM response.

    The Haiku model may wrap the JSON in markdown code fences. This helper strips
    surrounding fences and whitespace to yield a clean JSON document. It raises
    ``ValueError`` if no JSON block can be identified.
    """

    text = raw_text.strip()
    if not text:
        raise ValueError("Empty response received from LLM")

    if "```" in text:
        # Prefer explicit ```json fences when available.
        if "```json" in text.lower():
            parts = text.lower().split("```json", 1)[1].split("```", 1)
            text = parts[0]
        else:
            text = text.split("```", 1)[1].split("```", 1)[0]

    text = text.strip()

    # Ensure the payload starts with '{' or '['
    start = text.find("{")
    if start == -1:
        start = text.find("[")
    if start == -1:
        raise ValueError("LLM response does not contain JSON data")

    # Trim any leading commentary before the JSON block
    text = text[start:]

    # Heuristic: cut after the last matching brace to avoid trailing notes
    brace_stack = []
    end_index = None
    for index, char in enumerate(text):
        if char in "{[":
            brace_stack.append(char)
        elif char in "}]":
            if not brace_stack:
                break
            opening = brace_stack.pop()
            if not brace_stack:
                end_index = index + 1
                break

    if end_index is None:
        raise ValueError("Could not determine end of JSON document")

    return text[:end_index]


def build_cfdi_prompt(xml_content: str) -> str:
    """Generate the user prompt for Haiku.

    The prompt asks the model to analyse the CFDI and produce a normalized JSON
    representation with the key fiscal attributes required by the bank
    reconciliation UI.
    """

    instructions = textwrap.dedent(
        """
        Analiza el CFDI XML que te proporcionaré y devuelve **únicamente** un JSON válido
        con la siguiente estructura. Usa null cuando un dato no exista y valores
        numéricos en formato decimal (sin comas). Respeta mayúsculas de RFC y UUID.

        {
          "uuid": "string",                     // UUID del timbre fiscal
          "serie": "string | null",              // Serie del comprobante
          "folio": "string | null",              // Folio del comprobante
          "fecha_emision": "YYYY-MM-DD",
          "fecha_timbrado": "YYYY-MM-DD HH:mm:ss | null",  // Fecha de certificación del timbre
          "tipo_comprobante": "I|E|P|T|N",
          "moneda": "string",                   // Ej. MXN
          "tipo_cambio": number | null,          // 1.0 si no aplica
          "subtotal": number | null,
          "descuento": number | null,
          "total": number,
          "forma_pago": "string | null",        // Catálogo SAT (ej. 03)
          "metodo_pago": "string | null",       // PUE, PPD, etc.
          "uso_cfdi": "string | null",
          "sat_status": "vigente|cancelado|sustituido|desconocido",
          "emisor": {
            "nombre": "string | null",
            "rfc": "string | null",
            "regimen_fiscal": "string | null"
          },
          "receptor": {
            "nombre": "string | null",
            "rfc": "string | null",
            "uso_cfdi": "string | null",
            "domicilio_fiscal": "string | null"
          },
          "impuestos": {
            "traslados": [
              {"impuesto": "IVA|IEPS|OTRO", "tasa": number | null, "factor": "Tasa|Exento|Cuota", "importe": number}
            ],
            "retenciones": [
              {"impuesto": "IVA|ISR|OTRO", "tasa": number | null, "importe": number}
            ]
          },
          "tax_badges": ["iva_16", "iva_8", "iva_0", "ret_iva", "ret_isr"],
          "pagos": {
            "tipo": "PUE|PPD|NA",
            "numero_parcialidades": number | null
          }
        }

        Reglas adicionales:
        - Determina los badges "tax_badges" en función de los impuestos presentes.
          Incluye solo los que apliquen.
        - "tipo_cambio" debe ser numérico (ej. 1.0) o null.
        - Si falta el complemento de timbre, coloca "desconocido" en "sat_status".
        - No agregues comentarios ni explicaciones fuera del JSON.
        """
    ).strip()

    return f"{instructions}\n\n<cfdi_xml>\n{xml_content}\n</cfdi_xml>"


def extract_cfdi_metadata(
    xml_content: str,
    *,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    timeout: int = 60,
    max_retries: int = 3,
) -> Dict[str, Any]:
    """Call Claude Haiku to extract fiscal metadata from a CFDI XML string.

    Includes automatic retry logic for rate limit (429) and overload (529) errors.
    """

    api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise CFDILLMNotConfigured("ANTHROPIC_API_KEY is not configured")

    prompt = build_cfdi_prompt(xml_content)

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    payload = {
        "model": model or DEFAULT_MODEL,
        "max_tokens": 1000,
        "temperature": 0,
        "system": "Eres un experto fiscal mexicano. Responde solo con JSON válido.",
        "messages": [
            {
                "role": "user",
                "content": [{"type": "text", "text": prompt}],
            }
        ],
    }

    # Retry logic with exponential backoff
    last_exception = None
    for attempt in range(max_retries):
        try:
            response = requests.post(
                ANTHROPIC_MESSAGES_URL,
                headers=headers,
                json=payload,
                timeout=timeout,
            )
        except requests.RequestException as exc:
            last_exception = exc
            logger.warning(f"Attempt {attempt + 1}/{max_retries} - Error contacting Anthropic API: {exc}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s, 4s
                continue
            raise CFDILLMError(f"Error contacting Anthropic API: {exc}") from exc

        # Handle rate limit (429) and overload (529) errors with retry
        if response.status_code in [429, 529]:
            error_type = "rate limit" if response.status_code == 429 else "overload"

            # Calculate retry delay
            if attempt < max_retries - 1:
                # Exponential backoff: 10s, 30s, 60s for rate limits
                retry_delay = min(10 * (3 ** attempt), 60)
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries} - Anthropic API {error_type} error ({response.status_code}). "
                    f"Retrying in {retry_delay} seconds..."
                )
                time.sleep(retry_delay)
                continue
            else:
                raise CFDILLMError(
                    f"Anthropic API {error_type} error after {max_retries} attempts: {response.text[:400]}"
                )

        # Handle other 4xx/5xx errors (no retry)
        if response.status_code >= 400:
            raise CFDILLMError(
                f"Anthropic API returned {response.status_code}: {response.text[:400]}"
            )

        # Success - parse the response
        try:
            data = response.json()
            content = data.get("content", [])
            if not content:
                raise CFDILLMError("Anthropic response missing content block")

            text_blocks = [block.get("text", "") for block in content if isinstance(block, dict)]
            raw_text = "\n".join(filter(None, text_blocks))

            json_payload = _clean_json_response(raw_text)
            parsed = json.loads(json_payload)

            if isinstance(parsed, dict):
                parsed.setdefault("model_used", model or DEFAULT_MODEL)

            logger.info(f"Successfully extracted CFDI metadata on attempt {attempt + 1}")
            return parsed

        except Exception as exc:  # noqa: BLE001 - provide context
            logger.warning("Failed to parse LLM JSON response: %s", exc)
            raise CFDILLMError("Invalid JSON returned by LLM") from exc

    # Should never reach here, but just in case
    if last_exception:
        raise CFDILLMError(f"Failed after {max_retries} attempts") from last_exception
    raise CFDILLMError(f"Failed after {max_retries} attempts")


__all__ = [
    "extract_cfdi_metadata",
    "build_cfdi_prompt",
    "CFDILLMError",
    "CFDILLMNotConfigured",
]
