"""Company context analysis endpoints."""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, ValidationError, field_validator, ValidationInfo
from starlette.datastructures import UploadFile

from config.config import config
from core.unified_auth import User, get_current_active_user
from core.ai import (
    analyze_and_store_context,
    generate_context_questions,
    get_company_id_for_tenant,
    get_latest_context_for_company,
)
from core.voice_handler import transcribe_audio

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/companies", tags=["Company Context"])

_ALLOWED_SOURCES = {"text", "voice", "mixed", "onboarding"}
_ALLOWED_INPUT_TYPES: Tuple[str, ...] = ("text", "audio")


def _get_connection() -> sqlite3.Connection:
    db_path = Path(config.UNIFIED_DB_PATH)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _get_company_tenant(company_id: int) -> Optional[int]:
    with _get_connection() as conn:
        cursor = conn.execute("SELECT tenant_id FROM companies WHERE id = ?", (company_id,))
        row = cursor.fetchone()
    return int(row["tenant_id"]) if row else None


def _clean_context_text(raw_text: str) -> str:
    """Normalize context input by trimming whitespace and removing filler words."""
    if not raw_text:
        return ""

    cleaned = " ".join(raw_text.replace("\r", " ").replace("\n", " ").split())
    fillers = {"este", "estee", "esteee", "pues", "o sea", "eh", "mmm"}
    tokens = cleaned.split(" ")
    filtered_tokens: List[str] = []
    for token in tokens:
        normalized = token.lower()
        if normalized in fillers:
            continue
        filtered_tokens.append(token)
    return " ".join(filtered_tokens).strip()


def _ensure_str_list(value: Any) -> List[str]:
    """Coerce a value into a list of human readable strings."""
    if not value:
        return []

    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []

    result: List[str] = []
    iterable = value if isinstance(value, (list, tuple, set)) else [value]
    for item in iterable:
        candidate: Optional[str] = None
        if isinstance(item, str):
            candidate = item
        elif isinstance(item, dict):
            for key in ("name", "nombre", "label", "description", "tipo"):
                if key in item and item[key]:
                    candidate = str(item[key])
                    break
        else:
            candidate = str(item)

        if candidate:
            candidate = candidate.strip()
            if candidate and candidate not in result:
                result.append(candidate)

    return result


