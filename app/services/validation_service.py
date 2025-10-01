"""
Resource validation service following Red Hat best practices
"""
import logging
from typing import List, Dict, Any, Optional
from decimal import Decimal, InvalidOperation
import re

from app.models.resource_models import (
    PodResource, 
    ResourceValidation, 
    NamespaceResources,
    QoSClassification,
    ResourceQuota,
    ClusterHealth,
    PodHealthScore,
    SimplifiedValidation
)
from app.core.config import settings
from app.services.historical_analysis import HistoricalAnalysisService
from app.services.smart_recommendations import SmartRecommendationsService

logger = logging.getLogger(__name__)

class ValidationService:
    """Service for resource validation"""
    
    def __init__(self):
        self.cpu_ratio = settings.cpu_limit_ratio
        self.memory_ratio = settings.memory_limit_ratio
        self.min_cpu_request = settings.min_cpu_request
        self.min_memory_request = settings.min_memory_request
        self.historical_analysis = HistoricalAnalysisService()
        self.smart_recommendations = SmartRecommendationsService()
    
    def validate_pod_resources(self, pod: PodResource) -> List[ResourceValidation]:
        """Validate pod resources"""
        validations = []
        
        for container in pod.containers:
            container_validations = self._validate_container_resources(
                pod.name, pod.namespace, container
            )
            validations.extend(container_validations)
        
        return validations
    
    async def validate_pod_resources_with_historical_analysis(
        self, 
        pod: PodResource, 
        time_range: str = '24h'
    ) -> List[ResourceValidation]:
        """Validate pod resources including historical analysis"""
        # Static validations
        static_validations = self.validate_pod_resources(pod)
        
        # Historical analysis
        try:
            historical_validations = await self.historical_analysis.analyze_pod_historical_usage(
                pod, time_range
            )
            static_validations.extend(historical_validations)
        except Exception as e:
            logger.warning(f"Error in historical analysis for pod {pod.name}: {e}")
        
        return static_validations

    async def validate_workload_resources_with_historical_analysis(
        self, 
        pods: List[PodResource], 
        time_range: str = '24h'
    ) -> List[ResourceValidation]:
        """Validate workload resources including historical analysis (recommended approach)"""
        all_validations = []
        
        # Static validations for all pods
        for pod in pods:
            static_validations = self.validate_pod_resources(pod)
            all_validations.extend(static_validations)
        
        # Historical analysis by workload (more reliable than individual pods)
        try:
            historical_validations = await self.historical_analysis.analyze_workload_historical_usage(
                pods, time_range
            )
            all_validations.extend(historical_validations)
        except Exception as e:
            logger.warning(f"Error in workload historical analysis: {e}")
            # Fallback to individual pod analysis
            for pod in pods:
                try:
                    pod_historical = await self.historical_analysis.analyze_pod_historical_usage(
                        pod, time_range
                    )
                    all_validations.extend(pod_historical)
                except Exception as pod_e:
                    logger.warning(f"Error in historical analysis for pod {pod.name}: {pod_e}")
        
        return all_validations
    
    def _validate_container_resources(
        self, 
        pod_name: str, 
        namespace: str, 
        container: Any
    ) -> List[ResourceValidation]:
        """Validate container resources"""
        validations = []
        resources = container["resources"]
        requests = resources.get("requests", {})
        limits = resources.get("limits", {})
        
        # Determine QoS class based on Red Hat best practices
        qos_class = self._determine_qos_class(requests, limits)
        
        # 1. Check if requests are defined
        if not requests:
            validations.append(ResourceValidation(
                pod_name=pod_name,
                namespace=namespace,
                container_name=container["name"],
                validation_type="missing_requests",
                severity="error",
                message="Container without defined requests",
                recommendation="Define CPU and memory requests to guarantee QoS (currently BestEffort class)"
            ))
        
        # 2. Check if limits are defined
        if not limits:
            validations.append(ResourceValidation(
                pod_name=pod_name,
                namespace=namespace,
                container_name=container["name"],
                validation_type="missing_limits",
                severity="warning",
                message="Container without defined limits",
                recommendation="Define limits to avoid excessive resource consumption"
            ))
        
        # 3. Validate limit:request ratio (only if both requests and limits exist)
        if requests and limits:
            cpu_validation = self._validate_cpu_ratio(
                pod_name, namespace, container["name"], requests, limits
            )
            if cpu_validation:
                validations.append(cpu_validation)
            
            memory_validation = self._validate_memory_ratio(
                pod_name, namespace, container["name"], requests, limits
            )
            if memory_validation:
                validations.append(memory_validation)
        
        # 4. Add container resource metrics validation (only if resources exist)
        if requests or limits:
            metrics_validation = self._validate_container_metrics(
                pod_name, namespace, container["name"], requests, limits
            )
            if metrics_validation:
                validations.append(metrics_validation)
        
        # 5. Validate minimum values (only if requests exist)
        if requests:
            min_validation = self._validate_minimum_values(
                pod_name, namespace, container["name"], requests
            )
            validations.extend(min_validation)
        
        return validations
    
    def _validate_cpu_ratio(
        self, 
        pod_name: str, 
        namespace: str, 
        container_name: str,
        requests: Dict[str, str], 
        limits: Dict[str, str]
    ) -> ResourceValidation:
        """Validate CPU limit:request ratio"""
        if "cpu" not in requests or "cpu" not in limits:
            return None
        
        try:
            request_value = self._parse_cpu_value(requests["cpu"])
            limit_value = self._parse_cpu_value(limits["cpu"])
            
            if request_value > 0:
                ratio = limit_value / request_value
                
                if ratio > self.cpu_ratio:  # Sem tolerância excessiva
                    return ResourceValidation(
                        pod_name=pod_name,
                        namespace=namespace,
                        container_name=container_name,
                        validation_type="invalid_ratio",
                        severity="warning",
                        message=f"CPU limit:request ratio too high ({ratio:.2f}:1) - Request: {requests['cpu']}, Limit: {limits['cpu']}",
                        recommendation=f"Consider reducing limits or increasing requests (recommended ratio: {self.cpu_ratio}:1)"
                    )
                elif ratio < 1.0:
                    return ResourceValidation(
                        pod_name=pod_name,
                        namespace=namespace,
                        container_name=container_name,
                        validation_type="invalid_ratio",
                        severity="error",
                        message=f"CPU limit less than request ({ratio:.2f}:1) - Request: {requests['cpu']}, Limit: {limits['cpu']}",
                        recommendation="CPU limit should be greater than or equal to request"
                    )
        
        except (ValueError, InvalidOperation) as e:
            logger.warning(f"Error validating CPU ratio: {e}")
        
        return None
    
    def _validate_memory_ratio(
        self, 
        pod_name: str, 
        namespace: str, 
        container_name: str,
        requests: Dict[str, str], 
        limits: Dict[str, str]
    ) -> ResourceValidation:
        """Validate memory limit:request ratio"""
        if "memory" not in requests or "memory" not in limits:
            return None
        
        try:
            request_value = self._parse_memory_value(requests["memory"])
            limit_value = self._parse_memory_value(limits["memory"])
            
            if request_value > 0:
                ratio = limit_value / request_value
                
                if ratio > self.memory_ratio:  # Sem tolerância excessiva
                    return ResourceValidation(
                        pod_name=pod_name,
                        namespace=namespace,
                        container_name=container_name,
                        validation_type="invalid_ratio",
                        severity="warning",
                        message=f"Memory limit:request ratio too high ({ratio:.2f}:1) - Request: {requests['memory']}, Limit: {limits['memory']}",
                        recommendation=f"Consider reducing limits or increasing requests (recommended ratio: {self.memory_ratio}:1)"
                    )
                elif ratio < 1.0:
                    return ResourceValidation(
                        pod_name=pod_name,
                        namespace=namespace,
                        container_name=container_name,
                        validation_type="invalid_ratio",
                        severity="error",
                        message=f"Memory limit less than request ({ratio:.2f}:1) - Request: {requests['memory']}, Limit: {limits['memory']}",
                        recommendation="Memory limit should be greater than or equal to request"
                    )
        
        except (ValueError, InvalidOperation) as e:
            logger.warning(f"Error validating memory ratio: {e}")
        
        return None
    
    def _validate_container_metrics(
        self,
        pod_name: str,
        namespace: str,
        container_name: str,
        requests: Dict[str, str],
        limits: Dict[str, str]
    ) -> ResourceValidation:
        """Show container resource metrics and analysis"""
        try:
            # Parse CPU values
            cpu_request = requests.get("cpu", "0")
            cpu_limit = limits.get("cpu", "0")
            cpu_request_parsed = self._parse_cpu_value(cpu_request)
            cpu_limit_parsed = self._parse_cpu_value(cpu_limit)
            
            # Parse Memory values
            memory_request = requests.get("memory", "0")
            memory_limit = limits.get("memory", "0")
            memory_request_parsed = self._parse_memory_value(memory_request)
            memory_limit_parsed = self._parse_memory_value(memory_limit)
            
            # Calculate ratios
            cpu_ratio = cpu_limit_parsed / cpu_request_parsed if cpu_request_parsed > 0 else 0
            memory_ratio = memory_limit_parsed / memory_request_parsed if memory_request_parsed > 0 else 0
            
            # Format values for display
            cpu_request_display = f"{cpu_request_parsed:.1f} cores" if cpu_request_parsed >= 1.0 else f"{cpu_request_parsed * 1000:.0f}m"
            cpu_limit_display = f"{cpu_limit_parsed:.1f} cores" if cpu_limit_parsed >= 1.0 else f"{cpu_limit_parsed * 1000:.0f}m"
            
            memory_request_display = f"{memory_request_parsed / (1024*1024*1024):.1f} GiB" if memory_request_parsed >= 1024*1024*1024 else f"{memory_request_parsed / (1024*1024):.0f} MiB"
            memory_limit_display = f"{memory_limit_parsed / (1024*1024*1024):.1f} GiB" if memory_limit_parsed >= 1024*1024*1024 else f"{memory_limit_parsed / (1024*1024):.0f} MiB"
            
            # Create detailed message
            message = f"Container Resources - CPU: {cpu_request_display}→{cpu_limit_display} (ratio: {cpu_ratio:.1f}:1), Memory: {memory_request_display}→{memory_limit_display} (ratio: {memory_ratio:.1f}:1)"
            
            # Create recommendation based on ratios
            recommendations = []
            if cpu_ratio > self.cpu_ratio:
                recommendations.append(f"CPU ratio {cpu_ratio:.1f}:1 exceeds recommended {self.cpu_ratio}:1")
            if memory_ratio > self.memory_ratio:
                recommendations.append(f"Memory ratio {memory_ratio:.1f}:1 exceeds recommended {self.memory_ratio}:1")
            
            recommendation = "; ".join(recommendations) if recommendations else f"Resource allocation within recommended ratios (CPU: {self.cpu_ratio}:1, Memory: {self.memory_ratio}:1)"
            
            return ResourceValidation(
                pod_name=pod_name,
                namespace=namespace,
                container_name=container_name,
                validation_type="container_metrics",
                severity="info",
                message=message,
                recommendation=recommendation
            )
            
        except Exception as e:
            logger.warning(f"Error validating container metrics: {e}")
            return None
    
    def _validate_minimum_values(
        self, 
        pod_name: str, 
        namespace: str, 
        container_name: str,
        requests: Dict[str, str]
    ) -> List[ResourceValidation]:
        """Validate minimum request values"""
        validations = []
        
        # Validate minimum CPU
        if "cpu" in requests:
            try:
                request_value = self._parse_cpu_value(requests["cpu"])
                min_value = self._parse_cpu_value(self.min_cpu_request)
                
                if request_value < min_value:
                    validations.append(ResourceValidation(
                        pod_name=pod_name,
                        namespace=namespace,
                        container_name=container_name,
                        validation_type="minimum_value",
                        severity="warning",
                        message=f"CPU request too low ({requests['cpu']})",
                        recommendation=f"Consider increasing to at least {self.min_cpu_request}"
                    ))
            except (ValueError, InvalidOperation):
                pass
        
        # Validate minimum memory
        if "memory" in requests:
            try:
                request_value = self._parse_memory_value(requests["memory"])
                min_value = self._parse_memory_value(self.min_memory_request)
                
                if request_value < min_value:
                    validations.append(ResourceValidation(
                        pod_name=pod_name,
                        namespace=namespace,
                        container_name=container_name,
                        validation_type="minimum_value",
                        severity="warning",
                        message=f"Memory request too low ({requests['memory']})",
                        recommendation=f"Consider increasing to at least {self.min_memory_request}"
                    ))
            except (ValueError, InvalidOperation):
                pass
        
        return validations
    
    def _parse_cpu_value(self, value: str) -> float:
        """Convert CPU value to float (cores)"""
        if value.endswith('m'):
            return float(value[:-1]) / 1000
        elif value.endswith('n'):
            return float(value[:-1]) / 1000000000
        else:
            return float(value)
    
    def _parse_memory_value(self, value: str) -> int:
        """Convert memory value to bytes"""
        value = value.upper()
        
        if value.endswith('KI'):
            return int(float(value[:-2]) * 1024)
        elif value.endswith('MI'):
            return int(float(value[:-2]) * 1024 * 1024)
        elif value.endswith('GI'):
            return int(float(value[:-2]) * 1024 * 1024 * 1024)
        elif value.endswith('K'):
            return int(float(value[:-1]) * 1000)
        elif value.endswith('M'):
            return int(float(value[:-1]) * 1000 * 1000)
        elif value.endswith('G'):
            return int(float(value[:-1]) * 1000 * 1000 * 1000)
        else:
            return int(value)
    
    def _determine_qos_class(self, requests: Dict[str, str], limits: Dict[str, str]) -> str:
        """Determine QoS class based on requests and limits"""
        cpu_requests = self._parse_cpu_value(requests.get("cpu", "0"))
        memory_requests = self._parse_memory_value(requests.get("memory", "0")) / (1024 * 1024 * 1024)  # Convert to GB
        cpu_limits = self._parse_cpu_value(limits.get("cpu", "0"))
        memory_limits = self._parse_memory_value(limits.get("memory", "0")) / (1024 * 1024 * 1024)  # Convert to GB
        
        # Guaranteed: both CPU and memory requests and limits are set and equal
        if (cpu_requests > 0 and memory_requests > 0 and 
            cpu_requests == cpu_limits and memory_requests == memory_limits):
            return "Guaranteed"
        
        # Burstable: at least one request is set
        elif cpu_requests > 0 or memory_requests > 0:
            return "Burstable"
        
        # BestEffort: no requests set
        else:
            return "BestEffort"
    
    
    def validate_namespace_overcommit(
        self, 
        namespace_resources: NamespaceResources,
        node_capacity: Dict[str, str]
    ) -> List[ResourceValidation]:
        """Validate overcommit in a namespace"""
        validations = []
        
        # Calculate total namespace requests
        total_cpu_requests = self._parse_cpu_value(namespace_resources.total_cpu_requests)
        total_memory_requests = self._parse_memory_value(namespace_resources.total_memory_requests)
        
        # Calculate total node capacity
        total_cpu_capacity = self._parse_cpu_value(node_capacity.get("cpu", "0"))
        total_memory_capacity = self._parse_memory_value(node_capacity.get("memory", "0"))
        
        # Check CPU overcommit
        if total_cpu_capacity > 0:
            cpu_utilization = (total_cpu_requests / total_cpu_capacity) * 100
            if cpu_utilization > 100:
                validations.append(ResourceValidation(
                    pod_name="namespace",
                    namespace=namespace_resources.name,
                    container_name="all",
                    validation_type="overcommit",
                    severity="critical",
                    message=f"CPU overcommit in namespace: {cpu_utilization:.1f}%",
                    recommendation="Reduce CPU requests or add more nodes to the cluster"
                ))
        
        # Check memory overcommit
        if total_memory_capacity > 0:
            memory_utilization = (total_memory_requests / total_memory_capacity) * 100
            if memory_utilization > 100:
                validations.append(ResourceValidation(
                    pod_name="namespace",
                    namespace=namespace_resources.name,
                    container_name="all",
                    validation_type="overcommit",
                    severity="critical",
                    message=f"Memory overcommit in namespace: {memory_utilization:.1f}%",
                    recommendation="Reduce memory requests or add more nodes to the cluster"
                ))
        
        return validations
    
    def generate_recommendations(self, validations: List[ResourceValidation]) -> List[str]:
        """Generate recommendations based on validations"""
        recommendations = []
        
        # Group validations by type
        validation_counts = {}
        for validation in validations:
            validation_type = validation.validation_type
            if validation_type not in validation_counts:
                validation_counts[validation_type] = 0
            validation_counts[validation_type] += 1
        
        # Generate recommendations based on found issues
        if validation_counts.get("missing_requests", 0) > 0:
            recommendations.append(
                f"Implement LimitRange in namespace to define default requests "
                f"({validation_counts['missing_requests']} containers without requests)"
            )
        
        if validation_counts.get("missing_limits", 0) > 0:
            recommendations.append(
                f"Define limits for {validation_counts['missing_limits']} containers "
                "to avoid excessive resource consumption"
            )
        
        if validation_counts.get("invalid_ratio", 0) > 0:
            recommendations.append(
                f"Adjust limit:request ratio for {validation_counts['invalid_ratio']} containers "
                f"(recommended: {self.cpu_ratio}:1)"
            )
        
        if validation_counts.get("overcommit", 0) > 0:
            recommendations.append(
                f"Resolve overcommit in {validation_counts['overcommit']} namespaces "
                "to avoid performance issues"
            )
        
        return recommendations
    
    async def validate_pod_resources_with_categorization(
        self, 
        pod: PodResource, 
        workload_category: str = None,
        priority_score: int = None
    ) -> List[ResourceValidation]:
        """Validate pod resources with enhanced categorization and scoring"""
        validations = self.validate_pod_resources(pod)
        
        # Add categorization and scoring to validations
        for validation in validations:
            validation.workload_category = workload_category
            validation.priority_score = priority_score or self._calculate_priority_score(validation)
            validation.estimated_impact = self._determine_impact(validation.priority_score)
        
        return validations
    
    async def validate_pod_resources_with_smart_analysis(
        self, 
        pod: PodResource, 
        time_range: str = '24h'
    ) -> List[ResourceValidation]:
        """Validate pod resources with smart analysis including historical data"""
        # Static validations
        static_validations = self.validate_pod_resources(pod)
        
        # Get workload category
        workload_category = await self._categorize_workload(pod)
        
        # Get smart recommendations
        smart_recommendations = await self.smart_recommendations.generate_smart_recommendations([pod], [workload_category])
        
        # Enhance validations with smart analysis
        enhanced_validations = []
        for validation in static_validations:
            validation.workload_category = workload_category.category
            validation.priority_score = self._calculate_priority_score(validation)
            validation.estimated_impact = self._determine_impact(validation.priority_score)
            enhanced_validations.append(validation)
        
        # Add smart recommendations as validations
        for recommendation in smart_recommendations:
            smart_validation = ResourceValidation(
                pod_name=pod.name,
                namespace=pod.namespace,
                container_name="workload",
                validation_type="smart_recommendation",
                severity=recommendation.priority,
                message=recommendation.title,
                recommendation=recommendation.description,
                priority_score=self._get_priority_score_from_string(recommendation.priority),
                workload_category=workload_category.category,
                estimated_impact=recommendation.estimated_impact
            )
            enhanced_validations.append(smart_validation)
        
        return enhanced_validations
    
    async def _categorize_workload(self, pod: PodResource) -> Any:
        """Categorize a single workload"""
        categories = await self.smart_recommendations.categorize_workloads([pod])
        return categories[0] if categories else None
    
    def _get_priority_score_from_string(self, priority: str) -> int:
        """Convert priority string to numeric score"""
        priority_map = {
            "critical": 10,
            "high": 8,
            "medium": 5,
            "low": 2
        }
        return priority_map.get(priority, 5)
    
    def _calculate_priority_score(self, validation: ResourceValidation) -> int:
        """Calculate priority score for validation (1-10)"""
        score = 1
        
        # Base score by severity
        if validation.severity == "critical":
            score += 4
        elif validation.severity == "error":
            score += 3
        elif validation.severity == "warning":
            score += 1
        
        # Add score by validation type
        if validation.validation_type == "missing_requests":
            score += 3
        elif validation.validation_type == "missing_limits":
            score += 2
        elif validation.validation_type == "invalid_ratio":
            score += 1
        elif validation.validation_type == "overcommit":
            score += 4
        
        # Add score for production namespaces
        if validation.namespace in ["default", "production", "prod"]:
            score += 2
        
        return min(score, 10)
    
    def _determine_impact(self, priority_score: int) -> str:
        """Determine estimated impact based on priority score"""
        if priority_score >= 8:
            return "critical"
        elif priority_score >= 6:
            return "high"
        elif priority_score >= 4:
            return "medium"
        else:
            return "low"
    
    async def get_workload_categories(self, pods: List[PodResource]) -> List[Any]:
        """Get workload categories for all pods"""
        return await self.smart_recommendations.categorize_workloads(pods)
    
    async def get_smart_recommendations(self, pods: List[PodResource]) -> List[Any]:
        """Get smart recommendations for all workloads"""
        categories = await self.get_workload_categories(pods)
        return await self.smart_recommendations.generate_smart_recommendations(pods, categories)

    def classify_qos(self, pod: PodResource) -> QoSClassification:
        """Classify pod QoS based on Red Hat best practices"""
        cpu_requests = pod.cpu_requests
        memory_requests = pod.memory_requests
        cpu_limits = pod.cpu_limits
        memory_limits = pod.memory_limits
        
        # Determine QoS class
        if (cpu_requests > 0 and memory_requests > 0 and 
            cpu_limits > 0 and memory_limits > 0 and
            cpu_requests == cpu_limits and memory_requests == memory_limits):
            qos_class = "Guaranteed"
            efficiency_score = 1.0
        elif (cpu_requests > 0 or memory_requests > 0):
            qos_class = "Burstable"
            # Calculate efficiency based on request/limit ratio
            cpu_efficiency = cpu_requests / cpu_limits if cpu_limits > 0 else 0.5
            memory_efficiency = memory_requests / memory_limits if memory_limits > 0 else 0.5
            efficiency_score = (cpu_efficiency + memory_efficiency) / 2
        else:
            qos_class = "BestEffort"
            efficiency_score = 0.0
        
        # Generate recommendation
        recommendation = None
        if qos_class == "BestEffort":
            recommendation = "Define CPU and memory requests for better resource management"
        elif qos_class == "Burstable" and efficiency_score < 0.3:
            recommendation = "Consider setting limits closer to requests for better predictability"
        elif qos_class == "Guaranteed":
            recommendation = "Optimal QoS configuration for production workloads"
        
        return QoSClassification(
            pod_name=pod.name,
            namespace=pod.namespace,
            qos_class=qos_class,
            cpu_requests=cpu_requests,
            memory_requests=memory_requests,
            cpu_limits=cpu_limits,
            memory_limits=memory_limits,
            efficiency_score=efficiency_score,
            recommendation=recommendation
        )

    async def analyze_resource_quotas(self, namespaces: List[str]) -> List[ResourceQuota]:
        """Analyze Resource Quotas for namespaces"""
        quotas = []
        
        for namespace in namespaces:
            # This would typically query the Kubernetes API
            # For now, we'll simulate the analysis
            quota = ResourceQuota(
                namespace=namespace,
                name=f"quota-{namespace}",
                status="Missing",  # Would be determined by API call
                usage_percentage=0.0,
                recommended_quota={
                    "cpu": "2000m",
                    "memory": "8Gi",
                    "pods": "20"
                }
            )
            quotas.append(quota)
        
        return quotas

    async def _get_cluster_capacity(self) -> tuple[float, float, int]:
        """Get real cluster capacity from nodes"""
        try:
            from kubernetes import client
            v1 = client.CoreV1Api()
            nodes = v1.list_node()
            
            total_cpu_cores = 0.0
            total_memory_bytes = 0.0
            total_nodes = len(nodes.items)
            
            for node in nodes.items:
                # Parse CPU capacity
                cpu_capacity = node.status.capacity.get("cpu", "0")
                total_cpu_cores += self._parse_cpu_value(cpu_capacity)
                
                # Parse Memory capacity
                memory_capacity = node.status.capacity.get("memory", "0")
                total_memory_bytes += self._parse_memory_value(memory_capacity)
            
            # Convert memory to GiB
            total_memory_gib = total_memory_bytes / (1024 * 1024 * 1024)
            
            return total_cpu_cores, total_memory_gib, total_nodes
            
        except Exception as e:
            logger.warning(f"Could not get real cluster capacity: {e}. Using fallback values.")
            # Fallback values based on typical OpenShift cluster
            return 24.0, 70.0, 6

    async def get_cluster_health(self, pods: List[PodResource]) -> ClusterHealth:
        """Get cluster health overview with overcommit analysis"""
        total_pods = len(pods)
        total_namespaces = len(set(pod.namespace for pod in pods))
        
        # Calculate cluster resource totals
        cluster_cpu_requests = sum(pod.cpu_requests for pod in pods)
        cluster_memory_requests = sum(pod.memory_requests for pod in pods)
        cluster_cpu_limits = sum(pod.cpu_limits for pod in pods)
        cluster_memory_limits = sum(pod.memory_limits for pod in pods)
        
        # Get real cluster capacity
        cluster_cpu_capacity, cluster_memory_capacity, total_nodes = await self._get_cluster_capacity()
        
        # Calculate overcommit percentages
        cpu_overcommit = (cluster_cpu_requests / cluster_cpu_capacity) * 100
        # Convert memory capacity from GiB to bytes for consistent calculation
        cluster_memory_capacity_bytes = cluster_memory_capacity * (1024 * 1024 * 1024)
        memory_overcommit = (cluster_memory_requests / cluster_memory_capacity_bytes) * 100
        
        # Determine overall health
        if cpu_overcommit > 150 or memory_overcommit > 150:
            overall_health = "Critical"
        elif cpu_overcommit > 120 or memory_overcommit > 120:
            overall_health = "Warning"
        else:
            overall_health = "Healthy"
        
        # Count critical issues
        critical_issues = sum(1 for pod in pods if pod.cpu_requests == 0 or pod.memory_requests == 0)
        
        # Get top resource consumers
        top_consumers = sorted(
            pods, 
            key=lambda p: p.cpu_requests + p.memory_requests, 
            reverse=True
        )[:10]
        
        # QoS distribution
        qos_distribution = {"Guaranteed": 0, "Burstable": 0, "BestEffort": 0}
        for pod in pods:
            qos = self.classify_qos(pod)
            qos_distribution[qos.qos_class] += 1
        
        return ClusterHealth(
            total_pods=total_pods,
            total_namespaces=total_namespaces,
            total_nodes=total_nodes,
            cluster_cpu_capacity=cluster_cpu_capacity,
            cluster_memory_capacity=cluster_memory_capacity,
            cluster_cpu_requests=cluster_cpu_requests,
            cluster_memory_requests=cluster_memory_requests,
            cluster_cpu_limits=cluster_cpu_limits,
            cluster_memory_limits=cluster_memory_limits,
            cpu_overcommit_percentage=cpu_overcommit,
            memory_overcommit_percentage=memory_overcommit,
            overall_health=overall_health,
            critical_issues=critical_issues,
            namespaces_in_overcommit=len([ns for ns in set(pod.namespace for pod in pods) if self._is_namespace_in_overcommit(ns, pods)]),
            top_resource_consumers=[
                {
                    "name": pod.name,
                    "namespace": pod.namespace,
                    "cpu_requests": pod.cpu_requests,
                    "memory_requests": pod.memory_requests,
                    "qos_class": self.classify_qos(pod).qos_class
                }
                for pod in top_consumers
            ],
            qos_distribution=qos_distribution,
            resource_quota_coverage=self._calculate_resource_quota_coverage(pods)
        )

    def _is_namespace_in_overcommit(self, namespace: str, pods: List[PodResource]) -> bool:
        """Check if namespace is in overcommit"""
        namespace_pods = [pod for pod in pods if pod.namespace == namespace]
        if not namespace_pods:
            return False
        
        # Simple overcommit check: if any pod has limits > requests
        for pod in namespace_pods:
            if pod.cpu_limits > pod.cpu_requests or pod.memory_limits > pod.memory_requests:
                return True
        return False

    def _calculate_resource_quota_coverage(self, pods: List[PodResource]) -> float:
        """Calculate resource quota coverage percentage"""
        namespaces = set(pod.namespace for pod in pods)
        if not namespaces:
            return 0.0
        
        # For now, return a simple calculation based on namespace count
        # In a real implementation, this would check actual ResourceQuota objects
        return min(len(namespaces) * 0.2, 1.0)  # 20% per namespace, max 100%

    def calculate_pod_health_score(self, pod: PodResource, validations: List[ResourceValidation]) -> PodHealthScore:
        """Calculate pod health score and create simplified display"""
        # Calculate health score (0-10)
        health_score = 10
        
        # Deduct points for issues
        for validation in validations:
            if validation.severity == "critical":
                health_score -= 3
            elif validation.severity == "error":
                health_score -= 2
            elif validation.severity == "warning":
                health_score -= 1
        
        # Ensure score is between 0-10
        health_score = max(0, min(10, health_score))
        
        # Determine health status and visual indicators
        if health_score >= 9:
            health_status = "Excellent"
            status_color = "green"
            status_icon = "✅"
        elif health_score >= 7:
            health_status = "Good"
            status_color = "green"
            status_icon = "✅"
        elif health_score >= 5:
            health_status = "Medium"
            status_color = "yellow"
            status_icon = "🟡"
        elif health_score >= 3:
            health_status = "Poor"
            status_color = "orange"
            status_icon = "🟠"
        else:
            health_status = "Critical"
            status_color = "red"
            status_icon = "🔴"
        
        # Create simplified resource display
        cpu_display, cpu_status = self._create_cpu_display(pod)
        memory_display, memory_status = self._create_memory_display(pod)
        
        # Group validations by severity
        critical_issues = []
        warnings = []
        info_items = []
        
        for validation in validations:
            if validation.severity == "critical":
                critical_issues.append(validation.message)
            elif validation.severity in ["error", "warning"]:
                warnings.append(validation.message)
            else:
                info_items.append(validation.message)
        
        # Determine available actions
        available_actions = self._determine_available_actions(validations)
        oc_commands = self._generate_oc_commands(pod, validations)
        
        return PodHealthScore(
            pod_name=pod.name,
            namespace=pod.namespace,
            health_score=health_score,
            health_status=health_status,
            status_color=status_color,
            status_icon=status_icon,
            cpu_display=cpu_display,
            memory_display=memory_display,
            cpu_status=cpu_status,
            memory_status=memory_status,
            critical_issues=critical_issues,
            warnings=warnings,
            info_items=info_items,
            available_actions=available_actions,
            oc_commands=oc_commands
        )

    def _create_cpu_display(self, pod: PodResource) -> tuple[str, str]:
        """Create CPU display string and status"""
        if pod.cpu_requests == 0 and pod.cpu_limits == 0:
            return "No CPU resources defined", "🔴"
        
        # Format CPU values
        cpu_req_str = self._format_cpu_value(pod.cpu_requests)
        cpu_lim_str = self._format_cpu_value(pod.cpu_limits)
        
        # Calculate ratio
        if pod.cpu_requests > 0:
            ratio = pod.cpu_limits / pod.cpu_requests
            ratio_str = f"({ratio:.1f}:1 ratio)"
        else:
            ratio_str = "(no requests)"
        
        display = f"{cpu_req_str} → {cpu_lim_str} {ratio_str}"
        
        # Determine status
        if pod.cpu_requests == 0:
            status = "🔴"  # No requests
        elif pod.cpu_limits == 0:
            status = "🟡"  # No limits
        elif pod.cpu_requests > 0 and pod.cpu_limits > 0:
            ratio = pod.cpu_limits / pod.cpu_requests
            if ratio > 5:
                status = "🔴"  # Very high ratio
            elif ratio > 3:
                status = "🟡"  # High ratio
            else:
                status = "✅"  # Good ratio
        else:
            status = "🔴"
        
        return display, status

    def _create_memory_display(self, pod: PodResource) -> tuple[str, str]:
        """Create memory display string and status"""
        if pod.memory_requests == 0 and pod.memory_limits == 0:
            return "No memory resources defined", "🔴"
        
        # Format memory values
        mem_req_str = self._format_memory_value(pod.memory_requests)
        mem_lim_str = self._format_memory_value(pod.memory_limits)
        
        # Calculate ratio
        if pod.memory_requests > 0:
            ratio = pod.memory_limits / pod.memory_requests
            ratio_str = f"({ratio:.1f}:1 ratio)"
        else:
            ratio_str = "(no requests)"
        
        display = f"{mem_req_str} → {mem_lim_str} {ratio_str}"
        
        # Determine status
        if pod.memory_requests == 0:
            status = "🔴"  # No requests
        elif pod.memory_limits == 0:
            status = "🟡"  # No limits
        elif pod.memory_requests > 0 and pod.memory_limits > 0:
            ratio = pod.memory_limits / pod.memory_requests
            if ratio > 5:
                status = "🔴"  # Very high ratio
            elif ratio > 3:
                status = "🟡"  # High ratio
            else:
                status = "✅"  # Good ratio
        else:
            status = "🔴"
        
        return display, status

    def _format_cpu_value(self, value: float) -> str:
        """Format CPU value for display"""
        if value >= 1.0:
            return f"{value:.1f} cores"
        else:
            return f"{int(value * 1000)}m"

    def _format_memory_value(self, value_bytes: float) -> str:
        """Format memory value for display"""
        if value_bytes >= 1024 * 1024 * 1024:  # >= 1 GiB
            return f"{value_bytes / (1024 * 1024 * 1024):.1f} GiB"
        else:
            return f"{int(value_bytes / (1024 * 1024))} MiB"

    def _determine_available_actions(self, validations: List[ResourceValidation]) -> List[str]:
        """Determine available actions based on validations"""
        actions = []
        
        for validation in validations:
            if validation.validation_type == "missing_requests":
                actions.append("add_requests")
            elif validation.validation_type == "missing_limits":
                actions.append("add_limits")
            elif validation.validation_type == "cpu_ratio":
                actions.append("fix_cpu_ratio")
            elif validation.validation_type == "memory_ratio":
                actions.append("fix_memory_ratio")
        
        return list(set(actions))  # Remove duplicates

    def _generate_oc_commands(self, pod: PodResource, validations: List[ResourceValidation]) -> List[str]:
        """Generate oc commands for fixing issues"""
        commands = []
        
        # Generate commands for each validation
        for validation in validations:
            if validation.validation_type == "missing_requests":
                cmd = self._generate_add_requests_command(pod, validation)
                if cmd:
                    commands.append(cmd)
            elif validation.validation_type == "missing_limits":
                cmd = self._generate_add_limits_command(pod, validation)
                if cmd:
                    commands.append(cmd)
            elif validation.validation_type in ["cpu_ratio", "memory_ratio"]:
                cmd = self._generate_fix_ratio_command(pod, validation)
                if cmd:
                    commands.append(cmd)
        
        return commands

    def _generate_add_requests_command(self, pod: PodResource, validation: ResourceValidation) -> str:
        """Generate oc command to add requests"""
        # This would need to be implemented based on specific container
        return f"oc patch pod {pod.name} -n {pod.namespace} --type='merge' -p='{{\"spec\":{{\"containers\":[{{\"name\":\"{validation.container_name}\",\"resources\":{{\"requests\":{{\"cpu\":\"100m\",\"memory\":\"128Mi\"}}}}}}]}}}}'"

    def _generate_add_limits_command(self, pod: PodResource, validation: ResourceValidation) -> str:
        """Generate oc command to add limits"""
        return f"oc patch pod {pod.name} -n {pod.namespace} --type='merge' -p='{{\"spec\":{{\"containers\":[{{\"name\":\"{validation.container_name}\",\"resources\":{{\"limits\":{{\"cpu\":\"500m\",\"memory\":\"512Mi\"}}}}}}]}}}}'"

    def _generate_fix_ratio_command(self, pod: PodResource, validation: ResourceValidation) -> str:
        """Generate oc command to fix ratio"""
        # Calculate recommended limits based on 3:1 ratio
        if validation.validation_type == "cpu_ratio":
            recommended_limit = pod.cpu_requests * 3
            limit_str = self._format_cpu_value(recommended_limit)
            return f"oc patch pod {pod.name} -n {pod.namespace} --type='merge' -p='{{\"spec\":{{\"containers\":[{{\"name\":\"{validation.container_name}\",\"resources\":{{\"limits\":{{\"cpu\":\"{limit_str}\"}}}}}}]}}}}'"
        elif validation.validation_type == "memory_ratio":
            recommended_limit = pod.memory_requests * 3
            limit_str = self._format_memory_value(recommended_limit)
            return f"oc patch pod {pod.name} -n {pod.namespace} --type='merge' -p='{{\"spec\":{{\"containers\":[{{\"name\":\"{validation.container_name}\",\"resources\":{{\"limits\":{{\"memory\":\"{limit_str}\"}}}}}}]}}}}'"
        
        return ""
