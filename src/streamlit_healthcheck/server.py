# -*- coding: utf-8 -*-
"""
This module implements a FastAPI server for monitoring the health of a Streamlit application.

Features:

- Provides REST API endpoints to report health status of system resources, dependencies, and Streamlit pages.
- Uses a configurable health check service to gather health data.
- Supports startup and shutdown events for proper initialization and cleanup of the health check service.
- Includes endpoints:
    - `/health`: Returns complete health status.
    - `/health/system`: Returns system resource health (CPU, Memory, Disk).
    - `/health/dependencies`: Returns dependencies health status.
    - `/health/pages`: Returns Streamlit pages health status.
- Configurable via command-line arguments for host, port, and health check config file.
- Uses logging for operational visibility.

Global Variables:

- `health_service`: Instance of HealthCheckService, manages health checks.
- `config_file`: Path to health check configuration file.

Usage:

Run as a standalone server or import as a module.
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional
import uvicorn
from .healthcheck import HealthCheckService
import logging
import argparse
from contextlib import asynccontextmanager



# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # Prints to console
    ]
)
logger = logging.getLogger(__name__)

# Initialize health check service as global variable
health_service: Optional[HealthCheckService] = None
config_file: Optional[str] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI application"""
    # Startup
    global health_service
    logger.info("Initializing health check service")
    config_path = config_file if config_file is not None else "health_check_config.json"
    health_service = HealthCheckService(config_path=config_path)
    health_service.start()
    
    yield
    
    # Shutdown
    if health_service:
        logger.info("Stopping health check service")
        health_service.stop()


app = FastAPI(
    title="Streamlit Health Check API",
    description="API endpoints for monitoring Streamlit application health",
    version="1.0.0",
    lifespan=lifespan
)

# Root endpoint providing service metadata and available endpoints
@app.get("/", response_model=Dict[str, Any])
async def root():
    """Asynchronous handler for the application root ("/") endpoint.
    Returns a JSONResponse containing basic service metadata intended for health
    checks and simple API discovery. The returned JSON includes the service name,
    version, a short description, and a mapping of available health-related
    endpoints.
    
    Returns:
    
        JSONResponse: HTTP 200 response with a JSON body.
        
    Notes:
    
        - This function is asynchronous and suitable for use with Starlette or FastAPI.
        - No input parameters are required.
    """
    
    return JSONResponse(
        content={
            "service": "streamlit-healthcheck",
            "version": "1.0.0",
            "description": "API for monitoring Streamlit application health",
            "endpoints": {
                "health": "/health",
                "system": "/health/system",
                "dependencies": "/health/dependencies",
                "pages": "/health/pages"
            }
        }
    )

# Initialize health check service and config file path as global variables
# health_service and config_file are already defined above


@app.get("/health", response_model=Dict[str, Any])
async def get_health_status():
    """
    Asynchronous endpoint that retrieves and returns the application's health status as a JSON response.
    This coroutine uses the module-level `health_service` to obtain health data and returns it wrapped in a
    fastapi.responses.JSONResponse. It logs unexpected errors and maps them to appropriate HTTP error responses.
    
    Behavior:
    
    - If the global `health_service` is not initialized or falsy, raises HTTPException(status_code=503).
    - If `health_service.get_health_data()` succeeds, returns a JSONResponse with the health data (typically a dict).
    - If any exception occurs while obtaining health data, the exception is logged and an HTTPException(status_code=500) is raised with the original error message.
    
    Returns:
    
            fastapi.responses.JSONResponse: A JSONResponse containing the health data returned by `health_service.get_health_data()`.
    
    Raises:
    
            fastapi.HTTPException: With status_code=503 when the health service is not initialized.
            fastapi.HTTPException: With status_code=500 when an unexpected error occurs while retrieving health data.
    """
    
    global health_service
    if not health_service:
        raise HTTPException(status_code=503, detail="Health check service not initialized")
    
    try:
        health_data = health_service.get_health_data()
        return JSONResponse(content=health_data)
    except Exception as e:
        logger.error(f"Error getting health data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health/system", response_model=Dict[str, Any])
async def get_system_health():
    """
    Asynchronously retrieve the system health payload from the global health service and return it
    as a JSONResponse suitable for use in a FastAPI/Starlette endpoint.
    
    Behavior:
    
    - Verifies that the module-level 'health_service' is initialized; if not, raises HTTPException(503).
    - Calls health_service.get_health_data() to obtain health information.
    - Extracts the "system" sub-dictionary from the returned health data (defaults to an empty dict).
    - Returns a fastapi.responses.JSONResponse with content {"system": <system_data>}.
    - If any unexpected error occurs while obtaining or processing health data, logs the error and
        raises HTTPException(500) with the error message.
        
    Returns:
    
            fastapi.responses.JSONResponse: JSON response containing the "system" health data.
            
    Raises:
    
            HTTPException: with status_code=503 if the health service is not initialized.
            HTTPException: with status_code=500 if an unexpected error occurs while retrieving health data.
            
    Notes:
    
    - Relies on the module-level 'health_service' and 'logger' variables.
    - Designed to be used as an async request handler in a web application.
    """
    global health_service
    if not health_service:
        raise HTTPException(status_code=503, detail="Health check service not initialized")
    
    try:
        health_data = health_service.get_health_data()
        return JSONResponse(content={"system": health_data.get("system", {})})
    except Exception as e:
        logger.error(f"Error getting system health data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health/dependencies", response_model=Dict[str, Any])
