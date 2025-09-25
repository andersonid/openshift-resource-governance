"""
OpenShift Resource Governance Tool
Aplicação para governança de recursos no cluster OpenShift
"""
import os
import logging
from fastapi import FastAPI, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager

from app.core.config import settings
from app.api.routes import api_router
from app.core.kubernetes_client import K8sClient
from app.core.prometheus_client import PrometheusClient

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicialização e cleanup da aplicação"""
    logger.info("Iniciando OpenShift Resource Governance Tool")
    
    # Inicializar clientes
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
    
    logger.info("Finalizando aplicação")

# Criar aplicação FastAPI
app = FastAPI(
    title="OpenShift Resource Governance Tool",
    description="Ferramenta de governança de recursos para clusters OpenShift",
    version="1.0.0",
    lifespan=lifespan
)

# Incluir rotas da API
app.include_router(api_router, prefix="/api/v1")

# Servir arquivos estáticos
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def root():
    """Página principal da aplicação"""
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
