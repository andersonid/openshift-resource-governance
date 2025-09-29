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
    ClusterHealth
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
    
    def _validate_container_resources(
        self, 
        pod_name: str, 
        namespace: str, 
        container: Any
    ) -> List[ResourceValidation]:
        """Validate container resources"""
        validations = []
        resources = container.resources
        requests = resources.get("requests", {})
        limits = resources.get("limits", {})
        
        # Determine QoS class based on Red Hat best practices
        qos_class = self._determine_qos_class(requests, limits)
        
        # 1. Check if requests are defined
        if not requests:
            validations.append(ResourceValidation(
                pod_name=pod_name,
                namespace=namespace,
                container_name=container.name,
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
                container_name=container.name,
                validation_type="missing_limits",
                severity="warning",
                message="Container without defined limits",
                recommendation="Define limits to avoid excessive resource consumption"
            ))
        
        # 3. QoS Class validation based on Red Hat recommendations
        qos_validation = self._validate_qos_class(pod_name, namespace, container.name, qos_class, requests, limits)
        if qos_validation:
            validations.append(qos_validation)
        
        # 3. Validate limit:request ratio
        if requests and limits:
            cpu_validation = self._validate_cpu_ratio(
                pod_name, namespace, container.name, requests, limits
            )
            if cpu_validation:
                validations.append(cpu_validation)
            
            memory_validation = self._validate_memory_ratio(
                pod_name, namespace, container.name, requests, limits
            )
            if memory_validation:
                validations.append(memory_validation)
        
        # 4. Validate minimum values
        if requests:
            min_validation = self._validate_minimum_values(
                pod_name, namespace, container.name, requests
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
                
                if ratio > self.cpu_ratio * 1.5:  # 50% de tolerância
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
                
                if ratio > self.memory_ratio * 1.5:  # 50% de tolerância
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
    
    def _validate_qos_class(self, pod_name: str, namespace: str, container_name: str, qos_class: str, requests: Dict[str, str], limits: Dict[str, str]) -> Optional[ResourceValidation]:
        """Validate QoS class and provide recommendations"""
        cpu_requests = self._parse_cpu_value(requests.get("cpu", "0"))
        memory_requests = self._parse_memory_value(requests.get("memory", "0")) / (1024 * 1024 * 1024)  # Convert to GB
        cpu_limits = self._parse_cpu_value(limits.get("cpu", "0"))
        memory_limits = self._parse_memory_value(limits.get("memory", "0")) / (1024 * 1024 * 1024)  # Convert to GB
        
        # Check for missing requests (BestEffort pods)
        if qos_class == "BestEffort":
            return ResourceValidation(
                pod_name=pod_name,
                namespace=namespace,
                container_name=container_name,
                validation_type="missing_requests",
                severity="warning",
                message="Pod has no resource requests defined",
                recommendation="Define CPU and memory requests for better resource management",
                priority_score=7,
                workload_category="new",
                estimated_impact="medium"
            )
        
        # Check for missing limits (Burstable pods)
        elif qos_class == "Burstable" and (cpu_limits == 0 or memory_limits == 0):
            return ResourceValidation(
                pod_name=pod_name,
                namespace=namespace,
                container_name=container_name,
                validation_type="missing_limits",
                severity="warning",
                message="Pod has requests but no limits defined",
                recommendation="Define resource limits to prevent resource starvation",
                priority_score=5,
                workload_category="established",
                estimated_impact="low"
            )
        
        return None
    
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

    async def get_cluster_health(self, pods: List[PodResource]) -> ClusterHealth:
        """Get cluster health overview with overcommit analysis"""
        total_pods = len(pods)
        total_namespaces = len(set(pod.namespace for pod in pods))
        
        # Calculate cluster resource totals
        cluster_cpu_requests = sum(pod.cpu_requests for pod in pods)
        cluster_memory_requests = sum(pod.memory_requests for pod in pods)
        cluster_cpu_limits = sum(pod.cpu_limits for pod in pods)
        cluster_memory_limits = sum(pod.memory_limits for pod in pods)
        
        # Simulate cluster capacity (would come from node metrics)
        cluster_cpu_capacity = 100.0  # 100 CPU cores
        cluster_memory_capacity = 400.0  # 400 GiB
        
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
            total_nodes=10,  # Simulated
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
            namespaces_in_overcommit=3,  # Simulated
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
            resource_quota_coverage=0.6  # Simulated
        )
