"""
Rotas da API
"""
import logging
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import FileResponse

from app.models.resource_models import (
    ClusterReport, NamespaceReport, ExportRequest, 
    ApplyRecommendationRequest
)
from app.services.validation_service import ValidationService
from app.services.report_service import ReportService
from app.services.historical_analysis import HistoricalAnalysisService

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
        
        # Generate report
        report = report_service.generate_cluster_report(
            pods=pods,
            validations=all_validations,
            vpa_recommendations=vpa_recommendations,
            overcommit_info=overcommit_info,
            nodes_info=nodes_info
        )
        
        return report
        
    except Exception as e:
        logger.error(f"Error getting cluster status: {e}")
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
        
        # Generate report do namespace
        report = report_service.generate_namespace_report(
            namespace=namespace,
            pods=namespace_resources.pods,
            validations=all_validations,
            resource_usage=resource_usage
        )
        
        return report
        
    except Exception as e:
        logger.error(f"Error getting namespace {namespace} status: {e}")
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
        logger.error(f"Error listing pods: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/validations")
async def get_validations(
    namespace: Optional[str] = None,
    severity: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
    k8s_client=Depends(get_k8s_client)
):
    """Listar validações de recursos com paginação"""
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
        
        # Paginação
        total = len(all_validations)
        start = (page - 1) * page_size
        end = start + page_size
        paginated_validations = all_validations[start:end]
        
        return {
            "validations": paginated_validations,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting validations: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/validations/by-namespace")
async def get_validations_by_namespace(
    severity: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    include_system_namespaces: bool = False,
    k8s_client=Depends(get_k8s_client)
):
    """Listar validações agrupadas por namespace com paginação"""
    try:
        # Coletar todos os pods com filtro de namespaces do sistema
        pods = await k8s_client.get_all_pods(include_system_namespaces=include_system_namespaces)
        
        # Validar recursos e agrupar por namespace
        namespace_validations = {}
        for pod in pods:
            pod_validations = validation_service.validate_pod_resources(pod)
            
            if pod.namespace not in namespace_validations:
                namespace_validations[pod.namespace] = {
                    "namespace": pod.namespace,
                    "pods": {},
                    "total_validations": 0,
                    "severity_breakdown": {"error": 0, "warning": 0}
                }
            
            # Agrupar validações por pod
            if pod.name not in namespace_validations[pod.namespace]["pods"]:
                namespace_validations[pod.namespace]["pods"][pod.name] = {
                    "pod_name": pod.name,
                    "validations": []
                }
            
            # Filtrar por severidade se especificado
            if severity:
                pod_validations = [v for v in pod_validations if v.severity == severity]
            
            namespace_validations[pod.namespace]["pods"][pod.name]["validations"] = pod_validations
            namespace_validations[pod.namespace]["total_validations"] += len(pod_validations)
            
            # Contar severidades
            for validation in pod_validations:
                namespace_validations[pod.namespace]["severity_breakdown"][validation.severity] += 1
        
        # Converter para lista e ordenar por total de validações
        namespace_list = list(namespace_validations.values())
        namespace_list.sort(key=lambda x: x["total_validations"], reverse=True)
        
        # Paginação
        total = len(namespace_list)
        start = (page - 1) * page_size
        end = start + page_size
        paginated_namespaces = namespace_list[start:end]
        
        return {
            "namespaces": paginated_namespaces,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting validations by namespace: {e}")
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
        logger.error(f"Error getting VPA recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/export")
async def export_report(
    export_request: ExportRequest,
    k8s_client=Depends(get_k8s_client),
    prometheus_client=Depends(get_prometheus_client)
):
    """Export report in different formats"""
    try:
        # Generate report
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
        
        # Generate report
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
            "message": "Report exported successfully",
            "filepath": filepath,
            "format": export_request.format
        }
        
    except Exception as e:
        logger.error(f"Error exporting report: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/export/files")
async def list_exported_files():
    """List exported files"""
    try:
        files = report_service.get_exported_reports()
        return files
        
    except Exception as e:
        logger.error(f"Error listing exported files: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/export/files/{filename}")
async def download_exported_file(filename: str):
    """Download exported file"""
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
        logger.error(f"Error downloading file {filename}: {e}")
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
            raise HTTPException(status_code=501, detail="Recommendation application not implemented yet")
            
    except Exception as e:
        logger.error(f"Error applying recommendation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/validations/historical")
async def get_historical_validations(
    namespace: Optional[str] = None,
    time_range: str = "24h",
    k8s_client=Depends(get_k8s_client)
):
    """Obter validações com análise histórica do Prometheus"""
    try:
        validation_service = ValidationService()
        
        # Coletar pods
        if namespace:
            namespace_resources = await k8s_client.get_namespace_resources(namespace)
            pods = namespace_resources.pods
        else:
            pods = await k8s_client.get_all_pods()
        
        # Validar com análise histórica
        all_validations = []
        for pod in pods:
            pod_validations = await validation_service.validate_pod_resources_with_historical_analysis(
                pod, time_range
            )
            all_validations.extend(pod_validations)
        
        return {
            "validations": all_validations,
            "total": len(all_validations),
            "time_range": time_range,
            "namespace": namespace or "all"
        }
        
    except Exception as e:
        logger.error(f"Error getting historical validations: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/cluster/historical-summary")
async def get_cluster_historical_summary(
    time_range: str = "24h"
):
    """Obter resumo histórico do cluster"""
    try:
        historical_service = HistoricalAnalysisService()
        summary = await historical_service.get_cluster_historical_summary(time_range)
        
        return {
            "summary": summary,
            "time_range": time_range,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting historical summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/health")
async def health_check():
    """API health check"""
    return {
        "status": "healthy",
        "service": "resource-governance-api",
        "version": "1.0.0"
    }
