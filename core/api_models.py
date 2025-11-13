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
    ticket_id: Optional[int] = None
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
    ticket_id: Optional[int] = Field(None, description="ID de ticket existente vinculado al gasto")
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

    @validator('ticket_id')
    def validate_ticket_id(cls, value: Optional[int]) -> Optional[int]:
        """Valida que el ticket_id (si existe) sea un entero positivo."""
        if value is None:
            return None
        if value <= 0:
            raise ValueError('ticket_id debe ser un entero positivo')
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


# ============================================================================
# MCP Protocol Models
# ============================================================================

class MCPRequest(BaseModel):
    """MCP protocol request model."""
    method: str = Field(..., description="MCP method name")
    params: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Method parameters")


class MCPResponse(BaseModel):
    """MCP protocol response model."""
    success: bool = Field(..., description="Whether the request was successful")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")
    error: Optional[str] = Field(None, description="Error message if failed")


# ============================================================================
# Non-Reconciliation Models
# ============================================================================

class NonReconciliationRequest(BaseModel):
    """Request to mark expense as non-reconcilable."""
    expense_id: int = Field(..., description="ID of the expense")
    reason: str = Field(..., description="Reason for non-reconciliation")
    notes: Optional[str] = Field(None, description="Additional notes")


class NonReconciliationResponse(BaseModel):
    """Response for non-reconciliation action."""
    success: bool
    expense_id: int
    message: str


# ============================================================================
# Bulk Invoice Matching Models
# ============================================================================

class BulkInvoiceMatchRequest(BaseModel):
    """Request for bulk invoice matching."""
    company_id: str = Field(..., description="Company ID for batch processing")
    invoices: List[InvoiceMatchInput] = Field(..., description="List of invoices to process")
    auto_link_threshold: float = Field(0.8, ge=0.0, le=1.0, description="Confidence threshold for automatic linking")
    auto_mark_invoiced: bool = Field(False, description="Automatically mark expenses as invoiced when matched")
    create_placeholder_on_no_match: bool = Field(False, description="Create expense placeholder when invoice has no match")
    max_concurrent_items: Optional[int] = Field(None, description="Maximum concurrent items to process")
    batch_metadata: Optional[Dict[str, Any]] = Field(None, description="Additional batch metadata")


class BulkInvoiceMatchResponse(BaseModel):
    """Response for bulk invoice matching."""
    company_id: str
    batch_id: str
    processed: int
    linked: int
    no_matches: int
    errors: int
    results: List[InvoiceMatchResult] = Field(default_factory=list)
    processing_time_ms: int = 0
    batch_metadata: Optional[Dict[str, Any]] = None
    status: str
    started_at: str


# ============================================================================
# Expense Completion Models
# ============================================================================

class ExpenseCompletionSuggestionRequest(BaseModel):
    """Request for expense completion suggestions."""
    partial_expense: Dict[str, Any] = Field(..., description="Partially filled expense data")
    user_id: Optional[int] = Field(None, description="User ID for personalized suggestions")


class ExpenseCompletionSuggestionResponse(BaseModel):
    """Response with expense completion suggestions."""
    suggestions: Dict[str, Any] = Field(..., description="Suggested values for missing fields")
    confidence: float = Field(..., description="Overall confidence in suggestions")


# ============================================================================
# Conversational Assistant Models
# ============================================================================

class ConversationSessionRequest(BaseModel):
    """Request to create or continue a conversation session."""
    session_id: Optional[str] = Field(None, description="Existing session ID or None for new")
    message: str = Field(..., description="User message")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")


class ConversationSessionResponse(BaseModel):
    """Response from conversational assistant."""
    session_id: str
    response: str
    actions: Optional[List[Dict[str, Any]]] = Field(None, description="Suggested actions")


# ============================================================================
# Hybrid Processor Models
# ============================================================================

