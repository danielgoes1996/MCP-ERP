"""Core API models (minimal baseline)."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator


class ExpenseResponse(BaseModel):
    """Response model for expenses used by REST endpoints."""

    id: int
    descripcion: str
    monto_total: float
    fecha_gasto: Optional[str] = None
    categoria: Optional[str] = None
    proveedor: Optional[Dict[str, Any]] = None
    rfc: Optional[str] = None
    tax_info: Optional[Dict[str, Any]] = None
    asientos_contables: Optional[List[Dict[str, Any]]] = None
    workflow_status: str = "draft"
    estado_factura: str = "pendiente"
    estado_conciliacion: str = "pendiente"
    metodo_pago: Optional[str] = None
    payment_account_id: Optional[int] = None
    payment_account_nombre: Optional[str] = None
    payment_account_banco: Optional[str] = None
    payment_account_tipo: Optional[str] = None
    payment_account_subtipo: Optional[str] = None
    payment_account_numero_enmascarado: Optional[str] = None
    moneda: str = "MXN"
    tipo_cambio: float = 1.0
    subtotal: Optional[float] = None
    iva_16: Optional[float] = None
    iva_8: Optional[float] = None
    iva_0: Optional[float] = None
    ieps: Optional[float] = None
    isr_retenido: Optional[float] = None
    iva_retenido: Optional[float] = None
    deducible: bool = True
    deducible_status: str = "pendiente"
    deducible_percent: float = 100.0
    iva_acreditable: bool = True
    periodo: Optional[str] = None
    rfc_proveedor: Optional[str] = None
    cfdi_uuid: Optional[str] = None
    cfdi_status: Optional[str] = None
    cfdi_pdf_url: Optional[str] = None
    cfdi_xml_url: Optional[str] = None
    cfdi_fecha_timbrado: Optional[str] = None
    cfdi_folio_fiscal: Optional[str] = None
    ticket_image_url: Optional[str] = None
    ticket_folio: Optional[str] = None
    paid_by: str = "company_account"
    will_have_cfdi: bool = True
    movimientos_bancarios: Optional[List[Dict[str, Any]]] = None
    metadata: Optional[Dict[str, Any]] = None
    company_id: str = "default"
    is_advance: bool = False
    is_ppd: bool = False
    asset_class: Optional[str] = None
    payment_terms: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class InvoiceMatchCandidate(BaseModel):
    expense_id: str
    description: str
    amount: float
    provider: Optional[str] = None
    date: Optional[str] = None
    similarity_score: float
    match_reasons: List[str] = Field(default_factory=list)


class InvoiceMatchInput(BaseModel):
    filename: str
    uuid: Optional[str] = None
    total: float
    subtotal: Optional[float] = None
    iva_amount: Optional[float] = None
    currency: str = "MXN"
    issued_at: Optional[str] = None
    provider_name: Optional[str] = None
    provider_rfc: Optional[str] = None
    raw_xml: Optional[str] = None
    auto_mark_invoiced: bool = False


class InvoiceMatchResult(BaseModel):
    filename: str
    uuid: Optional[str] = None
    status: str
    message: str
    expense: Optional[Dict[str, Any]] = None
    candidates: List[InvoiceMatchCandidate] = Field(default_factory=list)
    confidence: Optional[float] = None


class InvoiceParseResponse(BaseModel):
    subtotal: float
    iva_amount: float
    total: float
    currency: str = "MXN"
    uuid: Optional[str] = None
    rfc_emisor: Optional[str] = None
    nombre_emisor: Optional[str] = None
    fecha_emision: Optional[str] = None
    file_name: Optional[str] = None
    taxes: List[Dict[str, Any]] = Field(default_factory=list)
    other_taxes: float = 0.0
    emitter: Optional[Dict[str, Any]] = None
    receiver: Optional[Dict[str, Any]] = None
    success: bool = True
    error_message: Optional[str] = None


class BankReconciliationFeedback(BaseModel):
    expense_id: str
    movement_id: str
    confidence: float
    decision: str
    company_id: str = "default"

    @validator('confidence')
    def validate_confidence(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError('Confidence must be between 0.0 and 1.0')
        return value


class CategoryPrediction(BaseModel):
    category: str
    confidence: float
    reasoning: str
    alternatives: List[Dict[str, Any]] = Field(default_factory=list)
    prediction_method: str = "hybrid"
    ml_model_version: Optional[str] = None


class CategoryPredictionRequest(BaseModel):
    description: str
    merchant_name: Optional[str] = None
    amount: Optional[float] = None
    user_id: Optional[int] = None
    prediction_method: str = "hybrid"
    include_alternatives: bool = True
    use_user_history: bool = True
    tenant_id: int = 1


class CategoryPredictionResponse(BaseModel):
    prediction: CategoryPrediction
    processing_time_ms: Optional[int] = None
    user_preferences_used: bool = False
    historical_matches: int = 0


class OnboardingRequest(BaseModel):
    method: str
    identifier: str
    full_name: Optional[str] = None

    @validator('identifier')
    def validate_identifier(cls, value: str, values):
        value = value.strip()
        method = values.get('method')
        if method == "email":
            if "@" not in value:
                raise ValueError('Invalid email format')
        elif method == "whatsapp":
            clean_phone = ''.join(ch for ch in value if ch.isdigit())
            if len(clean_phone) < 10:
                raise ValueError('Invalid WhatsApp number format')
        return value

    @validator('full_name')
    def validate_full_name(cls, value: Optional[str]):
        if value is None:
            return value
        value = value.strip()
        if value and len(value.split()) < 2:
            raise ValueError('Full name must include at least two words')
        return value.title() if value else value


class DemoSnapshot(BaseModel):
    total_expenses: int = 0
    total_amount: float = 0.0
    invoice_breakdown: Dict[str, int] = Field(default_factory=dict)
    categories: Dict[str, int] = Field(default_factory=dict)
    last_expense_date: Optional[str] = None


class OnboardingResponse(BaseModel):
    company_id: str
    user_id: int
    identifier: str
    display_name: Optional[str] = None
    already_exists: bool = False
    demo_snapshot: Optional[DemoSnapshot] = None
    demo_expenses: List[ExpenseResponse] = Field(default_factory=list)
    next_steps: List[str] = Field(default_factory=list)


class InvoiceActionRequest(BaseModel):
    uuid: Optional[str] = None
    status: Optional[str] = None
    actor: Optional[str] = None
    notes: Optional[str] = None


class ExpenseActionRequest(BaseModel):
    actor: Optional[str] = None
    notes: Optional[str] = None


class DuplicateCheckRequest(BaseModel):
    new_expense: Dict[str, Any]
    check_existing: bool = True


class DuplicateCheckResponse(BaseModel):
    has_duplicates: bool
    total_found: int
    risk_level: str
    recommendation: str
    duplicates: List[Dict[str, Any]] = Field(default_factory=list)


class WebhookPayload(BaseModel):
    event: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    data: Dict[str, Any]


class AutomationJobStatus(BaseModel):
    job_id: str
    status: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None

class ExpenseResponseMinimal(BaseModel):
    """Backward-compat Wrapper around ExpenseResponse."""

    id: int
    descripcion: str
    amount: float
    invoice_status: str
    bank_status: str