def _update_company_context(
    company_id: int,
    profile: Dict[str, Any],
    summary: Optional[str],
    raw_text: Optional[str],
    topics: List[str],
    user_id: Optional[int],
) -> Dict[str, Any]:
    """Persist extracted profile in companies table and audit trail."""
    updates: Dict[str, Any] = {}
    giro = profile.get("industry")
    if giro:
        updates["giro"] = str(giro).strip()

    business_model = profile.get("business_model")
    if business_model:
        updates["modelo_negocio"] = str(business_model).strip()

    clients = _ensure_str_list(profile.get("clients"))
    if clients:
        updates["clientes_clave"] = json.dumps(clients, ensure_ascii=False)

    suppliers = _ensure_str_list(profile.get("suppliers"))
    if suppliers:
        updates["proveedores_clave"] = json.dumps(suppliers, ensure_ascii=False)

    channels = _ensure_str_list(profile.get("channels"))
    if channels:
        updates["canales_venta"] = json.dumps(channels, ensure_ascii=False)

    frequency = profile.get("operation_frequency")
    if frequency:
        updates["frecuencia_operacion"] = str(frequency).strip()

    description = raw_text or summary
    if description:
        updates["descripcion_negocio"] = description[:2048]

    if profile:
        updates["context_profile"] = json.dumps(profile, ensure_ascii=False)

    updates_present = list(updates.keys())

    with _get_connection() as conn:
        cursor = conn.cursor()
        set_clauses = []
        params: List[Any] = []

        for column, value in updates.items():
            set_clauses.append(f"{column} = ?")
            params.append(value)

        set_clauses.append("context_last_updated = CURRENT_TIMESTAMP")
        set_clauses.append("updated_at = CURRENT_TIMESTAMP")
        params.append(company_id)

        cursor.execute(
            f"UPDATE companies SET {', '.join(set_clauses)} WHERE id = ?",
            params,
        )

        audit_payload = {
            "fields_updated": updates_present,
            "summary": summary,
            "raw_text": raw_text,
            "topics": topics,
        }
        cursor.execute(
            """
            INSERT INTO audit_trail (entidad, entidad_id, accion, usuario_id, cambios)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "company",
                company_id,
                "context_profile_update",
                user_id,
                json.dumps(audit_payload, ensure_ascii=False),
            ),
        )
        conn.commit()

    return {
        "giro": updates.get("giro"),
        "modelo_negocio": updates.get("modelo_negocio"),
        "clientes_clave": clients,
        "proveedores_clave": suppliers,
        "canales_venta": channels,
        "frecuencia_operacion": updates.get("frecuencia_operacion"),
        "descripcion_negocio": description,
    }


class ContextualProfilePayload(BaseModel):
    company_id: Optional[int] = Field(None, gt=0, description="Target company identifier")
    input_type: Literal[_ALLOWED_INPUT_TYPES] = Field("text", description="Input modality")
    content: Optional[str] = Field(None, description="Raw content when input_type is text")

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: Optional[str], info: ValidationInfo) -> Optional[str]:
        input_type = None
        if info.data:
            input_type = info.data.get("input_type")
        if input_type == "text":
            if not value or not value.strip():
                raise ValueError("content is required for text input")
        return value


class ContextualProfileResponse(BaseModel):
    company_id: int
    giro: Optional[str]
    modelo_negocio: Optional[str]
    clientes_clave: List[str] = Field(default_factory=list)
    proveedores_clave: List[str] = Field(default_factory=list)
    canales_venta: List[str] = Field(default_factory=list)
    frecuencia_operacion: Optional[str]
    descripcion_negocio: Optional[str]
    summary: Optional[str]
    topics: List[str] = Field(default_factory=list)
    embedding_vector: List[float] = Field(default_factory=list)
    context_record_id: Optional[int]
    last_refresh: Optional[str]
    model_name: Optional[str]
    confidence_score: Optional[float]
    source: str
    transcribed_text: Optional[str] = None


class ContextAnalyzeRequest(BaseModel):
    company_id: int = Field(..., gt=0, description="Target company identifier")
    text: str = Field(..., min_length=10, description="Raw contextual information")
    source: str = Field("text", description="Origin of the context data")

    @field_validator("source")
    @classmethod
    def validate_source(cls, value: str) -> str:
        normalized = value.lower().strip()
        if normalized not in _ALLOWED_SOURCES:
            raise ValueError(f"source must be one of: {', '.join(sorted(_ALLOWED_SOURCES))}")
        return normalized

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("text cannot be empty")
        return value


class ContextAnalyzeResponse(BaseModel):
    status: str = Field("success")
    analysis: Dict[str, Any]
    model_used: str


class ContextQuestionsRequest(BaseModel):
    company_id: Optional[int] = Field(None, gt=0, description="Company reference for permissions")
    context: str = Field(..., min_length=10, description="Initial description provided by the user")
    count: int = Field(5, ge=1, le=10, description="Number of questions to generate")

    @field_validator("context")
    @classmethod
    def validate_context(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("context cannot be empty")
        return value


class ContextQuestionsResponse(BaseModel):
    questions: List[Dict[str, str]]


class CompanyInfo(BaseModel):
    company_id: int
    tenant_id: int
    company_name: Optional[str] = None
    legal_name: Optional[str] = None
    short_name: Optional[str] = None


class ContextStatusResponse(BaseModel):
    summary: Optional[str] = None
    topics: List[str] = Field(default_factory=list)
    last_context_update: Optional[str] = None
    company: Optional[CompanyInfo] = None


@router.get("/context/status", response_model=ContextStatusResponse)
def get_company_context_status(
    current_user: User = Depends(get_current_active_user),
) -> ContextStatusResponse:
    """Return the latest stored context summary for the current user's primary company."""
    company_id = get_company_id_for_tenant(getattr(current_user, "tenant_id", None))
    if company_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    company_info: Optional[CompanyInfo] = None
    try:
        with _get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, tenant_id, company_name, legal_name, short_name
                  FROM companies
                 WHERE id = ?
                """,
                (company_id,),
            )
            row = cursor.fetchone()
            if row:
                company_info = CompanyInfo(
                    company_id=int(row["id"]),
                    tenant_id=int(row["tenant_id"]),
                    company_name=row["company_name"],
                    legal_name=row["legal_name"],
                    short_name=row["short_name"],
                )
    except Exception as exc:  # pragma: no cover - defensive path
        logger.warning("Unable to load company info for context status: %s", exc)

    latest = get_latest_context_for_company(company_id)
    if not latest:
        return ContextStatusResponse(company=company_info)

    topics: List[str] = []
    raw_topics = latest.get("topics")
    if isinstance(raw_topics, list):
        topics = [str(topic) for topic in raw_topics]

    return ContextStatusResponse(
        summary=latest.get("summary"),
        topics=topics,
        last_context_update=latest.get("created_at"),
        company=company_info,
    )


@router.post("/contextual_profile", response_model=ContextualProfileResponse)
async def create_company_contextual_profile(
    request: Request,
    current_user: User = Depends(get_current_active_user),
) -> ContextualProfileResponse:
    """Create or update the contextual profile for a company using text or audio input."""
    content_type = (request.headers.get("content-type") or "").lower()
    payload: ContextualProfilePayload
    upload_file: Optional[UploadFile] = None

    try:
        if "application/json" in content_type:
            body = await request.json()
            payload = ContextualProfilePayload(**body)
        elif "multipart/form-data" in content_type:
            form = await request.form()
            raw_company_id = form.get("company_id")
            raw_input_type = (form.get("input_type") or "text").lower()
            content = form.get("content")
            upload_file = form.get("file")
            try:
                company_id = int(raw_company_id)
            except (TypeError, ValueError):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="company_id must be a valid integer",
                )
            payload = ContextualProfilePayload(
                company_id=company_id,
                input_type=raw_input_type,  # type: ignore[arg-type]
                content=content,
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Unsupported content type. Use JSON or multipart/form-data.",
            )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=json.loads(exc.json()),
        ) from exc

    company_id = payload.company_id
    if company_id is None:
        company_id = get_company_id_for_tenant(getattr(current_user, "tenant_id", None))
        if company_id is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No primary company found for current tenant",
            )

    company_tenant = _get_company_tenant(company_id)
    if company_tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    if (
        not getattr(current_user, "is_superuser", False)
        and company_tenant != getattr(current_user, "tenant_id", None)
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to company")

    source_label = "voice" if payload.input_type == "audio" else "text"
    working_text: Optional[str] = payload.content
    transcribed_text: Optional[str] = None

    if payload.input_type == "audio":
        if upload_file is None or not isinstance(upload_file, UploadFile):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Audio file is required when input_type is audio",
            )

        try:
            upload_file.file.seek(0)
            transcription = transcribe_audio(upload_file.file)
        finally:
            await upload_file.close()

        if not transcription.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Audio transcription failed: {transcription.get('error', 'unknown error')}",
            )

        transcribed_text = (transcription.get("transcript") or "").strip()
        working_text = transcribed_text

    cleaned_text = _clean_context_text(working_text or "")
    if len(cleaned_text) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Context text is too short to analyze",
        )

    try:
        stored = analyze_and_store_context(
            company_id=company_id,
            context_text=cleaned_text,
            source=source_label,
            created_by=getattr(current_user, "id", None),
            preference=None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - resilience path
        logger.exception("Context analysis failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Context analysis failed",
        ) from exc

    business_profile = stored.get("business_profile") or {}
    topics = [str(topic).strip() for topic in stored.get("topics", []) if str(topic).strip()]
    summary = stored.get("summary")

    company_updates = _update_company_context(
        company_id=company_id,
        profile=business_profile,
        summary=summary,
        raw_text=cleaned_text,
        topics=topics,
        user_id=getattr(current_user, "id", None),
    )

    raw_embedding = stored.get("embedding_vector") or []
    if not isinstance(raw_embedding, list):
        raw_embedding = []
    embedding_vector: List[float] = []
    for item in raw_embedding:
        try:
            embedding_vector.append(float(item))
        except (TypeError, ValueError):
            continue

    response = ContextualProfileResponse(
        company_id=company_id,
        giro=company_updates.get("giro"),
        modelo_negocio=company_updates.get("modelo_negocio"),
        clientes_clave=company_updates.get("clientes_clave", []),
        proveedores_clave=company_updates.get("proveedores_clave", []),
        canales_venta=company_updates.get("canales_venta", []),
        frecuencia_operacion=company_updates.get("frecuencia_operacion"),
        descripcion_negocio=company_updates.get("descripcion_negocio"),
        summary=summary,
        topics=topics,
        embedding_vector=embedding_vector,
        context_record_id=stored.get("id"),
        last_refresh=stored.get("last_refresh") or stored.get("created_at"),
        model_name=stored.get("model_name"),
        confidence_score=float(stored.get("confidence_score") or 0.0),
        source=source_label,
        transcribed_text=transcribed_text,
    )
    return response


@router.post("/context/questions", response_model=ContextQuestionsResponse)
async def generate_company_context_questions(
    payload: ContextQuestionsRequest,
    current_user: User = Depends(get_current_active_user),
) -> ContextQuestionsResponse:
    """Generate conversational onboarding questions tailored to the company context."""
    company_id = payload.company_id
    if company_id is None:
        company_id = get_company_id_for_tenant(getattr(current_user, "tenant_id", None))
        if company_id is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    company_tenant = _get_company_tenant(company_id)
    if company_tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    if (
        not getattr(current_user, "is_superuser", False)
        and company_tenant != getattr(current_user, "tenant_id", None)
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to company")

    try:
        questions = generate_context_questions(
            payload.context,
            lang="es",
            count=payload.count,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Question generation failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Question generation failed") from exc

    return ContextQuestionsResponse(questions=questions)


@router.post("/context/analyze", response_model=ContextAnalyzeResponse)
async def analyze_company_context(
    payload: ContextAnalyzeRequest,
    current_user: User = Depends(get_current_active_user),
) -> ContextAnalyzeResponse:
    """Analyze company context using Claude and persist the results."""
    company_tenant = _get_company_tenant(payload.company_id)
    if company_tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    if (
        not getattr(current_user, "is_superuser", False)
        and company_tenant != getattr(current_user, "tenant_id", None)
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to company")

    try:
        logger.info(
            "Starting context analysis for company=%s by user=%s (source=%s)",
            payload.company_id,
            getattr(current_user, "id", None),
            payload.source,
        )
        stored = analyze_and_store_context(
            company_id=payload.company_id,
            context_text=payload.text,
            source=payload.source,
            created_by=getattr(current_user, "id", None),
            preference="claude",
        )
        logger.info(
            "Context analysis stored for company=%s (record_id=%s, model=%s)",
            payload.company_id,
            stored.get("id"),
            stored.get("model_name"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - unexpected runtime
        logger.exception("Context analysis failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Context analysis failed") from exc

    model_used = stored.get("model_name") or "claude-3-5-haiku"
    analysis_payload: Dict[str, Any] = {
        "summary": stored.get("summary"),
        "topics": stored.get("topics", []),
        "confidence_score": stored.get("confidence_score"),
        "language_detected": stored.get("language_detected"),
        "business_profile": stored.get("business_profile"),
        "embedding_vector": stored.get("embedding_vector"),
        "context_version": stored.get("context_version"),
        "created_at": stored.get("created_at"),
        "record_id": stored.get("id"),
    }

    return ContextAnalyzeResponse(status="success", analysis=analysis_payload, model_used=model_used)
