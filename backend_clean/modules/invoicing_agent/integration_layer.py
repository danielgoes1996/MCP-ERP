"""
Integration Layer - Conecta motor robusto con FastAPI existente sin romper nada.

Esta capa actúa como adaptador entre:
- API existente (tickets, merchants, jobs)
- Motor robusto (claude, google vision, 2captcha)
- Base de datos existente
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager

# Imports existentes (mantener compatibilidad)
from modules.invoicing_agent.models import (
    get_ticket, update_ticket, create_merchant,
    get_merchant, find_merchant_by_name
)
from modules.invoicing_agent.automation_persistence import create_automation_persistence

# Imports del motor robusto
try:
    from core.unified_automation_engine import create_unified_engine
    from core.service_stack_config import get_service_stack
    from core.claude_dom_analyzer import create_claude_analyzer
    ROBUST_ENGINE_AVAILABLE = True
except ImportError as e:
    ROBUST_ENGINE_AVAILABLE = False
    logging.warning(f"Robust engine not available: {e}")

logger = logging.getLogger(__name__)

class AutomationIntegrationLayer:
    """
    Capa de integración que conecta automáticamente el motor robusto
    con la API existente sin romper nada.
    """

    def __init__(self):
        self.engine = None
        self.persistence = create_automation_persistence()
        self.service_stack = None
        self._initialize_services()

    def _initialize_services(self):
        """Inicializar servicios robustos si están disponibles."""
        if ROBUST_ENGINE_AVAILABLE:
            try:
                self.engine = create_unified_engine()
                self.service_stack = get_service_stack()
                logger.info("✅ Robust automation engine initialized")
            except Exception as e:
                logger.warning(f"⚠️ Could not initialize robust engine: {e}")
        else:
            logger.info("🔄 Running in legacy mode (robust engine disabled)")

    def is_enhanced_mode(self) -> bool:
        """Check if enhanced automation is available."""
        return self.engine is not None

    async def process_ticket_enhanced(
        self,
        ticket_id: int,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Procesa ticket con motor robusto SI está disponible,
        fallback a procesamiento legacy si no.
        """
        try:
            # Get ticket data (using existing function)
            ticket_data = get_ticket(ticket_id)
            if not ticket_data:
                raise ValueError(f"Ticket {ticket_id} not found")

            # Try enhanced processing if available
            if self.is_enhanced_mode():
                logger.info(f"🚀 Processing ticket {ticket_id} with enhanced automation")
                return await self._process_with_robust_engine(ticket_id, ticket_data, config)
            else:
                logger.info(f"🔄 Processing ticket {ticket_id} with legacy automation")
                return await self._process_with_legacy_system(ticket_id, ticket_data, config)

        except Exception as e:
            logger.error(f"Error processing ticket {ticket_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "mode": "enhanced" if self.is_enhanced_mode() else "legacy"
            }

    async def _process_with_robust_engine(
        self,
        ticket_id: int,
        ticket_data: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Process with robust automation engine."""
        try:
            # 1. Extract merchant info (existing logic)
            merchant_name = config.get("merchant_hint") if config else None
            if not merchant_name:
                # Try to extract from ticket data or use AI
                merchant_name = await self._extract_merchant_from_ticket(ticket_data)

            # 2. Find or create merchant
            merchant = find_merchant_by_name(merchant_name) if merchant_name else None
            if not merchant and merchant_name:
                # Create basic merchant record for new ones
                merchant_id = create_merchant(
                    nombre=merchant_name,
                    metodo_facturacion="portal",
                    metadata={"auto_created": True}
                )
                merchant = get_merchant(merchant_id)

            # 3. Prepare merchant data for robust engine
            merchant_data = {
                "nombre": merchant.get("nombre", "Unknown") if merchant else "Unknown",
                "portal_url": merchant.get("metadata", {}).get("portal_url", "") if merchant else ""
            }

            # 4. Get alternative URLs if configured
            alternative_urls = []
            if config and config.get("alternative_urls"):
                alternative_urls = config["alternative_urls"]
            elif merchant and merchant.get("metadata", {}).get("alternative_urls"):
                alternative_urls = merchant["metadata"]["alternative_urls"]

            # 5. Process with unified engine
            result = await self.engine.process_invoice_automation(
                merchant=merchant_data,
                ticket_data=ticket_data,
                ticket_id=ticket_id,
                alternative_urls=alternative_urls
            )

            # 6. Update ticket status based on result
            new_status = "completado" if result.success else "fallido"
            update_ticket(
                ticket_id,
                estado=new_status,
                merchant_id=merchant.get("id") if merchant else None
            )

            # 7. Return enhanced result
            return {
                "success": result.success,
                "mode": "enhanced",
                "automation_summary": result.automation_summary,
                "service_stack_used": result.service_stack_used,
                "processing_time_ms": result.processing_time_ms,
                "cost_breakdown": result.cost_breakdown,
                "error_report": result.error_report,
                "merchant_identified": merchant_data["nombre"] if merchant else None
            }

        except Exception as e:
            logger.error(f"Error in robust engine processing: {e}")
            # Fallback to legacy if robust engine fails
            return await self._process_with_legacy_system(ticket_id, ticket_data, config)

    async def _process_with_legacy_system(
        self,
        ticket_id: int,
        ticket_data: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Fallback to existing legacy processing."""
        try:
            # Use existing worker if available
            from modules.invoicing_agent.worker import InvoicingWorker

            worker = InvoicingWorker()
            # Call existing processing method
            result = await worker.process_ticket(ticket_id)

            return {
                "success": result.get("success", False),
                "mode": "legacy",
                "result": result
            }

        except Exception as e:
            logger.error(f"Error in legacy processing: {e}")
            return {
                "success": False,
                "mode": "legacy",
                "error": str(e)
            }

    async def _extract_merchant_from_ticket(self, ticket_data: Dict[str, Any]) -> Optional[str]:
        """Extract merchant name from ticket using available services."""
        try:
            if self.is_enhanced_mode():
                # Use Claude for intelligent extraction
                analyzer = create_claude_analyzer()
                if analyzer.is_available():
                    # TODO: Implement Claude-based merchant extraction
                    pass

            # Fallback to simple text analysis
            text = ticket_data.get("texto_extraido", "")
            if text:
                # Simple heuristic: look for business names in first few lines
                lines = text.split('\n')[:3]
                for line in lines:
                    if len(line.strip()) > 3 and not line.strip().isdigit():
                        return line.strip()

            return None

        except Exception as e:
            logger.error(f"Error extracting merchant: {e}")
            return None

    def get_enhanced_ticket_data(self, ticket_id: int) -> Dict[str, Any]:
        """Get ticket with enhanced automation data if available."""
        try:
            # Get basic ticket data
            ticket_data = get_ticket(ticket_id)
            if not ticket_data:
                return None

            # Enhance with automation data if available
            if self.is_enhanced_mode():
                automation_data = self.persistence.get_automation_data(ticket_id)
                if not automation_data.get("error"):
                    ticket_data["automation_data"] = automation_data

            # Add service capabilities
            ticket_data["capabilities"] = self._get_available_capabilities()

            return ticket_data

        except Exception as e:
            logger.error(f"Error getting enhanced ticket data: {e}")
            return get_ticket(ticket_id)  # Fallback to basic

    def _get_available_capabilities(self) -> Dict[str, bool]:
        """Get list of available automation capabilities."""
        capabilities = {
            "enhanced_automation": self.is_enhanced_mode(),
            "claude_analysis": False,
            "google_vision_ocr": False,
            "captcha_solving": False,
            "multi_url_navigation": False,
            "screenshot_evidence": False
        }

        if self.is_enhanced_mode() and self.service_stack:
            service_status = self.service_stack.get_service_status()
            for service_key, info in service_status.get("services", {}).items():
                if service_key == "claude":
                    capabilities["claude_analysis"] = info["available"]
                elif service_key == "google_vision":
                    capabilities["google_vision_ocr"] = info["available"]
                elif service_key == "twocaptcha":
                    capabilities["captcha_solving"] = info["available"]

            # These are always available if engine is available
            capabilities["multi_url_navigation"] = True
            capabilities["screenshot_evidence"] = True

        return capabilities

    async def validate_system_health(self) -> Dict[str, Any]:
        """Validate overall system health."""
        health = {
            "status": "healthy",
            "mode": "enhanced" if self.is_enhanced_mode() else "legacy",
            "services": {},
            "warnings": [],
            "errors": []
        }

        try:
            # Check basic database connectivity
            test_ticket = get_ticket(1)  # Try to read any ticket
            health["services"]["database"] = {"status": "healthy", "tested": "ticket_read"}

        except Exception as e:
            health["services"]["database"] = {"status": "error", "error": str(e)}
            health["errors"].append(f"Database connectivity issue: {e}")
            health["status"] = "degraded"

        # Check enhanced services if available
        if self.is_enhanced_mode():
            try:
                service_status = self.service_stack.get_service_status()
                health["services"]["automation_engine"] = {
                    "status": "healthy",
                    "readiness_score": service_status["readiness_score"],
                    "available_services": service_status["available_services"]
                }

                if service_status["readiness_score"] < 0.5:
                    health["warnings"].append("Low automation readiness score")

            except Exception as e:
                health["services"]["automation_engine"] = {"status": "error", "error": str(e)}
                health["errors"].append(f"Automation engine issue: {e}")

        return health

# Global instance (singleton pattern)
_integration_layer = None

def get_integration_layer() -> AutomationIntegrationLayer:
    """Get singleton integration layer instance."""
    global _integration_layer
    if _integration_layer is None:
        _integration_layer = AutomationIntegrationLayer()
    return _integration_layer

# Convenience functions for backward compatibility
async def process_ticket_with_fallback(ticket_id: int, config: Dict[str, Any] = None) -> Dict[str, Any]:
    """Process ticket with automatic fallback between enhanced and legacy."""
    layer = get_integration_layer()
    return await layer.process_ticket_enhanced(ticket_id, config)

def get_ticket_with_automation_data(ticket_id: int) -> Dict[str, Any]:
    """Get ticket with automation data if available."""
    layer = get_integration_layer()
    return layer.get_enhanced_ticket_data(ticket_id)

async def validate_automation_system() -> Dict[str, Any]:
    """Validate automation system health."""
    layer = get_integration_layer()
    return await layer.validate_system_health()

def is_enhanced_automation_available() -> bool:
    """Check if enhanced automation is available."""
    layer = get_integration_layer()
    return layer.is_enhanced_mode()

# Context manager for safe automation processing
@asynccontextmanager
async def safe_automation_context(ticket_id: int):
    """Context manager for safe automation processing with cleanup."""
    layer = get_integration_layer()
    start_time = datetime.utcnow()

    try:
        # Log start
        logger.info(f"🚀 Starting automation for ticket {ticket_id}")

        # Update ticket status
        update_ticket(ticket_id, estado="procesando")

        yield layer

    except Exception as e:
        logger.error(f"❌ Automation failed for ticket {ticket_id}: {e}")
        update_ticket(ticket_id, estado="fallido")
        raise

    finally:
        # Log completion
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()
        logger.info(f"⏱️ Automation for ticket {ticket_id} completed in {duration:.2f}s")