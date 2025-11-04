"""
Orchestrator - Coordinador principal del sistema de facturación escalable.

Coordina OCR Service, Merchant Classifier, Queue Service y Workers.
Maneja el flujo completo desde subida de ticket hasta factura generada.
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

from .ocr_service import OCRService, OCRResult, extract_text_with_details
from .merchant_classifier import HybridMerchantClassifier, MerchantMatch, classify_merchant
from .queue_service import QueueService, JobPriority, Job

# Importar servicios del sistema original
from modules.invoicing_agent.models import (
    get_ticket, update_ticket, create_invoicing_job
)

logger = logging.getLogger(__name__)


class ProcessingStage(Enum):
    """Etapas del procesamiento de tickets."""
    UPLOADED = "uploaded"
    OCR_PROCESSING = "ocr_processing"
    MERCHANT_CLASSIFICATION = "merchant_classification"
    AUTOMATION_QUEUE = "automation_queue"
    WEB_AUTOMATION = "web_automation"
    INVOICE_GENERATION = "invoice_generation"
    COMPLETED = "completed"
    FAILED = "failed"
    HUMAN_REVIEW = "human_review"


@dataclass
class ProcessingResult:
    """Resultado del procesamiento de un ticket."""
    ticket_id: int
    stage: ProcessingStage
    success: bool
    processing_time: float
    ocr_result: Optional[OCRResult] = None
    merchant_match: Optional[MerchantMatch] = None
    automation_result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    requires_human_review: bool = False
    metadata: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convertir a diccionario para JSON serialization."""
        result = {
            "ticket_id": self.ticket_id,
            "stage": self.stage.value,
            "success": self.success,
            "processing_time": self.processing_time,
            "error_message": self.error_message,
            "requires_human_review": self.requires_human_review,
            "metadata": self.metadata or {}
        }

        if self.ocr_result:
            result["ocr"] = {
                "text_length": len(self.ocr_result.text),
                "confidence": self.ocr_result.confidence,
                "provider": self.ocr_result.provider.value,
                "processing_time": self.ocr_result.processing_time
            }

        if self.merchant_match:
            result["merchant"] = {
                "merchant_id": self.merchant_match.merchant_id,
                "merchant_name": self.merchant_match.merchant_name,
                "confidence": self.merchant_match.confidence,
                "method": self.merchant_match.method.value,
                "requires_review": self.merchant_match.metadata and
                                 self.merchant_match.metadata.get("requires_human_review", False)
            }

        if self.automation_result:
            result["automation"] = self.automation_result

        return result


