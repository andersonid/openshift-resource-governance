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
    ApplyRecommendationRequest, WorkloadCategory, SmartRecommendation,
    PodHealthScore, SimplifiedValidation
)
from app.services.validation_service import ValidationService
from app.services.report_service import ReportService
from app.services.historical_analysis import HistoricalAnalysisService
from app.core.prometheus_client import PrometheusClient

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
        
        # Validate resources with historical analysis
        all_validations = []
        historical_service = HistoricalAnalysisService()
        
        for pod in pods:
            # Static validations
            pod_validations = validation_service.validate_pod_resources(pod)
            all_validations.extend(pod_validations)
            
            # Historical analysis (async)
            try:
                historical_validations = await validation_service.validate_pod_resources_with_historical_analysis(pod, "24h")
                all_validations.extend(historical_validations)
            except Exception as e:
                logger.warning(f"Error in historical analysis for pod {pod.name}: {e}")
        
        # Get overcommit information
        overcommit_info = await prometheus_client.get_cluster_overcommit()
        
        # Get VPA recommendations
        vpa_recommendations = await k8s_client.get_vpa_recommendations()
        
        # Group pods by namespace for the frontend
        namespaces_data = {}
        pod_validations_map = {}
        
        # Create a map of pod validations (static + historical)
        for validation in all_validations:
            pod_key = f"{validation.namespace}/{validation.pod_name}"
            if pod_key not in pod_validations_map:
                pod_validations_map[pod_key] = []
            pod_validations_map[pod_key].append(validation)
        
        for pod in pods:
            namespace = pod.namespace
            if namespace not in namespaces_data:
                namespaces_data[namespace] = {
                    'namespace': namespace,
                    'pods': {},
                    'total_validations': 0,
                    'severity_breakdown': {'error': 0, 'warning': 0, 'info': 0}
                }
            
            # Add pod to namespace
            pod_name = pod.name
            pod_key = f"{namespace}/{pod_name}"
            pod_validations = pod_validations_map.get(pod_key, [])
            
            # Convert pod to the format expected by frontend
            pod_data = {
                'pod_name': pod_name,
                'namespace': namespace,
                'phase': pod.phase,
                'node_name': pod.node_name,
                'containers': [],
                'validations': []
            }
            
            # Add containers
            for container in pod.containers:
                container_data = {
                    'name': container['name'],
                    'image': container['image'],
                    'resources': container['resources']
                }
                pod_data['containers'].append(container_data)
            
            # Add validations for this pod
            for validation in pod_validations:
                validation_data = {
                    'rule_name': validation.validation_type,
                    'namespace': namespace,
                    'message': validation.message,
                    'recommendation': validation.recommendation,
                    'severity': validation.severity
                }
                pod_data['validations'].append(validation_data)
                
                # Update namespace severity breakdown
                namespaces_data[namespace]['severity_breakdown'][validation.severity] += 1
                namespaces_data[namespace]['total_validations'] += 1
            
            namespaces_data[namespace]['pods'][pod_name] = pod_data
        
        # Convert to list format expected by frontend
        namespaces_list = list(namespaces_data.values())
        
        # Count total errors and warnings
        total_errors = sum(ns['severity_breakdown']['error'] for ns in namespaces_list)
        total_warnings = sum(ns['severity_breakdown']['warning'] for ns in namespaces_list)
        
        # Process overcommit information
        cpu_overcommit_percent = 0
        memory_overcommit_percent = 0
        namespaces_in_overcommit = 0
        resource_quota_coverage = 0
        
        if overcommit_info and overcommit_info.get("cpu") and overcommit_info.get("memory"):
            cpu_capacity = 0
            cpu_requests = 0
            memory_capacity = 0
            memory_requests = 0
            
            # Extract CPU data
            if overcommit_info["cpu"].get("capacity", {}).get("status") == "success":
                for result in overcommit_info["cpu"]["capacity"].get("data", {}).get("result", []):
                    cpu_capacity += float(result["value"][1])
            
            if overcommit_info["cpu"].get("requests", {}).get("status") == "success":
                for result in overcommit_info["cpu"]["requests"].get("data", {}).get("result", []):
                    cpu_requests += float(result["value"][1])
            
            # Extract Memory data
            if overcommit_info["memory"].get("capacity", {}).get("status") == "success":
                for result in overcommit_info["memory"]["capacity"].get("data", {}).get("result", []):
                    memory_capacity += float(result["value"][1])
            
            if overcommit_info["memory"].get("requests", {}).get("status") == "success":
                for result in overcommit_info["memory"]["requests"].get("data", {}).get("result", []):
                    memory_requests += float(result["value"][1])
            
            # Calculate overcommit percentages
            if cpu_capacity > 0:
                cpu_overcommit_percent = round((cpu_requests / cpu_capacity) * 100, 1)
            
            if memory_capacity > 0:
                memory_overcommit_percent = round((memory_requests / memory_capacity) * 100, 1)
            
            # Debug logging
            logger.info(f"Overcommit Debug - CPU Capacity: {cpu_capacity}, CPU Requests: {cpu_requests}, CPU Overcommit: {cpu_overcommit_percent}%")
            logger.info(f"Overcommit Debug - Memory Capacity: {memory_capacity}, Memory Requests: {memory_requests}, Memory Overcommit: {memory_overcommit_percent}%")
            
            # Count namespaces in overcommit (simplified - any namespace with requests > 0)
            namespaces_in_overcommit = len([ns for ns in namespaces_list if ns['total_validations'] > 0])
            
            # Calculate resource quota coverage (simplified)
            if cpu_capacity > 0 and memory_capacity > 0:
                resource_quota_coverage = round(((cpu_requests + memory_requests) / (cpu_capacity + memory_capacity)) * 100, 1)
        
        return {
            "timestamp": datetime.now().isoformat(),
            "total_pods": len(pods),
            "total_namespaces": len(namespaces_list),
            "total_nodes": len(nodes_info) if nodes_info else 0,
            "total_errors": total_errors,
            "total_warnings": total_warnings,
            "namespaces": namespaces_list,
            "overcommit": {
                "cpu_overcommit_percent": cpu_overcommit_percent,
                "memory_overcommit_percent": memory_overcommit_percent,
                "namespaces_in_overcommit": namespaces_in_overcommit,
                "resource_quota_coverage": resource_quota_coverage,
                "cpu_capacity": cpu_capacity if 'cpu_capacity' in locals() else 0,
                "cpu_requests": cpu_requests if 'cpu_requests' in locals() else 0,
                "memory_capacity": memory_capacity if 'memory_capacity' in locals() else 0,
                "memory_requests": memory_requests if 'memory_requests' in locals() else 0
            }
        }
        
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
                    "severity_breakdown": {"error": 0, "warning": 0, "info": 0, "critical": 0}
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
                severity = validation.severity
                if severity in namespace_validations[pod.namespace]["severity_breakdown"]:
                    namespace_validations[pod.namespace]["severity_breakdown"][severity] += 1
                else:
                    # Handle unknown severity types
                    namespace_validations[pod.namespace]["severity_breakdown"]["info"] += 1
        
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