async def get_dependencies_health():
    """
    Asynchronously retrieve and return the health status of external dependencies.
    This function relies on a module-level `health_service` object. If the service is
    not initialized, it raises an HTTPException with status 503. Otherwise it calls
    `health_service.get_health_data()` and returns a JSONResponse containing the
    "dependencies" entry from the returned health data (an empty dict is returned
    if that key is missing). Any unexpected error during retrieval is logged and
    propagated as an HTTPException with status 500.
    
    Returns:
    
        JSONResponse: A JSON response with the shape {"dependencies": {...}}.
        
    Raises:
    
        HTTPException: 503 if the global health_service is not initialized.
        HTTPException: 500 for any unexpected error while fetching health data.
        
    Notes:
    
        - The function is asynchronous but calls a synchronous `get_health_data()` on
          the health service; the service implementation should be safe to call from
          an async context.
        - Errors are logged using the module-level `logger`.
    """
    
    global health_service
    if not health_service:
        raise HTTPException(status_code=503, detail="Health check service not initialized")
    
    try:
        health_data = health_service.get_health_data()
        return JSONResponse(content={"dependencies": health_data.get("dependencies", {})})
    except Exception as e:
        logger.error(f"Error getting dependencies health data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health/pages", response_model=Dict[str, Any])
async def get_pages_health():
    """
    Asynchronously run health checks and return the health status for Streamlit pages.
    This coroutine depends on a module-level `health_service` which must be initialized
    before calling. It triggers a fresh health check by calling `health_service.run_all_checks()`
    and then retrieves the aggregated health data via `health_service.get_health_data()`.
    Only the "streamlit_pages" portion of the health data is returned in a FastAPI
    JSONResponse (defaults to an empty dict if the key is absent).
    
    Returns:
    
        fastapi.responses.JSONResponse: A JSON response with the shape
            {"streamlit_pages": {...}}.
            
    Raises:
    
        fastapi.HTTPException: If `health_service` is not initialized (status_code=503).
        fastapi.HTTPException: If any unexpected error occurs while running checks or
            retrieving data (status_code=500). The exception detail contains the original
            error message.
            
    Side effects:
    
        - Calls `health_service.run_all_checks()` which may perform I/O or long-running checks.
        - Logs errors to the module logger when exceptions occur.
        
    Notes:
    
        - This function is intended to be used in an ASGI/FastAPI context and must be awaited.
        - Only the `"streamlit_pages"` key from the health payload is exposed to the caller.
    """
    
    global health_service
    if not health_service:
        raise HTTPException(status_code=503, detail="Health check service not initialized")
    
    try:
        health_service.run_all_checks()
        health_data = health_service.get_health_data()
        return JSONResponse(content={"streamlit_pages": health_data.get("streamlit_pages", {})})
    except Exception as e:
        logger.error(f"Error getting pages health data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def start_api_server(host: str = "0.0.0.0", port: int = 8000, config: str = "health_check_config.json"):
    """
    Start the API server using uvicorn and set the global configuration file.
    Sets the module-level variable `config_file` to the provided `config` path
    and then starts the ASGI server by calling `uvicorn.run(app, host=host, port=port)`.
    The call is blocking and will run until the server is stopped.
    
    Parameters
    ----------
    
    host : str, optional
        Host interface to bind the server to. Defaults to "0.0.0.0" (all interfaces).
    port : int, optional
        TCP port to listen on. Defaults to 8000.
    config : str, optional
        Path to the health check configuration file. Defaults to "health_check_config.json".
        This value is assigned to the module-level `config_file` variable before the server starts.
        
    Returns
    -------
    
    None
        This function does not return; it blocks while the server is running.
        
    Raises
    ------
    
    OSError
        If the server cannot bind to the given host/port (for example, if the port is already in use).
    
    Exception
        Any exceptions raised by uvicorn or the ASGI application are propagated.
    
    Example
    -------
    >>> start_api_server(host="127.0.0.1", port=8080, config="my_config.json")
    """
    
    global config_file
    config_file = config
    uvicorn.run(app, host=host, port=port)

def parse_args():
    """
    Parse command-line arguments for the Streamlit Health Check API Server.
    
    Defines and parses the following command-line options:
        --host   (str)  Host address to bind. Default: "0.0.0.0".
        --port   (int)  Port to run the server on. Default: 8000.
        --config (str)  Path to the health check configuration file. Default: "health_check_config.json".
        
    Returns:
    
            argparse.Namespace: The parsed arguments with attributes `host`, `port`, and `config`.
    """
    
    parser = argparse.ArgumentParser(description="Streamlit Health Check API Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host address to bind")
    parser.add_argument("--port", type=int, default=8000, help="Port to run the server on")
    parser.add_argument(
        "--config", 
        default="health_check_config.json",
        help="Path to health check configuration file"
    )
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    logger.info(f"Starting server with config file: {args.config}")
    start_api_server(host=args.host, port=args.port, config=args.config)