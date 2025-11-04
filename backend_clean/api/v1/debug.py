"""
MCP-Server API v1 - Debug Endpoints
Professional debugging API (restricted in production)
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from typing import List, Optional
from pydantic import BaseModel
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["debug-v1"])

# Response models
class DebugSession(BaseModel):
    session_id: str
    merchant: Optional[str] = None
    checkpoint_count: int
    screenshot_count: int
    last_activity: Optional[str] = None
    status: str

class DebugSessionsResponse(BaseModel):
    sessions: List[DebugSession]
    total_count: int

class Checkpoint(BaseModel):
    id: str
    timestamp: str
    step_name: str
    merchant: Optional[str] = None
    current_url: Optional[str] = None
    screenshot_path: Optional[str] = None
    has_errors: bool
    data: dict

class CheckpointsResponse(BaseModel):
    session_id: str
    checkpoints: List[Checkpoint]
    total_count: int

def check_debug_access():
    """Check if debug endpoints should be accessible"""
    debug_enabled = os.getenv("AUTOMATION_DEBUG", "false").lower() == "true"
    is_production = os.getenv("ENVIRONMENT", "development").lower() == "production"

    if is_production and not debug_enabled:
        raise HTTPException(
            status_code=403,
            detail="Debug endpoints are disabled in production"
        )

@router.get("/sessions", response_model=DebugSessionsResponse, dependencies=[Depends(check_debug_access)])
async def get_debug_sessions():
    """
    Get all debugging sessions

    Note: This endpoint is only available when AUTOMATION_DEBUG=true
    and is automatically disabled in production environments.
    """
    try:
        from modules.invoicing_agent.api import get_debug_sessions

        result = await get_debug_sessions()

        # Transform to v1 format
        sessions = [
            DebugSession(
                session_id=session["session_id"],
                merchant=session.get("merchant"),
                checkpoint_count=session["checkpoint_count"],
                screenshot_count=session["screenshot_count"],
                last_activity=session.get("last_activity"),
                status=session["status"]
            )
            for session in result["sessions"]
        ]

        return DebugSessionsResponse(
            sessions=sessions,
            total_count=len(sessions)
        )

    except Exception as e:
        logger.error(f"Error getting debug sessions: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/sessions/{session_id}/checkpoints", response_model=CheckpointsResponse, dependencies=[Depends(check_debug_access)])
async def get_session_checkpoints(session_id: str):
    """
    Get checkpoints for a specific debug session

    - **session_id**: Debug session identifier
    """
    try:
        from modules.invoicing_agent.api import get_debug_checkpoints

        result = await get_debug_checkpoints(session_id)

        if result.get("session_info", {}).get("status") == "not_found":
            raise HTTPException(status_code=404, detail="Debug session not found")

        # Transform to v1 format
        checkpoints = []
        for checkpoint_data in result["checkpoints"]:
            checkpoint = checkpoint_data.get("checkpoint", {})
            checkpoints.append(Checkpoint(
                id=checkpoint.get("id", ""),
                timestamp=checkpoint.get("timestamp", ""),
                step_name=checkpoint.get("step_name", ""),
                merchant=checkpoint.get("merchant"),
                current_url=checkpoint.get("current_url"),
                screenshot_path=checkpoint.get("screenshot_path"),
                has_errors=bool(checkpoint.get("errors", [])),
                data=checkpoint.get("data", {})
            ))

        return CheckpointsResponse(
            session_id=session_id,
            checkpoints=checkpoints,
            total_count=len(checkpoints)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting checkpoints for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/config")
async def get_debug_config(deps=Depends(check_debug_access)):
    """
    Get current debugging configuration
    """
    return {
        "debug_enabled": os.getenv("AUTOMATION_DEBUG", "false").lower() == "true",
        "pause_on_breakpoint": os.getenv("AUTOMATION_PAUSE_ON_BREAKPOINT", "false").lower() == "true",
        "environment": os.getenv("ENVIRONMENT", "development"),
        "version": "1.0.0"
    }

@router.get("/health")
async def debug_health_check():
    """
    Debug API health check
    """
    return {
        "status": "healthy",
        "debug_enabled": os.getenv("AUTOMATION_DEBUG", "false").lower() == "true",
        "version": "1.0.0",
        "api": "debug-v1"
    }