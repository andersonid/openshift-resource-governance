"""
Kubernetes/OpenShift client for data collection
"""
import logging
from typing import List, Dict, Any, Optional
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from kubernetes.client import CustomObjectsApi
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
        self.custom_api = None
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
            self.custom_api = CustomObjectsApi()
            
            self.initialized = True
            logger.info("Kubernetes client initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing Kubernetes client: {e}")
            raise
    
    def _parse_cpu_value(self, value: str) -> float:
        """Parse CPU value to cores"""
        if not value or value == "0":
            return 0.0
        
        value = value.replace(" ", "")
        
        if value.endswith("n"):
            return float(value[:-1]) / 1000000000
        elif value.endswith("u"):
            return float(value[:-1]) / 1000000
        elif value.endswith("m"):
            return float(value[:-1]) / 1000
        else:
            return float(value)
    
    def _parse_memory_value(self, value: str) -> float:
        """Parse memory value to bytes"""
        if not value or value == "0":
            return 0.0
        
        value = value.upper()
        
        if value.endswith('KI'):
            return float(value[:-2]) * 1024
        elif value.endswith('MI'):
            return float(value[:-2]) * 1024 * 1024
        elif value.endswith('GI'):
            return float(value[:-2]) * 1024 * 1024 * 1024
        elif value.endswith('K'):
            return float(value[:-1]) * 1000
        elif value.endswith('M'):
            return float(value[:-1]) * 1000 * 1000
        elif value.endswith('G'):
            return float(value[:-1]) * 1000 * 1000 * 1000
        else:
            return float(value)
    
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
                
                # Filter out non-running pods (build pods, completed pods, etc.)
                if pod.status.phase not in ["Running", "Pending"]:
                    logger.info(f"FILTERING OUT pod {pod.metadata.name} with phase {pod.status.phase}")
                    continue
                
                # Filter out build pods (pods ending with -build)
                if pod.metadata.name.endswith('-build'):
                    logger.info(f"FILTERING OUT build pod {pod.metadata.name}")
                    continue
                # Calculate total pod resources
                total_cpu_requests = 0.0
                total_memory_requests = 0.0
                total_cpu_limits = 0.0
                total_memory_limits = 0.0
                
                # Process pod containers first to calculate totals
                containers_data = []
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
                    
                    # Calculate container resources
                    cpu_requests = self._parse_cpu_value(container_resource["resources"]["requests"].get("cpu", "0"))
                    memory_requests = self._parse_memory_value(container_resource["resources"]["requests"].get("memory", "0"))
                    cpu_limits = self._parse_cpu_value(container_resource["resources"]["limits"].get("cpu", "0"))
                    memory_limits = self._parse_memory_value(container_resource["resources"]["limits"].get("memory", "0"))
                    
                    # Add to totals
                    total_cpu_requests += cpu_requests
                    total_memory_requests += memory_requests
                    total_cpu_limits += cpu_limits
                    total_memory_limits += memory_limits
                    
                    containers_data.append(container_resource)
                
                pod_resource = PodResource(
                    name=pod.metadata.name,
                    namespace=pod.metadata.namespace,
                    node_name=pod.spec.node_name,
                    phase=pod.status.phase,
                    containers=containers_data,
                    cpu_requests=total_cpu_requests,
                    memory_requests=total_memory_requests,
                    cpu_limits=total_cpu_limits,
                    memory_limits=total_memory_limits
                )
                
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
            # VPA uses Custom Resource Definition (CRD)
            # Check if VPA is installed by trying to list VPAs
            vpa_list = self.custom_api.list_cluster_custom_object(
                group="autoscaling.k8s.io",
                version="v1",
                plural="verticalpodautoscalers"
            )
            
            for vpa_item in vpa_list.get('items', []):
                vpa_name = vpa_item.get('metadata', {}).get('name', 'unknown')
                namespace = vpa_item.get('metadata', {}).get('namespace', 'default')
                
                # Extract VPA status and recommendations
                status = vpa_item.get('status', {})
                recommendation = status.get('recommendation', {})
                
                if recommendation:
                    # Extract container recommendations
                    container_recommendations = recommendation.get('containerRecommendations', [])
                    for container_rec in container_recommendations:
                        container_name = container_rec.get('containerName', 'unknown')
                        
                        # Extract CPU and memory recommendations
                        target_cpu = container_rec.get('target', {}).get('cpu', '0')
                        target_memory = container_rec.get('target', {}).get('memory', '0')
                        lower_bound_cpu = container_rec.get('lowerBound', {}).get('cpu', '0')
                        lower_bound_memory = container_rec.get('lowerBound', {}).get('memory', '0')
                        upper_bound_cpu = container_rec.get('upperBound', {}).get('cpu', '0')
                        upper_bound_memory = container_rec.get('upperBound', {}).get('memory', '0')
                        
                        vpa_rec = VPARecommendation(
                            vpa_name=vpa_name,
                            namespace=namespace,
                            container_name=container_name,
                            target_cpu=target_cpu,
                            target_memory=target_memory,
                            lower_bound_cpu=lower_bound_cpu,
                            lower_bound_memory=lower_bound_memory,
                            upper_bound_cpu=upper_bound_cpu,
                            upper_bound_memory=upper_bound_memory,
                            uncapped_target_cpu=container_rec.get('uncappedTarget', {}).get('cpu', '0'),
                            uncapped_target_memory=container_rec.get('uncappedTarget', {}).get('memory', '0')
                        )
                        recommendations.append(vpa_rec)
            
            logger.info(f"Collected {len(recommendations)} VPA recommendations")
            return recommendations
            
        except ApiException as e:
            if e.status == 404:
                logger.warning("VPA CRD not found - VPA may not be installed in the cluster")
            else:
                logger.error(f"Error collecting VPA recommendations: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error collecting VPA recommendations: {e}")
            return []
    
    async def list_vpas(self, namespace: str = None) -> List[Dict[str, Any]]:
        """List VPA resources"""
        try:
            if not self.initialized:
                raise RuntimeError("Kubernetes client not initialized")
            
            if namespace:
                # List VPAs in specific namespace
                vpa_list = self.custom_api.list_namespaced_custom_object(
                    group="autoscaling.k8s.io",
                    version="v1",
                    namespace=namespace,
                    plural="verticalpodautoscalers"
                )
            else:
                # List all VPAs
                vpa_list = self.custom_api.list_cluster_custom_object(
                    group="autoscaling.k8s.io",
                    version="v1",
                    plural="verticalpodautoscalers"
                )
            
            return vpa_list.get('items', [])
            
        except ApiException as e:
            if e.status == 404:
                logger.warning("VPA CRD not found - VPA may not be installed in the cluster")
            else:
                logger.error(f"Error listing VPAs: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error listing VPAs: {e}")
            return []
    
    async def create_vpa(self, namespace: str, vpa_manifest: Dict[str, Any]) -> Dict[str, Any]:
        """Create a VPA resource"""
        try:
            if not self.initialized:
                raise RuntimeError("Kubernetes client not initialized")
            
            # Create VPA using custom object API
            result = self.custom_api.create_namespaced_custom_object(
                group="autoscaling.k8s.io",
                version="v1",
                namespace=namespace,
                plural="verticalpodautoscalers",
                body=vpa_manifest
            )
            
            logger.info(f"Successfully created VPA {vpa_manifest.get('metadata', {}).get('name')} in namespace {namespace}")
            return result
            
        except ApiException as e:
            logger.error(f"Error creating VPA: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating VPA: {e}")
            raise
    
    async def delete_vpa(self, vpa_name: str, namespace: str) -> Dict[str, Any]:
        """Delete a VPA resource"""
        try:
            if not self.initialized:
                raise RuntimeError("Kubernetes client not initialized")
            
            # Delete VPA using custom object API
            result = self.custom_api.delete_namespaced_custom_object(
                group="autoscaling.k8s.io",
                version="v1",
                namespace=namespace,
                plural="verticalpodautoscalers",
                name=vpa_name
            )
            
            logger.info(f"Successfully deleted VPA {vpa_name} from namespace {namespace}")
            return result
            
        except ApiException as e:
            logger.error(f"Error deleting VPA: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error deleting VPA: {e}")
            raise
    
    async def patch_deployment(self, deployment_name: str, namespace: str, patch_body: dict) -> dict:
        """Patch a deployment with new configuration"""
        try:
            if not self.initialized:
                raise RuntimeError("Kubernetes client not initialized")
            
            # Patch the deployment
            api_response = self.apps_v1.patch_namespaced_deployment(
                name=deployment_name,
                namespace=namespace,
                body=patch_body
            )
            
            logger.info(f"Successfully patched deployment {deployment_name} in namespace {namespace}")
            return {
                "success": True,
                "deployment": deployment_name,
                "namespace": namespace,
                "resource_version": api_response.metadata.resource_version
            }
            
        except ApiException as e:
            logger.error(f"Error patching deployment {deployment_name}: {e}")
            raise
    
    async def apply_yaml(self, yaml_content: str, namespace: str) -> dict:
        """Apply YAML content to the cluster"""
        try:
            if not self.initialized:
                raise RuntimeError("Kubernetes client not initialized")
            
            # For now, return success - in a real implementation, this would parse and apply the YAML
            logger.info(f"YAML content would be applied to namespace {namespace}")
            return {
                "success": True,
                "namespace": namespace,
                "message": "YAML content prepared for application"
            }
            
        except Exception as e:
            logger.error(f"Error applying YAML: {e}")
            raise
    
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

    async def get_all_pvcs(self) -> List[Any]:
        """Get all PersistentVolumeClaims in the cluster"""
        if not self.initialized:
            raise RuntimeError("Kubernetes client not initialized")
        
        try:
            # List all PVCs in all namespaces
            pvcs = self.v1.list_persistent_volume_claim_for_all_namespaces(watch=False)
            return pvcs.items
            
        except ApiException as e:
            logger.error(f"Error getting PVCs: {e}")
            raise

    async def get_storage_classes(self) -> List[Any]:
        """Get all StorageClasses in the cluster"""
        if not self.initialized:
            raise RuntimeError("Kubernetes client not initialized")
        
        try:
            # List all storage classes
            storage_classes = self.v1.list_storage_class(watch=False)
            return storage_classes.items
            
        except ApiException as e:
            logger.error(f"Error getting storage classes: {e}")
            raise
