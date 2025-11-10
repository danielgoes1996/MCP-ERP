"""
API endpoints for Bulk Invoice Processing
Implementing Point 14 improvements for enterprise-grade bulk invoice matching
"""

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging

from core.api_models import (
    BulkInvoiceMatchRequest, BulkInvoiceMatchResponse,
    BulkInvoiceProcessingStatus, BulkInvoiceDetailedResults,
    BulkInvoiceAnalyticsRequest, BulkInvoiceAnalyticsResponse,
    BulkProcessingRule, BulkProcessingRuleResponse,
    InvoiceMatchResult, BulkInvoiceItemResult
)
from core.expenses.invoices.bulk_invoice_processor import bulk_invoice_processor
from core.shared.unified_db_adapter import get_db_adapter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/bulk-invoice", tags=["bulk-invoice-processing"])

# =========================================================
# CORE BULK PROCESSING ENDPOINTS
# =========================================================

@router.post("/process-batch", response_model=BulkInvoiceMatchResponse)
async def process_invoice_batch(
    request: BulkInvoiceMatchRequest,
    background_tasks: BackgroundTasks
):
    """
    Process a batch of invoices with enterprise-grade tracking and metrics
    """
    try:
        db = get_db_adapter()

        if not bulk_invoice_processor.db:
            await bulk_invoice_processor.initialize(db)

        # Validate request
        if not request.invoices:
            raise HTTPException(status_code=400, detail="No invoices provided for processing")

        # Convert invoice inputs to dict format
        invoices_data = []
        for invoice in request.invoices:
            invoice_dict = {
                "filename": invoice.filename,
                "uuid": invoice.uuid,
                "total": invoice.total,
                "subtotal": invoice.subtotal,
                "iva_amount": invoice.iva_amount,
                "currency": invoice.currency,
                "issued_date": invoice.issued_at,
                "provider_name": invoice.provider_name,
                "provider_rfc": invoice.provider_rfc,
                "raw_xml": getattr(invoice, 'raw_xml', None)
            }
            invoices_data.append(invoice_dict)

        logger.info(f"Creating bulk invoice batch for {len(invoices_data)} invoices")

        # Prepare batch metadata with placeholder creation flag
        batch_metadata = request.batch_metadata or {}
        batch_metadata["create_placeholder_on_no_match"] = request.create_placeholder_on_no_match

        # Create batch
        batch = await bulk_invoice_processor.create_batch(
            company_id=request.company_id,
            invoices=invoices_data,
            auto_link_threshold=request.auto_link_threshold,
            auto_mark_invoiced=request.auto_mark_invoiced,
            batch_metadata=batch_metadata,
            created_by=1  # TODO: Get from authentication context
        )

        # Start processing in background
        background_tasks.add_task(
            _process_batch_background,
            batch.batch_id,
            request.max_concurrent_items
        )

        # Convert items to API format
        api_results = []
        for item in batch.items:
            result = InvoiceMatchResult(
                filename=item.filename,
                status="pending",  # Initial status
                message="Batch created successfully, processing started",
                confidence=None
            )
            api_results.append(result)

        return BulkInvoiceMatchResponse(
            company_id=batch.company_id,
            batch_id=batch.batch_id,
            processed=0,  # Just started
            linked=0,
            no_matches=0,
            errors=0,
            results=api_results,
            processing_time_ms=0,
            batch_metadata=batch.batch_metadata,
            status="processing",
            started_at=batch.created_at
        )

    except Exception as e:
        logger.error(f"Error creating bulk invoice batch: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/batch/{batch_id}/status", response_model=BulkInvoiceProcessingStatus)
