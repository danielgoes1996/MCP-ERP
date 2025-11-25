import base64
import json
import logging
import os
import re
import tempfile
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from config.config import config
from core.whatsapp_integration import get_whatsapp_integration

try:
    from core.voice_handler import get_voice_handler
except ImportError:  # pragma: no cover - optional dependency
    get_voice_handler = None  # type: ignore

try:
    from modules.invoicing_agent.services.ocr_service import OCRService as OCRServiceClass
except ImportError:  # pragma: no cover - optional dependency
    OCRServiceClass = None  # type: ignore

if config.USE_UNIFIED_DB:
    from core.shared.unified_db_adapter import get_unified_adapter, record_internal_expense
else:  # pragma: no cover - fallback path
    from core.internal_db import record_internal_expense  # type: ignore

    get_unified_adapter = None  # type: ignore

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks/whatsapp", tags=["WhatsApp"])

DEFAULT_TENANT_ID = int(os.getenv("WHATSAPP_DEFAULT_TENANT_ID", "1"))
DEFAULT_COMPANY_ID = os.getenv("WHATSAPP_DEFAULT_COMPANY_ID", "default")
DEFAULT_USER_ID = int(os.getenv("WHATSAPP_DEFAULT_USER_ID", "1"))
VOICE_ENABLED = bool(get_voice_handler)
_voice_handler = None
_ocr_service: Optional[Any] = None


@router.get("")
async def verify_whatsapp_webhook(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
) -> PlainTextResponse:
    """Verification endpoint required by Meta."""
    integration = get_whatsapp_integration()
    verification = integration.verify_webhook(hub_mode or "", hub_verify_token or "", hub_challenge or "")
    if verification:
        return PlainTextResponse(content=verification)
    raise HTTPException(status_code=403, detail="WhatsApp verification failed")


@router.post("")
async def whatsapp_webhook(request: Request) -> JSONResponse:
    """Primary webhook that receives WhatsApp Business events."""
    integration = get_whatsapp_integration()
    signature = request.headers.get("X-Hub-Signature-256", "")
    payload_bytes = await request.body()

    if not integration.verify_signature(payload_bytes, signature):
        raise HTTPException(status_code=403, detail="Invalid webhook signature")

    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except json.JSONDecodeError as exc:
        logger.error(f"Invalid WhatsApp payload: {exc}")
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from exc

    # DEBUG: Log full webhook payload
    logger.info(f"📩 Webhook received: {json.dumps(payload, indent=2)}")

    processed_results: List[Dict[str, Any]] = []

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            field_type = change.get("field")
            logger.info(f"📋 Webhook field type: {field_type}")
            if field_type != "messages":
                logger.info(f"⏭️ Skipping non-message webhook: {field_type}")
                continue

            value = change.get("value", {})
            messages = value.get("messages", [])
            contacts = value.get("contacts", [])

            for message in messages:
                try:
                    result = await _process_single_message(message, contacts, integration)
                except Exception as exc:  # pragma: no cover - defensive logging
                    logger.exception(f"Failed to process WhatsApp message: {exc}")
                    result = {
                        "message_id": message.get("id"),
                        "status": "error",
                        "error": str(exc),
                    }
                processed_results.append(result)

    return JSONResponse(
        content={
            "success": True,
            "processed": processed_results,
            "total_messages": len(processed_results),
        }
    )


