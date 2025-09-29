"""
Data models for Kubernetes resources
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class ContainerResource(BaseModel):
    """Container resources"""
    name: str
    image: str
    resources: Dict[str, Dict[str, str]]

class PodResource(BaseModel):
    """Pod resources"""
    name: str
    namespace: str
    node_name: Optional[str] = None
    phase: str
    containers: List[ContainerResource]

class NamespaceResources(BaseModel):
    """Namespace resources"""
    name: str
    pods: List[PodResource]
    total_cpu_requests: str = "0"
    total_cpu_limits: str = "0"
    total_memory_requests: str = "0"
    total_memory_limits: str = "0"

class VPARecommendation(BaseModel):
    """VPA recommendation"""
    name: str
    namespace: str
    target_ref: Dict[str, str]
    recommendations: Dict[str, Any]

class ResourceValidation(BaseModel):
    """Resource validation result"""
    pod_name: str
    namespace: str
    container_name: str
    validation_type: str  # "missing_requests", "missing_limits", "invalid_ratio", "overcommit"
    severity: str  # "warning", "error", "critical"
    message: str
    recommendation: Optional[str] = None
    priority_score: Optional[int] = None  # 1-10, higher = more critical
    workload_category: Optional[str] = None  # "new", "established", "outlier", "compliant"
    estimated_impact: Optional[str] = None  # "low", "medium", "high", "critical"

class ClusterReport(BaseModel):
    """Cluster report"""
    timestamp: str
    total_pods: int
    total_namespaces: int
    total_nodes: int
    validations: List[ResourceValidation]
    vpa_recommendations: List[VPARecommendation]
    overcommit_info: Dict[str, Any]
    summary: Dict[str, Any]

class NamespaceReport(BaseModel):
    """Namespace report"""
    namespace: str
    timestamp: str
    total_pods: int
    validations: List[ResourceValidation]
    resource_usage: Dict[str, Any]
    recommendations: List[str]

class ExportRequest(BaseModel):
    """Request to export report"""
    format: str  # "json", "csv", "pdf"
    namespaces: Optional[List[str]] = None
    include_vpa: bool = True
    include_validations: bool = True

class ApplyRecommendationRequest(BaseModel):
    """Request to apply recommendation"""
    pod_name: str
    namespace: str
    container_name: str
    resource_type: str  # "cpu", "memory"
    action: str  # "requests", "limits"
    value: str
    dry_run: bool = True

class WorkloadCategory(BaseModel):
    """Workload categorization"""
    workload_name: str
    namespace: str
    category: str  # "new", "established", "outlier", "compliant"
    age_days: int
    resource_config_status: str  # "missing_requests", "missing_limits", "suboptimal_ratio", "compliant"
    priority_score: int  # 1-10
    estimated_impact: str  # "low", "medium", "high", "critical"
    vpa_candidate: bool = False
    historical_data_available: bool = False

class SmartRecommendation(BaseModel):
    """Smart recommendation based on analysis"""
    workload_name: str
    namespace: str
    recommendation_type: str  # "resource_config", "vpa_activation", "ratio_adjustment"
    priority: str  # "critical", "high", "medium", "low"
    title: str
    description: str
    current_config: Optional[Dict[str, str]] = None
    suggested_config: Optional[Dict[str, str]] = None
    confidence_level: Optional[float] = None  # 0.0-1.0
    estimated_impact: Optional[str] = None
    implementation_steps: Optional[List[str]] = None
    kubectl_commands: Optional[List[str]] = None
    vpa_yaml: Optional[str] = None
