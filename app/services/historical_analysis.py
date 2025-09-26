"""
Historical analysis service using Prometheus metrics
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
    """Service for historical resource analysis using Prometheus"""
    
    def __init__(self):
        self.prometheus_url = settings.prometheus_url
        self.time_ranges = {
            '1h': 3600,      # 1 hour
            '6h': 21600,     # 6 hours
            '24h': 86400,    # 24 hours
            '7d': 604800,    # 7 days
            '30d': 2592000   # 30 days
        }
    
    async def analyze_pod_historical_usage(
        self, 
        pod: PodResource, 
        time_range: str = '24h'
    ) -> List[ResourceValidation]:
        """Analyze historical usage of a pod"""
        validations = []
        
        if time_range not in self.time_ranges:
            time_range = '24h'
        
        end_time = datetime.now()
        start_time = end_time - timedelta(seconds=self.time_ranges[time_range])
        
        try:
            # Analyze CPU
            cpu_analysis = await self._analyze_cpu_usage(
                pod, start_time, end_time, time_range
            )
            validations.extend(cpu_analysis)
            
            # Analyze memory
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
        """Analyze historical CPU usage"""
        validations = []
        
        for container in pod.containers:
            container_name = container["name"]
            
            try:
                # Query for CPU usage rate
                cpu_query = f'''
                rate(container_cpu_usage_seconds_total{{
                    pod="{pod.name}",
                    namespace="{pod.namespace}",
                    container="{container_name}",
                    container!="POD",
                    container!=""
                }}[{time_range}])
                '''
                
                # Query for CPU requests
                cpu_requests_query = f'''
                kube_pod_container_resource_requests{{
                    pod="{pod.name}",
                    namespace="{pod.namespace}",
                    resource="cpu"
                }}
                '''
                
                # Query for CPU limits
                cpu_limits_query = f'''
                kube_pod_container_resource_limits{{
                    pod="{pod.name}",
                    namespace="{pod.namespace}",
                    resource="cpu"
                }}
                '''
                
                # Execute queries
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
        """Analyze historical memory usage"""
        validations = []
        
        for container in pod.containers:
            container_name = container["name"]
            
            try:
                # Query for memory usage
                memory_query = f'''
                container_memory_working_set_bytes{{
                    pod="{pod.name}",
                    namespace="{pod.namespace}",
                    container="{container_name}",
                    container!="POD",
                    container!=""
                }}
                '''
                
                # Query for memory requests
                memory_requests_query = f'''
                kube_pod_container_resource_requests{{
                    pod="{pod.name}",
                    namespace="{pod.namespace}",
                    resource="memory"
                }}
                '''
                
                # Query for memory limits
                memory_limits_query = f'''
                kube_pod_container_resource_limits{{
                    pod="{pod.name}",
                    namespace="{pod.namespace}",
                    resource="memory"
                }}
                '''
                
                # Execute queries
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
        """Analyze CPU metrics"""
        validations = []
        
        if not usage_data or not requests_data:
            return validations
        
        # Calculate usage statistics
        usage_values = [float(point[1]) for point in usage_data if point[1] != 'NaN']
        if not usage_values:
            return validations
        
        # Current values of requests/limits
        current_requests = float(requests_data[0][1]) if requests_data else 0
        current_limits = float(limits_data[0][1]) if limits_data else 0
        
        # Usage statistics
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
        """Analyze memory metrics"""
        validations = []
        
        if not usage_data or not requests_data:
            return validations
        
        # Calculate usage statistics
        usage_values = [float(point[1]) for point in usage_data if point[1] != 'NaN']
        if not usage_values:
            return validations
        
        # Current values of requests/limits (in bytes)
        current_requests = float(requests_data[0][1]) if requests_data else 0
        current_limits = float(limits_data[0][1]) if limits_data else 0
        
        # Usage statistics
        avg_usage = sum(usage_values) / len(usage_values)
        max_usage = max(usage_values)
        p95_usage = sorted(usage_values)[int(len(usage_values) * 0.95)]
        p99_usage = sorted(usage_values)[int(len(usage_values) * 0.99)]
        
        # Convert to MiB for better readability
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
        """Execute query in Prometheus"""
        try:
            async with aiohttp.ClientSession() as session:
                params = {
                    'query': query,
                    'start': start_time.timestamp(),
                    'end': end_time.timestamp(),
                    'step': '60s'  # 1 minute resolution
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
        """Get cluster historical summary"""
        try:
            # Query for total cluster CPU
            cpu_query = f'''
            sum(rate(container_cpu_usage_seconds_total{{
                container!="POD",
                container!=""
            }}[{time_range}]))
            '''
            
            # Query for total cluster memory
            memory_query = f'''
            sum(container_memory_working_set_bytes{{
                container!="POD",
                container!=""
            }})
            '''
            
            # Query for total requests
            cpu_requests_query = f'''
            sum(kube_pod_container_resource_requests{{resource="cpu"}})
            '''
            
            memory_requests_query = f'''
            sum(kube_pod_container_resource_requests{{resource="memory"}})
            '''
            
            # Execute queries
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

    async def get_namespace_historical_analysis(self, namespace: str, time_range: str, prometheus_client):
        """Get historical analysis for a specific namespace"""
        try:
            logger.info(f"Getting historical analysis for namespace: {namespace}")
            
            # Query for CPU usage by namespace
            cpu_query = f'''
            sum(rate(container_cpu_usage_seconds_total{{
                namespace="{namespace}",
                container!="POD",
                container!=""
            }}[{time_range}]))
            '''
            
            # Query for memory usage by namespace
            memory_query = f'''
            sum(container_memory_working_set_bytes{{
                namespace="{namespace}",
                container!="POD",
                container!=""
            }})
            '''
            
            # Query for CPU requests by namespace
            cpu_requests_query = f'''
            sum(kube_pod_container_resource_requests{{
                namespace="{namespace}",
                resource="cpu"
            }})
            '''
            
            # Query for memory requests by namespace
            memory_requests_query = f'''
            sum(kube_pod_container_resource_requests{{
                namespace="{namespace}",
                resource="memory"
            }})
            '''
            
            # Query for pod count by namespace
            pod_count_query = f'''
            count(kube_pod_info{{namespace="{namespace}"}})
            '''
            
            # Execute queries
            cpu_usage = await self._query_prometheus(cpu_query, 
                datetime.now() - timedelta(seconds=self.time_ranges[time_range]), 
                datetime.now(), prometheus_client)
            memory_usage = await self._query_prometheus(memory_query, 
                datetime.now() - timedelta(seconds=self.time_ranges[time_range]), 
                datetime.now(), prometheus_client)
            cpu_requests = await self._query_prometheus(cpu_requests_query, 
                datetime.now() - timedelta(seconds=self.time_ranges[time_range]), 
                datetime.now(), prometheus_client)
            memory_requests = await self._query_prometheus(memory_requests_query, 
                datetime.now() - timedelta(seconds=self.time_ranges[time_range]), 
                datetime.now(), prometheus_client)
            pod_count = await self._query_prometheus(pod_count_query, 
                datetime.now() - timedelta(seconds=self.time_ranges[time_range]), 
                datetime.now(), prometheus_client)
            
            # Calculate utilization percentages
            cpu_utilization = 0
            memory_utilization = 0
            
            if cpu_usage and cpu_requests and cpu_requests[0][1] != '0':
                cpu_utilization = (float(cpu_usage[0][1]) / float(cpu_requests[0][1])) * 100
                
            if memory_usage and memory_requests and memory_requests[0][1] != '0':
                memory_utilization = (float(memory_usage[0][1]) / float(memory_requests[0][1])) * 100
            
            # Generate recommendations based on utilization
            recommendations = []
            
            if cpu_utilization > 80:
                recommendations.append({
                    "type": "cpu_high_utilization",
                    "severity": "warning",
                    "message": f"High CPU utilization: {cpu_utilization:.1f}%",
                    "recommendation": "Consider increasing CPU requests or optimizing application performance"
                })
            elif cpu_utilization < 20:
                recommendations.append({
                    "type": "cpu_low_utilization", 
                    "severity": "info",
                    "message": f"Low CPU utilization: {cpu_utilization:.1f}%",
                    "recommendation": "Consider reducing CPU requests to optimize resource allocation"
                })
                
            if memory_utilization > 80:
                recommendations.append({
                    "type": "memory_high_utilization",
                    "severity": "warning", 
                    "message": f"High memory utilization: {memory_utilization:.1f}%",
                    "recommendation": "Consider increasing memory requests or optimizing memory usage"
                })
            elif memory_utilization < 20:
                recommendations.append({
                    "type": "memory_low_utilization",
                    "severity": "info",
                    "message": f"Low memory utilization: {memory_utilization:.1f}%", 
                    "recommendation": "Consider reducing memory requests to optimize resource allocation"
                })
            
            return {
                'namespace': namespace,
                'time_range': time_range,
                'cpu_usage': float(cpu_usage[0][1]) if cpu_usage else 0,
                'memory_usage': float(memory_usage[0][1]) if memory_usage else 0,
                'cpu_requests': float(cpu_requests[0][1]) if cpu_requests else 0,
                'memory_requests': float(memory_requests[0][1]) if memory_requests else 0,
                'cpu_utilization': cpu_utilization,
                'memory_utilization': memory_utilization,
                'pod_count': int(pod_count[0][1]) if pod_count else 0,
                'recommendations': recommendations
            }
            
        except Exception as e:
            logger.error(f"Error getting historical analysis for namespace {namespace}: {e}")
            return {
                'namespace': namespace,
                'time_range': time_range,
                'error': str(e),
                'recommendations': []
            }
