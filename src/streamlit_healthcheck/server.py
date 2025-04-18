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
    health_service = HealthCheckService(config_path=config_file)
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

# Initialize health check service and config file path as global variables
health_service: Optional[HealthCheckService] = None
config_file: Optional[str] = None

@app.on_event("startup")
async def startup_event():
    """Initialize health check service on startup"""
    global health_service, config_file
    logger.info(f"Initializing health check service with config: {config_file}")
    health_service = HealthCheckService(config_path=config_file)
    health_service.start()

@app.on_event("shutdown")
async def shutdown_event():
    """Stop health check service on shutdown"""
    global health_service
    if health_service:
        logger.info("Stopping health check service")
        health_service.stop()

@app.get("/health", response_model=Dict[str, Any])
async def get_health_status():
    """
    Get complete health check status including system resources, 
    dependencies, custom checks, and Streamlit pages
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
    """Get system resource health status (CPU, Memory, Disk)"""
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
    """Get dependencies health status"""
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
    """Get Streamlit pages health status"""
    global health_service
    if not health_service:
        raise HTTPException(status_code=503, detail="Health check service not initialized")
    
    try:
        health_data = health_service.get_health_data()
        return JSONResponse(content={"streamlit_pages": health_data.get("streamlit_pages", {})})
    except Exception as e:
        logger.error(f"Error getting pages health data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def start_api_server(host: str = "0.0.0.0", port: int = 8000, config: str = "health_check_config.json"):
    """Start the FastAPI server"""
    global config_file
    config_file = config
    uvicorn.run(app, host=host, port=port)

def parse_args():
    """Parse command line arguments"""
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