class HybridProcessorSessionCreateRequest(BaseModel):
    """Request to create hybrid processor session."""
    source_type: str = Field(..., description="Type of source: voice, text, image")
    data: Any = Field(..., description="Input data")
    company_id: str = Field("default", description="Company ID")


class HybridProcessorSessionResponse(BaseModel):
    """Response from hybrid processor."""
    session_id: str
    status: str
    extracted_data: Optional[Dict[str, Any]] = None


# ============================================================================
# Universal Invoice Engine Models
# ============================================================================

class UniversalInvoiceSessionCreateRequest(BaseModel):
    """Request to create universal invoice processing session."""
    merchant_info: Dict[str, Any] = Field(..., description="Merchant information")
    invoice_requirements: Dict[str, Any] = Field(..., description="Invoice requirements")
    automation_method: str = Field("rpa", description="Automation method: rpa, api, manual")


class UniversalInvoiceSessionResponse(BaseModel):
    """Response from universal invoice engine."""
    session_id: str
    status: str
    invoice_data: Optional[Dict[str, Any]] = None
    automation_logs: Optional[List[str]] = None


# ============================================================================
# Additional Missing Models
# ============================================================================

class NonReconciliationUpdate(BaseModel):
    """Update for non-reconciliation status."""
    status: str
    notes: Optional[str] = None


class BulkInvoiceProcessingStatus(BaseModel):
    """Status of bulk invoice processing."""
    batch_id: str
    status: str
    total_invoices: int
    processed_count: int
    linked_count: int
    no_matches_count: int
    errors_count: int
    success_rate: Optional[float] = None
    processing_time_ms: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress_percent: float
    estimated_completion_time: Optional[datetime] = None


class CompleteExpenseRequest(BaseModel):
    """Request to complete an expense."""
    expense_id: int
    completion_data: Dict[str, Any]


class CompletionInteractionRequest(BaseModel):
    """Request for completion interaction."""
    interaction_type: str
    data: Dict[str, Any]


class UserQueryRequest(BaseModel):
    """User query for conversational assistant."""
    query: str
    context: Optional[Dict[str, Any]] = None


class HybridProcessorProcessResponse(BaseModel):
    """Response from hybrid processor processing."""
    result: Dict[str, Any]
    status: str


class UniversalInvoiceProcessRequest(BaseModel):
    """Request to process invoice universally."""
    invoice_data: Optional[Dict[str, Any]] = None
    async_processing: bool = True
    processing_options: Optional[Dict[str, Any]] = None


class ExpenseInvoicePayload(BaseModel):
    """Payload for expense invoice association."""
    expense_id: int
    invoice_uuid: str
    invoice_data: Optional[Dict[str, Any]] = None


class QueryRequest(BaseModel):
    """Generic query request."""
    query: str
    filters: Optional[Dict[str, Any]] = None
    limit: int = 100


class QueryResponse(BaseModel):
    """Generic query response."""
    results: List[Dict[str, Any]]
    total: int
    has_more: bool = False


class ExpenseTagCreate(BaseModel):
    """Create expense tag."""
    name: str
    color: Optional[str] = None
    description: Optional[str] = None


class ExpenseTagUpdate(BaseModel):
    """Update expense tag."""
    name: Optional[str] = None
    color: Optional[str] = None
    description: Optional[str] = None


class ExpenseTagResponse(BaseModel):
    """Expense tag response."""
    id: int
    name: str
    color: Optional[str] = None
    description: Optional[str] = None


class ExpenseTagAssignment(BaseModel):
    """Assign tag to expense."""
    expense_id: int
    tag_ids: List[int]


class InvoiceCreate(BaseModel):
    """Create invoice."""
    uuid: str
    total: float
    invoice_data: Dict[str, Any]


class InvoiceUpdate(BaseModel):
    """Update invoice."""
    status: Optional[str] = None
    invoice_data: Optional[Dict[str, Any]] = None


