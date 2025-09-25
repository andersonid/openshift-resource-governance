"""
Serviço de análise histórica usando métricas do Prometheus
"""
import logging
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import aiohttp
import json

from app.models.resource_models import PodResource, ResourceValidation
from app.core.config import settings

logger = logging.getLogger(__name__)

class HistoricalAnalysisService:
    """Serviço para análise histórica de recursos usando Prometheus"""
    
    def __init__(self):
        self.prometheus_url = settings.prometheus_url
        self.time_ranges = {
            '1h': 3600,      # 1 hora
            '6h': 21600,     # 6 horas
            '24h': 86400,    # 24 horas
            '7d': 604800,    # 7 dias
            '30d': 2592000   # 30 dias
        }
    
    async def analyze_pod_historical_usage(
        self, 
        pod: PodResource, 
        time_range: str = '24h'
    ) -> List[ResourceValidation]:
        """Analisar uso histórico de um pod"""
        validations = []
        
        if time_range not in self.time_ranges:
            time_range = '24h'
        
        end_time = datetime.now()
        start_time = end_time - timedelta(seconds=self.time_ranges[time_range])
        
        try:
            # Analisar CPU
            cpu_analysis = await self._analyze_cpu_usage(
                pod, start_time, end_time, time_range
            )
            validations.extend(cpu_analysis)
            
            # Analisar memória
            memory_analysis = await self._analyze_memory_usage(
                pod, start_time, end_time, time_range
            )
            validations.extend(memory_analysis)
            
        except Exception as e:
            logger.error(f"Error in historical analysis for pod {pod.name}: {e}")
            validations.append(ResourceValidation(
                pod_name=pod.name,
                namespace=pod.namespace,
                container_name="all",
                validation_type="historical_analysis_error",
                severity="warning",
                message=f"Error in historical analysis: {str(e)}",
                recommendation="Check Prometheus connectivity"
            ))
        
        return validations
    
    async def _analyze_cpu_usage(
        self, 
        pod: PodResource, 
        start_time: datetime, 
        end_time: datetime,
        time_range: str
    ) -> List[ResourceValidation]:
        """Analisar uso histórico de CPU"""
        validations = []
        
        for container in pod.containers:
            container_name = container["name"]
            
            try:
                # Query para CPU usage rate
                cpu_query = f'''
                rate(container_cpu_usage_seconds_total{{
                    pod="{pod.name}",
                    namespace="{pod.namespace}",
                    container="{container_name}",
                    container!="POD",
                    container!=""
                }}[{time_range}])
                '''
                
                # Query para CPU requests
                cpu_requests_query = f'''
                kube_pod_container_resource_requests{{
                    pod="{pod.name}",
                    namespace="{pod.namespace}",
                    resource="cpu"
                }}
                '''
                
                # Query para CPU limits
                cpu_limits_query = f'''
                kube_pod_container_resource_limits{{
                    pod="{pod.name}",
                    namespace="{pod.namespace}",
                    resource="cpu"
                }}
                '''
                
                # Executar queries
                cpu_usage = await self._query_prometheus(cpu_query, start_time, end_time)
                cpu_requests = await self._query_prometheus(cpu_requests_query, start_time, end_time)
                cpu_limits = await self._query_prometheus(cpu_limits_query, start_time, end_time)
                
                if cpu_usage and cpu_requests:
                    analysis = self._analyze_cpu_metrics(
                        pod.name, pod.namespace, container_name,
                        cpu_usage, cpu_requests, cpu_limits, time_range
                    )
                    validations.extend(analysis)
                
            except Exception as e:
                logger.warning(f"Error analyzing CPU for container {container_name}: {e}")
        
        return validations
    
    async def _analyze_memory_usage(
        self, 
        pod: PodResource, 
        start_time: datetime, 
        end_time: datetime,
        time_range: str
    ) -> List[ResourceValidation]:
        """Analisar uso histórico de memória"""
        validations = []
        
        for container in pod.containers:
            container_name = container["name"]
            
            try:
                # Query para memória usage
                memory_query = f'''
                container_memory_working_set_bytes{{
                    pod="{pod.name}",
                    namespace="{pod.namespace}",
                    container="{container_name}",
                    container!="POD",
                    container!=""
                }}
                '''
                
                # Query para memória requests
                memory_requests_query = f'''
                kube_pod_container_resource_requests{{
                    pod="{pod.name}",
                    namespace="{pod.namespace}",
                    resource="memory"
                }}
                '''
                
                # Query para memória limits
                memory_limits_query = f'''
                kube_pod_container_resource_limits{{
                    pod="{pod.name}",
                    namespace="{pod.namespace}",
                    resource="memory"
                }}
                '''
                
                # Executar queries
                memory_usage = await self._query_prometheus(memory_query, start_time, end_time)
                memory_requests = await self._query_prometheus(memory_requests_query, start_time, end_time)
                memory_limits = await self._query_prometheus(memory_limits_query, start_time, end_time)
                
                if memory_usage and memory_requests:
                    analysis = self._analyze_memory_metrics(
                        pod.name, pod.namespace, container_name,
                        memory_usage, memory_requests, memory_limits, time_range
                    )
                    validations.extend(analysis)
                
            except Exception as e:
                logger.warning(f"Error analyzing memory for container {container_name}: {e}")
        
        return validations
    
    def _analyze_cpu_metrics(
        self,
        pod_name: str,
        namespace: str,
        container_name: str,
        usage_data: List[Dict],
        requests_data: List[Dict],
        limits_data: List[Dict],
        time_range: str
    ) -> List[ResourceValidation]:
        """Analisar métricas de CPU"""
        validations = []
        
        if not usage_data or not requests_data:
            return validations
        
        # Calcular estatísticas de uso
        usage_values = [float(point[1]) for point in usage_data if point[1] != 'NaN']
        if not usage_values:
            return validations
        
        # Valores atuais de requests/limits
        current_requests = float(requests_data[0][1]) if requests_data else 0
        current_limits = float(limits_data[0][1]) if limits_data else 0
        
        # Estatísticas de uso
        avg_usage = sum(usage_values) / len(usage_values)
        max_usage = max(usage_values)
        p95_usage = sorted(usage_values)[int(len(usage_values) * 0.95)]
        p99_usage = sorted(usage_values)[int(len(usage_values) * 0.99)]
        
        # Request adequacy analysis
        if current_requests > 0:
            # Request too high (average usage < 50% of request)
            if avg_usage < current_requests * 0.5:
                validations.append(ResourceValidation(
                    pod_name=pod_name,
                    namespace=namespace,
                    container_name=container_name,
                    validation_type="historical_analysis",
                    severity="warning",
                    message=f"CPU request too high: average usage {avg_usage:.3f} cores vs request {current_requests:.3f} cores",
                    recommendation=f"Consider reducing CPU request to ~{avg_usage * 1.2:.3f} cores (based on {time_range} of usage)"
                ))
            
            # Request too low (P95 usage > 80% of request)
            elif p95_usage > current_requests * 0.8:
                validations.append(ResourceValidation(
                    pod_name=pod_name,
                    namespace=namespace,
                    container_name=container_name,
                    validation_type="historical_analysis",
                    severity="warning",
                    message=f"CPU request may be insufficient: P95 {p95_usage:.3f} cores vs request {current_requests:.3f} cores",
                    recommendation=f"Consider increasing CPU request to ~{p95_usage * 1.2:.3f} cores (based on {time_range} of usage)"
                ))
        
        # Limit adequacy analysis
        if current_limits > 0:
            # Limit too high (P99 usage < 50% of limit)
            if p99_usage < current_limits * 0.5:
                validations.append(ResourceValidation(
                    pod_name=pod_name,
                    namespace=namespace,
                    container_name=container_name,
                    validation_type="historical_analysis",
                    severity="info",
                    message=f"CPU limit too high: P99 {p99_usage:.3f} cores vs limit {current_limits:.3f} cores",
                    recommendation=f"Consider reducing CPU limit to ~{p99_usage * 1.5:.3f} cores (based on {time_range} of usage)"
                ))
            
            # Limit too low (maximum usage > 90% of limit)
            elif max_usage > current_limits * 0.9:
                validations.append(ResourceValidation(
                    pod_name=pod_name,
                    namespace=namespace,
                    container_name=container_name,
                    validation_type="historical_analysis",
                    severity="warning",
                    message=f"CPU limit may be insufficient: maximum usage {max_usage:.3f} cores vs limit {current_limits:.3f} cores",
                    recommendation=f"Consider increasing CPU limit to ~{max_usage * 1.2:.3f} cores (based on {time_range} of usage)"
                ))
        
        return validations
    
    def _analyze_memory_metrics(
        self,
        pod_name: str,
        namespace: str,
        container_name: str,
        usage_data: List[Dict],
        requests_data: List[Dict],
        limits_data: List[Dict],
        time_range: str
    ) -> List[ResourceValidation]:
        """Analisar métricas de memória"""
        validations = []
        
        if not usage_data or not requests_data:
            return validations
        
        # Calcular estatísticas de uso
        usage_values = [float(point[1]) for point in usage_data if point[1] != 'NaN']
        if not usage_values:
            return validations
        
        # Valores atuais de requests/limits (em bytes)
        current_requests = float(requests_data[0][1]) if requests_data else 0
        current_limits = float(limits_data[0][1]) if limits_data else 0
        
        # Estatísticas de uso
        avg_usage = sum(usage_values) / len(usage_values)
        max_usage = max(usage_values)
        p95_usage = sorted(usage_values)[int(len(usage_values) * 0.95)]
        p99_usage = sorted(usage_values)[int(len(usage_values) * 0.99)]
        
        # Converter para MiB para melhor legibilidade
        def bytes_to_mib(bytes_value):
            return bytes_value / (1024 * 1024)
        
        # Request adequacy analysis
        if current_requests > 0:
            # Request too high (average usage < 50% of request)
            if avg_usage < current_requests * 0.5:
                validations.append(ResourceValidation(
                    pod_name=pod_name,
                    namespace=namespace,
                    container_name=container_name,
                    validation_type="historical_analysis",
                    severity="warning",
                    message=f"Memory request too high: average usage {bytes_to_mib(avg_usage):.1f}Mi vs request {bytes_to_mib(current_requests):.1f}Mi",
                    recommendation=f"Consider reducing memory request to ~{bytes_to_mib(avg_usage * 1.2):.1f}Mi (based on {time_range} of usage)"
                ))
            
            # Request too low (P95 usage > 80% of request)
            elif p95_usage > current_requests * 0.8:
                validations.append(ResourceValidation(
                    pod_name=pod_name,
                    namespace=namespace,
                    container_name=container_name,
                    validation_type="historical_analysis",
                    severity="warning",
                    message=f"Memory request may be insufficient: P95 {bytes_to_mib(p95_usage):.1f}Mi vs request {bytes_to_mib(current_requests):.1f}Mi",
                    recommendation=f"Consider increasing memory request to ~{bytes_to_mib(p95_usage * 1.2):.1f}Mi (based on {time_range} of usage)"
                ))
        
        # Limit adequacy analysis
        if current_limits > 0:
            # Limit too high (P99 usage < 50% of limit)
            if p99_usage < current_limits * 0.5:
                validations.append(ResourceValidation(
                    pod_name=pod_name,
                    namespace=namespace,
                    container_name=container_name,
                    validation_type="historical_analysis",
                    severity="info",
                    message=f"Memory limit too high: P99 {bytes_to_mib(p99_usage):.1f}Mi vs limit {bytes_to_mib(current_limits):.1f}Mi",
                    recommendation=f"Consider reducing memory limit to ~{bytes_to_mib(p99_usage * 1.5):.1f}Mi (based on {time_range} of usage)"
                ))
            
            # Limit too low (maximum usage > 90% of limit)
            elif max_usage > current_limits * 0.9:
                validations.append(ResourceValidation(
                    pod_name=pod_name,
                    namespace=namespace,
                    container_name=container_name,
                    validation_type="historical_analysis",
                    severity="warning",
                    message=f"Memory limit may be insufficient: maximum usage {bytes_to_mib(max_usage):.1f}Mi vs limit {bytes_to_mib(current_limits):.1f}Mi",
                    recommendation=f"Consider increasing memory limit to ~{bytes_to_mib(max_usage * 1.2):.1f}Mi (based on {time_range} of usage)"
                ))
        
        return validations
    
    async def _query_prometheus(self, query: str, start_time: datetime, end_time: datetime) -> List[Dict]:
        """Executar query no Prometheus"""
        try:
            async with aiohttp.ClientSession() as session:
                params = {
                    'query': query,
                    'start': start_time.timestamp(),
                    'end': end_time.timestamp(),
                    'step': '60s'  # 1 minuto de resolução
                }
                
                async with session.get(
                    f"{self.prometheus_url}/api/v1/query_range",
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data['status'] == 'success' and data['data']['result']:
                            return data['data']['result'][0]['values']
                    else:
                        logger.warning(f"Prometheus query failed: {response.status}")
                        return []
        except Exception as e:
            logger.error(f"Error querying Prometheus: {e}")
            return []
    
    async def get_cluster_historical_summary(self, time_range: str = '24h') -> Dict[str, Any]:
        """Obter resumo histórico do cluster"""
        try:
            # Query para CPU total do cluster
            cpu_query = f'''
            sum(rate(container_cpu_usage_seconds_total{{
                container!="POD",
                container!=""
            }}[{time_range}]))
            '''
            
            # Query para memória total do cluster
            memory_query = f'''
            sum(container_memory_working_set_bytes{{
                container!="POD",
                container!=""
            }})
            '''
            
            # Query para requests totais
            cpu_requests_query = f'''
            sum(kube_pod_container_resource_requests{{resource="cpu"}})
            '''
            
            memory_requests_query = f'''
            sum(kube_pod_container_resource_requests{{resource="memory"}})
            '''
            
            # Executar queries
            cpu_usage = await self._query_prometheus(cpu_query, 
                datetime.now() - timedelta(seconds=self.time_ranges[time_range]), 
                datetime.now())
            memory_usage = await self._query_prometheus(memory_query, 
                datetime.now() - timedelta(seconds=self.time_ranges[time_range]), 
                datetime.now())
            cpu_requests = await self._query_prometheus(cpu_requests_query, 
                datetime.now() - timedelta(seconds=self.time_ranges[time_range]), 
                datetime.now())
            memory_requests = await self._query_prometheus(memory_requests_query, 
                datetime.now() - timedelta(seconds=self.time_ranges[time_range]), 
                datetime.now())
            
            return {
                'time_range': time_range,
                'cpu_usage': float(cpu_usage[0][1]) if cpu_usage else 0,
                'memory_usage': float(memory_usage[0][1]) if memory_usage else 0,
                'cpu_requests': float(cpu_requests[0][1]) if cpu_requests else 0,
                'memory_requests': float(memory_requests[0][1]) if memory_requests else 0,
                'cpu_utilization': (float(cpu_usage[0][1]) / float(cpu_requests[0][1]) * 100) if cpu_usage and cpu_requests and cpu_requests[0][1] != '0' else 0,
                'memory_utilization': (float(memory_usage[0][1]) / float(memory_requests[0][1]) * 100) if memory_usage and memory_requests and memory_requests[0][1] != '0' else 0
            }
            
        except Exception as e:
            logger.error(f"Error getting historical summary: {e}")
            return {}
