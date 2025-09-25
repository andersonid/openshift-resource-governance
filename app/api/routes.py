"""
Rotas da API
"""
import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import FileResponse

from app.models.resource_models import (
    ClusterReport, NamespaceReport, ExportRequest, 
    ApplyRecommendationRequest
)
from app.services.validation_service import ValidationService
from app.services.report_service import ReportService

logger = logging.getLogger(__name__)

# Criar router
api_router = APIRouter()

# Inicializar serviços
validation_service = ValidationService()
report_service = ReportService()

def get_k8s_client(request: Request):
    """Dependency para obter cliente Kubernetes"""
    return request.app.state.k8s_client

def get_prometheus_client(request: Request):
    """Dependency para obter cliente Prometheus"""
    return request.app.state.prometheus_client

@api_router.get("/cluster/status")
async def get_cluster_status(
    k8s_client=Depends(get_k8s_client),
    prometheus_client=Depends(get_prometheus_client)
):
    """Obter status geral do cluster"""
    try:
        # Coletar dados básicos
        pods = await k8s_client.get_all_pods()
        nodes_info = await k8s_client.get_nodes_info()
        
        # Validar recursos
        all_validations = []
        for pod in pods:
            pod_validations = validation_service.validate_pod_resources(pod)
            all_validations.extend(pod_validations)
        
        # Obter informações de overcommit
        overcommit_info = await prometheus_client.get_cluster_overcommit()
        
        # Obter recomendações VPA
        vpa_recommendations = await k8s_client.get_vpa_recommendations()
        
        # Gerar relatório
        report = report_service.generate_cluster_report(
            pods=pods,
            validations=all_validations,
            vpa_recommendations=vpa_recommendations,
            overcommit_info=overcommit_info,
            nodes_info=nodes_info
        )
        
        return report
        
    except Exception as e:
        logger.error(f"Erro ao obter status do cluster: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/namespace/{namespace}/status")
async def get_namespace_status(
    namespace: str,
    k8s_client=Depends(get_k8s_client),
    prometheus_client=Depends(get_prometheus_client)
):
    """Obter status de um namespace específico"""
    try:
        # Coletar dados do namespace
        namespace_resources = await k8s_client.get_namespace_resources(namespace)
        
        # Validar recursos
        all_validations = []
        for pod in namespace_resources.pods:
            pod_validations = validation_service.validate_pod_resources(pod)
            all_validations.extend(pod_validations)
        
        # Obter uso de recursos do Prometheus
        resource_usage = await prometheus_client.get_namespace_resource_usage(namespace)
        
        # Gerar relatório do namespace
        report = report_service.generate_namespace_report(
            namespace=namespace,
            pods=namespace_resources.pods,
            validations=all_validations,
            resource_usage=resource_usage
        )
        
        return report
        
    except Exception as e:
        logger.error(f"Erro ao obter status do namespace {namespace}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/pods")
async def get_pods(
    namespace: Optional[str] = None,
    k8s_client=Depends(get_k8s_client)
):
    """Listar pods com informações de recursos"""
    try:
        if namespace:
            namespace_resources = await k8s_client.get_namespace_resources(namespace)
            return namespace_resources.pods
        else:
            return await k8s_client.get_all_pods()
            
    except Exception as e:
        logger.error(f"Erro ao listar pods: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/validations")
async def get_validations(
    namespace: Optional[str] = None,
    severity: Optional[str] = None,
    k8s_client=Depends(get_k8s_client)
):
    """Listar validações de recursos"""
    try:
        # Coletar pods
        if namespace:
            namespace_resources = await k8s_client.get_namespace_resources(namespace)
            pods = namespace_resources.pods
        else:
            pods = await k8s_client.get_all_pods()
        
        # Validar recursos
        all_validations = []
        for pod in pods:
            pod_validations = validation_service.validate_pod_resources(pod)
            all_validations.extend(pod_validations)
        
        # Filtrar por severidade se especificado
        if severity:
            all_validations = [
                v for v in all_validations if v.severity == severity
            ]
        
        return all_validations
        
    except Exception as e:
        logger.error(f"Erro ao obter validações: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/vpa/recommendations")