class TicketOrchestrator:
    """
    Orchestrador principal que coordina el procesamiento end-to-end.

    Arquitectura:
    1. OCR Service → extrae texto
    2. Merchant Classifier → identifica merchant
    3. Queue Service → encola automatización
    4. Web Automation → genera factura
    5. Monitoring → track everything
    """

    def __init__(self):
        # Servicios principales
        self.ocr_service = OCRService()
        self.merchant_classifier = HybridMerchantClassifier()
        self.queue_service = QueueService()
        self.invoicing_worker = None  # Se inicializará cuando se necesite

        # Configuración
        self.ocr_timeout = 30  # segundos
        self.classification_timeout = 10  # segundos
        self.automation_timeout = 300  # 5 minutos para automatización web

        # Métricas globales
        self.metrics = {
            "tickets_processed": 0,
            "ocr_success_rate": 0.0,
            "classification_success_rate": 0.0,
            "automation_success_rate": 0.0,
            "average_processing_time": 0.0,
            "human_review_rate": 0.0,
            "stage_metrics": {stage.value: 0 for stage in ProcessingStage}
        }

        # Registrar handler en queue service
        self.queue_service.register_task_handler("process_ticket", self._process_ticket_automation)

    async def process_ticket_complete(
        self,
        ticket_id: int,
        priority: JobPriority = JobPriority.NORMAL,
        company_id: str = "default"
    ) -> ProcessingResult:
        """
        Procesar ticket completo desde OCR hasta facturación.

        Args:
            ticket_id: ID del ticket a procesar
            priority: Prioridad de procesamiento
            company_id: ID de la empresa

        Returns:
            Resultado completo del procesamiento
        """
        start_time = time.time()

        try:
            # Obtener ticket de la base de datos
            ticket = get_ticket(ticket_id)
            if not ticket:
                raise ValueError(f"Ticket {ticket_id} no encontrado")

            logger.info(f"Iniciando procesamiento completo de ticket {ticket_id}")

            # Etapa 1: OCR
            ocr_result = await self._process_ocr_stage(ticket)
            if not ocr_result.text.strip():
                return ProcessingResult(
                    ticket_id=ticket_id,
                    stage=ProcessingStage.OCR_PROCESSING,
                    success=False,
                    processing_time=time.time() - start_time,
                    ocr_result=ocr_result,
                    error_message="No se pudo extraer texto del ticket"
                )

            # Etapa 2: Clasificación de Merchant
            merchant_match = await self._process_classification_stage(ocr_result.text)

            # Verificar si requiere revisión humana
            requires_review = (
                merchant_match.metadata and
                merchant_match.metadata.get("requires_human_review", False)
            )

            if requires_review:
                # Marcar para revisión humana pero continuar con procesamiento automático si es posible
                logger.warning(f"Ticket {ticket_id} requiere revisión humana pero continuará procesamiento")

            # Etapa 3: Encolar para automatización
            if merchant_match.merchant_id != "UNKNOWN":
                job_id = await self.queue_service.enqueue_ticket_processing(
                    ticket_id=ticket_id,
                    company_id=company_id,
                    priority=priority
                )

                # Actualizar ticket con estado de procesamiento
                update_ticket(
                    ticket_id,
                    estado="procesando"
                )

                processing_time = time.time() - start_time

                return ProcessingResult(
                    ticket_id=ticket_id,
                    stage=ProcessingStage.AUTOMATION_QUEUE,
                    success=True,
                    processing_time=processing_time,
                    ocr_result=ocr_result,
                    merchant_match=merchant_match,
                    requires_human_review=requires_review,
                    metadata={
                        "job_id": job_id,
                        "queued_at": datetime.utcnow().isoformat()
                    }
                )
            else:
                # Merchant desconocido - requiere revisión humana
                update_ticket(
                    ticket_id,
                    estado="revision_manual"
                )

                return ProcessingResult(
                    ticket_id=ticket_id,
                    stage=ProcessingStage.HUMAN_REVIEW,
                    success=False,
                    processing_time=time.time() - start_time,
                    ocr_result=ocr_result,
                    merchant_match=merchant_match,
                    requires_human_review=True,
                    error_message="Merchant no identificado - requiere revisión manual"
                )

        except Exception as e:
            error_msg = f"Error procesando ticket {ticket_id}: {str(e)}"
            logger.error(error_msg)

            # Marcar ticket como error
            update_ticket(ticket_id, estado="error")

            return ProcessingResult(
                ticket_id=ticket_id,
                stage=ProcessingStage.FAILED,
                success=False,
                processing_time=time.time() - start_time,
                error_message=error_msg
            )

    async def _process_ocr_stage(self, ticket: Dict[str, Any]) -> OCRResult:
        """Procesar etapa de OCR."""
        logger.info(f"Iniciando OCR para ticket {ticket['id']}")

        try:
            if ticket["tipo"] == "imagen":
                # Extraer texto de imagen base64
                base64_image = ticket["raw_data"]
                ocr_result = await asyncio.wait_for(
                    extract_text_with_details(base64_image),
                    timeout=self.ocr_timeout
                )
            elif ticket["tipo"] == "texto":
                # Ya es texto - crear resultado OCR simulado
                from .ocr_service import OCRResult, OCRProvider
                ocr_result = OCRResult(
                    text=ticket["raw_data"],
                    confidence=1.0,
                    provider=OCRProvider.SIMULATION,
                    processing_time=0.0,
                    metadata={"type": "direct_text"}
                )
            else:
                raise ValueError(f"Tipo de ticket no soportado: {ticket['tipo']}")

            logger.info(f"OCR completado para ticket {ticket['id']}: {len(ocr_result.text)} caracteres")
            return ocr_result

        except asyncio.TimeoutError:
            logger.error(f"OCR timeout para ticket {ticket['id']}")
            raise
        except Exception as e:
            logger.error(f"Error en OCR para ticket {ticket['id']}: {e}")
            raise

    async def _process_classification_stage(self, text: str) -> MerchantMatch:
        """Procesar etapa de clasificación de merchant."""
        logger.info("Iniciando clasificación de merchant")

        try:
            merchant_match = await asyncio.wait_for(
                classify_merchant(text),
                timeout=self.classification_timeout
            )

            logger.info(f"Merchant clasificado: {merchant_match.merchant_name} "
                       f"(confianza: {merchant_match.confidence:.3f})")
            return merchant_match

        except asyncio.TimeoutError:
            logger.error("Timeout en clasificación de merchant")
            raise
        except Exception as e:
            logger.error(f"Error en clasificación de merchant: {e}")
            raise

    async def _process_ticket_automation(self, job: Job) -> Dict[str, Any]:
        """
        Procesar automatización web de un ticket (llamado por Queue Service).

        Args:
            job: Job con información del ticket a procesar

        Returns:
            Resultado de la automatización
        """
        ticket_id = job.ticket_id
        logger.info(f"Iniciando automatización para ticket {ticket_id} (job {job.id})")

        try:
            # Crear job de facturación en el sistema original
            invoicing_job_id = create_invoicing_job(
                ticket_id=ticket_id,
                company_id=job.company_id,
                metadata={"queue_job_id": job.id}
            )

            # Inicializar worker si no existe (lazy loading para evitar import circular)
            if not self.invoicing_worker:
                from modules.invoicing_agent.worker import InvoicingWorker
                self.invoicing_worker = InvoicingWorker()

            # Procesar con el worker original
            automation_result = await self.invoicing_worker.process_job(invoicing_job_id)

            # Actualizar métricas
            self._update_automation_metrics(automation_result["success"])

            if automation_result["success"]:
                logger.info(f"Automatización exitosa para ticket {ticket_id}")
                return {
                    "success": True,
                    "ticket_id": ticket_id,
                    "automation_result": automation_result,
                    "invoicing_job_id": invoicing_job_id
                }
            else:
                logger.error(f"Automatización falló para ticket {ticket_id}: {automation_result.get('error')}")
                return {
                    "success": False,
                    "ticket_id": ticket_id,
                    "error": automation_result.get("error"),
                    "invoicing_job_id": invoicing_job_id
                }

        except Exception as e:
            error_msg = f"Error en automatización de ticket {ticket_id}: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "ticket_id": ticket_id,
                "error": error_msg
            }

    async def process_batch_tickets(
        self,
        ticket_ids: List[int],
        company_id: str = "default",
        max_concurrent: int = 10
    ) -> List[ProcessingResult]:
        """
        Procesar múltiples tickets en paralelo.

        Args:
            ticket_ids: Lista de IDs de tickets
            company_id: ID de la empresa
            max_concurrent: Máximo de tickets a procesar concurrentemente

        Returns:
            Lista de resultados de procesamiento
        """
        logger.info(f"Iniciando procesamiento en lote de {len(ticket_ids)} tickets")

        # Crear semáforo para limitar concurrencia
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_with_semaphore(ticket_id: int) -> ProcessingResult:
            async with semaphore:
                return await self.process_ticket_complete(
                    ticket_id=ticket_id,
                    company_id=company_id
                )

        # Procesar en paralelo
        tasks = [process_with_semaphore(ticket_id) for ticket_id in ticket_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Procesar resultados y excepciones
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(ProcessingResult(
                    ticket_id=ticket_ids[i],
                    stage=ProcessingStage.FAILED,
                    success=False,
                    processing_time=0.0,
                    error_message=str(result)
                ))
            else:
                processed_results.append(result)

        # Actualizar métricas globales
        successful = sum(1 for r in processed_results if r.success)
        logger.info(f"Procesamiento en lote completado: {successful}/{len(ticket_ids)} exitosos")

        return processed_results

    async def get_processing_status(self, ticket_id: int) -> Dict[str, Any]:
        """
        Obtener estado detallado del procesamiento de un ticket.

        Args:
            ticket_id: ID del ticket

        Returns:
            Estado detallado con información de todas las etapas
        """
        # Obtener información del ticket
        ticket = get_ticket(ticket_id)
        if not ticket:
            return {"error": "Ticket no encontrado"}

        status = {
            "ticket_id": ticket_id,
            "ticket_status": ticket.get("estado", "unknown"),
            "created_at": ticket.get("created_at"),
            "updated_at": ticket.get("updated_at"),
            "stages": {}
        }

        # Información de OCR
        if ticket.get("extracted_text"):
            status["stages"]["ocr"] = {
                "completed": True,
                "text_length": len(ticket["extracted_text"]),
                "preview": ticket["extracted_text"][:100] + "..." if len(ticket["extracted_text"]) > 100 else ticket["extracted_text"]
            }

        # Información de merchant
        if ticket.get("merchant_detected"):
            status["stages"]["merchant_classification"] = {
                "completed": True,
                "merchant_name": ticket["merchant_detected"]
            }

        # Información de job queue
        if ticket.get("job_id"):
            job_status = await self.queue_service.get_job_status(ticket["job_id"])
            if job_status:
                status["stages"]["queue"] = {
                    "job_id": ticket["job_id"],
                    "job_status": job_status["status"],
                    "created_at": job_status["created_at"],
                    "retry_count": job_status["retry_count"]
                }

        # Información de automatización
        if ticket.get("invoice_data"):
            status["stages"]["automation"] = {
                "completed": True,
                "invoice_data": ticket["invoice_data"]
            }

        return status

    def _update_automation_metrics(self, success: bool):
        """Actualizar métricas de automatización."""
        total_automation = self.metrics.get("total_automation_attempts", 0) + 1
        successful_automation = self.metrics.get("successful_automation", 0)

        if success:
            successful_automation += 1

        self.metrics["total_automation_attempts"] = total_automation
        self.metrics["successful_automation"] = successful_automation
        self.metrics["automation_success_rate"] = successful_automation / total_automation

    async def get_system_metrics(self) -> Dict[str, Any]:
        """Obtener métricas completas del sistema."""
        # Métricas de servicios individuales
        ocr_metrics = self.ocr_service.get_metrics()
        classifier_metrics = self.merchant_classifier.get_metrics()
        queue_metrics = await self.queue_service.get_queue_metrics()

        return {
            "orchestrator": self.metrics,
            "ocr_service": ocr_metrics,
            "merchant_classifier": classifier_metrics,
            "queue_service": queue_metrics,
            "system_health": {
                "ocr_available": len(ocr_metrics.get("available_backends", [])) > 0,
                "queue_operational": queue_metrics.get("total_pending_jobs", 0) >= 0,
                "classification_operational": classifier_metrics.get("total_classifications", 0) >= 0
            }
        }

    async def start_workers(self, company_id: str = "default", num_workers: int = 2):
        """
        Iniciar workers para procesamiento automático.

        Args:
            company_id: ID de empresa
            num_workers: Número de workers concurrentes
        """
        logger.info(f"Iniciando {num_workers} workers para {company_id}")

        # Importar función del queue service
        from .queue_service import run_queue_worker

        # Crear tasks para workers
        tasks = []
        for i in range(num_workers):
            task = asyncio.create_task(
                run_queue_worker(
                    company_id=company_id,
                    interval=5,  # Revisar cada 5 segundos
                    max_jobs_per_cycle=3
                ),
                name=f"worker-{company_id}-{i}"
            )
            tasks.append(task)

        # Esperar a que todos los workers terminen (normalmente por Ctrl+C)
        try:
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            logger.info("Deteniendo workers...")
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)


