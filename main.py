"""
Main FastAPI application for MCP Server
This is the entry point for the MCP (Model Context Protocol) Server that acts as
a universal layer between AI agents and business systems.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
import uvicorn
import logging

# Import our core MCP handler
from core.mcp_handler import handle_mcp_request
from config.config import config

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="MCP Server",
    description="Universal layer between AI agents and business systems",
    version="1.0.0",
    docs_url="/docs",  # Swagger UI
    redoc_url="/redoc"  # ReDoc
)


class MCPRequest(BaseModel):
    """
    Pydantic model for MCP request structure.
    """
    method: str
    params: Optional[Dict[str, Any]] = {}


class MCPResponse(BaseModel):
    """
    Pydantic model for MCP response structure.
    """
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@app.get("/")
async def root():
    """
    Root endpoint - health check for the MCP server.

    Returns:
        dict: Status message indicating server is running
    """
    logger.info("Root endpoint accessed")
    return {"status": "MCP Server running"}


@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring.

    Returns:
        dict: Detailed health status
    """
    return {
        "status": "healthy",
        "version": "1.0.0",
        "server": "MCP Server",
        "uptime": "active"
    }


@app.post("/mcp", response_model=MCPResponse)
async def mcp_endpoint(request: MCPRequest):
    """
    Main MCP endpoint that receives method calls and routes them to handlers.

    Args:
        request (MCPRequest): The MCP request containing method and parameters

    Returns:
        MCPResponse: The response from the MCP handler

    Raises:
        HTTPException: If there's an error processing the request
    """
    try:
        logger.info(f"MCP request received - Method: {request.method}, Params: {request.params}")

        # Call the core MCP handler
        result = handle_mcp_request(request.method, request.params)

        # Check if the result contains an error
        if "error" in result:
            logger.warning(f"MCP method error: {result['error']}")
            return MCPResponse(
                success=False,
                error=result["error"]
            )

        logger.info(f"MCP request processed successfully - Method: {request.method}")
        return MCPResponse(
            success=True,
            data=result
        )

    except Exception as e:
        logger.error(f"Unexpected error processing MCP request: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@app.get("/methods")
async def list_supported_methods():
    """
    List all supported MCP methods.

    Returns:
        dict: List of supported methods with descriptions
    """
    supported_methods = {
        "get_inventory": {
            "description": "Get inventory information for a product",
            "parameters": ["product_id", "location (optional)"]
        },
        "create_order": {
            "description": "Create a new order",
            "parameters": ["customer", "items"]
        },
        "create_expense": {
            "description": "Create a new expense record",
            "parameters": ["employee", "amount", "description"]
        }
    }

    return {
        "supported_methods": supported_methods,
        "total_methods": len(supported_methods)
    }


if __name__ == "__main__":
    # Run the server when executed directly
    logger.info(f"Starting MCP Server on {config.HOST}:{config.PORT}")
    uvicorn.run(
        "main:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.DEBUG,
        log_level=config.LOG_LEVEL.lower()
    )