async def get_vpa_recommendations(
    namespace: Optional[str] = None,
    k8s_client=Depends(get_k8s_client)
):
    """Obter recomendações do VPA"""
    try:
        recommendations = await k8s_client.get_vpa_recommendations()
        
        if namespace:
            recommendations = [
                r for r in recommendations if r.namespace == namespace
            ]
        
        return recommendations
        
    except Exception as e:
        logger.error(f"Erro ao obter recomendações VPA: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/export")
async def export_report(
    export_request: ExportRequest,
    k8s_client=Depends(get_k8s_client),
    prometheus_client=Depends(get_prometheus_client)
):
    """Exportar relatório em diferentes formatos"""
    try:
        # Gerar relatório
        pods = await k8s_client.get_all_pods()
        nodes_info = await k8s_client.get_nodes_info()
        
        # Filtrar por namespaces se especificado
        if export_request.namespaces:
            pods = [p for p in pods if p.namespace in export_request.namespaces]
        
        # Validar recursos
        all_validations = []
        for pod in pods:
            pod_validations = validation_service.validate_pod_resources(pod)
            all_validations.extend(pod_validations)
        
        # Obter informações adicionais
        overcommit_info = {}
        vpa_recommendations = []
        
        if export_request.include_vpa:
            vpa_recommendations = await k8s_client.get_vpa_recommendations()
        
        if export_request.include_validations:
            overcommit_info = await prometheus_client.get_cluster_overcommit()
        
        # Gerar relatório
        report = report_service.generate_cluster_report(
            pods=pods,
            validations=all_validations,
            vpa_recommendations=vpa_recommendations,
            overcommit_info=overcommit_info,
            nodes_info=nodes_info
        )
        
        # Exportar
        filepath = await report_service.export_report(report, export_request)
        
        return {
            "message": "Relatório exportado com sucesso",
            "filepath": filepath,
            "format": export_request.format
        }
        
    except Exception as e:
        logger.error(f"Erro ao exportar relatório: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/export/files")
async def list_exported_files():
    """Listar arquivos exportados"""
    try:
        files = report_service.get_exported_reports()
        return files
        
    except Exception as e:
        logger.error(f"Erro ao listar arquivos exportados: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/export/files/{filename}")
async def download_exported_file(filename: str):
    """Download de arquivo exportado"""
    try:
        files = report_service.get_exported_reports()
        file_info = next((f for f in files if f["filename"] == filename), None)
        
        if not file_info:
            raise HTTPException(status_code=404, detail="Arquivo não encontrado")
        
        return FileResponse(
            path=file_info["filepath"],
            filename=filename,
            media_type='application/octet-stream'
        )
        
    except Exception as e:
        logger.error(f"Erro ao baixar arquivo {filename}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/apply/recommendation")
async def apply_recommendation(
    recommendation: ApplyRecommendationRequest,
    k8s_client=Depends(get_k8s_client)
):
    """Aplicar recomendação de recursos"""
    try:
        # TODO: Implementar aplicação de recomendações
        # Por enquanto, apenas simular
        if recommendation.dry_run:
            return {
                "message": "Dry run - recomendação seria aplicada",
                "pod": recommendation.pod_name,
                "namespace": recommendation.namespace,
                "container": recommendation.container_name,
                "action": f"{recommendation.action} {recommendation.resource_type} = {recommendation.value}"
            }
        else:
            # Implementar aplicação real da recomendação
            raise HTTPException(status_code=501, detail="Aplicação de recomendações não implementada ainda")
            
    except Exception as e:
        logger.error(f"Erro ao aplicar recomendação: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/health")
async def health_check():
    """Health check da API"""
    return {
        "status": "healthy",
        "service": "resource-governance-api",
        "version": "1.0.0"
    }