@api_router.get("/workloads/{namespace}/{workload}/metrics")
async def get_workload_historical_metrics(
    namespace: str,
    workload: str,
    time_range: str = "24h"
):
    """Get historical metrics for a specific workload with cluster percentages"""
    try:
        prometheus_client = PrometheusClient()
        await prometheus_client.initialize()
        
        # Get cluster total resources first
        cluster_cpu_query = 'sum(kube_node_status_allocatable{resource="cpu"})'
        cluster_memory_query = 'sum(kube_node_status_allocatable{resource="memory"})'
        
        cluster_cpu_data = await prometheus_client.query(cluster_cpu_query)
        cluster_memory_data = await prometheus_client.query(cluster_memory_query)
        
        # Extract cluster totals
        cluster_cpu_total = 0
        cluster_memory_total = 0
        
        if cluster_cpu_data.get("status") == "success" and cluster_cpu_data.get("data", {}).get("result"):
            for result in cluster_cpu_data["data"]["result"]:
                cluster_cpu_total += float(result["value"][1])
        
        if cluster_memory_data.get("status") == "success" and cluster_memory_data.get("data", {}).get("result"):
            for result in cluster_memory_data["data"]["result"]:
                cluster_memory_total += float(result["value"][1])
        
        # Get workload-specific metrics using more precise queries
        # CPU usage for specific pod (using regex pattern to match pod name with suffix)
        cpu_usage_query = f'rate(container_cpu_usage_seconds_total{{namespace="{namespace}", pod=~"{workload}.*"}}[5m])'
        memory_usage_query = f'container_memory_working_set_bytes{{namespace="{namespace}", pod=~"{workload}.*", container!="", image!=""}}'
        
        # Resource requests and limits for specific pod
        cpu_requests_query = f'sum(kube_pod_container_resource_requests{{namespace="{namespace}", pod=~"{workload}.*", resource="cpu"}})'
        memory_requests_query = f'sum(kube_pod_container_resource_requests{{namespace="{namespace}", pod=~"{workload}.*", resource="memory"}})'
        cpu_limits_query = f'sum(kube_pod_container_resource_limits{{namespace="{namespace}", pod=~"{workload}.*", resource="cpu"}})'
        memory_limits_query = f'sum(kube_pod_container_resource_limits{{namespace="{namespace}", pod=~"{workload}.*", resource="memory"}})'
        
        # Execute queries
        cpu_usage_data = await prometheus_client.query(cpu_usage_query)
        memory_usage_data = await prometheus_client.query(memory_usage_query)
        cpu_requests_data = await prometheus_client.query(cpu_requests_query)
        memory_requests_data = await prometheus_client.query(memory_requests_query)
        cpu_limits_data = await prometheus_client.query(cpu_limits_query)
        memory_limits_data = await prometheus_client.query(memory_limits_query)
        
        # Extract values
        cpu_usage = 0
        memory_usage = 0
        cpu_requests = 0
        memory_requests = 0
        cpu_limits = 0
        memory_limits = 0
        
        # Extract CPU usage
        if cpu_usage_data.get("status") == "success" and cpu_usage_data.get("data", {}).get("result"):
            for result in cpu_usage_data["data"]["result"]:
                cpu_usage += float(result["value"][1])
        
        # Extract Memory usage
        if memory_usage_data.get("status") == "success" and memory_usage_data.get("data", {}).get("result"):
            for result in memory_usage_data["data"]["result"]:
                memory_usage += float(result["value"][1])
        
        # Extract CPU requests
        if cpu_requests_data.get("status") == "success" and cpu_requests_data.get("data", {}).get("result"):
            for result in cpu_requests_data["data"]["result"]:
                cpu_requests += float(result["value"][1])
        
        # Extract Memory requests
        if memory_requests_data.get("status") == "success" and memory_requests_data.get("data", {}).get("result"):
            for result in memory_requests_data["data"]["result"]:
                memory_requests += float(result["value"][1])
        
        # Extract CPU limits
        if cpu_limits_data.get("status") == "success" and cpu_limits_data.get("data", {}).get("result"):
            for result in cpu_limits_data["data"]["result"]:
                cpu_limits += float(result["value"][1])
        
        # Extract Memory limits
        if memory_limits_data.get("status") == "success" and memory_limits_data.get("data", {}).get("result"):
            for result in memory_limits_data["data"]["result"]:
                memory_limits += float(result["value"][1])
        
        # Check if we have real data
        prometheus_available = cluster_cpu_total > 0 and cluster_memory_total > 0
        
        # If no real data, return zeros with appropriate message
        if not prometheus_available:
            return {
                "workload": workload,
                "namespace": namespace,
                "time_range": time_range,
                "prometheus_available": False,
                "data_source": "no_data",
                "message": "No metrics data available for this workload",
                "cluster_total": {
                    "cpu_cores": 0,
                    "memory_bytes": 0,
                    "memory_gb": 0
                },
                "workload_metrics": {
                    "cpu": {
                        "usage_cores": 0,
                        "usage_percent": 0,
                        "requests_cores": 0,
                        "requests_percent": 0,
                        "limits_cores": 0,
                        "limits_percent": 0,
                        "efficiency_percent": 0
                    },
                    "memory": {
                        "usage_bytes": 0,
                        "usage_mb": 0,
                        "usage_percent": 0,
                        "requests_bytes": 0,
                        "requests_mb": 0,
                        "requests_percent": 0,
                        "limits_bytes": 0,
                        "limits_mb": 0,
                        "limits_percent": 0,
                        "efficiency_percent": 0
                    }
                }
            }
        
        # Calculate percentages
        cpu_usage_percent = (cpu_usage / cluster_cpu_total * 100) if cluster_cpu_total > 0 else 0
        memory_usage_percent = (memory_usage / cluster_memory_total * 100) if cluster_memory_total > 0 else 0
        cpu_requests_percent = (cpu_requests / cluster_cpu_total * 100) if cluster_cpu_total > 0 else 0
        memory_requests_percent = (memory_requests / cluster_memory_total * 100) if cluster_memory_total > 0 else 0
        cpu_limits_percent = (cpu_limits / cluster_cpu_total * 100) if cluster_cpu_total > 0 else 0
        memory_limits_percent = (memory_limits / cluster_memory_total * 100) if cluster_memory_total > 0 else 0
        
        # Calculate efficiency (usage vs requests)
        cpu_efficiency = (cpu_usage / cpu_requests * 100) if cpu_requests > 0 else 0
        memory_efficiency = (memory_usage / memory_requests * 100) if memory_requests > 0 else 0
        
        return {
            "workload": workload,
            "namespace": namespace,
            "time_range": time_range,
            "prometheus_available": True,
            "data_source": "prometheus",
            "timestamp": datetime.now().isoformat(),
            "cluster_total": {
                "cpu_cores": cluster_cpu_total,
                "memory_bytes": cluster_memory_total,
                "memory_gb": cluster_memory_total / (1024**3)
            },
            "workload_metrics": {
                "cpu": {
                    "usage_cores": cpu_usage,
                    "usage_percent": round(cpu_usage_percent, 2),
                    "requests_cores": cpu_requests,
                    "requests_percent": round(cpu_requests_percent, 2),
                    "limits_cores": cpu_limits,
                    "limits_percent": round(cpu_limits_percent, 2),
                    "efficiency_percent": round(cpu_efficiency, 1)
                },
                "memory": {
                    "usage_bytes": memory_usage,
                    "usage_mb": round(memory_usage / (1024**2), 2),
                    "usage_percent": round(memory_usage_percent, 2),
                    "requests_bytes": memory_requests,
                    "requests_mb": round(memory_requests / (1024**2), 2),
                    "requests_percent": round(memory_requests_percent, 2),
                    "limits_bytes": memory_limits,
                    "limits_mb": round(memory_limits / (1024**2), 2),
                    "limits_percent": round(memory_limits_percent, 2),
                    "efficiency_percent": round(memory_efficiency, 1)
                }
            }
        }
    except Exception as e:
        logger.error(f"Error getting workload metrics for {namespace}/{workload}: {e}")
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
    k8s_client=Depends(get_k8s_client),
    prometheus_client=Depends(get_prometheus_client)
):
    """Get historical analysis for a specific namespace"""
    try:
        historical_service = HistoricalAnalysisService()
        
        # Get historical analysis for the namespace
        analysis = await historical_service.get_namespace_historical_analysis(
            namespace, time_range, k8s_client
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

@api_router.get("/namespace/{namespace}/workload/{workload}/historical-analysis")
async def get_workload_historical_analysis(
    namespace: str,
    workload: str,
    time_range: str = "24h",
    prometheus_client=Depends(get_prometheus_client)
):
    """Get historical analysis for a specific workload/deployment"""
    try:
        historical_service = HistoricalAnalysisService()
        
        # Get historical analysis for the workload
        analysis = await historical_service.get_workload_historical_analysis(
            namespace, workload, time_range
        )
        
        return {
            "namespace": namespace,
            "workload": workload,
            "time_range": time_range,
            "analysis": analysis,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting historical analysis for workload {workload} in namespace {namespace}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/namespace/{namespace}/pod/{pod_name}/historical-analysis")
async def get_pod_historical_analysis(
    namespace: str,
    pod_name: str,
    time_range: str = "24h",
    prometheus_client=Depends(get_prometheus_client)
):
    """Get historical analysis for a specific pod (legacy endpoint)"""
    try:
        historical_service = HistoricalAnalysisService()
        
        # Get historical analysis for the pod
        analysis = await historical_service.get_pod_historical_analysis(
            namespace, pod_name, time_range
        )
        
        return {
            "namespace": namespace,
            "pod_name": pod_name,
            "time_range": time_range,
            "analysis": analysis,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting historical analysis for pod {pod_name} in namespace {namespace}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/smart-recommendations")
async def get_smart_recommendations(
    namespace: Optional[str] = None,
    priority: Optional[str] = None,
    k8s_client=Depends(get_k8s_client)
):
    """Get smart recommendations for workloads"""
    try:
        # Collect pods
        if namespace:
            namespace_resources = await k8s_client.get_namespace_resources(namespace)
            pods = namespace_resources.pods
        else:
            pods = await k8s_client.get_all_pods()
        
        # Get workload categories
        categories = await validation_service.get_workload_categories(pods)
        
        # Get smart recommendations
        recommendations = await validation_service.get_smart_recommendations(pods)
        
        # Filter by priority if specified
        if priority:
            recommendations = [
                r for r in recommendations if r.priority == priority
            ]
        
        return {
            "recommendations": recommendations,
            "categories": categories,
            "total": len(recommendations)
        }
        
    except Exception as e:
        logger.error(f"Error getting smart recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/workload-categories")
async def get_workload_categories(
    namespace: Optional[str] = None,
    k8s_client=Depends(get_k8s_client)
):
    """Get workload categories analysis"""
    try:
        # Collect pods
        if namespace:
            namespace_resources = await k8s_client.get_namespace_resources(namespace)
            pods = namespace_resources.pods
        else:
            pods = await k8s_client.get_all_pods()
        
        # Get workload categories
        categories = await validation_service.get_workload_categories(pods)
        
        # Group by category
        category_summary = {}
        for category in categories:
            cat_type = category.category
            if cat_type not in category_summary:
                category_summary[cat_type] = {
                    "count": 0,
                    "total_priority_score": 0,
                    "workloads": []
                }
            
            category_summary[cat_type]["count"] += 1
            category_summary[cat_type]["total_priority_score"] += category.priority_score
            category_summary[cat_type]["workloads"].append({
                "name": category.workload_name,
                "namespace": category.namespace,
                "priority_score": category.priority_score,
                "estimated_impact": category.estimated_impact,
                "vpa_candidate": category.vpa_candidate
            })
        
        # Calculate average priority scores
        for cat_type in category_summary:
            if category_summary[cat_type]["count"] > 0:
                category_summary[cat_type]["average_priority_score"] = (
                    category_summary[cat_type]["total_priority_score"] / 
                    category_summary[cat_type]["count"]
                )
        
        return {
            "categories": category_summary,
            "total_workloads": len(categories),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting workload categories: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/validations/smart")
async def get_smart_validations(
    namespace: Optional[str] = None,
    severity: Optional[str] = None,
    workload_category: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
    k8s_client=Depends(get_k8s_client)
):
    """Get validations with smart analysis and categorization"""
    try:
        # Collect pods
        if namespace:
            namespace_resources = await k8s_client.get_namespace_resources(namespace)
            pods = namespace_resources.pods
        else:
            pods = await k8s_client.get_all_pods()
        
        # Get smart validations
        all_validations = []
        for pod in pods:
            pod_validations = await validation_service.validate_pod_resources_with_smart_analysis(pod)
            all_validations.extend(pod_validations)
        
        # Filter by severity if specified
        if severity:
            all_validations = [
                v for v in all_validations if v.severity == severity
            ]
        
        # Filter by workload category if specified
        if workload_category:
            all_validations = [
                v for v in all_validations if v.workload_category == workload_category
            ]
        
        # Sort by priority score (descending)
        all_validations.sort(key=lambda x: x.priority_score or 0, reverse=True)
        
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
            },
            "summary": {
                "total_validations": total,
                "by_severity": {
                    "critical": len([v for v in all_validations if v.severity == "critical"]),
                    "error": len([v for v in all_validations if v.severity == "error"]),
                    "warning": len([v for v in all_validations if v.severity == "warning"]),
                    "info": len([v for v in all_validations if v.severity == "info"])
                },
                "by_category": {
                    "new": len([v for v in all_validations if v.workload_category == "new"]),
                    "established": len([v for v in all_validations if v.workload_category == "established"]),
                    "outlier": len([v for v in all_validations if v.workload_category == "outlier"]),
                    "compliant": len([v for v in all_validations if v.workload_category == "compliant"])
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting smart validations: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/cluster-health")
async def get_cluster_health(k8s_client=Depends(get_k8s_client)):
    """Get cluster health overview with overcommit analysis"""
    try:
        pods = await k8s_client.get_all_pods()
        cluster_health = await validation_service.get_cluster_health(pods)
        return cluster_health
    except Exception as e:
        logger.error(f"Error getting cluster health: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/qos-classification")
async def get_qos_classification(
    namespace: Optional[str] = None,
    k8s_client=Depends(get_k8s_client)
):
    """Get QoS classification for pods"""
    try:
        if namespace:
            namespace_resources = await k8s_client.get_namespace_resources(namespace)
            pods = namespace_resources.pods
        else:
            pods = await k8s_client.get_all_pods()
        
        qos_classifications = []
        for pod in pods:
            qos = validation_service.classify_qos(pod)
            qos_classifications.append(qos)
        
        return {
            "qos_classifications": qos_classifications,
            "total_pods": len(pods),
            "distribution": {
                "Guaranteed": len([q for q in qos_classifications if q.qos_class == "Guaranteed"]),
                "Burstable": len([q for q in qos_classifications if q.qos_class == "Burstable"]),
                "BestEffort": len([q for q in qos_classifications if q.qos_class == "BestEffort"])
            }
        }
    except Exception as e:
        logger.error(f"Error getting QoS classification: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/resource-quotas")
async def get_resource_quotas(
    namespace: Optional[str] = None,
    k8s_client=Depends(get_k8s_client)
):
    """Get Resource Quota analysis"""
    try:
        if namespace:
            namespaces = [namespace]
        else:
            pods = await k8s_client.get_all_pods()
            namespaces = list(set(pod.namespace for pod in pods))
        
        quotas = await validation_service.analyze_resource_quotas(namespaces)
        
        return {
            "resource_quotas": quotas,
            "total_namespaces": len(namespaces),
            "coverage_percentage": len([q for q in quotas if q.status == "Active"]) / len(namespaces) * 100
        }
    except Exception as e:
        logger.error(f"Error getting resource quotas: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/pod-health-scores")
async def get_pod_health_scores(
    namespace: Optional[str] = None,
    k8s_client=Depends(get_k8s_client)
):
    """Get simplified pod health scores with grouped validations"""
    try:
        # Get pods
        pods = await k8s_client.get_all_pods()
        
        if namespace:
            pods = [pod for pod in pods if pod.namespace == namespace]
        
        health_scores = []
        
        for pod in pods:
            # Get validations for this pod
            pod_validations = validation_service.validate_pod_resources(pod)
            
            # Calculate health score
            health_score = validation_service.calculate_pod_health_score(pod, pod_validations)
            health_scores.append(health_score)
        
        # Sort by health score (worst first)
        health_scores.sort(key=lambda x: x.health_score)
        
        return {
            "pods": health_scores,
            "total_pods": len(health_scores),
            "summary": {
                "excellent": len([h for h in health_scores if h.health_score >= 9]),
                "good": len([h for h in health_scores if 7 <= h.health_score < 9]),
                "medium": len([h for h in health_scores if 5 <= h.health_score < 7]),
                "poor": len([h for h in health_scores if 3 <= h.health_score < 5]),
                "critical": len([h for h in health_scores if h.health_score < 3])
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting pod health scores: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/health")
async def health_check():
    """API health check"""
    return {
        "status": "healthy",
        "service": "resource-governance-api",
        "version": "1.0.0"
    }