class InvoiceResponse(BaseModel):
    """Invoice response."""
    id: int
    uuid: str
    total: float
    status: str
    created_at: str


# ============================================================================
# Final Missing Models
# ============================================================================

class NonReconciliationEscalationRequest(BaseModel):
    """Escalation request for non-reconciliation."""
    expense_id: int
    escalation_reason: str


class BulkInvoiceDetailedResults(BaseModel):
    """Detailed results from bulk invoice processing."""
    batch_id: str
    company_id: str
    status: str
    summary: Dict[str, Any]
    items: List["BulkInvoiceItemResult"]
    performance_metrics: Optional[Dict[str, Any]] = None
    processing_phases: Optional[List[Dict[str, Any]]] = None


class UserPreferencesRequest(BaseModel):
    """User preferences request."""
    preferences: Dict[str, Any]


class UserQueryResponse(BaseModel):
    """Response to user query."""
    answer: str
    confidence: float
    sources: Optional[List[str]] = None


class HybridProcessorStatusResponse(BaseModel):
    """Status response from hybrid processor."""
    status: str
    progress: float
    message: Optional[str] = None


class UniversalInvoiceProcessResponse(BaseModel):
    """Response from universal invoice processing."""
    success: bool
    invoice_data: Optional[Dict[str, Any]] = None
    errors: Optional[List[str]] = None


class BankSuggestionResponse(BaseModel):
    """Bank reconciliation suggestion response."""
    suggestions: List[Dict[str, Any]]
    confidence: float


class BankSuggestionExpense(BaseModel):
    """Expense for bank reconciliation suggestions."""
    expense_id: int
    description: str
    amount: float
    date: str


class NonReconciliationBulkAction(BaseModel):
    """Bulk action for non-reconciliation."""
    expense_ids: List[int]
    action: str
    reason: Optional[str] = None


class BulkInvoiceAnalyticsRequest(BaseModel):
    """Request for bulk invoice analytics."""
    company_id: str
    period_start: datetime
    period_end: datetime
    group_by: List[str] = Field(default_factory=list, description="Grouping fields (e.g., 'day', 'hour')")
    include_error_analysis: bool = False


class UserPreferencesResponse(BaseModel):
    """Response with user preferences."""
    preferences: Dict[str, Any]
    user_id: int


class ConversationHistoryResponse(BaseModel):
    """Response with conversation history."""
    history: List[Dict[str, Any]]
    total: int


class HybridProcessorMetricsResponse(BaseModel):
    """Metrics response from hybrid processor."""
    metrics: Dict[str, Any]
    timestamp: str


class UniversalInvoiceStatusResponse(BaseModel):
    """Status response for universal invoice."""
    status: str
    progress: float
    invoice_uuid: Optional[str] = None


# ============================================================================
# Analytics and Stats Models
# ============================================================================

class NonReconciliationStats(BaseModel):
    """Statistics for non-reconciliation."""
    total: int
    by_reason: Dict[str, int]


class BulkInvoiceAnalyticsResponse(BaseModel):
    """Analytics response for bulk invoice processing."""
    company_id: str
    period_start: datetime
    period_end: datetime
    total_batches: int
    total_invoices_processed: int
    successful_batches: int
    failed_batches: int
    avg_processing_time_ms: Optional[float] = None
    median_processing_time_ms: Optional[float] = None
    throughput_invoices_per_hour: Optional[float] = None
    avg_success_rate: Optional[float] = None
    auto_match_rate: Optional[float] = None
    error_rate: Optional[float] = None
    most_common_errors: Optional[Dict[str, int]] = None
    daily_stats: Optional[List[Dict[str, Any]]] = None


class CompletionAnalyticsResponse(BaseModel):
    """Analytics for expense completion."""
    completion_rate: float
    metrics: Dict[str, Any]


class ConversationalAnalyticsResponse(BaseModel):
    """Analytics for conversational assistant."""
    total_conversations: int
    metrics: Dict[str, Any]


