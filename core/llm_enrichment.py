"""Servicios de enriquecimiento contable usando LLMs."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict
from typing import Any, Dict

from config.config import config
from core.accounting.accounting_catalog import (
    CategoryNormalizationResult,
    normalize_accounting_category,
)

logger = logging.getLogger(__name__)


def _humanize_payment_method(expense) -> str:
    mapping = {
        "tarjeta_credito": "tarjeta de crédito",
        "tarjeta_debito": "tarjeta de débito",
        "tarjeta_empresa": "tarjeta corporativa",
        "tarjeta_empleado": "tarjeta de empleado",
        "transferencia": "transferencia bancaria",
        "efectivo": "efectivo",
        "cheque": "cheque",
        "terminal": "terminal POS",
    }

    method = getattr(expense, "payment_method", None) or getattr(expense, "metodo_pago", None)
    if method:
        return mapping.get(method, method.replace("_", " "))

    return "método de pago"


def _format_amount(amount: float) -> str:
    try:
        return f"${amount:,.2f} MXN"
    except Exception:  # pragma: no cover - defensive
        return f"${amount} MXN"


def _fallback_description(expense, category: CategoryNormalizationResult) -> str:
    method_label = _humanize_payment_method(expense)
    proveedor = getattr(expense, "proveedor", None)
    if isinstance(proveedor, dict):
        proveedor = proveedor.get("nombre")

    if not proveedor:
        proveedor = getattr(expense, "merchant_name", None)

    if proveedor:
        return (
            f"Pago de {category.nombre.lower()} en {proveedor} con {method_label}"
            f" — {_format_amount(expense.monto_total)}"
        )

    return (
        f"Pago de {category.nombre.lower()} con {method_label}"
        f" — {_format_amount(expense.monto_total)}"
    )


def _call_openai(prompt: str) -> Dict[str, Any]:
    """Ejecuta la llamada a OpenAI y devuelve el JSON parseado."""

    api_key = config.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY no configurada")

    try:
        import openai
    except ImportError as exc:  # pragma: no cover - solo en entornos sin dependencia
        raise RuntimeError("openai package no instalado") from exc

    openai.api_key = api_key
    model = config.ACCOUNTING_ENRICHMENT_MODEL

    response = openai.ChatCompletion.create(
        model=model,
        temperature=0.2,
        messages=[
            {
                "role": "system",
                "content": (
                    "Eres un asistente contable. Redacta descripciones profesionales y"
                    " asigna categorías contables del catálogo proporcionado."
                    " Responde exclusivamente en JSON válido."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    )

    content = response["choices"][0]["message"]["content"]
    return json.loads(content)


def enrich_expense_details(expense, category_result: CategoryNormalizationResult) -> Dict[str, Any]:
    """Devuelve descripción y categoría refinadas aprovechando LLM.

    Si la capa LLM está deshabilitada o falla, se devuelve un formato
    determinista pero uniforme.
    """

    fallback_desc = _fallback_description(expense, category_result)

    enrichment = {
        "descripcion_normalizada": fallback_desc,
        "descripcion_fuente": "rule_based",
        "categoria_slug": category_result.slug,
        "categoria_normalizada": category_result.nombre,
        "categoria_confianza": category_result.confianza,
        "categoria_fuente": category_result.fuente,
        "sat_account_code": category_result.sat_account_code,
        "sat_product_service_code": category_result.sat_product_service_code,
        "needs_review": category_result.needs_review,
    }

    if not config.ACCOUNTING_ENRICHMENT_ENABLED:
        return enrichment

    try:
        prompt = json.dumps(
            {
                "descripcion_original": expense.descripcion,
                "monto": expense.monto_total,
                "moneda": getattr(expense, "moneda", "MXN"),
                "metodo_pago": _humanize_payment_method(expense),
                "proveedor": getattr(expense, "proveedor", None),
                "categoria_normalizada": asdict(category_result),
                "instrucciones": (
                    "Redacta una descripción concisa (<80 caracteres) en tono profesional."
                    " Devuelve JSON con campos: descripcion_normalizada, categoria_slug,"
                    " categoria_normalizada, categoria_confianza (0-1)."
                    " Si la categoría propuesta no está en el catálogo, reutiliza la proporcionada."
                ),
            },
            ensure_ascii=False,
        )

        llm_response = _call_openai(prompt)
        descripcion = llm_response.get("descripcion_normalizada")
        categoria_slug = llm_response.get("categoria_slug")
        categoria_nombre = llm_response.get("categoria_normalizada")
        categoria_conf = llm_response.get("categoria_confianza")

        if categoria_slug:
            validated_category = normalize_accounting_category(categoria_slug)
        elif categoria_nombre:
            validated_category = normalize_accounting_category(categoria_nombre)
        else:
            validated_category = category_result

        descripcion_final = descripcion or fallback_desc

        enrichment.update(
            {
                "descripcion_normalizada": descripcion_final,
                "descripcion_fuente": "llm" if descripcion else "rule_based",
                "categoria_slug": validated_category.slug,
                "categoria_normalizada": validated_category.nombre,
                "categoria_confianza": categoria_conf or validated_category.confianza,
                "categoria_fuente": "llm" if categoria_slug or categoria_nombre else validated_category.fuente,
                "sat_account_code": validated_category.sat_account_code,
                "sat_product_service_code": validated_category.sat_product_service_code,
                "needs_review": validated_category.needs_review,
            }
        )

        return enrichment

    except Exception as exc:  # pragma: no cover - protegido para entornos sin red
        logger.warning("Fallo enriquecimiento LLM, usando fallback: %s", exc)
        return enrichment