async def _process_single_message(
    message: Dict[str, Any],
    contacts: List[Dict[str, Any]],
    integration,
) -> Dict[str, Any]:
    message_type = message.get("type")
    message_id = message.get("id")
    from_number = message.get("from")
    timestamp = message.get("timestamp")

    logger.info(f"Processing WhatsApp message {message_id} type={message_type}")

    if message_type == "text":
        message_text = message.get("text", {}).get("body", "")
        logger.warning(f"WHATSAPP MESSAGE FROM {from_number}: {message_text}")
        expense = integration.process_text_payload(
            message_id=message_id,
            from_number=from_number,
            text=message_text,
            timestamp=timestamp,
            contacts=contacts,
            extra_metadata={"raw_context": message},
        )
        return await _persist_expense_if_needed(expense, from_number)

    if message_type in {"audio", "voice"}:
        media_id = message.get(message_type, {}).get("id")
        transcript = await _handle_audio_message(media_id, message_type)
        if not transcript:
            integration.send_info_message(
                from_number,
                "Recibí tu nota de voz pero no pude transcribirla. Intenta repetirla o enviar texto.",
            )
            return {"message_id": message_id, "status": "skipped", "reason": "transcription_failed"}

        expense = integration.process_text_payload(
            message_id=message_id,
            from_number=from_number,
            text=transcript,
            timestamp=timestamp,
            contacts=contacts,
            extra_metadata={"source_media_type": message_type},
        )
        return await _persist_expense_if_needed(expense, from_number)

    if message_type in {"image", "document"}:
        media_id = message.get(message_type, {}).get("id")
        ocr_text = await _handle_image_message(media_id)
        if not ocr_text:
            integration.send_info_message(
                from_number,
                "Recibí tu imagen/documento pero no pude leer los datos. Envía texto o una foto más clara.",
            )
            return {"message_id": message_id, "status": "skipped", "reason": "ocr_failed"}

        expense = integration.process_text_payload(
            message_id=message_id,
            from_number=from_number,
            text=ocr_text,
            timestamp=timestamp,
            contacts=contacts,
            extra_metadata={"source_media_type": message_type},
        )
        return await _persist_expense_if_needed(expense, from_number)

    logger.info(f"Ignoring unsupported WhatsApp message type: {message_type}")
    return {"message_id": message_id, "status": "ignored", "reason": "unsupported_type"}


async def _handle_audio_message(media_id: Optional[str], media_type: str) -> Optional[str]:
    if not media_id:
        return None
    if not VOICE_ENABLED:
        logger.warning("Voice handler not configured; skipping audio message")
        return None

    media_bytes, mime_type = await _fetch_media_bytes(media_id)
    handler = _get_voice_handler()
    if not handler:
        return None

    suffix = _extension_from_mime(mime_type) or ".mp3"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
        tmp_file.write(media_bytes)
        tmp_path = tmp_file.name

    try:
        result = handler.transcribe_audio(tmp_path)
        if result.get("success"):
            return result.get("transcript")
        logger.warning(f"Voice transcription failed: {result.get('error')}")
        return None
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            logger.debug("Could not remove temp audio file %s", tmp_path)


async def _handle_image_message(media_id: Optional[str]) -> Optional[str]:
    if not media_id:
        return None
    if OCRServiceClass is None:
        logger.warning("OCRService not available; cannot process WhatsApp images/documents")
        return None

    media_bytes, _ = await _fetch_media_bytes(media_id)
    service = _get_ocr_service()
    if not service:
        return None

    base64_image = base64.b64encode(media_bytes).decode("utf-8")
    try:
        result = await service.extract_text(base64_image)
    except Exception as exc:
        logger.error(f"OCR extraction failed: {exc}")
        return None

    if not result or not result.text:
        return None
    return result.text


async def _fetch_media_bytes(media_id: str) -> Tuple[bytes, Optional[str]]:
    access_token = os.getenv("WHATSAPP_ACCESS_TOKEN")
    if not access_token:
        raise HTTPException(status_code=500, detail="WhatsApp access token is not configured")

    base_url = "https://graph.facebook.com/v18.0"
    headers = {"Authorization": f"Bearer {access_token}"}

    async with httpx.AsyncClient(timeout=30) as client:
        meta_resp = await client.get(f"{base_url}/{media_id}", headers=headers)
        if meta_resp.status_code >= 400:
            logger.error(f"Failed to fetch media metadata: {meta_resp.text}")
            raise HTTPException(status_code=502, detail="Failed to fetch media metadata from Meta")

        meta_json = meta_resp.json()
        media_url = meta_json.get("url")
        mime_type = meta_json.get("mime_type")
        if not media_url:
            raise HTTPException(status_code=502, detail="Media URL missing in Meta response")

        file_resp = await client.get(media_url, headers=headers)
        if file_resp.status_code >= 400:
            logger.error(f"Failed to download media file: {file_resp.text}")
            raise HTTPException(status_code=502, detail="Failed to download media content")

        return file_resp.content, mime_type


