"""
Application settings
"""
import os
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    """Application settings"""
    
    # OpenShift/Kubernetes settings
    kubeconfig_path: Optional[str] = None
    cluster_url: Optional[str] = None
    token: Optional[str] = None
    
    # Prometheus settings
    prometheus_url: str = "https://prometheus-k8s.openshift-monitoring.svc.cluster.local:9091"
    
    # Validation settings
    cpu_limit_ratio: float = 3.0  # Default limit:request ratio for CPU
    memory_limit_ratio: float = 3.0  # Default limit:request ratio for memory
    min_cpu_request: str = "10m"  # Minimum CPU request
    min_memory_request: str = "32Mi"  # Minimum memory request
    
    # Critical namespaces for VPA
    critical_namespaces: List[str] = [
        "openshift-monitoring",
        "openshift-ingress",
        "openshift-apiserver",
        "openshift-controller-manager",
        "openshift-sdn"
    ]
    
    # Namespace filter settings
    include_system_namespaces: bool = Field(default=False, alias="INCLUDE_SYSTEM_NAMESPACES")
    system_namespace_prefixes: List[str] = Field(
        default=[
            "kube-",
            "openshift-",
            "default",
            "kube-system",
            "kube-public",
            "kube-node-lease"
        ],
        alias="SYSTEM_NAMESPACE_PREFIXES"
    )
    
    class Config:
        env_file = ".env"
        case_sensitive = False
    
    # Report settings
    report_export_path: str = "/tmp/reports"
    
    # Security settings
    enable_rbac: bool = True
    service_account_name: str = "resource-governance-sa"
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
