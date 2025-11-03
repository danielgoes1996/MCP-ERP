"""Core API models (minimal baseline)."""

from datetime import datetime, timedelta
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


class ProveedorData(BaseModel):
    """Estructura para datos del proveedor."""
    nombre: str
    rfc: Optional[str] = None


class ExpenseCreate(BaseModel):
    """Request model for creating expenses via POST /expenses."""

    # Campos obligatorios
    descripcion: str = Field(..., min_length=1, description="Descripción del gasto")
    monto_total: float = Field(..., gt=0, description="Monto total del gasto")
    fecha_gasto: str = Field(..., description="Fecha del gasto en formato ISO (YYYY-MM-DD)")

    # Información del proveedor
    proveedor: Optional[ProveedorData] = Field(None, description="Datos del proveedor")
    rfc: Optional[str] = Field(None, description="RFC del proveedor (12-13 caracteres alfanuméricos)")

    # Categorización
    categoria: Optional[str] = Field(None, description="Categoría del gasto")

    # Información fiscal
    tax_info: Optional[Dict[str, Any]] = Field(None, description="Información fiscal (UUID, totales, etc)")

    # Información contable
    asientos_contables: Optional[List[Dict[str, Any]]] = Field(None, description="Asientos contables generados")

    # Estados del workflow
    workflow_status: str = Field("draft", description="Estado del workflow")
    estado_factura: str = Field("pendiente", description="Estado de facturación")
    estado_conciliacion: str = Field("pendiente", description="Estado de conciliación bancaria")

    # Información de pago
    forma_pago: Optional[str] = Field(None, description="Forma de pago (tarjeta, efectivo, transferencia)")
    paid_by: str = Field("company_account", description="Quién pagó el gasto")
    will_have_cfdi: bool = Field(True, description="Si se espera factura CFDI")
    payment_account_id: Optional[int] = Field(None, description="ID de cuenta de pago")

    # Información bancaria
    movimientos_bancarios: Optional[List[Dict[str, Any]]] = Field(None, description="Movimientos bancarios asociados")

    # Metadata adicional
    metadata: Optional[Dict[str, Any]] = Field(None, description="Metadata adicional")
    company_id: str = Field("default", description="ID de la empresa")

    # Validadores
    @validator('fecha_gasto')
    def validate_fecha_gasto(cls, value: str) -> str:
        """Valida que la fecha sea válida y no futura."""
        try:
            fecha = datetime.fromisoformat(value.replace('Z', '+00:00'))
            # Permitir fechas hasta 1 día en el futuro (por zonas horarias)
            if fecha > datetime.now() + timedelta(days=1):
                raise ValueError('La fecha del gasto no puede ser futura')
            return value
        except (ValueError, AttributeError) as e:
            raise ValueError(f'Formato de fecha inválido. Use formato ISO (YYYY-MM-DD): {e}')

    @validator('rfc')
    def validate_rfc(cls, value: Optional[str]) -> Optional[str]:
        """Valida formato básico de RFC mexicano."""
        if value is None:
            return value

        value = value.strip().upper()

        # RFC debe ser alfanumérico de 12 o 13 caracteres
        if not value.isalnum():
            raise ValueError('RFC debe contener solo letras y números')

        if len(value) not in [12, 13]:
            raise ValueError('RFC debe tener 12 (moral) o 13 (física) caracteres')

        return value

    @validator('monto_total')
    def validate_monto_total(cls, value: float) -> float:
        """Valida que el monto sea razonable."""
        if value <= 0:
            raise ValueError('El monto debe ser mayor a cero')

        # Límite máximo razonable: 10 millones de pesos
        if value > 10_000_000:
            raise ValueError('El monto excede el límite máximo permitido (10,000,000 MXN)')

        return value

    @validator('categoria')
    def validate_categoria(cls, value: Optional[str]) -> Optional[str]:
        """Normaliza la categoría."""
        if value:
            return value.strip().lower()
        return value

    class Config:
        schema_extra = {
            "example": {
                "descripcion": "Gasolina para vehículo de reparto",
                "monto_total": 850.50,
                "fecha_gasto": "2025-01-15",
                "proveedor": {
                    "nombre": "Gasolinera PEMEX",
                    "rfc": "PEM840212XY1"
                },
                "rfc": "PEM840212XY1",
                "categoria": "combustibles",
                "forma_pago": "tarjeta",
                "paid_by": "company_account",
                "will_have_cfdi": True,
                "workflow_status": "draft",
                "estado_factura": "pendiente",
                "estado_conciliacion": "pendiente",
                "company_id": "default"
            }
        }


class ExpenseCreateEnhanced(ExpenseCreate):
    """Extended expense creation with duplicate detection and ML features."""

    check_duplicates: bool = Field(True, description="Verificar duplicados antes de crear")
    ml_features: Optional[Dict[str, Any]] = Field(None, description="Features ML para detección")
    auto_action_on_duplicates: Optional[str] = Field(None, description="Acción automática si hay duplicados")


class ExpenseResponseEnhanced(ExpenseResponse):
    """Extended expense response with duplicate detection info."""

    duplicate_ids: Optional[List[int]] = Field(None, description="IDs de posibles duplicados")
    similarity_score: Optional[float] = Field(None, description="Score de similitud con duplicados")
    risk_level: Optional[str] = Field(None, description="Nivel de riesgo de duplicado")
