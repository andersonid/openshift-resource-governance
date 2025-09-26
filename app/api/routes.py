"""
API Routes
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

# Create router
api_router = APIRouter()

# Initialize services
validation_service = ValidationService()
report_service = ReportService()

def get_k8s_client(request: Request):
    """Dependency to get Kubernetes client"""
    return request.app.state.k8s_client

def get_prometheus_client(request: Request):
    """Dependency to get Prometheus client"""
    return request.app.state.prometheus_client

@api_router.get("/cluster/status")
async def get_cluster_status(
    k8s_client=Depends(get_k8s_client),
    prometheus_client=Depends(get_prometheus_client)
):
    """Get overall cluster status"""
    try:
        # Collect basic data
        pods = await k8s_client.get_all_pods()
        nodes_info = await k8s_client.get_nodes_info()
        
        # Validate resources
        all_validations = []
        for pod in pods:
            pod_validations = validation_service.validate_pod_resources(pod)
            all_validations.extend(pod_validations)
        
        # Get overcommit information
        overcommit_info = await prometheus_client.get_cluster_overcommit()
        
        # Get VPA recommendations
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
    """Get status of a specific namespace"""
    try:
        # Collect namespace data
        namespace_resources = await k8s_client.get_namespace_resources(namespace)
        
        # Validate resources
        all_validations = []
        for pod in namespace_resources.pods:
            pod_validations = validation_service.validate_pod_resources(pod)
            all_validations.extend(pod_validations)
        
        # Get resource usage from Prometheus
        resource_usage = await prometheus_client.get_namespace_resource_usage(namespace)
        
        # Generate namespace report
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
    """List pods with resource information"""
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
    """List resource validations with pagination"""
    try:
        # Collect pods
        if namespace:
            namespace_resources = await k8s_client.get_namespace_resources(namespace)
            pods = namespace_resources.pods
        else:
            pods = await k8s_client.get_all_pods()
        
        # Validate resources
        all_validations = []
        for pod in pods:
            pod_validations = validation_service.validate_pod_resources(pod)
            all_validations.extend(pod_validations)
        
        # Filter by severity if specified
        if severity:
            all_validations = [
                v for v in all_validations if v.severity == severity
            ]
        
        # Pagination
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
    """List validations grouped by namespace with pagination"""
    try:
        # Collect all pods with system namespace filter
        pods = await k8s_client.get_all_pods(include_system_namespaces=include_system_namespaces)
        
        # Validate resources and group by namespace
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
            
            # Group validations by pod
            if pod.name not in namespace_validations[pod.namespace]["pods"]:
                namespace_validations[pod.namespace]["pods"][pod.name] = {
                    "pod_name": pod.name,
                    "validations": []
                }
            
            # Filter by severity if specified
            if severity:
                pod_validations = [v for v in pod_validations if v.severity == severity]
            
            namespace_validations[pod.namespace]["pods"][pod.name]["validations"] = pod_validations
            namespace_validations[pod.namespace]["total_validations"] += len(pod_validations)
            
            # Count severities
            for validation in pod_validations:
                namespace_validations[pod.namespace]["severity_breakdown"][validation.severity] += 1
        
        # Convert to list and sort by total validations
        namespace_list = list(namespace_validations.values())
        namespace_list.sort(key=lambda x: x["total_validations"], reverse=True)
        
        # Pagination
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
    """Get VPA recommendations"""
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
        
        # Filter by namespaces if specified
        if export_request.namespaces:
            pods = [p for p in pods if p.namespace in export_request.namespaces]
        
        # Validate resources
        all_validations = []
        for pod in pods:
            pod_validations = validation_service.validate_pod_resources(pod)
            all_validations.extend(pod_validations)
        
        # Get additional information
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
        
        # Export
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
            raise HTTPException(status_code=404, detail="File not found")
        
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
    """Apply resource recommendation"""
    try:
        # TODO: Implement recommendation application
        # For now, just simulate
        if recommendation.dry_run:
            return {
                "message": "Dry run - recommendation would be applied",
                "pod": recommendation.pod_name,
                "namespace": recommendation.namespace,
                "container": recommendation.container_name,
                "action": f"{recommendation.action} {recommendation.resource_type} = {recommendation.value}"
            }
        else:
            # Implement real recommendation application
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
    """Get validations with historical analysis from Prometheus"""
    try:
        validation_service = ValidationService()
        
        # Collect pods
        if namespace:
            namespace_resources = await k8s_client.get_namespace_resources(namespace)
            pods = namespace_resources.pods
        else:
            pods = await k8s_client.get_all_pods()
        
        # Validate with historical analysis
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
    """Get cluster historical summary"""
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

@api_router.get("/namespace/{namespace}/historical-analysis")
async def get_namespace_historical_analysis(
    namespace: str,
    time_range: str = "24h",
    prometheus_client=Depends(get_prometheus_client)
):
    """Get historical analysis for a specific namespace"""
    try:
        historical_service = HistoricalAnalysisService()
        
        # Get historical analysis for the namespace
        analysis = await historical_service.get_namespace_historical_analysis(
            namespace, time_range, prometheus_client
        )
        
        return {
            "namespace": namespace,
            "time_range": time_range,
            "analysis": analysis,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting historical analysis for namespace {namespace}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/health")
async def health_check():
    """API health check"""
    return {
        "status": "healthy",
        "service": "resource-governance-api",
        "version": "1.0.0"
    }