async def get_batch_status(batch_id: str):
    """
    Get current status of a batch processing operation
    """
    try:
        status = await bulk_invoice_processor.get_batch_status(batch_id)

        if not status:
            raise HTTPException(status_code=404, detail="Batch not found")

        # Calculate estimated completion time
        estimated_completion = None
        if status.get("status") == "processing" and status.get("processed_count", 0) > 0:
            total = status.get("total_invoices", 0)
            processed = status.get("processed_count", 0)
            processing_time_ms = status.get("processing_time_ms", 0)

            if processed > 0 and total > processed and processing_time_ms > 0:
                avg_time_per_item = processing_time_ms / processed
                remaining_items = total - processed
                remaining_time_ms = remaining_items * avg_time_per_item
                estimated_completion = datetime.utcnow() + timedelta(milliseconds=remaining_time_ms)

        return BulkInvoiceProcessingStatus(
            batch_id=status["batch_id"],
            status=status["status"],
            total_invoices=status["total_invoices"],
            processed_count=status["processed_count"],
            linked_count=status["linked_count"],
            no_matches_count=status["no_matches_count"],
            errors_count=status["errors_count"],
            success_rate=status.get("success_rate"),
            processing_time_ms=status.get("processing_time_ms"),
            started_at=datetime.fromisoformat(status["started_at"]) if status.get("started_at") else None,
            completed_at=datetime.fromisoformat(status["completed_at"]) if status.get("completed_at") else None,
            progress_percent=status["progress_percent"],
            estimated_completion_time=estimated_completion
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting batch status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/batch/{batch_id}/results", response_model=BulkInvoiceDetailedResults)
async def get_batch_results(batch_id: str):
    """
    Get detailed results of a completed batch processing operation
    """
    try:
        results = await bulk_invoice_processor.get_batch_results(batch_id)

        if not results:
            raise HTTPException(status_code=404, detail="Batch not found")

        # Convert items to API format
        api_items = []
        for item in results.get("items", []):
            api_item = BulkInvoiceItemResult(
                filename=item["filename"],
                uuid=item["uuid"],
                total_amount=item["total_amount"],
                status=item["status"],
                processing_time_ms=item["processing_time_ms"],
                matched_expense_id=item["matched_expense_id"],
                match_confidence=item["match_confidence"],
                match_method=item["match_method"],
                candidates_found=item["candidates_found"],
                error_message=item["error_message"]
            )
            api_items.append(api_item)

        return BulkInvoiceDetailedResults(
            batch_id=results["batch_id"],
            company_id=results["company_id"],
            status=results["status"],
            summary=results["summary"],
            items=api_items,
            performance_metrics=results.get("performance_metrics"),
            processing_phases=results.get("processing_phases")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting batch results: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================
# BATCH MANAGEMENT ENDPOINTS
# =========================================================

@router.get("/batches", response_model=List[BulkInvoiceProcessingStatus])
async def list_batches(
    company_id: str = "default",
    status: Optional[str] = None,
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0)
):
    """
    List batch processing operations with filtering
    """
    try:
        db = get_db_adapter()

        # Build query
        where_conditions = ["company_id = ?"]
        params = [company_id]

        if status:
            where_conditions.append("status = ?")
            params.append(status)

        query = f"""
        SELECT batch_id, status, total_invoices, processed_count, linked_count,
               no_matches_count, errors_count, success_rate, processing_time_ms,
               started_at, completed_at, created_at
        FROM bulk_invoice_batches
        WHERE {' AND '.join(where_conditions)}
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
        """

        params.extend([limit, offset])
        records = await db.fetch_all(query, params)

        batches = []
        for record in records:
            progress_percent = 0.0
            if record["total_invoices"] > 0:
                progress_percent = (record["processed_count"] / record["total_invoices"]) * 100

            batch_status = BulkInvoiceProcessingStatus(
                batch_id=record["batch_id"],
                status=record["status"],
                total_invoices=record["total_invoices"],
                processed_count=record["processed_count"],
                linked_count=record["linked_count"],
                no_matches_count=record["no_matches_count"],
                errors_count=record["errors_count"],
                success_rate=float(record["success_rate"]) if record["success_rate"] else None,
                processing_time_ms=record["processing_time_ms"],
                started_at=datetime.fromisoformat(record["started_at"]) if record["started_at"] else None,
                completed_at=datetime.fromisoformat(record["completed_at"]) if record["completed_at"] else None,
                progress_percent=progress_percent
            )
            batches.append(batch_status)

        return batches

    except Exception as e:
        logger.error(f"Error listing batches: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/batch/{batch_id}")
async def cancel_batch(batch_id: str):
    """
    Cancel a running batch processing operation
    """
    try:
        db = get_db_adapter()

        # Check if batch exists and is cancellable
        batch_query = "SELECT status FROM bulk_invoice_batches WHERE batch_id = ?"
        batch = await db.fetch_one(batch_query, (batch_id,))

        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")

        if batch["status"] in ["completed", "failed", "cancelled"]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot cancel batch with status: {batch['status']}"
            )

        # Update status to cancelled
        await db.execute(
            "UPDATE bulk_invoice_batches SET status = 'cancelled', updated_at = ? WHERE batch_id = ?",
            (datetime.utcnow().isoformat(), batch_id)
        )

        return {"message": "Batch cancelled successfully", "batch_id": batch_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling batch: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================
# ANALYTICS AND REPORTING ENDPOINTS
# =========================================================

@router.post("/analytics", response_model=BulkInvoiceAnalyticsResponse)
async def get_bulk_processing_analytics(request: BulkInvoiceAnalyticsRequest):
    """
    Get detailed analytics for bulk invoice processing
    """
    try:
        db = get_db_adapter()

        # Get volume metrics
        volume_query = """
        SELECT
            COUNT(*) as total_batches,
            SUM(total_invoices) as total_invoices_processed,
            COUNT(CASE WHEN status = 'completed' THEN 1 END) as successful_batches,
            COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_batches
        FROM bulk_invoice_batches
        WHERE company_id = ? AND created_at BETWEEN ? AND ?
        """

        volume_data = await db.fetch_one(volume_query, (
            request.company_id,
            request.period_start.isoformat(),
            request.period_end.isoformat()
        ))

        # Get performance metrics
        performance_query = """
        SELECT
            AVG(processing_time_ms) as avg_processing_time_ms,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY processing_time_ms) as median_processing_time_ms,
            AVG(throughput_invoices_per_second) * 3600 as avg_throughput_per_hour
        FROM bulk_invoice_batches
        WHERE company_id = ? AND created_at BETWEEN ? AND status = 'completed'
        """

        performance_data = await db.fetch_one(performance_query, (
            request.company_id,
            request.period_start.isoformat(),
            request.period_end.isoformat()
        ))

        # Get quality metrics
        quality_query = """
        SELECT
            AVG(success_rate) as avg_success_rate,
            AVG(CASE WHEN linked_count > 0 THEN linked_count::float / processed_count END) as auto_match_rate
        FROM bulk_invoice_batches
        WHERE company_id = ? AND created_at BETWEEN ? AND processed_count > 0
        """

        quality_data = await db.fetch_one(quality_query, (
            request.company_id,
            request.period_start.isoformat(),
            request.period_end.isoformat()
        ))

        # Get daily stats if requested
        daily_stats = None
        if "day" in request.group_by:
            daily_query = """
            SELECT
                DATE(created_at) as date,
                COUNT(*) as batches,
                SUM(total_invoices) as invoices,
                AVG(success_rate) as avg_success_rate,
                AVG(processing_time_ms) as avg_processing_time_ms
            FROM bulk_invoice_batches
            WHERE company_id = ? AND created_at BETWEEN ? AND ?
            GROUP BY DATE(created_at)
            ORDER BY date
            """

            daily_records = await db.fetch_all(daily_query, (
                request.company_id,
                request.period_start.isoformat(),
                request.period_end.isoformat()
            ))

            daily_stats = [
                {
                    "date": record["date"],
                    "batches": record["batches"],
                    "invoices": record["invoices"],
                    "avg_success_rate": float(record["avg_success_rate"]) if record["avg_success_rate"] else None,
                    "avg_processing_time_ms": float(record["avg_processing_time_ms"]) if record["avg_processing_time_ms"] else None
                } for record in daily_records
            ]

        # Get error analysis if requested
        most_common_errors = None
        error_rate = None
        if request.include_error_analysis:
            error_query = """
            SELECT
                error_code,
                COUNT(*) as error_count
            FROM bulk_invoice_batch_items
            WHERE batch_id IN (
                SELECT batch_id FROM bulk_invoice_batches
                WHERE company_id = ? AND created_at BETWEEN ? AND ?
            ) AND item_status = 'error' AND error_code IS NOT NULL
            GROUP BY error_code
            ORDER BY error_count DESC
            LIMIT 10
            """

            error_records = await db.fetch_all(error_query, (
                request.company_id,
                request.period_start.isoformat(),
                request.period_end.isoformat()
            ))

            most_common_errors = {
                record["error_code"]: record["error_count"]
                for record in error_records
            }

            # Calculate error rate
            total_items_query = """
            SELECT COUNT(*) as total_items,
                   COUNT(CASE WHEN item_status = 'error' THEN 1 END) as error_items
            FROM bulk_invoice_batch_items
            WHERE batch_id IN (
                SELECT batch_id FROM bulk_invoice_batches
                WHERE company_id = ? AND created_at BETWEEN ? AND ?
            )
            """

            error_data = await db.fetch_one(total_items_query, (
                request.company_id,
                request.period_start.isoformat(),
                request.period_end.isoformat()
            ))

            if error_data and error_data["total_items"] > 0:
                error_rate = error_data["error_items"] / error_data["total_items"]

        return BulkInvoiceAnalyticsResponse(
            company_id=request.company_id,
            period_start=request.period_start,
            period_end=request.period_end,
            total_batches=volume_data["total_batches"] if volume_data else 0,
            total_invoices_processed=volume_data["total_invoices_processed"] if volume_data else 0,
            successful_batches=volume_data["successful_batches"] if volume_data else 0,
            failed_batches=volume_data["failed_batches"] if volume_data else 0,
            avg_processing_time_ms=float(performance_data["avg_processing_time_ms"]) if performance_data and performance_data["avg_processing_time_ms"] else None,
            median_processing_time_ms=float(performance_data["median_processing_time_ms"]) if performance_data and performance_data["median_processing_time_ms"] else None,
            throughput_invoices_per_hour=float(performance_data["avg_throughput_per_hour"]) if performance_data and performance_data["avg_throughput_per_hour"] else None,
            avg_success_rate=float(quality_data["avg_success_rate"]) if quality_data and quality_data["avg_success_rate"] else None,
            auto_match_rate=float(quality_data["auto_match_rate"]) if quality_data and quality_data["auto_match_rate"] else None,
            error_rate=error_rate,
            most_common_errors=most_common_errors,
            daily_stats=daily_stats
        )

    except Exception as e:
        logger.error(f"Error generating bulk processing analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance-summary")
async def get_performance_summary(
    company_id: str = "default",
    days: int = Query(30, ge=1, le=90)
):
    """
    Get performance summary for bulk processing operations
    """
    try:
        db = get_db_adapter()

        start_date = datetime.utcnow() - timedelta(days=days)

        query = """
        SELECT
            COUNT(*) as total_batches,
            COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_batches,
            COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_batches,
            COUNT(CASE WHEN status = 'processing' THEN 1 END) as active_batches,
            SUM(total_invoices) as total_invoices,
            SUM(linked_count) as total_linked,
            SUM(errors_count) as total_errors,
            AVG(success_rate) as avg_success_rate,
            AVG(processing_time_ms) / 1000.0 as avg_processing_seconds,
            AVG(throughput_invoices_per_second) as avg_throughput,
            MAX(throughput_invoices_per_second) as peak_throughput
        FROM bulk_invoice_batches
        WHERE company_id = ? AND created_at >= ?
        """

        result = await db.fetch_one(query, (company_id, start_date.isoformat()))

        if not result:
            return {
                "summary": "No batch processing data found for the specified period",
                "total_batches": 0
            }

        return {
            "period_days": days,
            "total_batches": result["total_batches"],
            "completed_batches": result["completed_batches"],
            "failed_batches": result["failed_batches"],
            "active_batches": result["active_batches"],
            "completion_rate": result["completed_batches"] / result["total_batches"] if result["total_batches"] > 0 else 0,
            "total_invoices_processed": result["total_invoices"],
            "total_invoices_linked": result["total_linked"],
            "total_errors": result["total_errors"],
            "avg_success_rate": float(result["avg_success_rate"]) if result["avg_success_rate"] else 0,
            "avg_processing_time_seconds": float(result["avg_processing_seconds"]) if result["avg_processing_seconds"] else 0,
            "avg_throughput_ips": float(result["avg_throughput"]) if result["avg_throughput"] else 0,
            "peak_throughput_ips": float(result["peak_throughput"]) if result["peak_throughput"] else 0,
            "error_rate": result["total_errors"] / result["total_invoices"] if result["total_invoices"] and result["total_invoices"] > 0 else 0
        }

    except Exception as e:
        logger.error(f"Error getting performance summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================
# PROCESSING RULES ENDPOINTS
# =========================================================

@router.post("/rules", response_model=BulkProcessingRuleResponse)
async def create_processing_rule(request: BulkProcessingRule):
    """
    Create a new bulk processing rule
    """
    try:
        db = get_db_adapter()

        # Insert new rule
        query = """
        INSERT INTO bulk_processing_rules (
            company_id, rule_name, rule_code, rule_type, conditions,
            actions, priority, is_active, max_batch_size, parallel_processing,
            timeout_seconds, created_by, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        RETURNING id
        """

        rule_id = await db.fetch_val(query, (
            "default",  # TODO: Get from context
            request.rule_name,
            request.rule_code,
            request.rule_type,
            json.dumps(request.conditions),
            json.dumps(request.actions),
            request.priority,
            request.is_active,
            request.max_batch_size,
            request.parallel_processing,
            request.timeout_seconds,
            1,  # TODO: Get from authentication
            datetime.utcnow().isoformat()
        ))

        return BulkProcessingRuleResponse(
            id=rule_id,
            company_id="default",
            rule_name=request.rule_name,
            rule_code=request.rule_code,
            rule_type=request.rule_type,
            conditions=request.conditions,
            actions=request.actions,
            priority=request.priority,
            is_active=request.is_active,
            max_batch_size=request.max_batch_size,
            parallel_processing=request.parallel_processing,
            timeout_seconds=request.timeout_seconds,
            created_by=1,
            created_at=datetime.utcnow(),
            usage_count=0
        )

    except Exception as e:
        logger.error(f"Error creating processing rule: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rules", response_model=List[BulkProcessingRuleResponse])
async def list_processing_rules(
    company_id: str = "default",
    rule_type: Optional[str] = None,
    active_only: bool = True,
    limit: int = Query(50, le=200)
):
    """
    List bulk processing rules
    """
    try:
        db = get_db_adapter()

        # Build query
        where_conditions = ["company_id = ?"]
        params = [company_id]

        if rule_type:
            where_conditions.append("rule_type = ?")
            params.append(rule_type)

        if active_only:
            where_conditions.append("is_active = true")

        query = f"""
        SELECT * FROM bulk_processing_rules
        WHERE {' AND '.join(where_conditions)}
        ORDER BY priority ASC, created_at DESC
        LIMIT ?
        """

        params.append(limit)
        records = await db.fetch_all(query, params)

        rules = []
        for record in records:
            rule = BulkProcessingRuleResponse(
                id=record["id"],
                company_id=record["company_id"],
                rule_name=record["rule_name"],
                rule_code=record["rule_code"],
                rule_type=record["rule_type"],
                conditions=json.loads(record["conditions"]) if record["conditions"] else {},
                actions=json.loads(record["actions"]) if record["actions"] else {},
                priority=record["priority"],
                is_active=record["is_active"],
                max_batch_size=record["max_batch_size"],
                parallel_processing=record["parallel_processing"],
                timeout_seconds=record["timeout_seconds"],
                created_by=record["created_by"],
                created_at=datetime.fromisoformat(record["created_at"]),
                updated_at=datetime.fromisoformat(record["updated_at"]) if record["updated_at"] else None,
                last_used_at=datetime.fromisoformat(record["last_used_at"]) if record["last_used_at"] else None,
                usage_count=record["usage_count"]
            )
            rules.append(rule)

        return rules

    except Exception as e:
        logger.error(f"Error listing processing rules: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================
# HEALTH CHECK
# =========================================================

@router.get("/health")
async def health_check():
    """Health check endpoint for bulk invoice processing system"""
    try:
        # Test system components
        db_status = await bulk_invoice_processor.health_check()

        return {
            "status": "healthy" if db_status else "degraded",
            "timestamp": datetime.utcnow().isoformat(),
            "components": {
                "database": "healthy" if db_status else "unhealthy",
                "bulk_processor": "healthy",
                "background_tasks": "healthy"
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }
        )


# =========================================================
# BACKGROUND TASK FUNCTIONS
# =========================================================

async def _process_batch_background(batch_id: str, max_concurrent_items: Optional[int]):
    """Process batch in background task"""
    try:
        await bulk_invoice_processor.process_batch(batch_id, max_concurrent_items)
        logger.info(f"Background batch processing completed: {batch_id}")
    except Exception as e:
        logger.error(f"Background batch processing failed for {batch_id}: {e}")


# =========================================================
# UTILITY FUNCTIONS
# =========================================================

import json  # Add this import at the top if not already present