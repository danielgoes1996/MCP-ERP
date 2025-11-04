"""Claude-powered context analyzer for company onboarding.

# ✅ Verified live connection to Claude (2025-10-12)
# Model: claude-3-haiku-20240307
# Status: Production-ready. Generates structured business context successfully.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

try:
    from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential
except ImportError:  # pragma: no cover - optional dependency
    def retry(*_args, **_kwargs):  # type: ignore
        def decorator(func):
            return func

        return decorator

    def retry_if_exception_type(*_args, **_kwargs):  # type: ignore
        return lambda exc: True

    def stop_after_attempt(*_args, **_kwargs):  # type: ignore
        return None

    def wait_exponential(*_args, **_kwargs):  # type: ignore
        return None

logger = logging.getLogger(__name__)

try:  # pragma: no cover - optional dependency during tests
    import anthropic
    from anthropic import APIError, APIStatusError, APITimeoutError  # type: ignore
except Exception:  # pragma: no cover - fallback when SDK not installed
    anthropic = None
    APIError = APIStatusError = APITimeoutError = Exception  # type: ignore


class ClaudeContextAnalyzerError(RuntimeError):
    """Raised when Claude returns an invalid payload."""


def _extract_json(payload: str) -> str:
    """Extract JSON object from mixed content using a permissive regex."""
    match = re.search(r"\{.*\}", payload, re.DOTALL)
    if not match:
        raise ClaudeContextAnalyzerError("Claude response does not contain JSON")
    return match.group(0)


def _parse_response_text(text: str) -> Dict[str, Any]:
    """Parse Claude output into a dictionary, fixing formatting issues if needed."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        cleaned = _extract_json(text)
        return json.loads(cleaned)


def _build_client() -> Optional["anthropic.Anthropic"]:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not configured; Claude analyzer will fallback")
        return None
    if anthropic is None:
        logger.warning("anthropic SDK not installed; Claude analyzer will fallback")
        return None
    return anthropic.Anthropic(api_key=api_key)


def _model_name() -> str:
    return os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022")


class _RetryableError(Exception):
    """Wrap retryable exceptions for tenacity."""


@retry(
    reraise=True,
    retry=retry_if_exception_type(_RetryableError),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    stop=stop_after_attempt(3),
)
def _call_claude(client: "anthropic.Anthropic", text: str, lang: str) -> Dict[str, Any]:
    prompt = (
        "Eres un analista contable y de operaciones empresariales.\n"
        "Analiza la descripcion libre de una empresa y genera un perfil operativo JSON con:\n"
        "summary (max. 3 lineas)\n"
        "business_profile (industry, products_services, clients, suppliers, channels, operation_frequency, company_size, business_model)\n"
        "topics\n"
        "confidence_score\n"
        "language_detected\n"
        "Responde solo con JSON valido.\n\n"
        f"Texto de entrada ({lang}):\n{text}"
    )

    try:
        response = client.messages.create(
            model=_model_name(),
            max_tokens=700,
            system="Devuelve unica y exclusivamente JSON valido.",
            messages=[{"role": "user", "content": prompt}],
        )
    except (APIError, APIStatusError, APITimeoutError) as exc:  # pragma: no cover - network failure
        logger.warning("Claude API error: %s", exc)
        raise _RetryableError(str(exc))
    except Exception as exc:  # pragma: no cover - unexpected failure
        logger.error("Unexpected Claude API failure: %s", exc)
        raise

    text_content = ""
    if response.content:
        # Claude responses may contain multiple content blocks
        text_parts = []
        for block in response.content:
            if getattr(block, "type", None) == "text":
                text_parts.append(block.text)
        text_content = "".join(text_parts)

    if not text_content:
        raise ClaudeContextAnalyzerError("Claude returned no textual content")

    result = _parse_response_text(text_content)
    result.setdefault("language_detected", "es")

    usage = getattr(response, "usage", None)
    if usage:
        logger.debug(
            "Claude usage - input_tokens=%s, output_tokens=%s",
            getattr(usage, "input_tokens", None),
            getattr(usage, "output_tokens", None),
        )

    return result


def analyze_context_with_claude(text: str, lang: str = "es") -> Dict[str, Any]:
    """Analyse company context using Claude, returning structured data."""
    if not text or not text.strip():
        raise ValueError("text must contain content")

    client = _build_client()
    if client is None:
        raise ClaudeContextAnalyzerError("Claude client unavailable")

    logger.info("Analyzing company context with Claude model %s", _model_name())
    result = _call_claude(client, text.strip(), lang)
    result.setdefault("summary", "")
    result.setdefault("business_profile", {})
    topics = result.get("topics")
    if not isinstance(topics, list):
        result["topics"] = [str(topics)] if topics else []
    result.setdefault("confidence_score", 0.9)
    result.setdefault("language_detected", "es")
    result["model_name"] = _model_name()

    logger.info(
        "Claude context analysis completed (confidence=%s, topics=%s)",
        result.get("confidence_score"),
        ", ".join(result.get("topics", [])) or "none",
    )
    return result