class HybridProcessorResultsResponse(BaseModel):
    """Results from hybrid processor."""
    results: List[Dict[str, Any]]
    total: int


class UniversalInvoiceTemplateMatchResponse(BaseModel):
    """Template match response for universal invoice."""
    matched_template: Optional[str] = None
    confidence: float
    alternatives: List[str] = Field(default_factory=list)


# ============================================================================
# Bank Movement Models
# ============================================================================

class BankMovementCreate(BaseModel):
    """Create bank movement."""
    description: str = Field(..., description="Movement description")
    amount: float = Field(..., description="Movement amount")
    date: str = Field(..., description="Movement date")
    bank_account_id: Optional[int] = Field(None, description="Bank account ID")
    reference: Optional[str] = Field(None, description="Reference number")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class BankMovementUpdate(BaseModel):
    """Update bank movement."""
    description: Optional[str] = None
    matched: Optional[bool] = None
    expense_id: Optional[int] = None
    notes: Optional[str] = None


class BankMovementResponse(BaseModel):
    """Bank movement response."""
    movement_id: str
    description: str
    amount: float
    date: str
    matched: bool
    expense_id: Optional[int] = None


class BankReconciliationRequest(BaseModel):
    """Request to reconcile bank movement with expense."""
    movement_id: str = Field(..., description="Bank movement ID")
    expense_id: int = Field(..., description="Expense ID to match")
    confidence: Optional[float] = Field(None, description="Confidence score")
    notes: Optional[str] = Field(None, description="Reconciliation notes")


class BankReconciliationResponse(BaseModel):
    """Response from bank reconciliation."""
    success: bool
    movement_id: str
    expense_id: int
    message: str


# ============================================================================
# Remaining Missing Models
# ============================================================================

class EscalationRuleCreate(BaseModel):
    """Create escalation rule."""
    name: str = Field(..., description="Rule name")
    condition: Dict[str, Any] = Field(..., description="Escalation condition")
    action: str = Field(..., description="Action to take")
    priority: int = Field(1, description="Rule priority")


class BulkProcessingRule(BaseModel):
    """Rule for bulk processing."""
    rule_name: str = Field(..., description="Rule name")
    rule_code: str = Field(..., description="Rule code")
    rule_type: str = Field(..., description="Type of rule")
    conditions: Dict[str, Any] = Field(..., description="Rule conditions")
    actions: Dict[str, Any] = Field(..., description="Actions to execute")
    priority: int = Field(1, description="Rule priority")
    is_active: bool = Field(True, description="Whether rule is active")
    max_batch_size: Optional[int] = Field(None, description="Maximum batch size for rule")
    parallel_processing: bool = Field(True, description="Enable parallel processing")
    timeout_seconds: Optional[int] = Field(None, description="Timeout in seconds")


class FieldCompletionSuggestion(BaseModel):
    """Suggestion for completing a field."""
    field_name: str
    suggested_value: Any
    confidence: float
    reasoning: str


class LLMModelConfigRequest(BaseModel):
    """Request to configure LLM model."""
    model_name: str = Field(..., description="LLM model name")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Model parameters")
    temperature: float = Field(0.7, description="Temperature setting")


class HybridProcessorCancelResponse(BaseModel):
    """Response from canceling hybrid processor."""
    success: bool
    session_id: str
    message: str


class UniversalInvoiceValidationResponse(BaseModel):
    """Validation response for universal invoice."""
    is_valid: bool
    validation_errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class EnhancedOnboardingRequest(BaseModel):
    """Enhanced onboarding request with additional features."""
    method: str
    identifier: str
    full_name: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None
    company_info: Optional[Dict[str, Any]] = None


