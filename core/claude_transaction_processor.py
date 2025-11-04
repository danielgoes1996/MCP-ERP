"""Gemini-powered post-processing for bank statement extraction.

This module takes the raw JSON emitted by the Gemini native parser and asks
Gemini 2.5 to normalize, classify, and enrich the transactions using the company
context stored in ContaFlow. The goal is to keep the native parser focused on
OCR while Gemini applies business rules and contextual knowledge before the data
reaches the UI or database layer.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, date
import textwrap
from typing import Any, Dict, List, Optional, Tuple

import re

try:
    import google.generativeai as genai

    GEMINI_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    genai = None
    GEMINI_AVAILABLE = False

from core.bank_statements_models import (
    BankTransaction,
    MovementKind,
    TransactionType,
    infer_movement_kind,
)

logger = logging.getLogger(__name__)


class ClaudeTransactionProcessor:
    """Use Gemini 2.5 to enrich raw transactions with business context."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        self.api_key = (
            api_key
            or os.getenv("GOOGLE_AI_API_KEY")
            or os.getenv("GEMINI_API_KEY")
        )
        self.model = (
            model
            or os.getenv("GEMINI_TRANSACTION_MODEL")
            or os.getenv("CLAUDE_TRANSACTION_MODEL")
            or os.getenv("CLAUDE_MODEL")
            or "gemini-2.5-flash"
        )

        if self.model and self.model.lower().startswith("claude"):
            logger.info(
                "Gemini enrichment overriding incompatible model '%s' with 'gemini-2.5-flash'",
                self.model,
            )
            self.model = "gemini-2.5-flash"

        self._generation_config = None
        self._request_timeout = int(os.getenv("GEMINI_ENRICH_TIMEOUT", "180"))
        self._gemini_model = None

        if not GEMINI_AVAILABLE:
            logger.warning(
                "⚠️ google-generativeai not installed – skipping Gemini enrichment"
            )
            return

        if not self.api_key:
            logger.warning(
                "⚠️ Google AI API key not configured – skipping Gemini enrichment"
            )
            return

        try:
            genai.configure(api_key=self.api_key)
            max_tokens = int(os.getenv("GEMINI_ENRICH_MAX_TOKENS", "8192"))
            temperature = float(os.getenv("GEMINI_ENRICH_TEMPERATURE", "0.0"))
            self._generation_config = genai.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
                response_mime_type="application/json",
            )
            self._gemini_model = genai.GenerativeModel(self.model)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("⚠️ Unable to initialise Gemini enrichment: %s", exc)
            self._gemini_model = None

    def enrich_transactions(
        self,
        raw_extraction: Dict[str, Any],
        existing_transactions: List[BankTransaction],
        company_context: Optional[Dict[str, Any]],
        account_id: int,
        user_id: int,
        tenant_id: int,
    ) -> Optional[Dict[str, Any]]:
        """Return enriched transactions and metadata, or None on failure."""

        if not self.api_key or not self._gemini_model:
            return None

        raw_transactions = raw_extraction.get("raw_transactions") or []
        if not raw_transactions:
            logger.info("Gemini enrichment skipped – no raw_transactions provided")
            return None

        chunk_env = os.getenv("GEMINI_ENRICH_CHUNK") or os.getenv("CLAUDE_ENRICH_CHUNK") or "8"
        try:
            chunk_size = int(chunk_env)
        except ValueError:
            logger.warning("Invalid GEMINI_ENRICH_CHUNK value '%s' – defaulting to 8", chunk_env)
            chunk_size = 8
        chunk_size = max(1, chunk_size)

        aggregated_transactions: List[BankTransaction] = []
        combined_summary: Dict[str, Any] = {
            "issues": [],
            "warnings": [],
            "inferred_period": {}
        }

        try:
            total_transactions = len(raw_transactions)
            start = 0
            chunk_index = 1

            while start < total_transactions:
                attempts = 0
                current_size = chunk_size

                while True:
                    end = min(total_transactions, start + current_size)
                    raw_chunk = raw_transactions[start:end]
                    existing_chunk = existing_transactions[start:end]

                    chunk_payload = dict(raw_extraction)
                    chunk_payload['raw_transactions'] = raw_chunk

                    prompt = self._build_prompt(
                        chunk_payload,
                        existing_chunk,
                        company_context,
                        current_size,
                    )

                    logger.info(
                        "Gemini chunk %s [%s-%s) | prompt chars=%s | raw_tx=%s | model=%s | chunk_size=%s",
                        chunk_index,
                        start,
                        end,
                        len(prompt),
                        len(raw_chunk),
                        self.model,
                        current_size,
                    )

                    response_text, finish_reason = self._call_gemini(prompt)
                    logger.info(
                        "Gemini chunk %s | respuesta=%s chars",
                        chunk_index,
                        len(response_text),
                    )

                    try:
                        structured = self._parse_response(response_text)
                    except ValueError as parse_exc:
                        if current_size == 1 or attempts >= 4:
                            raise
                        attempts += 1
                        current_size = max(1, current_size // 2)
                        logger.warning(
                            "Gemini JSON parse failed (%s). Reducing chunk size to %s and retrying",
                            parse_exc,
                            current_size,
                        )
                        continue

                    if finish_reason == 2 and current_size > 1 and attempts < 4:
                        attempts += 1
                        current_size = max(1, current_size // 2)
                        logger.warning(
                            "Gemini max_tokens hit for chunk size %s. Reducing chunk size to %s and retrying",
                            len(raw_chunk),
                            current_size,
                        )
                        continue

                    chunk_size = current_size  # adapt for subsequent iterations
                    break

                enriched_chunk = self._convert_to_transactions(
                    structured.get("transactions", []),
                    account_id,
                    user_id,
                    tenant_id,
                    company_context,
                )

                if not enriched_chunk:
                    logger.warning(
                        "Gemini enrichment returned no transactions for chunk %s-%s – keeping base output",
                        start,
                        end,
                    )
                    continue

                aggregated_transactions.extend(enriched_chunk)

                summary = structured.get("summary") or {}
                combined_summary.setdefault("issues", []).extend(summary.get("issues", []))
                combined_summary.setdefault("warnings", []).extend(summary.get("warnings", []))

                inferred = summary.get("inferred_period") or {}
                if inferred:
                    combined_summary["inferred_period"] = inferred

                start = end
                chunk_index += 1

            if not aggregated_transactions:
                logger.warning("Gemini enrichment returned no transactions after chunking – keeping base output")
                return None

            return {
                "transactions": aggregated_transactions,
                "summary": combined_summary,
                "model": self.model,
            }

        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(
                "⚠️ Gemini enrichment failed: %s (prompt_len=%s)",
                exc,
                len(prompt) if 'prompt' in locals() else 'n/a',
            )
            logger.debug("Gemini enrichment error", exc_info=True)
            return None

    # ------------------------------------------------------------------
    # Prompt building & API communication
    # ------------------------------------------------------------------
    def _build_prompt(
        self,
        raw_extraction: Dict[str, Any],
        existing_transactions: List[BankTransaction],
        company_context: Optional[Dict[str, Any]],
        chunk_size: int,
    ) -> str:
        """Build a structured prompt describing the enrichment task."""

        context_block, alias_block, category_block = self._format_company_context(company_context)
        bank_info_json = json.dumps(
            raw_extraction.get("bank_info", {}),
            ensure_ascii=False,
            indent=2,
        )
        balances_json = json.dumps(
            raw_extraction.get("balances", {}),
            ensure_ascii=False,
            indent=2,
        )
        metadata_json = json.dumps(
            raw_extraction.get("metadata", {}),
            ensure_ascii=False,
            indent=2,
        )

        # Gemini already extracted a minimal transaction list; include a compact
        # snapshot so the enrichment model can cross-check any inferred fields.
        minimal_transactions = [
            {
                "date": txn.date.isoformat(),
                "description": txn.description[:120],
                "amount": txn.amount,
                "transaction_type": txn.transaction_type,
                "movement_kind": txn.movement_kind,
            }
            for txn in existing_transactions[:20]
        ]

        minimal_json = json.dumps(minimal_transactions, ensure_ascii=False, indent=2)

        # Limit payload to avoid oversized prompts while preserving ordering.
        raw_transactions = raw_extraction.get("raw_transactions", [])[:chunk_size]
        simplified_raw = []
        for item in raw_transactions:
            simplified_raw.append({
                "date_raw": (item.get("date_raw") or item.get("date") or '')[:32],
                "description_raw": (item.get("description_raw") or item.get("description") or '')[:160],
                "amount_raw": item.get("amount_raw") or item.get("amount"),
                "type_raw": item.get("type_raw") or item.get("transaction_type"),
                "reference_raw": (item.get("reference_raw") or item.get("reference") or '')[:64],
            })

        raw_transactions_json = json.dumps(simplified_raw, ensure_ascii=False, indent=2)

        instructions = textwrap.dedent(
            """
            Eres un analista bancario experto de ContaFlow. Recibes transacciones extraídas por Gemini (sin contexto de negocio).
            Tu trabajo es:
            1. Normalizar fechas al formato YYYY-MM-DD inferidas del periodo.
            2. Convertir montos a números flotantes, negativos para egresos (cargos) y positivos para ingresos (abonos).
            3. Determinar transaction_type (credit/debit) y movement_kind (Ingreso/Gasto/Transferencia).
            4. Inferir categorías de gasto/ingreso con máximo contexto disponible.
            5. Detectar notas relevantes (comisiones, impuestos, transferencias internas, duplicados).
            6. Generar un campo `display_name` claro y legible: capitaliza apropiadamente, expande abreviaturas comunes (ej. "GPO" → "Grupo"), respeta alias conocidos y acrónimos ("MX", "SAT").
            7. Reportar cualquier transacción dudosa o sin suficiente información.

            Reglas críticas:
            - No inventes transacciones nuevas.
            - Si falta información para clasificar, marca `movement_kind` como "Transferencia" y agrega una nota.
            - Usa el contexto de la empresa para mejorar categorías o detectar fraudes.
            - Respeta el idioma original de las descripciones.
            - Siempre devuelve JSON válido (sin comentarios ni texto extra).

            Salida requerida:
            {
              "transactions": [
                {
                  "date": "YYYY-MM-DD",
                  "description": "texto exacto",
                  "display_name": "versión legible y amigable de la descripción",
                  "amount": -123.45,
                  "transaction_type": "debit" | "credit",
                  "movement_kind": "Ingreso" | "Gasto" | "Transferencia",
                  "category": "string opcional",
                  "reference": "opcional",
                  "balance_after": "float opcional",
                  "confidence": 0.0-1.0,
                  "notes": "opcional",
                  "source_line": "texto original si aplica"
                }
              ],
              "summary": {
                "issues": ["texto"],
                "warnings": ["texto"],
                "inferred_period": {
                  "start": "YYYY-MM-DD opcional",
                  "end": "YYYY-MM-DD opcional"
                }
              }
            }

            Incluye todas las transacciones recibidas. No devuelvas explicaciones fuera del JSON.
            """
        ).strip()

        return (
            f"Contexto de la empresa:\n{context_block}\n\n"
            f"Alias conocidos de proveedores y entradas frecuentes:\n{alias_block}\n\n"
            f"Categorías base sugeridas por la empresa:\n{category_block}\n\n"
            f"Información detectada del estado de cuenta (Gemini):\n{bank_info_json}\n\n"
            f"Balances detectados:\n{balances_json}\n\n"
            f"Metadata del documento:\n{metadata_json}\n\n"
            f"Transacciones mínimas convertidas por Gemini:\n{minimal_json}\n\n"
            f"Transacciones crudas extraídas por Gemini:\n{raw_transactions_json}\n\n"
            f"{instructions}"
        )

    def _call_gemini(self, prompt: str) -> Tuple[str, Optional[int]]:
        if not self._gemini_model:
            raise RuntimeError("Gemini model not initialised")

        request_options = {"timeout": self._request_timeout} if self._request_timeout else None

        response = self._gemini_model.generate_content(
            prompt,
            generation_config=self._generation_config,
            request_options=request_options,
        )

        # google.generativeai may return parsed structured output; prefer text to
        # keep backward compatibility with the existing JSON parser.
        response_text: Optional[str] = None
        finish_reason: Optional[int] = None
        try:
            response_text = getattr(response, "text", None)
        except Exception as exc:  # pragma: no cover - depends on SDK internals
            logger.debug("Gemini response.text unavailable: %s", exc)
            response_text = None

        if not response_text and hasattr(response, "candidates"):
            parts: List[str] = []
            for candidate in response.candidates or []:  # type: ignore[attr-defined]
                content = getattr(candidate, "content", None)
                if content is None:
                    continue
                candidate_parts = getattr(content, "parts", None)
                if not candidate_parts:
                    continue
                for part in candidate_parts:  # pragma: no cover - depends on SDK internals
                    text = getattr(part, "text", None)
                    if text:
                        parts.append(text)
                finish_reason = getattr(candidate, "finish_reason", None)
                if finish_reason and finish_reason != 1:
                    logger.warning(
                        "Gemini candidate finished with reason %s (see https://ai.google.dev/api/generate-content#finishreason)",
                        finish_reason,
                    )
            response_text = "\n".join(parts)

        if not response_text:
            logger.warning("Gemini response returned no text; raw response: %s", response)
            response_text = str(response)
        elif finish_reason and finish_reason != 1:
            logger.warning(
                "Gemini enrichment completed with non-standard finish_reason=%s; output length=%s",
                finish_reason,
                len(response_text),
            )

        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]

        return response_text.strip(), finish_reason

    # ------------------------------------------------------------------
    # Response conversion helpers
    # ------------------------------------------------------------------
    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        try:
            return json.loads(response_text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Gemini respuesta inválida: {exc}") from exc

    def _convert_to_transactions(
        self,
        items: List[Dict[str, Any]],
        account_id: int,
        user_id: int,
        tenant_id: int,
        company_context: Optional[Dict[str, Any]],
    ) -> List[BankTransaction]:
        if not items:
            return []

        context_json, context_confidence, context_version = self._prepare_context_metadata(
            company_context
        )

        alias_map = self._build_alias_map(company_context)

        transactions: List[BankTransaction] = []

        for item in items:
            try:
                date_value = self._parse_date(item.get("date"))
                if not date_value:
                    logger.debug(f"Skipping transaction without valid date: {item}")
                    continue

                amount_value = self._parse_amount(item.get("amount"))
                transaction_type = self._determine_type(item.get("transaction_type"), amount_value)
                if transaction_type == TransactionType.DEBIT and amount_value > 0:
                    amount_value = -abs(amount_value)
                elif transaction_type == TransactionType.CREDIT and amount_value < 0:
                    amount_value = abs(amount_value)

                movement_kind = self._parse_movement_kind(item.get("movement_kind"), transaction_type, item.get("description"))

                category = item.get("category") or None
                reference = item.get("reference") or None
                balance_after = self._parse_optional_float(item.get("balance_after"))
                confidence = self._parse_confidence(item.get("confidence"))

                description = (item.get("description") or "").strip()
                if not description:
                    continue

                notes = (item.get("notes") or "").strip()

                raw_payload = item.copy()
                if notes:
                    raw_payload.setdefault("notes", notes)

                display_name = (
                    item.get("display_name")
                    or self._normalize_display_name(description, alias_map)
                )

                transaction = BankTransaction(
                    account_id=account_id,
                    user_id=user_id,
                    tenant_id=tenant_id,
                    date=date_value,
                    description=description[:500],
                    amount=amount_value,
                    transaction_type=transaction_type,
                    category=category,
                    reference=reference[:120] if reference else None,
                    balance_after=balance_after,
                    movement_kind=movement_kind,
                    confidence=confidence,
                    raw_data=json.dumps(raw_payload, ensure_ascii=False)[:1000],
                    ai_model=self.model,
                    context_used=context_json or None,
                    context_confidence=context_confidence,
                    context_version=context_version,
                    display_name=display_name[:500] if display_name else description[:500],
                )

                transactions.append(transaction)

            except Exception as exc:  # pragma: no cover - defensive
                logger.debug(f"Skipping transaction due to error: {exc}")
                continue

        return transactions

    @staticmethod
    def _build_alias_map(company_context: Optional[Dict[str, Any]]) -> Dict[str, str]:
        alias_map: Dict[str, str] = {}
        if not company_context:
            return alias_map

        aliases = company_context.get("aliases")
        if isinstance(aliases, dict):
            alias_map.update({str(k).lower(): str(v) for k, v in aliases.items()})

        legacy_aliases = company_context.get("alias")
        if isinstance(legacy_aliases, dict):
            for k, v in legacy_aliases.items():
                alias_map[str(k).lower()] = str(v)

        business_profile = company_context.get("business_profile")
        if isinstance(business_profile, dict):
            profile_aliases = business_profile.get("aliases")
            if isinstance(profile_aliases, dict):
                for k, v in profile_aliases.items():
                    alias_map.setdefault(str(k).lower(), str(v))

        return alias_map

    @staticmethod
    def _normalize_display_name(description: str, alias_map: Dict[str, str]) -> str:
        text = description.strip()
        lower = text.lower()
        for key, value in alias_map.items():
            if key and key in lower:
                normalized_value = value.strip()
                if normalized_value[:1].islower():
                    normalized_value = normalized_value[:1].upper() + normalized_value[1:]
                return normalized_value

        # Remove repeated spaces and apply title casing, preserving common acronyms
        cleaned = re.sub(r"\s+", " ", text)
        title = cleaned.title()
        # Restore uppercase acronyms present in original text
        for token in re.findall(r"[A-Z]{2,}", description):
            title = re.sub(re.escape(token.title()), token, title)
        if title[:1].islower():
            title = title[:1].upper() + title[1:]
        return title

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _format_company_context(
        context: Optional[Dict[str, Any]]
    ) -> tuple[str, str, str]:
        if not context:
            return (
                "Contexto no disponible",
                "Sin alias registrados",
                "Sin categorías preferentes",
            )

        summary = context.get("summary") or "Contexto no disponible"
        profile = context.get("business_profile")
        if isinstance(profile, str):
            try:
                profile = json.loads(profile)
            except (TypeError, json.JSONDecodeError):
                pass

        if isinstance(profile, (dict, list)):
            profile_text = json.dumps(profile, ensure_ascii=False, indent=2)
        elif profile:
            profile_text = str(profile)
        else:
            profile_text = "Perfil no disponible"

        base_block = (
            f"Resumen:\n{summary}\n\n"
            f"Perfil de negocio:\n{profile_text}"
        ).strip()

        aliases = context.get("aliases") or {}
        business_profile = context.get("business_profile")
        if isinstance(business_profile, dict):
            profile_aliases = business_profile.get("aliases")
            if isinstance(profile_aliases, dict):
                for key, value in profile_aliases.items():
                    aliases.setdefault(str(key), str(value))
        alias_lines = [
            f"- {key} → {value}"
            for key, value in aliases.items()
        ]
        if not alias_lines:
            alias_lines = ["- Sin alias conocidos"]
        alias_block = "\n".join(alias_lines)

        favorite_categories = (
            context.get("categorias_frecuentes")
            or context.get("favorite_categories")
            or {}
        )
        if isinstance(business_profile, dict):
            profile_categories = (
                business_profile.get("categorias_frecuentes")
                or business_profile.get("favorite_categories")
            )
            if isinstance(profile_categories, dict):
                for provider, category in profile_categories.items():
                    favorite_categories.setdefault(str(provider), str(category))
        category_lines = [
            f"- {provider} → {category}"
            for provider, category in favorite_categories.items()
        ]
        if not category_lines:
            category_lines = ["- Sin categorías preferentes"]
        category_block = "\n".join(category_lines)

        return base_block, alias_block, category_block

    @staticmethod
    def _prepare_context_metadata(
        context: Optional[Dict[str, Any]]
    ) -> tuple[Optional[str], Optional[float], Optional[int]]:
        if not context:
            return None, None, None

        summary = context.get("summary")
        profile = context.get("business_profile")
        if isinstance(profile, str):
            try:
                profile = json.loads(profile)
            except (TypeError, json.JSONDecodeError):
                pass

        payload = {"summary": summary, "business_profile": profile}
        context_json = json.dumps(payload, ensure_ascii=False)

        confidence = None
        version = None

        if context.get("confidence_score") is not None:
            try:
                confidence = float(context["confidence_score"])
            except (TypeError, ValueError):  # pragma: no cover - defensive
                logger.debug(f"Invalid context confidence: {context['confidence_score']}")
                confidence = None

        if context.get("context_version") is not None:
            try:
                version = int(context["context_version"])
            except (TypeError, ValueError):  # pragma: no cover - defensive
                logger.debug(f"Invalid context version: {context['context_version']}")
                version = None

        return context_json, confidence, version

    @staticmethod
    def _parse_date(value: Any) -> Optional[date]:
        if not value:
            return None

        if isinstance(value, datetime):
            return value.date()

        text = str(value).strip()
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        return None

    @staticmethod
    def _parse_amount(value: Any) -> float:
        if isinstance(value, (int, float)):
            return round(float(value), 2)

        text = str(value).replace("$", "").replace(",", "").strip()
        if not text:
            return 0.0

        try:
            return round(float(text), 2)
        except ValueError:
            return 0.0

    @staticmethod
    def _parse_movement_kind(
        value: Any,
        transaction_type: TransactionType,
        description: Optional[str],
    ) -> MovementKind:
        if isinstance(value, str):
            normalized = value.strip().lower()
            if "ingreso" in normalized:
                return MovementKind.INGRESO
            if "gasto" in normalized:
                return MovementKind.GASTO
            if "transfer" in normalized:
                return MovementKind.TRANSFERENCIA

        return infer_movement_kind(transaction_type, description)

    @staticmethod
    def _parse_confidence(value: Any) -> float:
        try:
            if value is None:
                return 0.85
            conf = float(value)
            if conf == 0:
                return 0.75
            if conf < 0:
                return 0.0
            if conf > 1:
                return 1.0
            return conf
        except (TypeError, ValueError):
            return 0.85

    @staticmethod
    def _parse_optional_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(str(value).replace(',', '').replace('$', '').strip())
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _determine_type(value: Any, amount: float) -> TransactionType:
        if isinstance(value, str):
            text = value.strip().lower()
            if text in {"credit", "cr", "abono"}:
                return TransactionType.CREDIT
            if text in {"debit", "db", "cargo"}:
                return TransactionType.DEBIT

        if amount >= 0:
            return TransactionType.CREDIT
        return TransactionType.DEBIT


__all__ = ["ClaudeTransactionProcessor"]