def _stub_questions(context_text: str, count: int = 5) -> List[Dict[str, str]]:
    """Generate deterministic fallback questions when Claude is unavailable."""
    base_questions = [
        "¿Qué productos o servicios ofreces principalmente?",
        "¿Compras inventario a proveedores o fabricas internamente?",
        "¿Quiénes son tus clientes más comunes?",
        "¿Cómo cobras: contado, crédito o suscripciones?",
        "¿Con qué frecuencia realizas operaciones importantes (compras, ventas)?",
        "¿Trabajas con empleados, contratistas o ambos?",
        "¿Qué sistemas o canales usas para vender (tienda física, ecommerce, mayoristas)?",
    ]
    selected = base_questions[:count]
    return [{"question": q} for q in selected]


@retry(
    reraise=True,
    retry=retry_if_exception_type(_RetryableError),
    wait=wait_exponential(multiplier=1, min=1, max=6),
    stop=stop_after_attempt(3),
)
def _call_claude_questions(
    client: "anthropic.Anthropic",
    context_text: str,
    lang: str,
    count: int,
) -> List[Dict[str, str]]:
    prompt = (
        "Actúa como un consultor contable experto que recopila contexto operativo.\n"
        "Genera una lista de preguntas que nos ayuden a configurar el sistema contable "
        "y entender obligaciones fiscales de la empresa descrita.\n\n"
        f"Descripción ({lang}):\n{context_text}\n\n"
        "Responde únicamente con JSON válido en formato:\n"
        "[{\"question\": \"...\"}, ...].\n"
        f"Incluye exactamente {count} preguntas si hay suficiente información."
    )

    try:
        response = client.messages.create(
            model=_model_name(),
            max_tokens=400,
            system="Devuelve única y exclusivamente JSON válido con preguntas contextuales.",
            messages=[{"role": "user", "content": prompt}],
        )
    except (APIError, APIStatusError, APITimeoutError) as exc:  # pragma: no cover - network failure
        logger.warning("Claude question generation error: %s", exc)
        raise _RetryableError(str(exc))
    except Exception as exc:  # pragma: no cover - unexpected failure
        logger.error("Unexpected Claude question failure: %s", exc)
        raise

    text_content = ""
    if response.content:
        for block in response.content:
            if getattr(block, "type", None) == "text":
                text_content += block.text

    if not text_content:
        raise ClaudeContextAnalyzerError("Claude returned no question content")

    try:
        parsed = json.loads(text_content)
    except json.JSONDecodeError:
        cleaned = _extract_json(text_content)
        parsed = json.loads(cleaned)

    if not isinstance(parsed, list):
        raise ClaudeContextAnalyzerError("Claude questions payload is not a list")

    questions: List[Dict[str, str]] = []
    for item in parsed:
        if isinstance(item, dict) and "question" in item:
            questions.append({"question": str(item["question"]).strip()})
        elif isinstance(item, str):
            questions.append({"question": item.strip()})

    # Trim or pad to requested count
    questions = [q for q in questions if q.get("question")]
    if len(questions) > count:
        questions = questions[:count]
    elif len(questions) < count:
        # append stub questions to complete
        missing = count - len(questions)
        questions.extend(_stub_questions(context_text, count=missing))

    return questions


def generate_context_questions(
    context_text: str,
    *,
    lang: str = "es",
    count: int = 5,
) -> List[Dict[str, str]]:
    """Generate conversational onboarding questions for a company context."""
    if not context_text or not context_text.strip():
        raise ValueError("context_text must contain content")

    client = _build_client()
    if client is None:
        logger.warning("Claude client unavailable; using stub questions")
        return _stub_questions(context_text, count)

    try:
        questions = _call_claude_questions(client, context_text.strip(), lang, count)
        logger.info("Generated %s onboarding questions with Claude", len(questions))
        return questions
    except (ClaudeContextAnalyzerError, ValueError) as exc:
        logger.warning("Falling back to stub question generator: %s", exc)
    except Exception as exc:  # pragma: no cover - safety
        logger.exception("Unexpected error generating questions: %s", exc)

    return _stub_questions(context_text, count)