class EnhancedOnboardingResponse(BaseModel):
    """Enhanced onboarding response with additional features."""
    company_id: str
    user_id: int
    identifier: str
    display_name: Optional[str] = None
    already_exists: bool = False
    demo_snapshot: Optional[DemoSnapshot] = None
    demo_expenses: List[ExpenseResponse] = Field(default_factory=list)
    next_steps: List[str] = Field(default_factory=list)
    recommendations: Optional[List[str]] = Field(default_factory=list)
    setup_completed: bool = False


class EscalationRuleResponse(BaseModel):
    """Response for escalation rule."""
    id: int
    name: str
    condition: Dict[str, Any]
    action: str
    priority: int
    created_at: str


class BulkProcessingRuleResponse(BaseModel):
    """Response for bulk processing rule."""
    id: int
    company_id: str
    rule_name: str
    rule_code: str
    rule_type: str
    conditions: Dict[str, Any]
    actions: Dict[str, Any]
    priority: int
    is_active: bool
    max_batch_size: Optional[int] = None
    parallel_processing: bool
    timeout_seconds: Optional[int] = None
    created_by: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    usage_count: int = 0


class BulkCompletionRequest(BaseModel):
    """Request for bulk completion."""
    expense_ids: List[int] = Field(..., description="List of expense IDs to complete")
    completion_data: Optional[Dict[str, Any]] = Field(None, description="Common completion data")


class LLMModelConfigResponse(BaseModel):
    """Response for LLM model configuration."""
    model_name: str
    parameters: Dict[str, Any]
    status: str


class HybridProcessorListResponse(BaseModel):
    """List response for hybrid processor sessions."""
    sessions: List[Dict[str, Any]]
    total: int


class UniversalInvoiceDataResponse(BaseModel):
    """Data response for universal invoice."""
    invoice_data: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None


class OnboardingStepRequest(BaseModel):
    """Request for onboarding step."""
    step_name: str = Field(..., description="Name of the onboarding step")
    data: Dict[str, Any] = Field(..., description="Step data")


class OnboardingStepResponse(BaseModel):
    """Response for onboarding step."""
    step_name: str
    status: str
    next_step: Optional[str] = None


class NonReconciliationNotificationRequest(BaseModel):
    """Request to send notification for non-reconciliation."""
    expense_id: int
    notification_type: str
    recipients: List[str]


class BulkInvoiceItemResult(BaseModel):
    """Result for a single bulk invoice item."""
    filename: str
    uuid: Optional[str] = None
    total_amount: float
    status: str
    processing_time_ms: int
    matched_expense_id: Optional[int] = None
    match_confidence: Optional[float] = None
    match_method: Optional[str] = None
    candidates_found: int = 0
    error_message: Optional[str] = None


class BulkCompletionResponse(BaseModel):
    """Response for bulk completion."""
    total: int
    completed: int
    failed: int
    results: List[Dict[str, Any]] = Field(default_factory=list)


class CacheStatsResponse(BaseModel):
    """Response with cache statistics."""
    hit_rate: float
    total_hits: int
    total_misses: int
    cache_size: int


class HybridProcessorCompanyMetricsResponse(BaseModel):
    """Company metrics for hybrid processor."""
    company_id: str
    metrics: Dict[str, Any]
    period: str


class UniversalInvoiceParsersResponse(BaseModel):
    """Response with available parsers for universal invoice."""
    parsers: List[str]
    default_parser: str


class UserOnboardingStatus(BaseModel):
    """Status of user onboarding."""
    user_id: int
    company_id: str
    current_step: str
    completed_steps: List[str] = Field(default_factory=list)
    progress_percent: float
    is_complete: bool


class NonReconciliationHistoryResponse(BaseModel):
    """Response with non-reconciliation history."""
    history: List[Dict[str, Any]]
    total: int


class CompletionRuleRequest(BaseModel):
    """Request to create completion rule."""
    rule_name: str = Field(..., description="Rule name")
    conditions: Dict[str, Any] = Field(..., description="Rule conditions")
    completions: Dict[str, Any] = Field(..., description="Field completions")


