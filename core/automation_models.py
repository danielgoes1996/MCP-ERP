"""
Pydantic models for Automation Engine v2 API.
These models are for the new automation functionality.
"""

from datetime import datetime
from typing import Dict, Any, List, Optional, Literal
from pydantic import BaseModel, Field, validator

class AutomationJobState(str):
    """Valid automation job states."""
    PENDIENTE = "pendiente"
    EN_PROGRESO = "en_progreso"
    COMPLETADO = "completado"
    FALLIDO = "fallido"
    CANCELADO = "cancelado"
    PAUSADO = "pausado"

class AutomationJobResponse(BaseModel):
    """Response model for automation jobs."""

    # Core fields
    id: int
    ticket_id: int
    merchant_id: Optional[int] = None
    user_id: Optional[int] = None

    # State management
    estado: str = Field(..., description="Current job state")
    automation_type: str = Field(..., description="Type of automation")

    # Priority and retry logic
    priority: int = Field(..., ge=1, le=10, description="Job priority (1=urgent, 10=low)")
    retry_count: int = Field(..., ge=0, description="Number of retries attempted")
    max_retries: int = Field(..., ge=0, description="Maximum retries allowed")

    # Configuration and results
    config: Optional[Dict[str, Any]] = Field(None, description="Job configuration")
    result: Optional[Dict[str, Any]] = Field(None, description="Job result data")
    error_details: Optional[Dict[str, Any]] = Field(None, description="Error details if failed")

    # Progress tracking
    current_step: Optional[str] = Field(None, description="Current execution step")
    progress_percentage: int = Field(..., ge=0, le=100, description="Progress percentage")

    # Timing
    scheduled_at: Optional[datetime] = Field(None, description="When job was scheduled")
    started_at: Optional[datetime] = Field(None, description="When job started")
    completed_at: Optional[datetime] = Field(None, description="When job completed")
    estimated_completion: Optional[datetime] = Field(None, description="Estimated completion time")

    # Traceability
    session_id: str = Field(..., description="Session ID for grouping logs/screenshots")
    company_id: str = Field(..., description="Company ID for multi-tenancy")

    # Automation metadata
    selenium_session_id: Optional[str] = Field(None, description="Selenium session ID")
    captcha_attempts: int = Field(0, ge=0, description="Number of captcha attempts")
    ocr_confidence: Optional[float] = Field(None, ge=0, le=1, description="OCR confidence score")

    # Timestamps
    created_at: datetime
    updated_at: datetime

    # HATEOAS links
    links: Optional[Dict[str, str]] = Field(default_factory=dict, description="Related resource links")

    @validator('estado')
    def validate_estado(cls, v):
        valid_states = ['pendiente', 'en_progreso', 'completado', 'fallido', 'cancelado', 'pausado']
        if v not in valid_states:
            raise ValueError(f'estado must be one of: {valid_states}')
        return v

    @validator('automation_type')
    def validate_automation_type(cls, v):
        valid_types = ['selenium', 'api', 'manual', 'hybrid']
        if v not in valid_types:
            raise ValueError(f'automation_type must be one of: {valid_types}')
        return v

class AutomationLogEntry(BaseModel):
    """Response model for automation log entries."""

    id: int
    job_id: int
    session_id: str

    # Log metadata
    level: Literal['debug', 'info', 'warning', 'error', 'critical']
    category: Literal['navigation', 'ocr', 'captcha', 'form_fill', 'download', 'validation']
    message: str

    # Technical context
    url: Optional[str] = None
    element_selector: Optional[str] = None
    screenshot_id: Optional[int] = None
    execution_time_ms: Optional[int] = Field(None, ge=0)

    # Structured data
    data: Optional[Dict[str, Any]] = None

    # Technical metadata
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None

    timestamp: datetime
    company_id: str

class AutomationScreenshot(BaseModel):
    """Response model for automation screenshots."""

    id: int
    job_id: int
    session_id: str

    # Screenshot metadata
    step_name: str
    screenshot_type: Literal['step', 'error', 'success', 'captcha', 'manual']
    file_path: str
    file_size: Optional[int] = Field(None, ge=0)

    # Navigation context
    url: Optional[str] = None
    window_title: Optional[str] = None
    viewport_size: Optional[str] = None
    page_load_time_ms: Optional[int] = Field(None, ge=0)

    # Content analysis
    has_captcha: bool = False
    captcha_type: Optional[str] = None
    detected_elements: Optional[Dict[str, Any]] = None
    ocr_text: Optional[str] = None

    # Manual annotations
    manual_annotations: Optional[Dict[str, Any]] = None
    is_sensitive: bool = False

    created_at: datetime
    company_id: str

class AutomationConfigEntry(BaseModel):
    """Response model for automation configuration."""

    id: int
    key: str
    value: str
    value_type: Literal['string', 'boolean', 'integer', 'json']

    # Scope management
    scope: Literal['global', 'company', 'merchant', 'user']
    scope_id: Optional[str] = None

    # Metadata
    description: Optional[str] = None
    category: Optional[str] = None
    is_active: bool = True
    is_readonly: bool = False

    # Change tracking
    previous_value: Optional[str] = None
    updated_at: datetime
    updated_by: Optional[str] = None
    change_reason: Optional[str] = None

class AutomationJobList(BaseModel):
    """Response model for paginated job lists."""

    jobs: List[AutomationJobResponse]
    total: int
    page: int = Field(..., ge=1)
    per_page: int = Field(..., ge=1, le=100)
    total_pages: int
    has_next: bool
    has_prev: bool

class AutomationHealthResponse(BaseModel):
    """Response model for automation health check."""

    status: Literal['healthy', 'degraded', 'unhealthy']
    timestamp: datetime

    # Component health
    database: Dict[str, Any]
    selenium_grid: Dict[str, Any]
    captcha_service: Dict[str, Any]
    ocr_backends: Dict[str, Any]

    # Metrics
    active_jobs: int
    queue_size: int
    error_rate: float

    # Feature flags
    automation_engine_enabled: bool

class AutomationMetricsResponse(BaseModel):
    """Response model for automation metrics."""

    timeframe: str
    timestamp: datetime

    # Job metrics
    jobs_completed: int
    jobs_failed: int
    jobs_cancelled: int
    avg_processing_time_seconds: float

    # Success rates
    overall_success_rate: float
    success_rate_by_merchant: Dict[str, float]

    # OCR metrics
    avg_ocr_confidence: float
    ocr_fallback_rate: float

    # Captcha metrics
    captcha_solve_rate: float
    avg_captcha_solve_time_seconds: float

    # System metrics
    avg_queue_wait_time_seconds: float
    peak_concurrent_jobs: int