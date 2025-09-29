"""
Kubernetes/OpenShift client for data collection
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
    """Client for interaction with Kubernetes/OpenShift"""
    
    def __init__(self):
        self.v1 = None
        self.autoscaling_v1 = None
        self.apps_v1 = None
        self.initialized = False
    
    async def initialize(self):
        """Initialize Kubernetes client"""
        try:
            # Try to load cluster configuration
            if settings.kubeconfig_path:
                config.load_kube_config(config_file=settings.kubeconfig_path)
            else:
                # Use in-cluster configuration
                try:
                    config.load_incluster_config()
                except config.ConfigException:
                    # If in-cluster config fails, try to use service account token
                    try:
                        with open('/var/run/secrets/kubernetes.io/serviceaccount/token', 'r') as f:
                            token = f.read().strip()
                        
                        with open('/var/run/secrets/kubernetes.io/serviceaccount/namespace', 'r') as f:
                            namespace = f.read().strip()
                        
                        # Create configuration with token and handle SSL properly
                        configuration = client.Configuration()
                        configuration.host = f"https://kubernetes.default.svc"
                        configuration.api_key = {"authorization": f"Bearer {token}"}
                        
                        # Try to use CA cert, but disable SSL verification if not available
                        try:
                            with open('/var/run/secrets/kubernetes.io/serviceaccount/ca.crt', 'r') as f:
                                ca_cert = f.read().strip()
                            if ca_cert:
                                configuration.ssl_ca_cert = '/var/run/secrets/kubernetes.io/serviceaccount/ca.crt'
                                configuration.verify_ssl = True
                            else:
                                configuration.verify_ssl = False
                        except:
                            configuration.verify_ssl = False
                        
                        client.Configuration.set_default(configuration)
                        
                    except FileNotFoundError:
                        # Fallback to default configuration
                        config.load_kube_config()
            
            # Initialize API clients
            self.v1 = client.CoreV1Api()
            self.autoscaling_v1 = client.AutoscalingV1Api()
            self.apps_v1 = client.AppsV1Api()
            
            self.initialized = True
            logger.info("Kubernetes client initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing Kubernetes client: {e}")
            raise
    
    def _is_system_namespace(self, namespace: str, include_system: bool = None) -> bool:
        """Check if a namespace is a system namespace"""
        # Use parameter if provided, otherwise use global configuration
        should_include = include_system if include_system is not None else settings.include_system_namespaces
        
        if should_include:
            return False
        
        for prefix in settings.system_namespace_prefixes:
            if namespace.startswith(prefix):
                return True
        return False
    
    async def get_all_pods(self, include_system_namespaces: bool = None) -> List[PodResource]:
        """Collect information from all pods in the cluster"""
        if not self.initialized:
            raise RuntimeError("Kubernetes client not initialized")
        
        pods_data = []
        
        try:
            # List all pods in all namespaces
            pods = self.v1.list_pod_for_all_namespaces(watch=False)
            
            for pod in pods.items:
                # Filter system namespaces
                if self._is_system_namespace(pod.metadata.namespace, include_system_namespaces):
                    continue
                pod_resource = PodResource(
                    name=pod.metadata.name,
                    namespace=pod.metadata.namespace,
                    node_name=pod.spec.node_name,
                    phase=pod.status.phase,
                    containers=[]
                )
                
                # Process pod containers
                for container in pod.spec.containers:
                    container_resource = {
                        "name": container.name,
                        "image": container.image,
                        "resources": {
                            "requests": {},
                            "limits": {}
                        }
                    }
                    
                    # Extract requests and limits
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
            
            logger.info(f"Collected {len(pods_data)} pods")
            return pods_data
            
        except ApiException as e:
            logger.error(f"Error listing pods: {e}")
            raise
    
    async def get_namespace_resources(self, namespace: str) -> NamespaceResources:
        """Collect resources from a specific namespace"""
        if not self.initialized:
            raise RuntimeError("Kubernetes client not initialized")
        
        # Check if it's a system namespace
        if self._is_system_namespace(namespace):
            logger.info(f"Namespace {namespace} is system, returning empty")
            return NamespaceResources(
                name=namespace,
                pods=[],
                total_cpu_requests="0",
                total_cpu_limits="0",
                total_memory_requests="0",
                total_memory_limits="0"
            )
        
        try:
            # List namespace pods
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
        """Collect VPA recommendations"""
        if not self.initialized:
            raise RuntimeError("Kubernetes client not initialized")
        
        recommendations = []
        
        try:
            # VPA is not available in the standard Kubernetes API
            # TODO: Implement using Custom Resource Definition (CRD)
            logger.warning("VPA is not available in the standard Kubernetes API")
            return []
            
            logger.info(f"Collected {len(recommendations)} VPA recommendations")
            return recommendations
            
        except ApiException as e:
            logger.error(f"Error collecting VPA recommendations: {e}")
            # VPA may not be installed, return empty list
            return []
    
    async def get_nodes_info(self) -> List[Dict[str, Any]]:
        """Collect cluster node information"""
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
                
                # Node capacity
                if node.status.capacity:
                    node_info["capacity"] = {
                        k: v for k, v in node.status.capacity.items()
                    }
                
                # Allocatable resources
                if node.status.allocatable:
                    node_info["allocatable"] = {
                        k: v for k, v in node.status.allocatable.items()
                    }
                
                # Node conditions
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
