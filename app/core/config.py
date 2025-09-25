"""
Configurações da aplicação
"""
import os
from typing import List, Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Configurações da aplicação"""
    
    # Configurações do OpenShift/Kubernetes
    kubeconfig_path: Optional[str] = None
    cluster_url: Optional[str] = None
    token: Optional[str] = None
    
    # Configurações do Prometheus
    prometheus_url: str = "http://prometheus.openshift-monitoring.svc.cluster.local:9090"
    
    # Configurações de validação
    cpu_limit_ratio: float = 3.0  # Ratio padrão limit:request para CPU
    memory_limit_ratio: float = 3.0  # Ratio padrão limit:request para memória
    min_cpu_request: str = "10m"  # Mínimo de CPU request
    min_memory_request: str = "32Mi"  # Mínimo de memória request
    
    # Namespaces críticos para VPA
    critical_namespaces: List[str] = [
        "openshift-monitoring",
        "openshift-ingress",
        "openshift-apiserver",
        "openshift-controller-manager",
        "openshift-sdn"
    ]
    
    # Configurações de relatório
    report_export_path: str = "/tmp/reports"
    
    # Configurações de segurança
    enable_rbac: bool = True
    service_account_name: str = "resource-governance-sa"
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