# Instancia global
orchestrator = TicketOrchestrator()


# Funciones de conveniencia
async def process_ticket(ticket_id: int, company_id: str = "default") -> ProcessingResult:
    """Función simple para procesar un ticket."""
    return await orchestrator.process_ticket_complete(ticket_id, company_id=company_id)


async def process_multiple_tickets(ticket_ids: List[int], company_id: str = "default") -> List[ProcessingResult]:
    """Función simple para procesar múltiples tickets."""
    return await orchestrator.process_batch_tickets(ticket_ids, company_id=company_id)


if __name__ == "__main__":
    # Test del orchestrator
    async def test_orchestrator():
        print("=== Test Ticket Orchestrator ===")

        # Crear tickets de prueba (simulado)
        test_tickets = [
            {
                "id": 1001,
                "tipo": "texto",
                "raw_data": "PEMEX GASOLINERA #1234\nRFC: PEP970814SF3\nTOTAL: $523.25",
                "company_id": "test-company"
            },
            {
                "id": 1002,
                "tipo": "texto",
                "raw_data": "OXXO TIENDA #5678\nRFC: OXX970814HS9\nTOTAL: $45.50",
                "company_id": "test-company"
            }
        ]

        # Mock de función get_ticket para testing
        def mock_get_ticket(ticket_id):
            for ticket in test_tickets:
                if ticket["id"] == ticket_id:
                    return ticket
            return None

        # Reemplazar temporalmente
        import modules.invoicing_agent.models as models
        original_get_ticket = models.get_ticket
        models.get_ticket = mock_get_ticket

        try:
            # Procesar tickets individuales
            for ticket in test_tickets:
                print(f"\n--- Procesando ticket {ticket['id']} ---")
                result = await process_ticket(ticket["id"])
                print(f"Resultado: {result.success}")
                print(f"Etapa: {result.stage.value}")
                if result.merchant_match:
                    print(f"Merchant: {result.merchant_match.merchant_name}")
                if result.error_message:
                    print(f"Error: {result.error_message}")

            # Métricas del sistema
            print("\n=== Métricas del Sistema ===")
            metrics = await orchestrator.get_system_metrics()
            for service, service_metrics in metrics.items():
                print(f"\n{service}:")
                for key, value in service_metrics.items():
                    print(f"  {key}: {value}")

        finally:
            # Restaurar función original
            models.get_ticket = original_get_ticket

    asyncio.run(test_orchestrator())