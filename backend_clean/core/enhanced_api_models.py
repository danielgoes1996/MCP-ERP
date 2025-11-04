"""
Enhanced API Models para integración robusta del motor de automatización.

Extend existing models with backward compatibility + new v2 endpoints.
"""

from typing import Dict, List, Any, Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

# ===================================================================
# ENHANCED ENUMS & STATUS
# ===================================================================

class AutomationStatus(str, Enum):
    """Estados mejorados de automatización"""
    PENDING = "pendiente"
    QUEUED = "en_cola"
    PROCESSING = "procesando"
    OCR_COMPLETED = "ocr_completado"
    MERCHANT_IDENTIFIED = "merchant_identificado"
    NAVIGATING = "navegando"
    CAPTCHA_SOLVING = "resolviendo_captcha"
    FORM_FILLING = "llenando_formulario"
    DOWNLOAD_PENDING = "descarga_pendiente"
    COMPLETED = "completado"
    FAILED = "fallido"
    REQUIRES_INTERVENTION = "requiere_intervencion"
    TIMEOUT = "timeout"
    CANCELLED = "cancelado"

class JobPriority(str, Enum):
    """Prioridades de jobs"""
    LOW = "baja"
    NORMAL = "normal"
    HIGH = "alta"
    URGENT = "urgente"

# ===================================================================
# ENHANCED REQUEST MODELS
# ===================================================================

class EnhancedTicketCreate(BaseModel):
    """Enhanced ticket creation with automation features"""
    # Existing fields (backward compatibility)
    raw_data: str
    tipo: Literal["imagen", "pdf", "texto", "voz"]
    user_id: Optional[int] = None
    company_id: str = "default"

    # New automation fields
    auto_process: bool = Field(True, description="Enable automatic processing")
    priority: JobPriority = Field(JobPriority.NORMAL, description="Processing priority")
    merchant_hint: Optional[str] = Field(None, description="Merchant name hint for faster matching")
    alternative_urls: Optional[List[str]] = Field(None, description="Alternative URLs to try")
    max_retries: int = Field(3, description="Maximum retry attempts")
    timeout_seconds: int = Field(300, description="Maximum processing timeout")
    enable_captcha_solving: bool = Field(True, description="Enable automatic captcha solving")
    notification_webhook: Optional[str] = Field(None, description="Webhook for status updates")

class AutomationJobRequest(BaseModel):
    """Create automation job directly"""
    ticket_id: int
    merchant_id: Optional[int] = None
    priority: JobPriority = JobPriority.NORMAL
    config: Optional[Dict[str, Any]] = Field(default_factory=dict)
    scheduled_at: Optional[datetime] = None

# ===================================================================
# ENHANCED RESPONSE MODELS
# ===================================================================

class AutomationStep(BaseModel):
    """Individual automation step"""
    step_number: int
    action_type: str
    description: str
    url: Optional[str] = None
    selector: Optional[str] = None
    result: str
    timing_ms: int
    screenshot_url: Optional[str] = None
    error_message: Optional[str] = None
    llm_reasoning: Optional[str] = None

class AutomationSummary(BaseModel):
    """Summary of automation execution"""
    total_steps: int
    success_rate: float
    total_time_ms: int
    screenshots_count: int
    urls_attempted: List[str]
    final_status: AutomationStatus
    final_url: Optional[str] = None
    captchas_solved: int = 0

class EnhancedTicketResponse(BaseModel):
    """Enhanced ticket response with full automation data"""
    # Original fields
    id: int
    user_id: Optional[int]
    raw_data: str
    tipo: str
    estado: str
    company_id: str
    created_at: str
    updated_at: str

    # Enhanced automation fields
    automation_status: AutomationStatus
    automation_summary: Optional[AutomationSummary] = None
    automation_steps: List[AutomationStep] = Field(default_factory=list)
    automation_job_id: Optional[int] = None
    error_explanation: Optional[str] = None
    retry_count: int = 0
    merchant_confidence: Optional[float] = None
    processing_time_ms: Optional[int] = None
    cost_breakdown: Optional[Dict[str, float]] = None

class AutomationJobResponse(BaseModel):
    """Automation job with full details"""
    id: int
    ticket_id: int
    session_id: str
    status: AutomationStatus
    priority: JobPriority
    progress_percentage: float = 0.0

    # Execution details
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_time_ms: Optional[int] = None
    retry_count: int = 0

    # Results
    success: bool = False
    final_url: Optional[str] = None
    downloaded_files: List[str] = Field(default_factory=list)

    # Error handling
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    human_explanation: Optional[str] = None
    requires_intervention: bool = False
    intervention_instructions: Optional[str] = None

    # Service usage
    services_used: Dict[str, str] = Field(default_factory=dict)
    cost_breakdown: Dict[str, float] = Field(default_factory=dict)

    # Metadata
    config: Dict[str, Any] = Field(default_factory=dict)
    company_id: str
    created_at: datetime
    updated_at: datetime

# ===================================================================
# BULK & BATCH OPERATIONS
# ===================================================================

class BulkAutomationRequest(BaseModel):
    """Bulk automation processing"""
    ticket_ids: List[int]
    priority: JobPriority = JobPriority.NORMAL
    max_concurrent: int = Field(3, ge=1, le=10)
    notification_webhook: Optional[str] = None
    company_id: str = "default"

class BulkAutomationResponse(BaseModel):
    """Bulk operation response"""
    batch_id: str
    total_tickets: int
    jobs_created: List[int]
    estimated_completion: datetime
    status_url: str

# ===================================================================
# SYSTEM STATUS & HEALTH
# ===================================================================

class ServiceHealth(BaseModel):
    """Individual service health"""
    name: str
    status: Literal["healthy", "degraded", "down", "unknown"]
    response_time_ms: Optional[int] = None
    error_rate: Optional[float] = None
    last_check: datetime

class SystemHealth(BaseModel):
    """Overall system health"""
    status: Literal["healthy", "degraded", "down"]
    services: List[ServiceHealth]
    active_jobs: int
    queue_size: int
    average_processing_time_ms: int
    success_rate_24h: float

class AutomationMetrics(BaseModel):
    """System metrics"""
    total_jobs_today: int
    successful_jobs_today: int
    failed_jobs_today: int
    average_processing_time_ms: int
    captchas_solved_today: int
    cost_today: float
    top_error_types: List[Dict[str, Any]]

# ===================================================================
# FEATURE FLAGS & CONFIGURATION
# ===================================================================

class FeatureFlags(BaseModel):
    """Feature flags for gradual rollout"""
    enhanced_automation: bool = True
    claude_analysis: bool = True
    google_vision_ocr: bool = True
    captcha_solving: bool = True
    multi_url_navigation: bool = True
    screenshot_evidence: bool = True
    llm_error_explanation: bool = True

class TenantConfig(BaseModel):
    """Per-tenant configuration"""
    company_id: str
    feature_flags: FeatureFlags
    max_concurrent_jobs: int = 3
    max_daily_jobs: int = 100
    storage_quota_mb: int = 1000
    webhook_url: Optional[str] = None
    custom_timeout_seconds: int = 300