async def _persist_expense_if_needed(expense_data: Optional[Dict[str, Any]], from_number: Optional[str]) -> Dict[str, Any]:
    if not expense_data:
        return {"status": "skipped", "reason": "no_expense_detected"}

    tenant_id, company_id, user_id = _resolve_tenant_context(from_number)
    metadata = expense_data.get("metadata") or {}
    metadata.setdefault("source", "whatsapp")

    description = expense_data.get("descripcion") or expense_data.get("metadata", {}).get("intent_analysis", {}).get("original_text")
    amount_value = expense_data.get("monto_total") or expense_data.get("metadata", {}).get("intent_analysis", {}).get("monto")

    try:
        amount = float(amount_value) if amount_value is not None else 0.0
    except (TypeError, ValueError):
        amount = 0.0

    payload = {
        "description": description or "Gasto WhatsApp",
        "amount": amount,
        "currency": expense_data.get("moneda", "MXN"),
        "date": expense_data.get("fecha_gasto"),
        "category": expense_data.get("categoria"),
        "merchant_name": (expense_data.get("proveedor") or {}).get("nombre"),
        "metadata": metadata,
        "registro_via": "whatsapp",
        "workflow_status": expense_data.get("workflow_status", "pendiente_validacion"),
        "invoice_status": expense_data.get("estado_factura", "pendiente"),
        "status": expense_data.get("workflow_status", "pending"),
        "company_id": company_id,
        "user_id": user_id,
    }

    if amount <= 0:
        logger.info("Detected expense without valid amount; skipping persistence")
        return {"status": "skipped", "reason": "amount_missing"}

    try:
        if config.USE_UNIFIED_DB:
            expense_id = record_internal_expense(payload, tenant_id=tenant_id)
        else:  # pragma: no cover - legacy path
            expense_id = record_internal_expense(
                description=payload["description"],
                amount=payload["amount"],
                currency=payload["currency"],
                expense_date=payload.get("date"),
                category=payload.get("category"),
                provider_name=payload.get("merchant_name"),
                workflow_status=payload.get("workflow_status"),
                invoice_status=payload.get("invoice_status"),
                metadata=payload.get("metadata"),
                company_id=company_id,
            )
    except Exception as exc:
        logger.exception(f"Failed to persist WhatsApp expense: {exc}")
        return {"status": "error", "error": str(exc)}

    logger.info(f"WhatsApp expense created with ID {expense_id}")
    return {"status": "created", "expense_id": expense_id}


def _resolve_tenant_context(phone_number: Optional[str]) -> Tuple[int, str, int]:
    normalized = _normalize_phone(phone_number)
    tenant_id = DEFAULT_TENANT_ID
    company_id = DEFAULT_COMPANY_ID
    user_id = DEFAULT_USER_ID

    if config.USE_UNIFIED_DB and get_unified_adapter and normalized:
        try:
            adapter = get_unified_adapter()
            with adapter.get_connection() as conn:  # type: ignore[attr-defined]
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, tenant_id, COALESCE(company_id, 'default') as company_id,
                           COALESCE(updated_at, '1970-01-01T00:00:00') as last_update
                    FROM users
                    WHERE REPLACE(REPLACE(REPLACE(COALESCE(phone, ''), '+', ''), '-', ''), ' ', '') LIKE ?
                    ORDER BY last_update DESC, id DESC
                    LIMIT 1
                    """,
                    (f"%{normalized[-10:]}%",),
                )
                row = cursor.fetchone()
                if row:
                    user_id = int(row[0])
                    tenant_id = int(row[1] or tenant_id)
                    company_id = row[2] or company_id
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(f"Unable to map phone {phone_number} to tenant: {exc}")

    return tenant_id, company_id, user_id


def _normalize_phone(phone_number: Optional[str]) -> str:
    if not phone_number:
        return ""
    digits = re.sub(r"\D", "", phone_number)
    return digits


def _get_voice_handler():
    global _voice_handler
    if _voice_handler is None and get_voice_handler:
        try:
            _voice_handler = get_voice_handler()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(f"Unable to initialize voice handler: {exc}")
            _voice_handler = None
    return _voice_handler


def _get_ocr_service() -> Optional[Any]:
    global _ocr_service
    if _ocr_service is None and OCRServiceClass is not None:
        try:
            _ocr_service = OCRServiceClass()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(f"Unable to initialize OCR service: {exc}")
            _ocr_service = None
    return _ocr_service


def _extension_from_mime(mime_type: Optional[str]) -> Optional[str]:
    if not mime_type:
        return None
    mapping = {
        "audio/ogg": ".ogg",
        "audio/mpeg": ".mp3",
        "audio/mp4": ".m4a",
        "audio/wav": ".wav",
    }
    return mapping.get(mime_type.lower())