class QueryInteraction(BaseModel):
    """Interaction for query."""
    query: str
    response: str
    timestamp: str
    confidence: Optional[float] = None


class HybridProcessorHealthCheckResponse(BaseModel):
    """Health check response for hybrid processor."""
    status: str
    uptime: float
    active_sessions: int


class UniversalInvoiceFormatsResponse(BaseModel):
    """Response with supported formats for universal invoice."""
    formats: List[str]
    recommended_format: str


class DemoPreferences(BaseModel):
    """Preferences for demo data generation."""
    include_expenses: bool = True
    expense_count: int = Field(10, description="Number of demo expenses to create")
    categories: Optional[List[str]] = Field(None, description="Categories to include")
    date_range_days: int = Field(30, description="Date range for demo data in days")


class NonReconciliationAnalyticsRequest(BaseModel):
    """Request for non-reconciliation analytics."""
    start_date: str
    end_date: str
    group_by: Optional[str] = Field(None, description="Grouping field")


class CompletionRuleResponse(BaseModel):
    """Response for completion rule."""
    id: int
    rule_name: str
    conditions: Dict[str, Any]
    completions: Dict[str, Any]
    created_at: str


class UniversalInvoiceFormatCreateRequest(BaseModel):
    """Request to create universal invoice format."""
    format_name: str = Field(..., description="Format name")
    format_spec: Dict[str, Any] = Field(..., description="Format specification")
    description: Optional[str] = Field(None, description="Format description")


class DuplicateDetectionRequest(BaseModel):
    """Request for duplicate detection."""
    expense_data: Dict[str, Any] = Field(..., description="Expense data to check for duplicates")
    similarity_threshold: float = Field(0.85, description="Similarity threshold for duplicate detection")
    check_fields: Optional[List[str]] = Field(None, description="Fields to check for duplicates")


class DuplicateDetectionResponse(BaseModel):
    """Response for duplicate detection."""
    has_duplicates: bool
    total_found: int
    duplicates: List[Dict[str, Any]] = Field(default_factory=list)
    risk_level: str
    recommendation: str


class NonReconciliationAnalyticsResponse(BaseModel):
    """Response for non-reconciliation analytics."""
    analytics: Dict[str, Any]
    total: int
    period: str


class CompletionPatternResponse(BaseModel):
    """Response for completion patterns."""
    patterns: List[Dict[str, Any]]
    total: int


class UniversalInvoiceFormatResponse(BaseModel):
    """Response for universal invoice format."""
    id: int
    format_name: str
    format_spec: Dict[str, Any]
    description: Optional[str] = None
    created_at: str


class NonReconciliationReason(BaseModel):
    """Reason for non-reconciliation."""
    code: str
    description: str
    user_facing_message: str


class UniversalInvoiceCancelResponse(BaseModel):
    """Response for canceling universal invoice processing."""
    success: bool
    session_id: str
    message: str
    canceled_at: str


class DuplicateReviewRequest(BaseModel):
    """Request to review duplicate expenses."""
    expense_id: int = Field(..., description="Primary expense ID")
    duplicate_ids: List[int] = Field(..., description="List of duplicate expense IDs")
    action: str = Field(..., description="Action to take: merge, keep_both, delete_duplicates")
    notes: Optional[str] = Field(None, description="Review notes")


class DuplicateReviewResponse(BaseModel):
    """Response for duplicate review."""
    success: bool
    action_taken: str
    affected_expense_ids: List[int]
    message: str


class DuplicateStatsResponse(BaseModel):
    """Response with duplicate statistics."""
    total_duplicates: int
    duplicate_groups: int
    resolved: int
    pending: int
    stats_by_category: Dict[str, int] = Field(default_factory=dict)


class ReconciliationStatus(BaseModel):
    """Status of reconciliation."""
    status: str
    total_items: int
    reconciled: int
    pending: int
    failed: int
