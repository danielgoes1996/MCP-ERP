"""
Automation Engine v2 API endpoints - Read-only implementation for Week 1.
These endpoints provide read access to the new automation functionality.
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from core.automation_models import (
    AutomationJobResponse,
    AutomationLogEntry,
    AutomationScreenshot,
    AutomationConfigEntry,
    AutomationJobList,
    AutomationHealthResponse,
    AutomationMetricsResponse
)
from core.internal_db import _get_db_path

# Create router for v2 automation endpoints
router = APIRouter(prefix="/api/v2/automation", tags=["automation-v2"])

def get_automation_db():
    """Get database connection for automation queries."""
    return sqlite3.connect(_get_db_path())

def check_automation_feature_enabled():
    """Check if automation engine v2 is enabled via feature flag."""
    try:
        with get_automation_db() as conn:
            conn.row_factory = sqlite3.Row
            result = conn.execute("""
                SELECT value FROM automation_config
                WHERE key = 'automation_engine_enabled' AND is_active = 1
            """).fetchone()

            if result and result['value'].lower() == 'true':
                return True

        # Default to disabled for safety
        return False
    except Exception:
        return False

def automation_feature_required():
    """Dependency to check if automation feature is enabled."""
    if not check_automation_feature_enabled():
        raise HTTPException(
            status_code=503,
            detail="Automation Engine v2 is not enabled for this tenant"
        )

# ===================================================================
# READ-ONLY ENDPOINTS (Week 1 Implementation)
# ===================================================================

@router.get("/health", response_model=AutomationHealthResponse)
async def get_automation_health():
    """
    Get automation system health status.

    Returns health information for all automation components.
    """

    try:
        health_data = {
            "status": "healthy",
            "timestamp": datetime.utcnow(),
            "database": {"status": "unknown"},
            "selenium_grid": {"status": "unknown"},
            "captcha_service": {"status": "unknown"},
            "ocr_backends": {"status": "unknown"},
            "active_jobs": 0,
            "queue_size": 0,
            "error_rate": 0.0,
            "automation_engine_enabled": False
        }

        with get_automation_db() as conn:
            conn.row_factory = sqlite3.Row

            # Check database health
            try:
                conn.execute("SELECT 1 FROM automation_jobs LIMIT 1")
                health_data["database"] = {"status": "healthy"}
            except Exception as e:
                health_data["database"] = {"status": "unhealthy", "error": str(e)}
                health_data["status"] = "degraded"

            # Get active jobs count
            try:
                active_count = conn.execute("""
                    SELECT COUNT(*) FROM automation_jobs
                    WHERE estado IN ('pendiente', 'en_progreso')
                """).fetchone()[0]
                health_data["active_jobs"] = active_count
            except Exception:
                pass

            # Check feature flag
            try:
                result = conn.execute("""
                    SELECT value FROM automation_config
                    WHERE key = 'automation_engine_enabled'
                """).fetchone()
                if result:
                    health_data["automation_engine_enabled"] = result['value'].lower() == 'true'
            except Exception:
                pass

        # Mock external service checks for now
        health_data["selenium_grid"] = {"status": "unknown", "message": "Not implemented in Week 1"}
        health_data["captcha_service"] = {"status": "unknown", "message": "Not implemented in Week 1"}
        health_data["ocr_backends"] = {"status": "unknown", "message": "Not implemented in Week 1"}

        return AutomationHealthResponse(**health_data)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

@router.get("/config", response_model=List[AutomationConfigEntry])
async def get_automation_config(
    scope: Optional[str] = Query(None, description="Filter by scope (global, company, merchant, user)"),
    category: Optional[str] = Query(None, description="Filter by category"),
    active_only: bool = Query(True, description="Only return active configurations")
):
    """
    Get automation configuration entries.

    Returns configuration entries with optional filtering.
    """

    try:
        with get_automation_db() as conn:
            conn.row_factory = sqlite3.Row

            # Build query with filters
            query = "SELECT * FROM automation_config WHERE 1=1"
            params = []

            if scope:
                query += " AND scope = ?"
                params.append(scope)

            if category:
                query += " AND category = ?"
                params.append(category)

            if active_only:
                query += " AND is_active = 1"

            query += " ORDER BY category, key"

            if params:
                rows = conn.execute(query, params).fetchall()
            else:
                rows = conn.execute(query).fetchall()

            configs = []
            for row in rows:
                config_dict = dict(row)
                config_dict['is_active'] = bool(config_dict['is_active'])
                config_dict['is_readonly'] = bool(config_dict['is_readonly'])
                config_dict['updated_at'] = datetime.fromisoformat(config_dict['updated_at'])

                configs.append(AutomationConfigEntry(**config_dict))

            return configs

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch config: {str(e)}")

@router.get("/jobs", response_model=AutomationJobList)
async def get_automation_jobs(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    estado: Optional[str] = Query(None, description="Filter by job state"),
    automation_type: Optional[str] = Query(None, description="Filter by automation type"),
    company_id: Optional[str] = Query("default", description="Company ID filter")
):
    """
    Get paginated list of automation jobs.

    Returns automation jobs with pagination and filtering.
    """

    try:
        with get_automation_db() as conn:
            conn.row_factory = sqlite3.Row

            # Build base query
            base_query = """
                FROM automation_jobs
                WHERE company_id = ?
            """
            params = [company_id]

            if estado:
                base_query += " AND estado = ?"
                params.append(estado)

            if automation_type:
                base_query += " AND automation_type = ?"
                params.append(automation_type)

            # Get total count
            total_query = f"SELECT COUNT(*) {base_query}"
            total = conn.execute(total_query, params).fetchone()[0]

            # Calculate pagination
            total_pages = (total + per_page - 1) // per_page
            offset = (page - 1) * per_page

            # Get jobs for current page
            jobs_query = f"""
                SELECT * {base_query}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """
            params.extend([per_page, offset])

            rows = conn.execute(jobs_query, params).fetchall()

            jobs = []
            for row in rows:
                job_dict = dict(row)

                # Parse JSON fields
                for json_field in ['config', 'result', 'error_details']:
                    if job_dict.get(json_field):
                        try:
                            job_dict[json_field] = json.loads(job_dict[json_field])
                        except json.JSONDecodeError:
                            job_dict[json_field] = None

                # Parse datetime fields
                for dt_field in ['scheduled_at', 'started_at', 'completed_at', 'estimated_completion', 'created_at', 'updated_at']:
                    if job_dict.get(dt_field):
                        try:
                            job_dict[dt_field] = datetime.fromisoformat(job_dict[dt_field])
                        except (ValueError, TypeError):
                            job_dict[dt_field] = None

                # Add HATEOAS links
                job_dict['links'] = {
                    'self': f"/api/v2/automation/jobs/{job_dict['id']}",
                    'logs': f"/api/v2/automation/jobs/{job_dict['id']}/logs",
                    'screenshots': f"/api/v2/automation/jobs/{job_dict['id']}/screenshots",
                    'ticket': f"/api/v1/invoicing/tickets/{job_dict['ticket_id']}"
                }

                jobs.append(AutomationJobResponse(**job_dict))

            return AutomationJobList(
                jobs=jobs,
                total=total,
                page=page,
                per_page=per_page,
                total_pages=total_pages,
                has_next=page < total_pages,
                has_prev=page > 1
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch jobs: {str(e)}")

@router.get("/jobs/{job_id}", response_model=AutomationJobResponse)
async def get_automation_job(job_id: int):
    """
    Get specific automation job by ID.

    Returns detailed information about a single automation job.
    """

    try:
        with get_automation_db() as conn:
            conn.row_factory = sqlite3.Row

            row = conn.execute("""
                SELECT * FROM automation_jobs WHERE id = ?
            """, (job_id,)).fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="Automation job not found")

            job_dict = dict(row)

            # Parse JSON fields
            for json_field in ['config', 'result', 'error_details']:
                if job_dict.get(json_field):
                    try:
                        job_dict[json_field] = json.loads(job_dict[json_field])
                    except json.JSONDecodeError:
                        job_dict[json_field] = None

            # Parse datetime fields
            for dt_field in ['scheduled_at', 'started_at', 'completed_at', 'estimated_completion', 'created_at', 'updated_at']:
                if job_dict.get(dt_field):
                    try:
                        job_dict[dt_field] = datetime.fromisoformat(job_dict[dt_field])
                    except (ValueError, TypeError):
                        job_dict[dt_field] = None

            # Add HATEOAS links
            job_dict['links'] = {
                'self': f"/api/v2/automation/jobs/{job_id}",
                'logs': f"/api/v2/automation/jobs/{job_id}/logs",
                'screenshots': f"/api/v2/automation/jobs/{job_id}/screenshots",
                'ticket': f"/api/v1/invoicing/tickets/{job_dict['ticket_id']}"
            }

            return AutomationJobResponse(**job_dict)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch job: {str(e)}")

@router.get("/jobs/{job_id}/logs", response_model=List[AutomationLogEntry])
async def get_automation_job_logs(
    job_id: int,
    level: Optional[str] = Query(None, description="Filter by log level"),
    category: Optional[str] = Query(None, description="Filter by log category"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of logs to return")
):
    """
    Get logs for a specific automation job.

    Returns log entries with optional filtering.
    """

    try:
        with get_automation_db() as conn:
            conn.row_factory = sqlite3.Row

            # Verify job exists
            job_exists = conn.execute("""
                SELECT id FROM automation_jobs WHERE id = ?
            """, (job_id,)).fetchone()

            if not job_exists:
                raise HTTPException(status_code=404, detail="Automation job not found")

            # Build query with filters
            query = "SELECT * FROM automation_logs WHERE job_id = ?"
            params = [job_id]

            if level:
                query += " AND level = ?"
                params.append(level)

            if category:
                query += " AND category = ?"
                params.append(category)

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(query, params).fetchall()

            logs = []
            for row in rows:
                log_dict = dict(row)

                # Parse JSON data field
                if log_dict.get('data'):
                    try:
                        log_dict['data'] = json.loads(log_dict['data'])
                    except json.JSONDecodeError:
                        log_dict['data'] = None

                # Parse timestamp
                if log_dict.get('timestamp'):
                    try:
                        log_dict['timestamp'] = datetime.fromisoformat(log_dict['timestamp'])
                    except (ValueError, TypeError):
                        log_dict['timestamp'] = datetime.utcnow()

                logs.append(AutomationLogEntry(**log_dict))

            return logs

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch logs: {str(e)}")

@router.get("/jobs/{job_id}/screenshots", response_model=List[AutomationScreenshot])
async def get_automation_job_screenshots(
    job_id: int,
    screenshot_type: Optional[str] = Query(None, description="Filter by screenshot type"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of screenshots to return")
):
    """
    Get screenshots for a specific automation job.

    Returns screenshot metadata with optional filtering.
    """

    try:
        with get_automation_db() as conn:
            conn.row_factory = sqlite3.Row

            # Verify job exists
            job_exists = conn.execute("""
                SELECT id FROM automation_jobs WHERE id = ?
            """, (job_id,)).fetchone()

            if not job_exists:
                raise HTTPException(status_code=404, detail="Automation job not found")

            # Build query with filters
            query = "SELECT * FROM automation_screenshots WHERE job_id = ?"
            params = [job_id]

            if screenshot_type:
                query += " AND screenshot_type = ?"
                params.append(screenshot_type)

            query += " ORDER BY created_at ASC LIMIT ?"
            params.append(limit)

            rows = conn.execute(query, params).fetchall()

            screenshots = []
            for row in rows:
                screenshot_dict = dict(row)

                # Parse JSON fields
                for json_field in ['detected_elements', 'manual_annotations']:
                    if screenshot_dict.get(json_field):
                        try:
                            screenshot_dict[json_field] = json.loads(screenshot_dict[json_field])
                        except json.JSONDecodeError:
                            screenshot_dict[json_field] = None

                # Parse boolean fields
                screenshot_dict['has_captcha'] = bool(screenshot_dict.get('has_captcha', False))
                screenshot_dict['is_sensitive'] = bool(screenshot_dict.get('is_sensitive', False))

                # Parse datetime
                if screenshot_dict.get('created_at'):
                    try:
                        screenshot_dict['created_at'] = datetime.fromisoformat(screenshot_dict['created_at'])
                    except (ValueError, TypeError):
                        screenshot_dict['created_at'] = datetime.utcnow()

                screenshots.append(AutomationScreenshot(**screenshot_dict))

            return screenshots

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch screenshots: {str(e)}")

@router.get("/metrics", response_model=AutomationMetricsResponse)
async def get_automation_metrics(
    timeframe: str = Query("24h", description="Timeframe for metrics (1h, 24h, 7d, 30d)")
):
    """
    Get automation system metrics.

    Returns aggregated metrics for the specified timeframe.
    """

    # Parse timeframe
    timeframe_hours = {
        "1h": 1,
        "24h": 24,
        "7d": 24 * 7,
        "30d": 24 * 30
    }.get(timeframe, 24)

    since = datetime.utcnow() - timedelta(hours=timeframe_hours)

    try:
        with get_automation_db() as conn:
            conn.row_factory = sqlite3.Row

            # Get job counts by status
            job_stats = conn.execute("""
                SELECT estado, COUNT(*) as count
                FROM automation_jobs
                WHERE datetime(created_at) >= datetime(?)
                GROUP BY estado
            """, (since.isoformat(),)).fetchall()

            # Initialize metrics
            metrics = {
                "timeframe": timeframe,
                "timestamp": datetime.utcnow(),
                "jobs_completed": 0,
                "jobs_failed": 0,
                "jobs_cancelled": 0,
                "avg_processing_time_seconds": 0.0,
                "overall_success_rate": 0.0,
                "success_rate_by_merchant": {},
                "avg_ocr_confidence": 0.0,
                "ocr_fallback_rate": 0.0,
                "captcha_solve_rate": 1.0,  # Mock data for Week 1
                "avg_captcha_solve_time_seconds": 15.0,  # Mock data
                "avg_queue_wait_time_seconds": 2.0,  # Mock data
                "peak_concurrent_jobs": 0
            }

            # Process job statistics
            total_jobs = 0
            for stat in job_stats:
                count = stat['count']
                total_jobs += count

                if stat['estado'] == 'completado':
                    metrics["jobs_completed"] = count
                elif stat['estado'] == 'fallido':
                    metrics["jobs_failed"] = count
                elif stat['estado'] == 'cancelado':
                    metrics["jobs_cancelled"] = count

            # Calculate success rate
            if total_jobs > 0:
                metrics["overall_success_rate"] = metrics["jobs_completed"] / total_jobs

            # Get average processing time for completed jobs
            avg_time = conn.execute("""
                SELECT AVG(
                    (julianday(completed_at) - julianday(started_at)) * 86400
                ) as avg_seconds
                FROM automation_jobs
                WHERE estado = 'completado'
                AND started_at IS NOT NULL
                AND completed_at IS NOT NULL
                AND datetime(created_at) >= datetime(?)
            """, (since.isoformat(),)).fetchone()

            if avg_time and avg_time['avg_seconds']:
                metrics["avg_processing_time_seconds"] = float(avg_time['avg_seconds'])

            # Get average OCR confidence
            avg_confidence = conn.execute("""
                SELECT AVG(ocr_confidence) as avg_confidence
                FROM automation_jobs
                WHERE ocr_confidence IS NOT NULL
                AND datetime(created_at) >= datetime(?)
            """, (since.isoformat(),)).fetchone()

            if avg_confidence and avg_confidence['avg_confidence']:
                metrics["avg_ocr_confidence"] = float(avg_confidence['avg_confidence'])

            return AutomationMetricsResponse(**metrics)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch metrics: {str(e)}")

# ===================================================================
# FEATURE FLAG CHECK ENDPOINT
# ===================================================================

@router.get("/feature-status")
async def get_automation_feature_status():
    """
    Check if automation engine v2 is enabled.

    Returns feature flag status and basic info.
    """

    try:
        enabled = check_automation_feature_enabled()

        # Get additional status info
        with get_automation_db() as conn:
            conn.row_factory = sqlite3.Row

            # Get config info
            configs = conn.execute("""
                SELECT key, value, category FROM automation_config
                WHERE is_active = 1
                ORDER BY category, key
            """).fetchall()

            # Get table counts
            table_counts = {}
            for table in ['automation_jobs', 'automation_logs', 'automation_screenshots']:
                count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                table_counts[table] = count

        return {
            "automation_engine_v2_enabled": enabled,
            "migration_applied": True,
            "database_tables": table_counts,
            "active_configs": len(configs),
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        return {
            "automation_engine_v2_enabled": False,
            "migration_applied": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }