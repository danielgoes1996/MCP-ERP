"""
Sistema de Procesamiento Masivo de Facturas
Punto 14: Bulk Invoice Matching - Complete Implementation

Este módulo proporciona:
- Procesamiento batch optimizado de facturas
- Tracking completo de performance y métricas
- Sistema de retry automático para fallos
- Analytics en tiempo real de procesamiento
- Error handling robusto con recovery
"""

import uuid
import asyncio
import time
import psutil
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import logging
import json

logger = logging.getLogger(__name__)


class BatchStatus(Enum):
    """Estados del batch de procesamiento"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIALLY_FAILED = "partially_failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class ItemStatus(Enum):
    """Estados de los items individuales"""
    PENDING = "pending"
    PROCESSING = "processing"
    MATCHED = "matched"
    NO_MATCH = "no_match"
    ERROR = "error"
    SKIPPED = "skipped"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"


class ProcessingPhase(Enum):
    """Fases del procesamiento"""
    INITIALIZATION = "initialization"
    PREPROCESSING = "preprocessing"
    PROCESSING = "processing"
    POSTPROCESSING = "postprocessing"
    FINALIZATION = "finalization"
    ERROR_HANDLING = "error_handling"


@dataclass
class BatchMetrics:
    """Métricas de performance del batch"""
    cpu_usage_percent: float
    memory_usage_mb: int
    items_processed: int
    items_per_second: float
    active_workers: int
    queue_size: int
    db_connections: int
    processing_time_ms: int
    success_rate: float
    error_rate: float


@dataclass
class InvoiceItem:
    """Item individual de factura en el batch"""
    filename: str
    uuid: Optional[str]
    total_amount: float
    subtotal_amount: Optional[float]
    iva_amount: Optional[float]
    currency: str
    issued_date: Optional[str]
    provider_name: Optional[str]
    provider_rfc: Optional[str]
    file_size: Optional[int]
    file_hash: Optional[str]
    raw_xml: Optional[str]

    # Processing results
    status: ItemStatus = ItemStatus.PENDING
    processing_time_ms: Optional[int] = None
    matched_expense_id: Optional[int] = None
    match_confidence: Optional[float] = None
    match_method: Optional[str] = None
    match_reasons: List[str] = None
    candidates_found: int = 0
    candidates_data: List[Dict[str, Any]] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None


@dataclass
class BatchRecord:
    """Registro completo del batch de procesamiento"""
    batch_id: str
    company_id: str
    total_invoices: int
    auto_link_threshold: float
    auto_mark_invoiced: bool

    # Status tracking
    status: BatchStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    processing_time_ms: Optional[int] = None

    # Results
    processed_count: int = 0
    linked_count: int = 0
    no_matches_count: int = 0
    errors_count: int = 0
    success_rate: Optional[float] = None

    # Performance metrics
    avg_processing_time_per_invoice: Optional[int] = None
    throughput_invoices_per_second: Optional[float] = None
    peak_memory_usage_mb: Optional[int] = None
    cpu_usage_percent: Optional[float] = None

    # Metadata
    batch_metadata: Optional[Dict[str, Any]] = None
    request_metadata: Optional[Dict[str, Any]] = None
    system_metrics: Optional[Dict[str, Any]] = None

    # Error handling
    error_summary: Optional[str] = None
    failed_invoices: int = 0
    retry_count: int = 0
    max_retries: int = 3

    # Items
    items: List[InvoiceItem] = None

    # Audit
    created_by: Optional[int] = None
    created_at: datetime = None
    updated_at: Optional[datetime] = None


class BulkInvoiceProcessor:
    """
    Procesador masivo de facturas con capacidades enterprise
    """

    def __init__(self):
        self.db = None
        self.max_concurrent_batches = 5
        self.max_concurrent_items = 10
        self.performance_monitoring_enabled = True
        self.retry_failed_items = True
        self.auto_optimize_performance = True

    async def initialize(self, db_adapter):
        """Inicializar el procesador con adaptador de BD"""
        self.db = db_adapter
        logger.info("BulkInvoiceProcessor initialized")

    async def create_batch(
        self,
        company_id: str,
        invoices: List[Dict[str, Any]],
        auto_link_threshold: float = 0.8,
        auto_mark_invoiced: bool = False,
        batch_metadata: Optional[Dict[str, Any]] = None,
        created_by: Optional[int] = None
    ) -> BatchRecord:
        """
        Crear un nuevo batch de procesamiento
        """
        try:
            batch_id = f"batch_{uuid.uuid4().hex[:16]}"

            # Convert invoices to InvoiceItem objects
            items = []
            for inv_data in invoices:
                item = InvoiceItem(
                    filename=inv_data.get("filename", ""),
                    uuid=inv_data.get("uuid"),
                    total_amount=inv_data.get("total", 0.0),
                    subtotal_amount=inv_data.get("subtotal"),
                    iva_amount=inv_data.get("iva_amount"),
                    currency=inv_data.get("currency", "MXN"),
                    issued_date=inv_data.get("issued_date"),
                    provider_name=inv_data.get("provider_name"),
                    provider_rfc=inv_data.get("provider_rfc"),
                    file_size=inv_data.get("file_size"),
                    file_hash=inv_data.get("file_hash"),
                    raw_xml=inv_data.get("raw_xml"),
                    candidates_data=[]
                )
                items.append(item)

            # Create batch record
            batch = BatchRecord(
                batch_id=batch_id,
                company_id=company_id,
                total_invoices=len(items),
                auto_link_threshold=auto_link_threshold,
                auto_mark_invoiced=auto_mark_invoiced,
                status=BatchStatus.PENDING,
                batch_metadata=batch_metadata or {},
                request_metadata={
                    "total_invoices": len(items),
                    "avg_invoice_amount": sum(item.total_amount for item in items) / len(items) if items else 0,
                    "unique_providers": len(set(item.provider_rfc for item in items if item.provider_rfc)),
                    "date_range": {
                        "earliest": min((item.issued_date for item in items if item.issued_date), default=None),
                        "latest": max((item.issued_date for item in items if item.issued_date), default=None)
                    }
                },
                items=items,
                created_by=created_by,
                created_at=datetime.utcnow(),
                max_retries=3
            )

            # Store in database
            await self._store_batch_record(batch)
            await self._store_batch_items(batch)

            logger.info(f"Created batch {batch_id} with {len(items)} invoices")
            return batch

        except Exception as e:
            logger.error(f"Error creating batch: {e}")
            raise

    async def process_batch(
        self,
        batch_id: str,
        max_concurrent_items: Optional[int] = None
    ) -> BatchRecord:
        """
        Procesar un batch completo de facturas
        """
        try:
            # Load batch from database
            batch = await self._load_batch_record(batch_id)
            if not batch:
                raise ValueError(f"Batch {batch_id} not found")

            if batch.status != BatchStatus.PENDING:
                raise ValueError(f"Batch {batch_id} is not in pending status")

            # Start processing
            batch.status = BatchStatus.PROCESSING
            batch.started_at = datetime.utcnow()
            await self._update_batch_status(batch)

            # Record performance metrics
            if self.performance_monitoring_enabled:
                await self._record_performance_metric(
                    batch_id, ProcessingPhase.INITIALIZATION,
                    await self._get_system_metrics()
                )

            logger.info(f"Starting batch processing: {batch_id}")

            # Process items with controlled concurrency
            concurrent_limit = max_concurrent_items or self.max_concurrent_items
            semaphore = asyncio.Semaphore(concurrent_limit)

            # Create tasks for all items
            tasks = []
            for item in batch.items:
                task = asyncio.create_task(
                    self._process_item_with_semaphore(semaphore, batch, item)
                )
                tasks.append(task)

            # Wait for all items to complete
            await asyncio.gather(*tasks, return_exceptions=True)

            # Finalize batch
            await self._finalize_batch(batch)

            # Record final metrics
            if self.performance_monitoring_enabled:
                await self._record_performance_metric(
                    batch_id, ProcessingPhase.FINALIZATION,
                    await self._get_system_metrics()
                )

            logger.info(f"Batch processing completed: {batch_id}")
            return batch

        except Exception as e:
            logger.error(f"Error processing batch {batch_id}: {e}")
            if 'batch' in locals():
                batch.status = BatchStatus.FAILED
                batch.error_summary = str(e)
                await self._update_batch_status(batch)
            raise

    async def _process_item_with_semaphore(
        self,
        semaphore: asyncio.Semaphore,
        batch: BatchRecord,
        item: InvoiceItem
    ):
        """Procesar un item individual con control de concurrencia"""
        async with semaphore:
            await self._process_single_item(batch, item)

    async def _process_single_item(
        self,
        batch: BatchRecord,
        item: InvoiceItem
    ):
        """
        Procesar un item individual de factura
        """
        start_time = time.time()
        item.status = ItemStatus.PROCESSING

        try:
            # Update item status in database
            await self._update_item_status(batch.batch_id, item)

            # Validate item data
            if not item.total_amount or item.total_amount <= 0:
                item.status = ItemStatus.ERROR
                item.error_code = "INVALID_AMOUNT"
                item.error_message = "Invalid or missing total amount"
                return

            # Find matching expenses
            candidates = await self._find_matching_expenses(batch, item)
            item.candidates_found = len(candidates)
            item.candidates_data = candidates

            if not candidates:
                # Check if we should create placeholder for invoices without match
                create_placeholder = batch.batch_metadata.get("create_placeholder_on_no_match", False)

                if create_placeholder:
                    # Try to create expense placeholder from invoice
                    expense_id = await self._create_expense_from_invoice(item, batch.company_id)

                    if expense_id:
                        # Successfully created placeholder
                        item.status = ItemStatus.MATCHED
                        item.matched_expense_id = expense_id
                        item.match_confidence = 1.0
                        item.match_method = "auto_created_placeholder"
                        item.match_reasons = ["auto_created_from_invoice", "placeholder_needs_review"]
                    else:
                        # Failed to create placeholder, mark as no match
                        item.status = ItemStatus.NO_MATCH
                        item.match_method = "no_candidates_placeholder_failed"
                else:
                    # Normal no match flow
                    item.status = ItemStatus.NO_MATCH
                    item.match_method = "no_candidates"
            else:
                # Find best match
                best_match = self._select_best_match(candidates, batch.auto_link_threshold)

                if best_match and best_match["confidence"] >= batch.auto_link_threshold:
                    # Auto-link
                    item.status = ItemStatus.MATCHED
                    item.matched_expense_id = best_match["expense_id"]
                    item.match_confidence = best_match["confidence"]
                    item.match_method = "auto"
                    item.match_reasons = best_match.get("reasons", [])

                    # Mark expense as invoiced if requested
                    if batch.auto_mark_invoiced:
                        await self._mark_expense_invoiced(best_match["expense_id"], item)

                elif candidates:
                    # Has candidates but below threshold
                    item.status = ItemStatus.MANUAL_REVIEW_REQUIRED
                    item.match_confidence = candidates[0]["confidence"]
                    item.match_method = "manual_review"
                else:
                    item.status = ItemStatus.NO_MATCH
                    item.match_method = "no_suitable_matches"

        except Exception as e:
            logger.error(f"Error processing item {item.filename}: {e}")
            item.status = ItemStatus.ERROR
            item.error_message = str(e)
            item.error_code = "PROCESSING_ERROR"
            item.error_details = {"exception_type": type(e).__name__}

        finally:
            # Calculate processing time
            item.processing_time_ms = int((time.time() - start_time) * 1000)

            # Update item in database
            await self._update_item_status(batch.batch_id, item)

            # Update batch progress
            batch.processed_count += 1
            if item.status == ItemStatus.MATCHED:
                batch.linked_count += 1
            elif item.status == ItemStatus.NO_MATCH:
                batch.no_matches_count += 1
            elif item.status == ItemStatus.ERROR:
                batch.errors_count += 1

            await self._update_batch_progress(batch)

    async def _find_matching_expenses(
        self,
        batch: BatchRecord,
        item: InvoiceItem
    ) -> List[Dict[str, Any]]:
        """
        Buscar gastos que coincidan con la factura
        """
        try:
            # Query for potential matches
            query = """
            SELECT
                id, description, amount, provider_name, expense_date,
                category, metadata, created_at
            FROM expenses
            WHERE company_id = ?
            AND bank_status != 'invoiced'
            AND ABS(amount - ?) <= (? * 0.1)  -- 10% tolerance
            ORDER BY ABS(amount - ?) ASC, created_at DESC
            LIMIT 10
            """

            records = await self.db.fetch_all(
                query,
                (batch.company_id, item.total_amount, item.total_amount, item.total_amount)
            )

            candidates = []
            for record in records:
                confidence = self._calculate_match_confidence(item, record)
                reasons = self._get_match_reasons(item, record, confidence)

                candidates.append({
                    "expense_id": record["id"],
                    "description": record["description"],
                    "amount": record["amount"],
                    "provider_name": record["provider_name"],
                    "expense_date": record["expense_date"],
                    "confidence": confidence,
                    "reasons": reasons,
                    "amount_difference": abs(float(record["amount"]) - item.total_amount),
                    "amount_match_quality": self._get_amount_match_quality(
                        float(record["amount"]), item.total_amount
                    )
                })

            # Sort by confidence
            candidates.sort(key=lambda x: x["confidence"], reverse=True)
            return candidates

        except Exception as e:
            logger.error(f"Error finding matches for {item.filename}: {e}")
            return []

    def _calculate_match_confidence(
        self,
        item: InvoiceItem,
        expense_record: Dict[str, Any]
    ) -> float:
        """
        Calcular confianza de match entre factura y gasto
        """
        confidence = 0.0

        # Amount similarity (40% weight)
        amount_diff = abs(float(expense_record["amount"]) - item.total_amount)
        amount_tolerance = max(item.total_amount * 0.05, 10.0)  # 5% or $10 minimum

        if amount_diff <= amount_tolerance:
            amount_score = 1.0 - (amount_diff / amount_tolerance)
            confidence += amount_score * 0.4

        # Provider name similarity (30% weight)
        if item.provider_name and expense_record.get("provider_name"):
            provider_similarity = self._calculate_text_similarity(
                item.provider_name.lower(),
                expense_record["provider_name"].lower()
            )
            confidence += provider_similarity * 0.3

        # Date proximity (20% weight)
        if item.issued_date and expense_record.get("expense_date"):
            try:
                invoice_date = datetime.fromisoformat(item.issued_date.replace('Z', '+00:00'))
                expense_date = datetime.fromisoformat(expense_record["expense_date"])

                date_diff_days = abs((invoice_date - expense_date).days)
                if date_diff_days <= 30:  # Within 30 days
                    date_score = 1.0 - (date_diff_days / 30.0)
                    confidence += date_score * 0.2
            except:
                pass

        # UUID exact match (100% if available)
        if item.uuid:
            expense_metadata = expense_record.get("metadata", {})
            if isinstance(expense_metadata, str):
                try:
                    expense_metadata = json.loads(expense_metadata)
                except:
                    expense_metadata = {}

            if expense_metadata.get("cfdi_uuid") == item.uuid:
                confidence = 1.0

        return min(confidence, 1.0)

    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calcular similitud entre dos textos"""
        if not text1 or not text2:
            return 0.0

        # Simple Jaccard similarity on words
        words1 = set(text1.split())
        words2 = set(text2.split())

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        if not union:
            return 0.0

        return len(intersection) / len(union)

    def _get_match_reasons(
        self,
        item: InvoiceItem,
        expense_record: Dict[str, Any],
        confidence: float
    ) -> List[str]:
        """Obtener razones del match"""
        reasons = []

        if confidence >= 0.9:
            reasons.append("high_confidence_match")

        amount_diff = abs(float(expense_record["amount"]) - item.total_amount)
        if amount_diff <= 1.0:
            reasons.append("exact_amount_match")
        elif amount_diff <= item.total_amount * 0.05:
            reasons.append("close_amount_match")

        if item.provider_name and expense_record.get("provider_name"):
            if item.provider_name.lower() in expense_record["provider_name"].lower():
                reasons.append("provider_name_match")

        if item.uuid:
            expense_metadata = expense_record.get("metadata", {})
            if isinstance(expense_metadata, str):
                try:
                    expense_metadata = json.loads(expense_metadata)
                except:
                    expense_metadata = {}

            if expense_metadata.get("cfdi_uuid") == item.uuid:
                reasons.append("uuid_exact_match")

        return reasons

    def _get_amount_match_quality(self, expense_amount: float, invoice_amount: float) -> str:
        """Evaluar calidad del match por monto"""
        diff = abs(expense_amount - invoice_amount)
        tolerance = max(invoice_amount * 0.05, 1.0)

        if diff <= 1.0:
            return "exact"
        elif diff <= tolerance:
            return "close"
        elif diff <= invoice_amount * 0.1:
            return "acceptable"
        else:
            return "poor"

    def _select_best_match(
        self,
        candidates: List[Dict[str, Any]],
        threshold: float
    ) -> Optional[Dict[str, Any]]:
        """Seleccionar el mejor match de los candidatos"""
        if not candidates:
            return None

        best_match = candidates[0]
        if best_match["confidence"] >= threshold:
            return best_match

        return None

    async def _mark_expense_invoiced(self, expense_id: int, item: InvoiceItem):
        """Marcar gasto como facturado"""
        try:
            update_data = {
                "invoice_status": "invoiced",
                "invoice_uuid": item.uuid,
                "invoice_filename": item.filename,
                "invoice_linked_at": datetime.utcnow().isoformat()
            }

            await self.db.execute(
                "UPDATE expenses SET invoice_status = ?, metadata = json_patch(COALESCE(metadata, '{}'), ?) WHERE id = ?",
                ("invoiced", json.dumps(update_data), expense_id)
            )

        except Exception as e:
            logger.error(f"Error marking expense {expense_id} as invoiced: {e}")

    async def _get_default_payment_account(self, company_id: str) -> Optional[int]:
        """
        Obtener cuenta de pago por defecto para la empresa.

        Args:
            company_id: ID de la empresa

        Returns:
            payment_account_id o None si no hay cuenta por defecto
        """
        try:
            # Convert company_id to tenant_id (user_payment_accounts uses tenant_id)
            from core.tenancy_middleware import extract_tenant_from_company_id
            tenant_id = extract_tenant_from_company_id(company_id)

            # Buscar cuenta marcada como default
            query = """
            SELECT id FROM user_payment_accounts
            WHERE tenant_id = ? AND is_default = 1
            ORDER BY created_at DESC
            LIMIT 1
            """

            record = await self.db.fetch_one(query, (tenant_id,))

            if record:
                return record["id"]

            # Si no hay default, buscar la primera cuenta disponible
            fallback_query = """
            SELECT id FROM user_payment_accounts
            WHERE tenant_id = ?
            ORDER BY created_at ASC
            LIMIT 1
            """

            fallback_record = await self.db.fetch_one(fallback_query, (tenant_id,))

            if fallback_record:
                logger.warning(
                    f"No default payment account found for company {company_id} (tenant {tenant_id}), "
                    f"using first available account {fallback_record['id']}"
                )
                return fallback_record["id"]

            logger.error(f"No payment accounts found for company {company_id} (tenant {tenant_id})")
            return None

        except Exception as e:
            logger.error(f"Error getting default payment account for company {company_id}: {e}")
            return None

    async def _create_expense_from_invoice(
        self,
        item: InvoiceItem,
        company_id: str
    ) -> Optional[int]:
        """
        Crear expense placeholder desde datos de factura.

        Esta función se llama cuando una factura no tiene gasto relacionado,
        para crear automáticamente un expense placeholder que luego puede
        ser completado manualmente.

        Args:
            item: InvoiceItem con datos de la factura
            company_id: ID de la empresa

        Returns:
            expense_id del expense creado o None si falla
        """
        try:
            from core.expense_validation import expense_validator

            # Obtener cuenta de pago por defecto
            payment_account_id = await self._get_default_payment_account(company_id)

            # Construir datos preliminares del expense
            expense_data = {
                "descripcion": f"Factura {item.provider_name or 'Proveedor desconocido'}",
                "monto_total": item.total_amount,
                "fecha_gasto": item.issued_date,
                "categoria": None,  # Usuario debe elegir
                "proveedor_nombre": item.provider_name,
                "proveedor_rfc": item.provider_rfc,
                "payment_account_id": payment_account_id,
            }

            if item.uuid:
                expense_data["descripcion"] += f" (UUID: {item.uuid[:8]}...)"

            # Validar campos faltantes
            invoice_data_for_validation = {
                "uuid": item.uuid,
                "filename": item.filename,
                "provider_name": item.provider_name,
                "provider_rfc": item.provider_rfc,
                "total_amount": item.total_amount,
                "issued_date": item.issued_date,
            }

            validation_result = expense_validator.validate_expense_data(
                expense_data,
                context="bulk_invoice"
            )

            # Construir metadata con información de validación
            metadata = {
                "auto_created": True,
                "created_from_bulk_invoice": True,
                "bulk_filename": item.filename,
                "invoice_uuid": item.uuid,
                "invoice_issued_date": item.issued_date,
                "invoice_provider_rfc": item.provider_rfc,
                "created_at": datetime.utcnow().isoformat(),
                # Información de validación
                "validation_status": "incomplete" if not validation_result.is_complete else "complete",
                "missing_fields": validation_result.missing_fields,
                "requires_user_completion": not validation_result.is_complete,
            }

            # Si faltan campos, agregar datos para el popup
            if not validation_result.is_complete:
                completion_prompt = expense_validator.get_completion_prompt_data(
                    expense_data,
                    invoice_data_for_validation
                )
                metadata["completion_prompt"] = completion_prompt
                metadata["placeholder_needs_review"] = True

                logger.warning(
                    f"⚠️ Expense placeholder for {item.filename} is incomplete. "
                    f"Missing fields: {', '.join(validation_result.missing_fields)}"
                )

            # Crear expense en la base de datos directamente (bypass record_internal_expense)
            # porque necesitamos manejar payment_account_id que puede ser None
            expense_id = await self._insert_expense_record(
                description=expense_data["descripcion"],
                amount=item.total_amount,
                currency=item.currency,
                expense_date=item.issued_date or datetime.utcnow().isoformat()[:10],
                category=expense_data.get("categoria") or "sin_clasificar",
                provider_name=item.provider_name,
                provider_rfc=item.provider_rfc,
                invoice_status="facturado",
                invoice_uuid=item.uuid,
                will_have_cfdi=True,
                payment_account_id=payment_account_id,
                company_id=company_id,
                workflow_status="requiere_completar" if not validation_result.is_complete else "draft",
                metadata=metadata,
            )

            if expense_id:
                status_emoji = "⚠️" if not validation_result.is_complete else "✅"
                logger.info(
                    f"{status_emoji} Created expense placeholder {expense_id} from invoice {item.filename} "
                    f"(amount: {item.total_amount}, complete: {validation_result.is_complete})"
                )

            return expense_id

        except Exception as e:
            logger.error(
                f"❌ Error creating expense placeholder from invoice {item.filename}: {e}"
            )
            import traceback
            logger.error(traceback.format_exc())
            return None

    async def _insert_expense_record(
        self,
        description: str,
        amount: float,
        currency: str,
        expense_date: str,
        category: str,
        provider_name: Optional[str],
        provider_rfc: Optional[str],
        invoice_status: str,
        invoice_uuid: Optional[str],
        will_have_cfdi: bool,
        payment_account_id: Optional[int],
        company_id: str,
        workflow_status: str,
        metadata: Dict[str, Any],
    ) -> Optional[int]:
        """
        Inserta un expense record directamente en la BD.
        Necesario porque record_internal_expense no maneja payment_account_id nullable.
        """
        try:
            now = datetime.utcnow().isoformat()
            metadata_json = json.dumps(metadata)

            query = """
            INSERT INTO expense_records (
                description, amount, currency, expense_date, category,
                provider_name, provider_rfc, invoice_status, invoice_uuid,
                will_have_cfdi, payment_account_id, company_id, workflow_status,
                bank_status, paid_by, metadata, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

            await self.db.execute(query, (
                description,
                amount,
                currency,
                expense_date,
                category,
                provider_name,
                provider_rfc,
                invoice_status,
                invoice_uuid,
                1 if will_have_cfdi else 0,
                payment_account_id,
                company_id,
                workflow_status,
                "pendiente",  # bank_status
                "company_account",  # paid_by
                metadata_json,
                now,
                now,
            ))

            # Get the last inserted ID
            result = await self.db.fetch_one("SELECT last_insert_rowid() as id")
            return result["id"] if result else None

        except Exception as e:
            logger.error(f"Error inserting expense record: {e}")
            return None

    async def _finalize_batch(self, batch: BatchRecord):
        """Finalizar el procesamiento del batch"""
        try:
            # Calculate final metrics
            batch.completed_at = datetime.utcnow()
            if batch.started_at:
                batch.processing_time_ms = int(
                    (batch.completed_at - batch.started_at).total_seconds() * 1000
                )

            # Calculate success rate
            if batch.total_invoices > 0:
                batch.success_rate = batch.linked_count / batch.total_invoices

            # Calculate throughput
            if batch.processing_time_ms and batch.processing_time_ms > 0:
                batch.throughput_invoices_per_second = (
                    batch.processed_count / (batch.processing_time_ms / 1000.0)
                )

            # Determine final status
            if batch.errors_count == 0:
                batch.status = BatchStatus.COMPLETED
            elif batch.linked_count > 0:
                batch.status = BatchStatus.PARTIALLY_FAILED
            else:
                batch.status = BatchStatus.FAILED

            # Calculate system metrics summary
            processing_items = [item for item in batch.items if item.processing_time_ms]
            if processing_items:
                batch.avg_processing_time_per_invoice = int(
                    sum(item.processing_time_ms for item in processing_items) / len(processing_items)
                )

            # Update database
            await self._update_batch_status(batch)

            logger.info(f"Batch {batch.batch_id} finalized: {batch.status.value}")

        except Exception as e:
            logger.error(f"Error finalizing batch {batch.batch_id}: {e}")
            batch.status = BatchStatus.FAILED
            batch.error_summary = f"Finalization error: {str(e)}"
            await self._update_batch_status(batch)

    # Database operations
    async def _store_batch_record(self, batch: BatchRecord):
        """Almacenar registro de batch en BD"""
        try:
            query = """
            INSERT INTO bulk_invoice_batches (
                batch_id, company_id, total_invoices, auto_link_threshold,
                auto_mark_invoiced, status, batch_metadata, request_metadata,
                max_retries, created_by, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

            await self.db.execute(query, (
                batch.batch_id,
                batch.company_id,
                batch.total_invoices,
                batch.auto_link_threshold,
                batch.auto_mark_invoiced,
                batch.status.value,
                json.dumps(batch.batch_metadata),
                json.dumps(batch.request_metadata),
                batch.max_retries,
                batch.created_by,
                batch.created_at.isoformat()
            ))

        except Exception as e:
            logger.error(f"Error storing batch record: {e}")
            raise

    async def _store_batch_items(self, batch: BatchRecord):
        """Almacenar items del batch en BD"""
        try:
            query = """
            INSERT INTO bulk_invoice_batch_items (
                batch_id, filename, uuid, total_amount, subtotal_amount,
                iva_amount, currency, issued_date, provider_name, provider_rfc,
                file_size, file_hash, item_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

            for item in batch.items:
                await self.db.execute(query, (
                    batch.batch_id,
                    item.filename,
                    item.uuid,
                    item.total_amount,
                    item.subtotal_amount,
                    item.iva_amount,
                    item.currency,
                    item.issued_date,
                    item.provider_name,
                    item.provider_rfc,
                    item.file_size,
                    item.file_hash,
                    item.status.value
                ))

        except Exception as e:
            logger.error(f"Error storing batch items: {e}")
            raise

    async def _load_batch_record(self, batch_id: str) -> Optional[BatchRecord]:
        """Cargar registro de batch desde BD"""
        try:
            # Load batch data
            batch_query = """
            SELECT * FROM bulk_invoice_batches WHERE batch_id = ?
            """
            batch_data = await self.db.fetch_one(batch_query, (batch_id,))

            if not batch_data:
                return None

            # Load batch items
            items_query = """
            SELECT * FROM bulk_invoice_batch_items WHERE batch_id = ? ORDER BY id
            """
            items_data = await self.db.fetch_all(items_query, (batch_id,))

            # Convert to objects
            items = []
            for item_data in items_data:
                item = InvoiceItem(
                    filename=item_data["filename"],
                    uuid=item_data["uuid"],
                    total_amount=float(item_data["total_amount"]),
                    subtotal_amount=float(item_data["subtotal_amount"]) if item_data["subtotal_amount"] else None,
                    iva_amount=float(item_data["iva_amount"]) if item_data["iva_amount"] else None,
                    currency=item_data["currency"],
                    issued_date=item_data["issued_date"],
                    provider_name=item_data["provider_name"],
                    provider_rfc=item_data["provider_rfc"],
                    file_size=item_data["file_size"],
                    file_hash=item_data["file_hash"],
                    status=ItemStatus(item_data["item_status"]),
                    processing_time_ms=item_data["processing_time_ms"],
                    matched_expense_id=item_data["matched_expense_id"],
                    match_confidence=float(item_data["match_confidence"]) if item_data["match_confidence"] else None,
                    match_method=item_data["match_method"],
                    match_reasons=item_data["match_reasons"] or [],
                    candidates_found=item_data["candidates_found"] or 0,
                    candidates_data=json.loads(item_data["candidates_data"]) if item_data["candidates_data"] else [],
                    error_message=item_data["error_message"],
                    error_code=item_data["error_code"],
                    error_details=json.loads(item_data["error_details"]) if item_data["error_details"] else None
                )
                items.append(item)

            # Create batch record
            batch = BatchRecord(
                batch_id=batch_data["batch_id"],
                company_id=batch_data["company_id"],
                total_invoices=batch_data["total_invoices"],
                auto_link_threshold=float(batch_data["auto_link_threshold"]),
                auto_mark_invoiced=batch_data["auto_mark_invoiced"],
                status=BatchStatus(batch_data["status"]),
                started_at=datetime.fromisoformat(batch_data["started_at"]) if batch_data["started_at"] else None,
                completed_at=datetime.fromisoformat(batch_data["completed_at"]) if batch_data["completed_at"] else None,
                processing_time_ms=batch_data["processing_time_ms"],
                processed_count=batch_data["processed_count"],
                linked_count=batch_data["linked_count"],
                no_matches_count=batch_data["no_matches_count"],
                errors_count=batch_data["errors_count"],
                success_rate=float(batch_data["success_rate"]) if batch_data["success_rate"] else None,
                batch_metadata=json.loads(batch_data["batch_metadata"]) if batch_data["batch_metadata"] else {},
                request_metadata=json.loads(batch_data["request_metadata"]) if batch_data["request_metadata"] else {},
                items=items,
                created_by=batch_data["created_by"],
                created_at=datetime.fromisoformat(batch_data["created_at"]),
                updated_at=datetime.fromisoformat(batch_data["updated_at"]) if batch_data["updated_at"] else None
            )

            return batch

        except Exception as e:
            logger.error(f"Error loading batch record {batch_id}: {e}")
            return None

    async def _update_batch_status(self, batch: BatchRecord):
        """Actualizar status del batch en BD"""
        try:
            query = """
            UPDATE bulk_invoice_batches SET
                status = ?, started_at = ?, completed_at = ?, processing_time_ms = ?,
                processed_count = ?, linked_count = ?, no_matches_count = ?, errors_count = ?,
                success_rate = ?, avg_processing_time_per_invoice = ?,
                throughput_invoices_per_second = ?, peak_memory_usage_mb = ?,
                cpu_usage_percent = ?, error_summary = ?, failed_invoices = ?,
                updated_at = ?
            WHERE batch_id = ?
            """

            await self.db.execute(query, (
                batch.status.value,
                batch.started_at.isoformat() if batch.started_at else None,
                batch.completed_at.isoformat() if batch.completed_at else None,
                batch.processing_time_ms,
                batch.processed_count,
                batch.linked_count,
                batch.no_matches_count,
                batch.errors_count,
                batch.success_rate,
                batch.avg_processing_time_per_invoice,
                batch.throughput_invoices_per_second,
                batch.peak_memory_usage_mb,
                batch.cpu_usage_percent,
                batch.error_summary,
                batch.failed_invoices,
                datetime.utcnow().isoformat()
            ), (batch.batch_id,))

        except Exception as e:
            logger.error(f"Error updating batch status: {e}")

    async def _update_batch_progress(self, batch: BatchRecord):
        """Actualizar progreso del batch"""
        try:
            query = """
            UPDATE bulk_invoice_batches SET
                processed_count = ?, linked_count = ?, no_matches_count = ?,
                errors_count = ?, updated_at = ?
            WHERE batch_id = ?
            """

            await self.db.execute(query, (
                batch.processed_count,
                batch.linked_count,
                batch.no_matches_count,
                batch.errors_count,
                datetime.utcnow().isoformat(),
                batch.batch_id
            ))

        except Exception as e:
            logger.error(f"Error updating batch progress: {e}")

    async def _update_item_status(self, batch_id: str, item: InvoiceItem):
        """Actualizar status de un item"""
        try:
            query = """
            UPDATE bulk_invoice_batch_items SET
                item_status = ?, processing_started_at = ?, processing_completed_at = ?,
                processing_time_ms = ?, matched_expense_id = ?, match_confidence = ?,
                match_method = ?, match_reasons = ?, candidates_found = ?,
                candidates_data = ?, error_message = ?, error_code = ?,
                error_details = ?, updated_at = ?
            WHERE batch_id = ? AND filename = ?
            """

            await self.db.execute(query, (
                item.status.value,
                datetime.utcnow().isoformat() if item.status == ItemStatus.PROCESSING else None,
                datetime.utcnow().isoformat() if item.status != ItemStatus.PROCESSING else None,
                item.processing_time_ms,
                item.matched_expense_id,
                item.match_confidence,
                item.match_method,
                json.dumps(item.match_reasons) if item.match_reasons else None,
                item.candidates_found,
                json.dumps(item.candidates_data) if item.candidates_data else None,
                item.error_message,
                item.error_code,
                json.dumps(item.error_details) if item.error_details else None,
                datetime.utcnow().isoformat(),
                batch_id,
                item.filename
            ))

        except Exception as e:
            logger.error(f"Error updating item status: {e}")

    async def _get_system_metrics(self) -> Dict[str, Any]:
        """Obtener métricas del sistema"""
        try:
            process = psutil.Process()

            return {
                "cpu_usage_percent": psutil.cpu_percent(interval=0.1),
                "memory_usage_mb": process.memory_info().rss / 1024 / 1024,
                "memory_percent": process.memory_percent(),
                "open_files": len(process.open_files()),
                "connections": len(process.connections()),
                "threads": process.num_threads(),
                "timestamp": datetime.utcnow().isoformat()
            }
        except:
            return {}

    async def _record_performance_metric(
        self,
        batch_id: str,
        phase: ProcessingPhase,
        metrics: Dict[str, Any]
    ):
        """Registrar métricas de performance"""
        try:
            query = """
            INSERT INTO bulk_processing_performance (
                batch_id, phase, cpu_usage_percent, memory_usage_mb,
                custom_metrics
            ) VALUES (?, ?, ?, ?, ?)
            """

            await self.db.execute(query, (
                batch_id,
                phase.value,
                metrics.get("cpu_usage_percent"),
                metrics.get("memory_usage_mb"),
                json.dumps(metrics)
            ))

        except Exception as e:
            logger.error(f"Error recording performance metric: {e}")

    # Public API methods
    async def get_batch_status(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """Obtener estado del batch"""
        batch = await self._load_batch_record(batch_id)
        if not batch:
            return None

        return {
            "batch_id": batch.batch_id,
            "status": batch.status.value,
            "total_invoices": batch.total_invoices,
            "processed_count": batch.processed_count,
            "linked_count": batch.linked_count,
            "no_matches_count": batch.no_matches_count,
            "errors_count": batch.errors_count,
            "success_rate": batch.success_rate,
            "processing_time_ms": batch.processing_time_ms,
            "started_at": batch.started_at.isoformat() if batch.started_at else None,
            "completed_at": batch.completed_at.isoformat() if batch.completed_at else None,
            "progress_percent": (batch.processed_count / batch.total_invoices * 100) if batch.total_invoices > 0 else 0
        }

    async def get_batch_results(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """Obtener resultados detallados del batch"""
        batch = await self._load_batch_record(batch_id)
        if not batch:
            return None

        return {
            "batch_id": batch.batch_id,
            "company_id": batch.company_id,
            "status": batch.status.value,
            "summary": {
                "total_invoices": batch.total_invoices,
                "processed": batch.processed_count,
                "linked": batch.linked_count,
                "no_matches": batch.no_matches_count,
                "errors": batch.errors_count,
                "success_rate": batch.success_rate,
                "processing_time_ms": batch.processing_time_ms,
                "throughput_invoices_per_second": batch.throughput_invoices_per_second
            },
            "items": [
                {
                    "filename": item.filename,
                    "uuid": item.uuid,
                    "total_amount": item.total_amount,
                    "status": item.status.value,
                    "processing_time_ms": item.processing_time_ms,
                    "matched_expense_id": item.matched_expense_id,
                    "match_confidence": item.match_confidence,
                    "match_method": item.match_method,
                    "candidates_found": item.candidates_found,
                    "error_message": item.error_message
                } for item in batch.items
            ] if batch.items else []
        }

    async def retry_failed_batch(
        self,
        batch_id: str,
        retry_failed_items_only: bool = True
    ) -> BatchRecord:
        """
        Retry a failed batch or specific failed items
        """
        try:
            # Load original batch
            batch = await self._load_batch_record(batch_id)
            if not batch:
                raise ValueError(f"Batch {batch_id} not found")

            # Check retry count
            if batch.retry_count >= batch.max_retries:
                raise ValueError(f"Batch {batch_id} has exceeded maximum retries ({batch.max_retries})")

            logger.info(f"Retrying batch {batch_id}, attempt {batch.retry_count + 1}")

            # Update retry count and status
            batch.retry_count += 1
            batch.status = BatchStatus.RETRYING
            await self._update_batch_status(batch)

            # Determine which items to retry
            items_to_retry = []
            if retry_failed_items_only:
                # Only retry failed or error items
                items_to_retry = [item for item in batch.items if item.status in [ItemStatus.ERROR, ItemStatus.SKIPPED]]
            else:
                # Retry all non-successful items
                items_to_retry = [item for item in batch.items if item.status != ItemStatus.MATCHED]

            if not items_to_retry:
                batch.status = BatchStatus.COMPLETED
                await self._update_batch_status(batch)
                logger.info(f"No items to retry for batch {batch_id}")
                return batch

            logger.info(f"Retrying {len(items_to_retry)} items from batch {batch_id}")

            # Reset retry items to pending
            for item in items_to_retry:
                item.status = ItemStatus.PENDING
                item.error_message = None
                item.error_code = None
                item.processing_time_ms = None

            # Process retry items
            batch.status = BatchStatus.PROCESSING
            await self._update_batch_status(batch)

            # Process items with controlled concurrency
            semaphore = asyncio.Semaphore(self.max_concurrent_items)

            # Create tasks for retry items
            tasks = []
            for item in items_to_retry:
                task = asyncio.create_task(
                    self._process_item_with_semaphore(semaphore, batch, item)
                )
                tasks.append(task)

            # Wait for all retry items to complete
            await asyncio.gather(*tasks, return_exceptions=True)

            # Finalize batch
            await self._finalize_batch(batch)

            logger.info(f"Batch retry completed: {batch_id}, status: {batch.status.value}")
            return batch

        except Exception as e:
            logger.error(f"Error retrying batch {batch_id}: {e}")
            if 'batch' in locals():
                batch.status = BatchStatus.FAILED
                batch.error_summary = f"Retry failed: {str(e)}"
                await self._update_batch_status(batch)
            raise

    async def get_failed_batches(
        self,
        company_id: str,
        days_back: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Get failed batches that can be retried
        """
        try:
            start_date = datetime.utcnow() - timedelta(days=days_back)

            query = """
            SELECT batch_id, company_id, total_invoices, processed_count,
                   linked_count, errors_count, retry_count, max_retries,
                   status, error_summary, created_at, updated_at
            FROM bulk_invoice_batches
            WHERE company_id = ? AND status IN ('failed', 'partially_failed')
            AND retry_count < max_retries AND created_at >= ?
            ORDER BY created_at DESC
            """

            records = await self.db.fetch_all(query, (company_id, start_date.isoformat()))

            failed_batches = []
            for record in records:
                batch_info = {
                    "batch_id": record["batch_id"],
                    "company_id": record["company_id"],
                    "total_invoices": record["total_invoices"],
                    "processed_count": record["processed_count"],
                    "linked_count": record["linked_count"],
                    "errors_count": record["errors_count"],
                    "retry_count": record["retry_count"],
                    "max_retries": record["max_retries"],
                    "status": record["status"],
                    "error_summary": record["error_summary"],
                    "created_at": record["created_at"],
                    "updated_at": record["updated_at"],
                    "can_retry": record["retry_count"] < record["max_retries"],
                    "failure_rate": record["errors_count"] / record["total_invoices"] if record["total_invoices"] > 0 else 0
                }
                failed_batches.append(batch_info)

            return failed_batches

        except Exception as e:
            logger.error(f"Error getting failed batches: {e}")
            return []

    async def get_retry_recommendations(
        self,
        batch_id: str
    ) -> Dict[str, Any]:
        """
        Get recommendations for retrying a failed batch
        """
        try:
            batch = await self._load_batch_record(batch_id)
            if not batch:
                return {"error": "Batch not found"}

            # Analyze failure patterns
            error_analysis = {}
            failed_items = [item for item in batch.items if item.status == ItemStatus.ERROR]

            for item in failed_items:
                error_code = item.error_code or "unknown"
                if error_code not in error_analysis:
                    error_analysis[error_code] = {
                        "count": 0,
                        "items": [],
                        "avg_amount": 0,
                        "retry_success_probability": 0.8  # Default
                    }

                error_analysis[error_code]["count"] += 1
                error_analysis[error_code]["items"].append(item.filename)

            # Calculate success probability based on error types
            retry_probability = 0.0
            total_failed = len(failed_items)

            if total_failed > 0:
                for error_code, analysis in error_analysis.items():
                    weight = analysis["count"] / total_failed

                    # Adjust probability based on error type
                    if error_code in ["PROCESSING_ERROR", "API_TIMEOUT"]:
                        analysis["retry_success_probability"] = 0.7
                    elif error_code in ["INVALID_AMOUNT", "MISSING_DATA"]:
                        analysis["retry_success_probability"] = 0.3
                    elif error_code in ["SYSTEM_ERROR"]:
                        analysis["retry_success_probability"] = 0.9

                    retry_probability += weight * analysis["retry_success_probability"]

            recommendations = {
                "batch_id": batch_id,
                "can_retry": batch.retry_count < batch.max_retries,
                "retry_count": batch.retry_count,
                "max_retries": batch.max_retries,
                "failed_items_count": len(failed_items),
                "total_items": len(batch.items),
                "retry_success_probability": retry_probability,
                "error_analysis": error_analysis,
                "recommendations": []
            }

            # Generate specific recommendations
            if retry_probability > 0.7:
                recommendations["recommendations"].append("High success probability - recommend full retry")
            elif retry_probability > 0.4:
                recommendations["recommendations"].append("Moderate success probability - recommend selective retry")
            else:
                recommendations["recommendations"].append("Low success probability - review errors before retry")

            if batch.retry_count == 0:
                recommendations["recommendations"].append("First retry attempt - use default settings")
            else:
                recommendations["recommendations"].append("Multiple retry attempts - consider manual review")

            # Specific recommendations based on error patterns
            if "API_TIMEOUT" in error_analysis:
                recommendations["recommendations"].append("API timeout errors detected - reduce concurrent processing")

            if "SYSTEM_ERROR" in error_analysis:
                recommendations["recommendations"].append("System errors detected - likely resolved, retry recommended")

            return recommendations

        except Exception as e:
            logger.error(f"Error getting retry recommendations for {batch_id}: {e}")
            return {"error": str(e)}

    async def schedule_automatic_retry(
        self,
        batch_id: str,
        delay_minutes: int = 30
    ):
        """
        Schedule automatic retry for a failed batch
        """
        try:
            # This would be implemented with a job scheduler in production
            # For now, we'll log the intent
            logger.info(
                f"Automatic retry scheduled for batch {batch_id} in {delay_minutes} minutes"
            )

            # In a real implementation, you would:
            # 1. Use a job scheduler like Celery, APScheduler, or similar
            # 2. Store the retry job information
            # 3. Execute the retry at the scheduled time

            retry_time = datetime.utcnow() + timedelta(minutes=delay_minutes)

            # Update batch with retry schedule info
            await self.db.execute(
                """
                UPDATE bulk_invoice_batches SET
                    batch_metadata = json_patch(
                        COALESCE(batch_metadata, '{}'),
                        ?
                    )
                WHERE batch_id = ?
                """,
                (
                    json.dumps({
                        "auto_retry_scheduled": True,
                        "retry_scheduled_for": retry_time.isoformat(),
                        "retry_delay_minutes": delay_minutes
                    }),
                    batch_id
                )
            )

            return {
                "batch_id": batch_id,
                "retry_scheduled": True,
                "retry_time": retry_time.isoformat(),
                "delay_minutes": delay_minutes
            }

        except Exception as e:
            logger.error(f"Error scheduling automatic retry for {batch_id}: {e}")
            raise

    async def health_check(self) -> bool:
        """Health check del sistema"""
        try:
            if not self.db:
                return False

            # Test database connectivity
            await self.db.fetch_one("SELECT 1")
            return True
        except:
            return False


# Singleton instance
bulk_invoice_processor = BulkInvoiceProcessor()