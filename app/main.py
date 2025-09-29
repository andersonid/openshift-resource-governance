"""
OpenShift Resource Governance Tool
Application for resource governance in OpenShift cluster
"""
import os
import logging
from fastapi import FastAPI, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.api.routes import api_router
from app.core.kubernetes_client import K8sClient
from app.core.prometheus_client import PrometheusClient

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application initialization and cleanup"""
    logger.info("Starting OpenShift Resource Governance Tool")
    
    # Initialize clients
    app.state.k8s_client = K8sClient()
    app.state.prometheus_client = PrometheusClient()
    
    try:
        await app.state.k8s_client.initialize()
        await app.state.prometheus_client.initialize()
        logger.info("Clients initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing clients: {e}")
        raise
    
    yield
    
    logger.info("Shutting down application")

# Create FastAPI application
app = FastAPI(
    title="OpenShift Resource Governance Tool",
    description="Resource governance tool for OpenShift clusters",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

# Include API routes
app.include_router(api_router, prefix="/api/v1")

# Serve static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def root():
    """Main application page"""
    with open("app/static/index.html", "r") as f:
        return HTMLResponse(content=f.read())

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "openshift-resource-governance",
        "version": "1.0.0"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8080,
        reload=True
    )
