"""
Serviço de validação de recursos seguindo best practices Red Hat
"""
import logging
from typing import List, Dict, Any
from decimal import Decimal, InvalidOperation
import re

from app.models.resource_models import PodResource, ResourceValidation, NamespaceResources
from app.core.config import settings
from app.services.historical_analysis import HistoricalAnalysisService

logger = logging.getLogger(__name__)

class ValidationService:
    """Serviço para validação de recursos"""
    
    def __init__(self):
        self.cpu_ratio = settings.cpu_limit_ratio
        self.memory_ratio = settings.memory_limit_ratio
        self.min_cpu_request = settings.min_cpu_request
        self.min_memory_request = settings.min_memory_request
        self.historical_analysis = HistoricalAnalysisService()
    
    def validate_pod_resources(self, pod: PodResource) -> List[ResourceValidation]:
        """Validar recursos de um pod"""
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
        """Validar recursos de um pod incluindo análise histórica"""
        # Validações estáticas
        static_validations = self.validate_pod_resources(pod)
        
        # Análise histórica
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
        container: Dict[str, Any]
    ) -> List[ResourceValidation]:
        """Validar recursos de um container"""
        validations = []
        resources = container.get("resources", {})
        requests = resources.get("requests", {})
        limits = resources.get("limits", {})
        
        # 1. Verificar se requests estão definidos
        if not requests:
            validations.append(ResourceValidation(
                pod_name=pod_name,
                namespace=namespace,
                container_name=container["name"],
                validation_type="missing_requests",
                severity="error",
                message="Container without defined requests",
                recommendation="Define CPU and memory requests to guarantee QoS"
            ))
        
        # 2. Verificar se limits estão definidos
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
        
        # 3. Validar ratio limit:request
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
        
        # 4. Validar valores mínimos
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
        """Validar ratio CPU limit:request"""
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
                        message=f"CPU limit:request ratio too high ({ratio:.2f}:1)",
                        recommendation=f"Consider reducing limits or increasing requests (recommended ratio: {self.cpu_ratio}:1)"
                    )
                elif ratio < 1.0:
                    return ResourceValidation(
                        pod_name=pod_name,
                        namespace=namespace,
                        container_name=container_name,
                        validation_type="invalid_ratio",
                        severity="error",
                        message=f"CPU limit less than request ({ratio:.2f}:1)",
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
        """Validar ratio memória limit:request"""
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
                        message=f"Memory limit:request ratio too high ({ratio:.2f}:1)",
                        recommendation=f"Consider reducing limits or increasing requests (recommended ratio: {self.memory_ratio}:1)"
                    )
                elif ratio < 1.0:
                    return ResourceValidation(
                        pod_name=pod_name,
                        namespace=namespace,
                        container_name=container_name,
                        validation_type="invalid_ratio",
                        severity="error",
                        message=f"Memory limit less than request ({ratio:.2f}:1)",
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
        """Validar valores mínimos de requests"""
        validations = []
        
        # Validar CPU mínima
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
        
        # Validar memória mínima
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
        """Converter valor de CPU para float (cores)"""
        if value.endswith('m'):
            return float(value[:-1]) / 1000
        elif value.endswith('n'):
            return float(value[:-1]) / 1000000000
        else:
            return float(value)
    
    def _parse_memory_value(self, value: str) -> int:
        """Converter valor de memória para bytes"""
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
    
    def validate_namespace_overcommit(
        self, 
        namespace_resources: NamespaceResources,
        node_capacity: Dict[str, str]
    ) -> List[ResourceValidation]:
        """Validar overcommit em um namespace"""
        validations = []
        
        # Calcular total de requests do namespace
        total_cpu_requests = self._parse_cpu_value(namespace_resources.total_cpu_requests)
        total_memory_requests = self._parse_memory_value(namespace_resources.total_memory_requests)
        
        # Calcular capacidade total dos nós
        total_cpu_capacity = self._parse_cpu_value(node_capacity.get("cpu", "0"))
        total_memory_capacity = self._parse_memory_value(node_capacity.get("memory", "0"))
        
        # Verificar overcommit de CPU
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
        
        # Verificar overcommit de memória
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
        """Gerar recomendações baseadas nas validações"""
        recommendations = []
        
        # Agrupar validações por tipo
        validation_counts = {}
        for validation in validations:
            validation_type = validation.validation_type
            if validation_type not in validation_counts:
                validation_counts[validation_type] = 0
            validation_counts[validation_type] += 1
        
        # Gerar recomendações baseadas nos problemas encontrados
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
