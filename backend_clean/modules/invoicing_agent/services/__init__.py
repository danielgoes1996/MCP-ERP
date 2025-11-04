"""
Servicios escalables para el sistema de facturación automática.

Arquitectura por capas:
- OCR Service: Extracción de texto con múltiples backends
- Merchant Classifier: Clasificación inteligente con embeddings
- Queue Service: Sistema de colas robusto con Redis
- Orchestrator: Coordinador principal del sistema
"""

from .ocr_service import OCRService, extract_text_from_image, extract_text_with_details
from .merchant_classifier import HybridMerchantClassifier, classify_merchant
from .queue_service import QueueService, JobPriority, JobStatus
from .orchestrator import TicketOrchestrator, process_ticket, process_multiple_tickets

__all__ = [
    # OCR Service
    'OCRService',
    'extract_text_from_image',
    'extract_text_with_details',

    # Merchant Classifier
    'HybridMerchantClassifier',
    'classify_merchant',

    # Queue Service
    'QueueService',
    'JobPriority',
    'JobStatus',

    # Orchestrator
    'TicketOrchestrator',
    'process_ticket',
    'process_multiple_tickets'
]

# Instancias globales para uso fácil
from .ocr_service import ocr_service
from .merchant_classifier import merchant_classifier
from .queue_service import queue_service
from .orchestrator import orchestrator

# Función de inicialización
async def initialize_services():
    """
    Inicializar todos los servicios escalables.

    Debe llamarse al inicio de la aplicación.
    """
    import logging
    logger = logging.getLogger(__name__)

    logger.info("Inicializando servicios escalables...")

    # Verificar disponibilidad de servicios
    ocr_metrics = ocr_service.get_metrics()
    merchant_classifier.get_metrics()
    queue_metrics = await queue_service.get_queue_stats()

    logger.info(f"OCR Service: {len(ocr_metrics.get('available_backends', []))} backends disponibles")
    logger.info(f"Merchant Classifier: Listo para clasificación")
    logger.info(f"Queue Service: {queue_metrics.get('total_pending_jobs', 0)} jobs pendientes")

    logger.info("Servicios escalables inicializados correctamente")

    return {
        "ocr_service": ocr_service,
        "merchant_classifier": merchant_classifier,
        "queue_service": queue_service,
        "orchestrator": orchestrator
    }

# Función de métricas unificadas
async def get_system_health():
    """
    Obtener estado de salud de todos los servicios.

    Returns:
        Dict con estado de cada servicio
    """
    return await orchestrator.get_system_metrics()