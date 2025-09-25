"""
Cliente Kubernetes/OpenShift para coleta de dados
"""
import logging
from typing import List, Dict, Any, Optional
from kubernetes import client, config
from kubernetes.client.rest import ApiException
import asyncio
import aiohttp

from app.core.config import settings
from app.models.resource_models import PodResource, NamespaceResources, VPARecommendation

logger = logging.getLogger(__name__)

class K8sClient:
    """Cliente para interação com Kubernetes/OpenShift"""
    
    def __init__(self):
        self.v1 = None
        self.autoscaling_v1 = None
        self.apps_v1 = None
        self.initialized = False
    
    async def initialize(self):
        """Inicializar cliente Kubernetes"""
        try:
            # Tentar carregar configuração do cluster
            if settings.kubeconfig_path:
                config.load_kube_config(config_file=settings.kubeconfig_path)
            else:
                # Usar configuração in-cluster
                config.load_incluster_config()
            
            # Inicializar clientes da API
            self.v1 = client.CoreV1Api()
            self.autoscaling_v1 = client.AutoscalingV1Api()
            self.apps_v1 = client.AppsV1Api()
            
            self.initialized = True
            logger.info("Kubernetes client initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing Kubernetes client: {e}")
            raise
    
    def _is_system_namespace(self, namespace: str, include_system: bool = None) -> bool:
        """Verificar se um namespace é do sistema"""
        # Usar parâmetro se fornecido, senão usar configuração global
        should_include = include_system if include_system is not None else settings.include_system_namespaces
        
        if should_include:
            return False
        
        for prefix in settings.system_namespace_prefixes:
            if namespace.startswith(prefix):
                return True
        return False
    
    async def get_all_pods(self, include_system_namespaces: bool = None) -> List[PodResource]:
        """Coletar informações de todos os pods do cluster"""
        if not self.initialized:
            raise RuntimeError("Kubernetes client not initialized")
        
        pods_data = []
        
        try:
            # Listar todos os pods em todos os namespaces
            pods = self.v1.list_pod_for_all_namespaces(watch=False)
            
            for pod in pods.items:
                # Filtrar namespaces do sistema
                if self._is_system_namespace(pod.metadata.namespace, include_system_namespaces):
                    continue
                pod_resource = PodResource(
                    name=pod.metadata.name,
                    namespace=pod.metadata.namespace,
                    node_name=pod.spec.node_name,
                    phase=pod.status.phase,
                    containers=[]
                )
                
                # Processar containers do pod
                for container in pod.spec.containers:
                    container_resource = {
                        "name": container.name,
                        "image": container.image,
                        "resources": {
                            "requests": {},
                            "limits": {}
                        }
                    }
                    
                    # Extrair requests e limits
                    if container.resources:
                        if container.resources.requests:
                            container_resource["resources"]["requests"] = {
                                k: v for k, v in container.resources.requests.items()
                            }
                        if container.resources.limits:
                            container_resource["resources"]["limits"] = {
                                k: v for k, v in container.resources.limits.items()
                            }
                    
                    pod_resource.containers.append(container_resource)
                
                pods_data.append(pod_resource)
            
            logger.info(f"Coletados {len(pods_data)} pods")
            return pods_data
            
        except ApiException as e:
            logger.error(f"Error listing pods: {e}")
            raise
    
    async def get_namespace_resources(self, namespace: str) -> NamespaceResources:
        """Coletar recursos de um namespace específico"""
        if not self.initialized:
            raise RuntimeError("Kubernetes client not initialized")
        
        # Verificar se é namespace do sistema
        if self._is_system_namespace(namespace):
            logger.info(f"Namespace {namespace} é do sistema, retornando vazio")
            return NamespaceResources(
                name=namespace,
                pods=[],
                total_cpu_requests="0",
                total_cpu_limits="0",
                total_memory_requests="0",
                total_memory_limits="0"
            )
        
        try:
            # Listar pods do namespace
            pods = self.v1.list_namespaced_pod(namespace=namespace)
            
            namespace_resource = NamespaceResources(
                name=namespace,
                pods=[],
                total_cpu_requests="0",
                total_cpu_limits="0",
                total_memory_requests="0",
                total_memory_limits="0"
            )
            
            for pod in pods.items:
                pod_resource = PodResource(
                    name=pod.metadata.name,
                    namespace=pod.metadata.namespace,
                    node_name=pod.spec.node_name,
                    phase=pod.status.phase,
                    containers=[]
                )
                
                for container in pod.spec.containers:
                    container_resource = {
                        "name": container.name,
                        "image": container.image,
                        "resources": {
                            "requests": {},
                            "limits": {}
                        }
                    }
                    
                    if container.resources:
                        if container.resources.requests:
                            container_resource["resources"]["requests"] = {
                                k: v for k, v in container.resources.requests.items()
                            }
                        if container.resources.limits:
                            container_resource["resources"]["limits"] = {
                                k: v for k, v in container.resources.limits.items()
                            }
                    
                    pod_resource.containers.append(container_resource)
                
                namespace_resource.pods.append(pod_resource)
            
            return namespace_resource
            
        except ApiException as e:
            logger.error(f"Error collecting resources for namespace {namespace}: {e}")
            raise
    
    async def get_vpa_recommendations(self) -> List[VPARecommendation]:
        """Coletar recomendações do VPA"""
        if not self.initialized:
            raise RuntimeError("Kubernetes client not initialized")
        
        recommendations = []
        
        try:
            # VPA não está disponível na API padrão do Kubernetes
            # TODO: Implementar usando Custom Resource Definition (CRD)
            logger.warning("VPA não está disponível na API padrão do Kubernetes")
            return []
            
            logger.info(f"Coletadas {len(recommendations)} recomendações VPA")
            return recommendations
            
        except ApiException as e:
            logger.error(f"Error collecting VPA recommendations: {e}")
            # VPA pode não estar instalado, retornar lista vazia
            return []
    
    async def get_nodes_info(self) -> List[Dict[str, Any]]:
        """Coletar informações dos nós do cluster"""
        if not self.initialized:
            raise RuntimeError("Kubernetes client not initialized")
        
        try:
            nodes = self.v1.list_node()
            nodes_info = []
            
            for node in nodes.items:
                node_info = {
                    "name": node.metadata.name,
                    "labels": node.metadata.labels or {},
                    "capacity": {},
                    "allocatable": {},
                    "conditions": []
                }
                
                # Capacidade do nó
                if node.status.capacity:
                    node_info["capacity"] = {
                        k: v for k, v in node.status.capacity.items()
                    }
                
                # Recursos alocáveis
                if node.status.allocatable:
                    node_info["allocatable"] = {
                        k: v for k, v in node.status.allocatable.items()
                    }
                
                # Condições do nó
                if node.status.conditions:
                    node_info["conditions"] = [
                        {
                            "type": condition.type,
                            "status": condition.status,
                            "reason": condition.reason,
                            "message": condition.message
                        }
                        for condition in node.status.conditions
                    ]
                
                nodes_info.append(node_info)
            
            return nodes_info
            
        except ApiException as e:
            logger.error(f"Error collecting node information: {e}")
            raise
