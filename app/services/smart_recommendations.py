"""
Smart recommendations service for resource governance
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

from app.models.resource_models import (
    PodResource, 
    WorkloadCategory, 
    SmartRecommendation,
    ResourceValidation
)
from app.services.historical_analysis import HistoricalAnalysisService

logger = logging.getLogger(__name__)

@dataclass
class WorkloadAnalysis:
    """Workload analysis data"""
    workload_name: str
    namespace: str
    age_days: int
    has_requests: bool
    has_limits: bool
    has_optimal_ratios: bool
    resource_usage: Optional[Dict[str, float]] = None
    historical_data_available: bool = False

class SmartRecommendationsService:
    """Service for generating smart recommendations"""
    
    def __init__(self):
        self.historical_analysis = HistoricalAnalysisService()
        self.new_workload_threshold_days = 7
        self.outlier_cpu_threshold = 0.8  # 80% CPU usage
        self.outlier_memory_threshold = 0.8  # 80% Memory usage
    
    async def categorize_workloads(self, pods: List[PodResource]) -> List[WorkloadCategory]:
        """Categorize workloads based on age and resource configuration"""
        categories = []
        
        # Group pods by workload (deployment)
        workloads = self._group_pods_by_workload(pods)
        
        for workload_name, workload_pods in workloads.items():
            if not workload_pods:
                continue
                
            # Analyze workload
            analysis = await self._analyze_workload(workload_name, workload_pods)
            
            # Categorize workload
            category = self._categorize_workload(analysis)
            categories.append(category)
        
        return categories
    
    async def generate_smart_recommendations(
        self, 
        pods: List[PodResource],
        categories: List[WorkloadCategory]
    ) -> List[SmartRecommendation]:
        """Generate smart recommendations based on workload analysis"""
        recommendations = []
        
        for category in categories:
            workload_pods = [p for p in pods if self._extract_workload_name(p.name) == category.workload_name and p.namespace == category.namespace]
            
            if not workload_pods:
                continue
            
            # Generate recommendations based on category
            workload_recommendations = await self._generate_workload_recommendations(
                category, workload_pods
            )
            recommendations.extend(workload_recommendations)
        
        # Sort by priority
        recommendations.sort(key=lambda x: self._get_priority_score(x.priority), reverse=True)
        
        return recommendations
    
    def _group_pods_by_workload(self, pods: List[PodResource]) -> Dict[str, List[PodResource]]:
        """Group pods by workload (deployment) name"""
        workloads = {}
        
        for pod in pods:
            workload_name = self._extract_workload_name(pod.name)
            if workload_name not in workloads:
                workloads[workload_name] = []
            workloads[workload_name].append(pod)
        
        return workloads
    
    def _extract_workload_name(self, pod_name: str) -> str:
        """Extract workload name from pod name"""
        # Remove replica set suffix (e.g., "app-74ffb8c66-9kpdg" -> "app")
        parts = pod_name.split('-')
        if len(parts) >= 3 and parts[-2].isalnum() and parts[-1].isalnum():
            return '-'.join(parts[:-2])
        return pod_name
    
    async def _analyze_workload(self, workload_name: str, pods: List[PodResource]) -> WorkloadAnalysis:
        """Analyze a workload to determine its characteristics"""
        if not pods:
            return WorkloadAnalysis(workload_name, "", 0, False, False, False)
        
        # Get namespace from first pod
        namespace = pods[0].namespace
        
        # Calculate age (use oldest pod)
        oldest_pod = min(pods, key=lambda p: p.creation_timestamp if hasattr(p, 'creation_timestamp') else datetime.now())
        age_days = 0
        if hasattr(oldest_pod, 'creation_timestamp'):
            age_days = (datetime.now() - oldest_pod.creation_timestamp).days
        
        # Analyze resource configuration
        has_requests = all(
            any(container.get("resources", {}).get("requests") for container in pod.containers)
            for pod in pods
        )
        
        has_limits = all(
            any(container.get("resources", {}).get("limits") for container in pod.containers)
            for pod in pods
        )
        
        # Check for optimal ratios (simplified)
        has_optimal_ratios = True
        for pod in pods:
            for container in pod.containers:
                resources = container.get("resources", {})
                requests = resources.get("requests", {})
                limits = resources.get("limits", {})
                
                if requests and limits:
                    # Check CPU ratio
                    if "cpu" in requests and "cpu" in limits:
                        try:
                            cpu_request = self._parse_cpu_value(requests["cpu"])
                            cpu_limit = self._parse_cpu_value(limits["cpu"])
                            if cpu_request > 0 and cpu_limit / cpu_request > 5.0:  # > 5:1 ratio
                                has_optimal_ratios = False
                        except:
                            pass
                    
                    # Check memory ratio
                    if "memory" in requests and "memory" in limits:
                        try:
                            mem_request = self._parse_memory_value(requests["memory"])
                            mem_limit = self._parse_memory_value(limits["memory"])
                            if mem_request > 0 and mem_limit / mem_request > 5.0:  # > 5:1 ratio
                                has_optimal_ratios = False
                        except:
                            pass
        
        # Check historical data availability
        historical_data_available = False
        try:
            # Try to get historical data for the workload
            historical_data = await self.historical_analysis.get_workload_historical_analysis(
                namespace, workload_name, "7d"
            )
            historical_data_available = not historical_data.get('error')
        except:
            pass
        
        return WorkloadAnalysis(
            workload_name=workload_name,
            namespace=namespace,
            age_days=age_days,
            has_requests=has_requests,
            has_limits=has_limits,
            has_optimal_ratios=has_optimal_ratios,
            historical_data_available=historical_data_available
        )
    
    def _categorize_workload(self, analysis: WorkloadAnalysis) -> WorkloadCategory:
        """Categorize workload based on analysis"""
        # Determine category
        if analysis.age_days < self.new_workload_threshold_days:
            category = "new"
        elif not analysis.has_requests or not analysis.has_limits:
            category = "outlier"
        elif not analysis.has_optimal_ratios:
            category = "outlier"
        else:
            category = "compliant"
        
        # Determine resource config status
        if not analysis.has_requests:
            resource_status = "missing_requests"
        elif not analysis.has_limits:
            resource_status = "missing_limits"
        elif not analysis.has_optimal_ratios:
            resource_status = "suboptimal_ratio"
        else:
            resource_status = "compliant"
        
        # Calculate priority score
        priority_score = self._calculate_priority_score(analysis, category, resource_status)
        
        # Determine estimated impact
        estimated_impact = self._determine_impact(priority_score, category)
        
        # Determine if VPA candidate
        vpa_candidate = (
            category == "new" or 
            (category == "outlier" and not analysis.historical_data_available)
        )
        
        return WorkloadCategory(
            workload_name=analysis.workload_name,
            namespace=analysis.namespace,
            category=category,
            age_days=analysis.age_days,
            resource_config_status=resource_status,
            priority_score=priority_score,
            estimated_impact=estimated_impact,
            vpa_candidate=vpa_candidate,
            historical_data_available=analysis.historical_data_available
        )
    
    def _calculate_priority_score(self, analysis: WorkloadAnalysis, category: str, resource_status: str) -> int:
        """Calculate priority score (1-10) for workload"""
        score = 1
        
        # Base score by category
        if category == "outlier":
            score += 4
        elif category == "new":
            score += 2
        
        # Add score by resource status
        if resource_status == "missing_requests":
            score += 3
        elif resource_status == "missing_limits":
            score += 2
        elif resource_status == "suboptimal_ratio":
            score += 1
        
        # Add score for production namespaces
        if analysis.namespace in ["default", "production", "prod"]:
            score += 2
        
        # Add score for age (older workloads are more critical)
        if analysis.age_days > 30:
            score += 1
        
        return min(score, 10)
    
    def _determine_impact(self, priority_score: int, category: str) -> str:
        """Determine estimated impact based on priority score and category"""
        if priority_score >= 8:
            return "critical"
        elif priority_score >= 6:
            return "high"
        elif priority_score >= 4:
            return "medium"
        else:
            return "low"
    
    async def _generate_workload_recommendations(
        self, 
        category: WorkloadCategory, 
        pods: List[PodResource]
    ) -> List[SmartRecommendation]:
        """Generate recommendations for a specific workload"""
        recommendations = []
        
        if category.category == "new":
            # New workload recommendations
            recommendations.append(self._create_vpa_activation_recommendation(category))
        
        elif category.category == "outlier":
            if category.resource_config_status == "missing_requests":
                recommendations.append(self._create_missing_requests_recommendation(category, pods))
            elif category.resource_config_status == "missing_limits":
                recommendations.append(self._create_missing_limits_recommendation(category, pods))
            elif category.resource_config_status == "suboptimal_ratio":
                recommendations.append(self._create_ratio_adjustment_recommendation(category, pods))
        
        # Add VPA recommendation for outliers without historical data
        if category.vpa_candidate and not category.historical_data_available:
            recommendations.append(self._create_vpa_activation_recommendation(category))
        
        return recommendations
    
    def _create_vpa_activation_recommendation(self, category: WorkloadCategory) -> SmartRecommendation:
        """Create VPA activation recommendation"""
        return SmartRecommendation(
            workload_name=category.workload_name,
            namespace=category.namespace,
            recommendation_type="vpa_activation",
            priority=category.estimated_impact,
            title=f"Activate VPA for {category.workload_name}",
            description=f"Enable VPA for {category.workload_name} to get automatic resource recommendations based on usage patterns.",
            confidence_level=0.8 if category.historical_data_available else 0.6,
            estimated_impact=category.estimated_impact,
            implementation_steps=[
                f"Create VPA resource for {category.workload_name}",
                "Set updateMode to 'Off' for recommendation-only mode",
                "Monitor VPA recommendations for 24-48 hours",
                "Apply recommended values when confident"
            ],
            kubectl_commands=[
                f"kubectl create -f vpa-{category.workload_name}.yaml"
            ],
            vpa_yaml=self._generate_vpa_yaml(category)
        )
    
    def _create_missing_requests_recommendation(self, category: WorkloadCategory, pods: List[PodResource]) -> SmartRecommendation:
        """Create missing requests recommendation"""
        return SmartRecommendation(
            workload_name=category.workload_name,
            namespace=category.namespace,
            recommendation_type="resource_config",
            priority=category.estimated_impact,
            title=f"Add Resource Requests for {category.workload_name}",
            description=f"Define CPU and memory requests for {category.workload_name} to guarantee QoS and enable proper scheduling.",
            confidence_level=0.9,
            estimated_impact=category.estimated_impact,
            implementation_steps=[
                f"Analyze current resource usage for {category.workload_name}",
                "Set CPU requests based on P95 usage + 20% buffer",
                "Set memory requests based on P95 usage + 20% buffer",
                "Update deployment with new resource requests"
            ],
            kubectl_commands=[
                f"kubectl patch deployment {category.workload_name} -n {category.namespace} -p '{{\"spec\":{{\"template\":{{\"spec\":{{\"containers\":[{{\"name\":\"{category.workload_name}\",\"resources\":{{\"requests\":{{\"cpu\":\"200m\",\"memory\":\"512Mi\"}}}}}}]}}}}}}}}'"
            ]
        )
    
    def _create_missing_limits_recommendation(self, category: WorkloadCategory, pods: List[PodResource]) -> SmartRecommendation:
        """Create missing limits recommendation"""
        return SmartRecommendation(
            workload_name=category.workload_name,
            namespace=category.namespace,
            recommendation_type="resource_config",
            priority=category.estimated_impact,
            title=f"Add Resource Limits for {category.workload_name}",
            description=f"Define CPU and memory limits for {category.workload_name} to prevent excessive resource consumption.",
            confidence_level=0.9,
            estimated_impact=category.estimated_impact,
            implementation_steps=[
                f"Analyze current resource usage for {category.workload_name}",
                "Set CPU limits based on P95 usage * 3 (3:1 ratio)",
                "Set memory limits based on P95 usage * 3 (3:1 ratio)",
                "Update deployment with new resource limits"
            ],
            kubectl_commands=[
                f"kubectl patch deployment {category.workload_name} -n {category.namespace} -p '{{\"spec\":{{\"template\":{{\"spec\":{{\"containers\":[{{\"name\":\"{category.workload_name}\",\"resources\":{{\"limits\":{{\"cpu\":\"600m\",\"memory\":\"1536Mi\"}}}}}}]}}}}}}}}'"
            ]
        )
    
    def _create_ratio_adjustment_recommendation(self, category: WorkloadCategory, pods: List[PodResource]) -> SmartRecommendation:
        """Create ratio adjustment recommendation"""
        return SmartRecommendation(
            workload_name=category.workload_name,
            namespace=category.namespace,
            recommendation_type="ratio_adjustment",
            priority=category.estimated_impact,
            title=f"Adjust Resource Ratios for {category.workload_name}",
            description=f"Optimize CPU and memory limit:request ratios for {category.workload_name} to follow best practices (3:1 ratio).",
            confidence_level=0.8,
            estimated_impact=category.estimated_impact,
            implementation_steps=[
                f"Analyze current resource ratios for {category.workload_name}",
                "Adjust limits to maintain 3:1 ratio with requests",
                "Test with updated ratios in staging environment",
                "Apply changes to production"
            ],
            kubectl_commands=[
                f"kubectl patch deployment {category.workload_name} -n {category.namespace} -p '{{\"spec\":{{\"template\":{{\"spec\":{{\"containers\":[{{\"name\":\"{category.workload_name}\",\"resources\":{{\"requests\":{{\"cpu\":\"200m\",\"memory\":\"512Mi\"}},\"limits\":{{\"cpu\":\"600m\",\"memory\":\"1536Mi\"}}}}}}]}}}}}}}}'"
            ]
        )
    
    def _generate_vpa_yaml(self, category: WorkloadCategory) -> str:
        """Generate VPA YAML for workload"""
        return f"""apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: {category.workload_name}-vpa
  namespace: {category.namespace}
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: {category.workload_name}
  updatePolicy:
    updateMode: "Off"  # Recommendation only
  resourcePolicy:
    containerPolicies:
    - containerName: {category.workload_name}
      maxAllowed:
        cpu: 2
        memory: 4Gi
      minAllowed:
        cpu: 100m
        memory: 128Mi"""
    
    def _get_priority_score(self, priority: str) -> int:
        """Convert priority string to numeric score for sorting"""
        priority_map = {
            "critical": 4,
            "high": 3,
            "medium": 2,
            "low": 1
        }
        return priority_map.get(priority, 0)
    
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
