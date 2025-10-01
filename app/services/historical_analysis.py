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
    
    def _safe_float(self, value, default=0):
        """Safely convert value to float, handling inf and NaN"""
        try:
            result = float(value)
            if result == float('inf') or result == float('-inf') or result != result:  # NaN check
                return default
            return result
        except (ValueError, TypeError):
            return default
    
    def _extract_workload_name(self, pod_name: str) -> str:
        """Extract workload name from pod name (remove pod suffix)"""
        # Pod names typically follow pattern: workload-name-hash-suffix
        # e.g., resource-governance-798b5579d6-7h298 -> resource-governance
        parts = pod_name.split('-')
        if len(parts) >= 3 and parts[-1].isalnum() and len(parts[-1]) == 5:
            # Remove the last two parts (hash and suffix)
            return '-'.join(parts[:-2])
        elif len(parts) >= 2 and parts[-1].isalnum() and len(parts[-1]) == 5:
            # Remove the last part (suffix)
            return '-'.join(parts[:-1])
        else:
            # Fallback to pod name if pattern doesn't match
            return pod_name

    async def analyze_workload_historical_usage(
        self, 
        pods: List[PodResource], 
        time_range: str = '24h'
    ) -> List[ResourceValidation]:
        """Analyze historical usage for a workload (group of pods)"""
        if not pods:
            return []
        
        # Group pods by workload name
        workload_pods = {}
        for pod in pods:
            workload_name = self._extract_workload_name(pod.name)
            if workload_name not in workload_pods:
                workload_pods[workload_name] = []
            workload_pods[workload_name].append(pod)
        
        all_validations = []
        
        # Analyze each workload
        for workload_name, workload_pod_list in workload_pods.items():
            try:
                # Use the first pod as representative for the workload
                representative_pod = workload_pod_list[0]
                
                # Analyze historical usage for the workload
                workload_validations = await self._analyze_workload_metrics(
                    workload_name, representative_pod.namespace, workload_pod_list, time_range
                )
                all_validations.extend(workload_validations)
                
            except Exception as e:
                logger.warning(f"Error analyzing workload {workload_name}: {e}")
                # Fallback to individual pod analysis
                for pod in workload_pod_list:
                    try:
                        pod_validations = await self.analyze_pod_historical_usage(pod, time_range)
                        all_validations.extend(pod_validations)
                    except Exception as pod_e:
                        logger.warning(f"Error analyzing pod {pod.name}: {pod_e}")
        
        return all_validations

    async def _analyze_workload_metrics(
        self, 
        workload_name: str, 
        namespace: str, 
        pods: List[PodResource], 
        time_range: str
    ) -> List[ResourceValidation]:
        """Analyze metrics for a workload using Prometheus queries"""
        validations = []
        
        try:
            # Query for CPU usage by workload
            cpu_query = f'''
            sum(
                node_namespace_pod_container:container_cpu_usage_seconds_total:sum_irate{{
                    cluster="", 
                    namespace="{namespace}"
                }}
                * on(namespace,pod)
                group_left(workload, workload_type) 
                namespace_workload_pod:kube_pod_owner:relabel{{
                    cluster="", 
                    namespace="{namespace}", 
                    workload="{workload_name}",
                    workload_type=~".+"
                }}
            ) by (workload, workload_type)
            '''
            
            # Query for memory usage by workload
            memory_query = f'''
            sum(
                container_memory_working_set_bytes{{
                    job="kubelet", 
                    metrics_path="/metrics/cadvisor", 
                    cluster="", 
                    namespace="{namespace}", 
                    container!="", 
                    image!=""
                }}
                * on(namespace,pod)
                group_left(workload, workload_type) 
                namespace_workload_pod:kube_pod_owner:relabel{{
                    cluster="", 
                    namespace="{namespace}", 
                    workload="{workload_name}",
                    workload_type=~".+"
                }}
            ) by (workload, workload_type)
            '''
            
            # Query for CPU requests by workload
            cpu_requests_query = f'''
            sum(
                kube_pod_container_resource_requests{{
                    resource="cpu",
                    namespace="{namespace}"
                }}
                * on(namespace,pod)
                group_left(workload, workload_type) 
                namespace_workload_pod:kube_pod_owner:relabel{{
                    cluster="", 
                    namespace="{namespace}", 
                    workload="{workload_name}",
                    workload_type=~".+"
                }}
            ) by (workload, workload_type)
            '''
            
            # Query for memory requests by workload
            memory_requests_query = f'''
            sum(
                kube_pod_container_resource_requests{{
                    resource="memory",
                    namespace="{namespace}"
                }}
                * on(namespace,pod)
                group_left(workload, workload_type) 
                namespace_workload_pod:kube_pod_owner:relabel{{
                    cluster="", 
                    namespace="{namespace}", 
                    workload="{workload_name}",
                    workload_type=~".+"
                }}
            ) by (workload, workload_type)
            '''
            
            # Query for CPU limits by workload
            cpu_limits_query = f'''
            sum(
                kube_pod_container_resource_limits{{
                    resource="cpu",
                    namespace="{namespace}"
                }}
                * on(namespace,pod)
                group_left(workload, workload_type) 
                namespace_workload_pod:kube_pod_owner:relabel{{
                    cluster="", 
                    namespace="{namespace}", 
                    workload="{workload_name}",
                    workload_type=~".+"
                }}
            ) by (workload, workload_type)
            '''
            
            # Query for memory limits by workload
            memory_limits_query = f'''
            sum(
                kube_pod_container_resource_limits{{
                    resource="memory",
                    namespace="{namespace}"
                }}
                * on(namespace,pod)
                group_left(workload, workload_type) 
                namespace_workload_pod:kube_pod_owner:relabel{{
                    cluster="", 
                    namespace="{namespace}", 
                    workload="{workload_name}",
                    workload_type=~".+"
                }}
            ) by (workload, workload_type)
            '''
            
            # Execute queries
            cpu_usage_data = await self._query_prometheus(cpu_query, time_range)
            memory_usage_data = await self._query_prometheus(memory_query, time_range)
            cpu_requests_data = await self._query_prometheus(cpu_requests_query, time_range)
            memory_requests_data = await self._query_prometheus(memory_requests_query, time_range)
            cpu_limits_data = await self._query_prometheus(cpu_limits_query, time_range)
            memory_limits_data = await self._query_prometheus(memory_limits_query, time_range)
            
            # Analyze CPU metrics for workload
            if cpu_usage_data and cpu_requests_data and cpu_limits_data:
                cpu_validations = self._analyze_cpu_metrics(
                    workload_name, namespace, "workload", 
                    cpu_usage_data, cpu_requests_data, cpu_limits_data, time_range
                )
                validations.extend(cpu_validations)
            
            # Analyze memory metrics for workload
            if memory_usage_data and memory_requests_data and memory_limits_data:
                memory_validations = self._analyze_memory_metrics(
                    workload_name, namespace, "workload", 
                    memory_usage_data, memory_requests_data, memory_limits_data, time_range
                )
                validations.extend(memory_validations)
            
        except Exception as e:
            logger.warning(f"Error analyzing workload metrics for {workload_name}: {e}")
            # Fallback to individual pod analysis
            for pod in pods:
                try:
                    pod_validations = await self.analyze_pod_historical_usage(pod, time_range)
                    validations.extend(pod_validations)
                except Exception as pod_e:
                    logger.warning(f"Error analyzing pod {pod.name}: {pod_e}")
        
        return validations

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
                    pod=~"{pod.name}.*",
                    namespace="{pod.namespace}",
                    container="{container_name}",
                    container!="POD",
                    container!=""
                }}[{time_range}])
                '''
                
                # Query for CPU requests
                cpu_requests_query = f'''
                kube_pod_container_resource_requests{{
                    pod=~"{pod.name}.*",
                    namespace="{pod.namespace}",
                    resource="cpu"
                }}
                '''
                
                # Query for CPU limits
                cpu_limits_query = f'''
                kube_pod_container_resource_limits{{
                    pod=~"{pod.name}.*",
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
                    pod=~"{pod.name}.*",
                    namespace="{pod.namespace}",
                    container="{container_name}",
                    container!="POD",
                    container!=""
                }}
                '''
                
                # Query for memory requests
                memory_requests_query = f'''
                kube_pod_container_resource_requests{{
                    pod=~"{pod.name}.*",
                    namespace="{pod.namespace}",
                    resource="memory"
                }}
                '''
                
                # Query for memory limits
                memory_limits_query = f'''
                kube_pod_container_resource_limits{{
                    pod=~"{pod.name}.*",
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
    
    def _detect_seasonal_patterns(
        self,
        pod_name: str,
        namespace: str,
        container_name: str,
        usage_values: List[float],
        time_range: str
    ) -> List[ResourceValidation]:
        """Detect seasonal patterns and trends in resource usage"""
        validations = []
        
        if len(usage_values) < 20:  # Need at least 20 data points for pattern detection
            return validations
        
        # Calculate trend (simple linear regression)
        n = len(usage_values)
        x = list(range(n))
        y = usage_values
        
        # Calculate slope
        x_mean = sum(x) / n
        y_mean = sum(y) / n
        
        numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        if denominator != 0:
            slope = numerator / denominator
            
            # Detect significant trends
            if slope > 0.1:  # Increasing trend
                validations.append(ResourceValidation(
                    pod_name=pod_name,
                    namespace=namespace,
                    container_name=container_name,
                    validation_type="seasonal_pattern",
                    severity="info",
                    message=f"Detected increasing resource usage trend over {time_range}",
                    recommendation="Monitor for continued growth and consider proactive scaling"
                ))
            elif slope < -0.1:  # Decreasing trend
                validations.append(ResourceValidation(
                    pod_name=pod_name,
                    namespace=namespace,
                    container_name=container_name,
                    validation_type="seasonal_pattern",
                    severity="info",
                    message=f"Detected decreasing resource usage trend over {time_range}",
                    recommendation="Consider reducing resource requests/limits if trend continues"
                ))
        
        # Detect high variability (coefficient of variation > 50%)
        if y_mean > 0:
            variance = sum((y[i] - y_mean) ** 2 for i in range(n)) / n
            std_dev = variance ** 0.5
            cv = std_dev / y_mean
            
            if cv > 0.5:  # High variability
                validations.append(ResourceValidation(
                    pod_name=pod_name,
                    namespace=namespace,
                    container_name=container_name,
                    validation_type="seasonal_pattern",
                    severity="warning",
                    message=f"High resource usage variability detected (CV: {cv:.2f})",
                    recommendation="Consider higher safety margins for requests/limits due to unpredictable usage"
                ))
        
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
        
        # Check for insufficient historical data
        if not usage_data:
            validations.append(ResourceValidation(
                pod_name=pod_name,
                namespace=namespace,
                container_name=container_name,
                validation_type="insufficient_historical_data",
                severity="info",
                message=f"No CPU usage data available for {time_range}",
                recommendation="Monitor workload for at least 24h to get reliable resource recommendations"
            ))
            return validations
        
        # Calculate usage statistics
        usage_values = [float(point[1]) for point in usage_data if point[1] != 'NaN']
        logger.info(f"CPU analysis for {pod_name}/{container_name}: {len(usage_data)} raw points, {len(usage_values)} valid points")
        if not usage_values:
            validations.append(ResourceValidation(
                pod_name=pod_name,
                namespace=namespace,
                container_name=container_name,
                validation_type="insufficient_historical_data",
                severity="info",
                message=f"No valid CPU usage data points for {time_range}",
                recommendation="Check if pod is running and generating metrics"
            ))
            return validations
        
        # Check for minimal data points (less than 3 data points)
        if len(usage_values) < 3:
            validations.append(ResourceValidation(
                pod_name=pod_name,
                namespace=namespace,
                container_name=container_name,
                validation_type="insufficient_historical_data",
                severity="warning",
                message=f"Limited CPU usage data ({len(usage_values)} points) for {time_range}",
                recommendation="Wait for more data points or extend time range for reliable analysis"
            ))
            return validations  # Don't proceed with historical analysis if insufficient data
        
        # Current values of requests/limits
        current_requests = self._safe_float(requests_data[0][1]) if requests_data else 0
        current_limits = self._safe_float(limits_data[0][1]) if limits_data else 0
        
        # Usage statistics
        avg_usage = sum(usage_values) / len(usage_values)
        max_usage = max(usage_values)
        p95_usage = sorted(usage_values)[int(len(usage_values) * 0.95)]
        p99_usage = sorted(usage_values)[int(len(usage_values) * 0.99)]
        
        # Detect seasonal patterns
        seasonal_validations = self._detect_seasonal_patterns(
            pod_name, namespace, container_name, usage_values, time_range
        )
        validations.extend(seasonal_validations)
        
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
        
        # Check for insufficient historical data
        if not usage_data:
            validations.append(ResourceValidation(
                pod_name=pod_name,
                namespace=namespace,
                container_name=container_name,
                validation_type="insufficient_historical_data",
                severity="info",
                message=f"No memory usage data available for {time_range}",
                recommendation="Monitor workload for at least 24h to get reliable resource recommendations"
            ))
            return validations
        
        # Calculate usage statistics
        usage_values = [float(point[1]) for point in usage_data if point[1] != 'NaN']
        logger.info(f"Memory analysis for {pod_name}/{container_name}: {len(usage_data)} raw points, {len(usage_values)} valid points")
        if not usage_values:
            validations.append(ResourceValidation(
                pod_name=pod_name,
                namespace=namespace,
                container_name=container_name,
                validation_type="insufficient_historical_data",
                severity="info",
                message=f"No valid memory usage data points for {time_range}",
                recommendation="Check if pod is running and generating metrics"
            ))
            return validations
        
        # Check for minimal data points (less than 3 data points)
        if len(usage_values) < 3:
            validations.append(ResourceValidation(
                pod_name=pod_name,
                namespace=namespace,
                container_name=container_name,
                validation_type="insufficient_historical_data",
                severity="warning",
                message=f"Limited memory usage data ({len(usage_values)} points) for {time_range}",
                recommendation="Wait for more data points or extend time range for reliable analysis"
            ))
            return validations  # Don't proceed with historical analysis if insufficient data
        
        # Current values of requests/limits (in bytes)
        current_requests = self._safe_float(requests_data[0][1]) if requests_data else 0
        current_limits = self._safe_float(limits_data[0][1]) if limits_data else 0
        
        # Usage statistics
        avg_usage = sum(usage_values) / len(usage_values)
        max_usage = max(usage_values)
        p95_usage = sorted(usage_values)[int(len(usage_values) * 0.95)]
        p99_usage = sorted(usage_values)[int(len(usage_values) * 0.99)]
        
        # Detect seasonal patterns
        seasonal_validations = self._detect_seasonal_patterns(
            pod_name, namespace, container_name, usage_values, time_range
        )
        validations.extend(seasonal_validations)
        
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
            # Get service account token for authentication
            token = None
            try:
                with open('/var/run/secrets/kubernetes.io/serviceaccount/token', 'r') as f:
                    token = f.read().strip()
            except FileNotFoundError:
                logger.warning("Service account token not found, proceeding without authentication")
            
            # Create headers with token if available
            headers = {}
            if token:
                headers['Authorization'] = f'Bearer {token}'
            
            # Create session with SSL verification disabled for self-signed certificates
            connector = aiohttp.TCPConnector(ssl=False)
            
            async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
                params = {
                    'query': query,
                    'start': start_time.timestamp(),
                    'end': end_time.timestamp(),
                    'step': '60s'  # 1 minute resolution
                }
                
                async with session.get(
                    f"{self.prometheus_url}/api/v1/query_range",
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=30),
                    ssl=False
                ) as response:
                    logger.info(f"Prometheus query: {query}, status: {response.status}")
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"Prometheus response: {data}")
                        if data['status'] == 'success' and data['data']['result']:
                            values = data['data']['result'][0]['values']
                            logger.info(f"Returning {len(values)} data points")
                            return values
                        else:
                            logger.warning(f"No data in Prometheus response: {data}")
                            return []
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
                'cpu_usage': self._safe_float(cpu_usage[0][1]) if cpu_usage and len(cpu_usage) > 0 else 0,
                'memory_usage': self._safe_float(memory_usage[0][1]) if memory_usage and len(memory_usage) > 0 else 0,
                'cpu_requests': self._safe_float(cpu_requests[0][1]) if cpu_requests and len(cpu_requests) > 0 else 0,
                'memory_requests': self._safe_float(memory_requests[0][1]) if memory_requests and len(memory_requests) > 0 else 0,
                'cpu_utilization': (self._safe_float(cpu_usage[0][1]) / self._safe_float(cpu_requests[0][1]) * 100) if cpu_usage and cpu_requests and self._safe_float(cpu_requests[0][1]) != 0 else 0,
                'memory_utilization': (self._safe_float(memory_usage[0][1]) / self._safe_float(memory_requests[0][1]) * 100) if memory_usage and memory_requests and self._safe_float(memory_requests[0][1]) != 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error getting historical summary: {e}")
            return {}

    async def get_namespace_historical_analysis(self, namespace: str, time_range: str, k8s_client=None):
        """Get historical analysis for a specific namespace"""
        try:
            logger.info(f"Getting historical analysis for namespace: {namespace}")
            
            # Query for CPU usage by namespace (using correct OpenShift metrics)
            cpu_query = f'''
            sum(
                node_namespace_pod_container:container_cpu_usage_seconds_total:sum_irate{{
                    cluster="", 
                    namespace="{namespace}"
                }}
            ) by (namespace)
            '''
            
            # Query for memory usage by namespace (using correct OpenShift metrics)
            memory_query = f'''
            sum(
                container_memory_working_set_bytes{{
                    job="kubelet", 
                    metrics_path="/metrics/cadvisor", 
                    cluster="", 
                    namespace="{namespace}", 
                    container!="", 
                    image!=""
                }}
            ) by (namespace)
            '''
            
            # Query for CPU requests by namespace (using correct OpenShift resource quota)
            cpu_requests_query = f'''
            scalar(kube_resourcequota{{
                cluster="", 
                namespace="{namespace}", 
                type="hard",
                resource="requests.cpu"
            }})
            '''
            
            # Query for memory requests by namespace (using correct OpenShift resource quota)
            memory_requests_query = f'''
            scalar(kube_resourcequota{{
                cluster="", 
                namespace="{namespace}", 
                type="hard",
                resource="requests.memory"
            }})
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
            
            # Get pod count using Kubernetes API (more reliable than Prometheus)
            pod_count = 0
            if k8s_client:
                try:
                    pods = await k8s_client.get_all_pods()
                    namespace_pods = [pod for pod in pods if pod.namespace == namespace]
                    pod_count = len(namespace_pods)
                except Exception as e:
                    logger.warning(f"Could not get pod count from Kubernetes API: {e}")
                    # Fallback to Prometheus query
                    pod_count_query = f'count(kube_pod_info{{namespace="{namespace}"}})'
                    pod_count_result = await self._query_prometheus(pod_count_query, 
                        datetime.now() - timedelta(seconds=self.time_ranges[time_range]), 
                        datetime.now())
                    pod_count = int(self._safe_float(pod_count_result[0][1])) if pod_count_result and len(pod_count_result) > 0 else 0
            else:
                # Fallback to Prometheus query if no k8s_client
                pod_count_query = f'count(kube_pod_info{{namespace="{namespace}"}})'
                pod_count_result = await self._query_prometheus(pod_count_query, 
                    datetime.now() - timedelta(seconds=self.time_ranges[time_range]), 
                    datetime.now())
                pod_count = int(self._safe_float(pod_count_result[0][1])) if pod_count_result and len(pod_count_result) > 0 else 0
            
            # Calculate utilization percentages
            cpu_utilization = 0
            memory_utilization = 0
            
            if cpu_usage and cpu_requests and len(cpu_usage) > 0 and len(cpu_requests) > 0 and self._safe_float(cpu_requests[0][1]) != 0:
                cpu_utilization = (self._safe_float(cpu_usage[0][1]) / self._safe_float(cpu_requests[0][1])) * 100
                
            if memory_usage and memory_requests and len(memory_usage) > 0 and len(memory_requests) > 0 and self._safe_float(memory_requests[0][1]) != 0:
                memory_utilization = (self._safe_float(memory_usage[0][1]) / self._safe_float(memory_requests[0][1])) * 100
            
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
                'cpu_usage': self._safe_float(cpu_usage[0][1]) if cpu_usage and len(cpu_usage) > 0 else 0,
                'memory_usage': self._safe_float(memory_usage[0][1]) if memory_usage and len(memory_usage) > 0 else 0,
                'cpu_requests': self._safe_float(cpu_requests[0][1]) if cpu_requests and len(cpu_requests) > 0 else 0,
                'memory_requests': self._safe_float(memory_requests[0][1]) if memory_requests and len(memory_requests) > 0 else 0,
                'cpu_utilization': cpu_utilization,
                'memory_utilization': memory_utilization,
                'pod_count': pod_count,
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

    async def get_workload_historical_analysis(self, namespace: str, workload: str, time_range: str):
        """Get historical analysis for a specific workload/deployment"""
        try:
            logger.info(f"Getting historical analysis for workload: {workload} in namespace: {namespace}")
            
            # Query for CPU usage by workload (using correct OpenShift metrics)
            cpu_query = f'''
            sum(
                node_namespace_pod_container:container_cpu_usage_seconds_total:sum_irate{{
                    cluster="", 
                    namespace="{namespace}"
                }}
                * on(namespace,pod)
                group_left(workload, workload_type) 
                namespace_workload_pod:kube_pod_owner:relabel{{
                    cluster="", 
                    namespace="{namespace}", 
                    workload_type=~".+"
                }}
            ) by (workload, workload_type)
            '''
            
            # Query for memory usage by workload (using correct OpenShift metrics)
            memory_query = f'''
            sum(
                container_memory_working_set_bytes{{
                    job="kubelet", 
                    metrics_path="/metrics/cadvisor", 
                    cluster="", 
                    namespace="{namespace}", 
                    container!="", 
                    image!=""
                }}
                * on(namespace,pod)
                group_left(workload, workload_type) 
                namespace_workload_pod:kube_pod_owner:relabel{{
                    cluster="", 
                    namespace="{namespace}", 
                    workload_type=~".+"
                }}
            ) by (workload, workload_type)
            '''
            
            # Query for CPU requests by namespace (using correct OpenShift resource quota)
            cpu_requests_query = f'''
            scalar(kube_resourcequota{{
                cluster="", 
                namespace="{namespace}", 
                type="hard",
                resource="requests.cpu"
            }})
            '''
            
            # Query for memory requests by namespace (using correct OpenShift resource quota)
            memory_requests_query = f'''
            scalar(kube_resourcequota{{
                cluster="", 
                namespace="{namespace}", 
                type="hard",
                resource="requests.memory"
            }})
            '''
            
            # Query for CPU limits by namespace (using correct OpenShift resource quota)
            cpu_limits_query = f'''
            scalar(kube_resourcequota{{
                cluster="", 
                namespace="{namespace}", 
                type="hard",
                resource="limits.cpu"
            }})
            '''
            
            # Query for memory limits by namespace (using correct OpenShift resource quota)
            memory_limits_query = f'''
            scalar(kube_resourcequota{{
                cluster="", 
                namespace="{namespace}", 
                type="hard",
                resource="limits.memory"
            }})
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
            cpu_limits = await self._query_prometheus(cpu_limits_query, 
                datetime.now() - timedelta(seconds=self.time_ranges[time_range]), 
                datetime.now())
            memory_limits = await self._query_prometheus(memory_limits_query, 
                datetime.now() - timedelta(seconds=self.time_ranges[time_range]), 
                datetime.now())
            
            # Calculate utilization percentages
            cpu_utilization = 0
            memory_utilization = 0
            
            if cpu_usage and cpu_requests and len(cpu_usage) > 0 and len(cpu_requests) > 0 and self._safe_float(cpu_requests[0][1]) != 0:
                cpu_utilization = (self._safe_float(cpu_usage[0][1]) / self._safe_float(cpu_requests[0][1])) * 100
                
            if memory_usage and memory_requests and len(memory_usage) > 0 and len(memory_requests) > 0 and self._safe_float(memory_requests[0][1]) != 0:
                memory_utilization = (self._safe_float(memory_usage[0][1]) / self._safe_float(memory_requests[0][1])) * 100
            
            # Generate recommendations based on utilization
            recommendations = []
            
            if cpu_utilization > 80:
                recommendations.append({
                    "type": "cpu_high_utilization",
                    "severity": "warning",
                    "message": f"High CPU utilization: {cpu_utilization:.1f}%",
                    "recommendation": "Consider increasing CPU requests or optimizing application performance"
                })
            elif cpu_utilization < 20 and cpu_utilization > 0:
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
            elif memory_utilization < 20 and memory_utilization > 0:
                recommendations.append({
                    "type": "memory_low_utilization",
                    "severity": "info",
                    "message": f"Low memory utilization: {memory_utilization:.1f}%", 
                    "recommendation": "Consider reducing memory requests to optimize resource allocation"
                })
            
            return {
                'namespace': namespace,
                'workload': workload,
                'time_range': time_range,
                'cpu_usage': self._safe_float(cpu_usage[0][1]) if cpu_usage and len(cpu_usage) > 0 else 0,
                'memory_usage': self._safe_float(memory_usage[0][1]) if memory_usage and len(memory_usage) > 0 else 0,
                'cpu_requests': self._safe_float(cpu_requests[0][1]) if cpu_requests and len(cpu_requests) > 0 else 0,
                'memory_requests': self._safe_float(memory_requests[0][1]) if memory_requests and len(memory_requests) > 0 else 0,
                'cpu_limits': self._safe_float(cpu_limits[0][1]) if cpu_limits and len(cpu_limits) > 0 else 0,
                'memory_limits': self._safe_float(memory_limits[0][1]) if memory_limits and len(memory_limits) > 0 else 0,
                'cpu_utilization': cpu_utilization,
                'memory_utilization': memory_utilization,
                'recommendations': recommendations
            }
            
        except Exception as e:
            logger.error(f"Error getting historical analysis for workload {workload} in namespace {namespace}: {e}")
            return {
                'namespace': namespace,
                'workload': workload,
                'time_range': time_range,
                'error': str(e),
                'recommendations': []
            }

    async def get_pod_historical_analysis(self, namespace: str, pod_name: str, time_range: str):
        """Get historical analysis for a specific pod"""
        try:
            logger.info(f"Getting historical analysis for pod: {pod_name} in namespace: {namespace}")
            
            # Query for CPU usage by pod (more generic query)
            cpu_query = f'''
            sum(rate(container_cpu_usage_seconds_total{{
                namespace="{namespace}",
                pod=~"{pod_name}.*",
                container!="POD",
                container!=""
            }}[{time_range}]))
            '''
            
            # Query for memory usage by pod (more generic query)
            memory_query = f'''
            sum(container_memory_working_set_bytes{{
                namespace="{namespace}",
                pod=~"{pod_name}.*",
                container!="POD",
                container!=""
            }})
            '''
            
            # Query for CPU requests by pod (more generic query)
            cpu_requests_query = f'''
            sum(kube_pod_container_resource_requests{{
                namespace="{namespace}",
                pod=~"{pod_name}.*",
                resource="cpu"
            }})
            '''
            
            # Query for memory requests by pod (more generic query)
            memory_requests_query = f'''
            sum(kube_pod_container_resource_requests{{
                namespace="{namespace}",
                pod=~"{pod_name}.*",
                resource="memory"
            }})
            '''
            
            # Query for container count by pod (more generic query)
            container_count_query = f'''
            count(container_memory_working_set_bytes{{
                namespace="{namespace}",
                pod=~"{pod_name}.*",
                container!="POD",
                container!=""
            }})
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
            container_count = await self._query_prometheus(container_count_query, 
                datetime.now() - timedelta(seconds=self.time_ranges[time_range]), 
                datetime.now())
            
            # Calculate utilization percentages
            cpu_utilization = 0
            memory_utilization = 0
            
            if cpu_usage and cpu_requests and len(cpu_usage) > 0 and len(cpu_requests) > 0 and self._safe_float(cpu_requests[0][1]) != 0:
                cpu_utilization = (self._safe_float(cpu_usage[0][1]) / self._safe_float(cpu_requests[0][1])) * 100
                
            if memory_usage and memory_requests and len(memory_usage) > 0 and len(memory_requests) > 0 and self._safe_float(memory_requests[0][1]) != 0:
                memory_utilization = (self._safe_float(memory_usage[0][1]) / self._safe_float(memory_requests[0][1])) * 100
            
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
                'pod_name': pod_name,
                'time_range': time_range,
                'cpu_usage': self._safe_float(cpu_usage[0][1]) if cpu_usage and len(cpu_usage) > 0 else 0,
                'memory_usage': self._safe_float(memory_usage[0][1]) if memory_usage and len(memory_usage) > 0 else 0,
                'cpu_requests': self._safe_float(cpu_requests[0][1]) if cpu_requests and len(cpu_requests) > 0 else 0,
                'memory_requests': self._safe_float(memory_requests[0][1]) if memory_requests and len(memory_requests) > 0 else 0,
                'cpu_utilization': cpu_utilization,
                'memory_utilization': memory_utilization,
                'container_count': int(self._safe_float(container_count[0][1])) if container_count and len(container_count) > 0 else 0,
                'recommendations': recommendations
            }
            
        except Exception as e:
            logger.error(f"Error getting historical analysis for pod {pod_name} in namespace {namespace}: {e}")
            return {
                'namespace': namespace,
                'pod_name': pod_name,
                'time_range': time_range,
                'error': str(e),
                'recommendations': []
            }
