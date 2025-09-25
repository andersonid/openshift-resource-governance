"""
Modelos de dados para recursos Kubernetes
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class ContainerResource(BaseModel):
    """Recursos de um container"""
    name: str
    image: str
    resources: Dict[str, Dict[str, str]]

class PodResource(BaseModel):
    """Recursos de um pod"""
    name: str
    namespace: str
    node_name: Optional[str] = None
    phase: str
    containers: List[ContainerResource]

class NamespaceResources(BaseModel):
    """Recursos de um namespace"""
    name: str
    pods: List[PodResource]
    total_cpu_requests: str = "0"
    total_cpu_limits: str = "0"
    total_memory_requests: str = "0"
    total_memory_limits: str = "0"

class VPARecommendation(BaseModel):
    """Recomendação do VPA"""
    name: str
    namespace: str
    target_ref: Dict[str, str]
    recommendations: Dict[str, Any]

class ResourceValidation(BaseModel):
    """Resultado de validação de recursos"""
    pod_name: str
    namespace: str
    container_name: str
    validation_type: str  # "missing_requests", "missing_limits", "invalid_ratio", "overcommit"
    severity: str  # "warning", "error", "critical"
    message: str
    recommendation: Optional[str] = None

class ClusterReport(BaseModel):
    """Relatório do cluster"""
    timestamp: str
    total_pods: int
    total_namespaces: int
    total_nodes: int
    validations: List[ResourceValidation]
    vpa_recommendations: List[VPARecommendation]
    overcommit_info: Dict[str, Any]
    summary: Dict[str, Any]

class NamespaceReport(BaseModel):
    """Relatório de um namespace"""
    namespace: str
    timestamp: str
    total_pods: int
    validations: List[ResourceValidation]
    resource_usage: Dict[str, Any]
    recommendations: List[str]

class ExportRequest(BaseModel):
    """Request para exportar relatório"""
    format: str  # "json", "csv", "pdf"
    namespaces: Optional[List[str]] = None
    include_vpa: bool = True
    include_validations: bool = True

class ApplyRecommendationRequest(BaseModel):
    """Request para aplicar recomendação"""
    pod_name: str
    namespace: str
    container_name: str
    resource_type: str  # "cpu", "memory"
    action: str  # "requests", "limits"
    value: str
    dry_run: bool = True
