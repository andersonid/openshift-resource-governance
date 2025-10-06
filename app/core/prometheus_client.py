"""
Prometheus client for metrics collection
"""
import logging
import aiohttp
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from app.core.config import settings

logger = logging.getLogger(__name__)

class PrometheusClient:
    """Client for Prometheus interaction"""
    
    def __init__(self):
        self.base_url = settings.prometheus_url
        self.session = None
        self.initialized = False
    
    async def initialize(self):
        """Initialize Prometheus client"""
        try:
            # Create session with SSL verification disabled for self-signed certificates
            connector = aiohttp.TCPConnector(ssl=False)
            
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
            
            self.session = aiohttp.ClientSession(connector=connector, headers=headers)
            
            # Test connection with SSL verification disabled
            async with self.session.get(f"{self.base_url}/api/v1/query?query=up", ssl=False) as response:
                if response.status == 200:
                    self.initialized = True
                    logger.info("Prometheus client initialized successfully")
                else:
                    logger.warning(f"Prometheus returned status {response.status}")
                    
        except Exception as e:
            logger.error(f"Error initializing Prometheus client: {e}")
            # Prometheus may not be available, continue without it
            self.initialized = False
    
    async def query(self, query: str, time: Optional[datetime] = None) -> Dict[str, Any]:
        """Execute query in Prometheus"""
        if not self.initialized or not self.session:
            return {"status": "error", "message": "Prometheus not available"}
        
        try:
            params = {"query": query}
            if time:
                params["time"] = int(time.timestamp())
            
            async with self.session.get(
                f"{self.base_url}/api/v1/query",
                params=params,
                ssl=False
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                else:
                    logger.error(f"Error in Prometheus query: {response.status}")
                    return {"status": "error", "message": f"HTTP {response.status}"}
                    
        except Exception as e:
            logger.error(f"Error executing Prometheus query: {e}")
            return {"status": "error", "message": str(e)}
    
    async def query_range(self, query: str, time_range: str = "24h") -> List[List[float]]:
        """Execute a Prometheus range query"""
        if not self.initialized or not self.session:
            return []
        
        try:
            # Calculate time range
            end_time = datetime.now()
            if time_range == "1h":
                start_time = end_time - timedelta(hours=1)
                step = "1m"
            elif time_range == "6h":
                start_time = end_time - timedelta(hours=6)
                step = "5m"
            elif time_range == "24h":
                start_time = end_time - timedelta(hours=24)
                step = "15m"
            elif time_range == "7d":
                start_time = end_time - timedelta(days=7)
                step = "1h"
            else:
                start_time = end_time - timedelta(hours=24)
                step = "15m"
            
            params = {
                'query': query,
                'start': int(start_time.timestamp()),
                'end': int(end_time.timestamp()),
                'step': step
            }
            
            async with self.session.get(
                f"{self.base_url}/api/v1/query_range",
                params=params,
                ssl=False
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("status") == "success" and data.get("data", {}).get("result"):
                        # Extract time series data points
                        result = data["data"]["result"][0]
                        return result.get("values", [])
                    else:
                        logger.warning(f"No data returned for query: {query}")
                        return []
                else:
                    logger.error(f"Prometheus range query failed: {response.status}")
                    return []
        
        except Exception as e:
            logger.error(f"Error querying Prometheus range: {e}")
            return []
    
    async def get_pod_cpu_usage(self, namespace: str, pod_name: str) -> Dict[str, Any]:
        """Get CPU usage for a specific pod"""
        query = f'rate(container_cpu_usage_seconds_total{{namespace="{namespace}", pod="{pod_name}"}}[5m])'
        return await self.query(query)
    
    async def get_pod_memory_usage(self, namespace: str, pod_name: str) -> Dict[str, Any]:
        """Get memory usage for a specific pod"""
        query = f'container_memory_working_set_bytes{{namespace="{namespace}", pod="{pod_name}"}}'
        return await self.query(query)
    
    async def get_namespace_resource_usage(self, namespace: str) -> Dict[str, Any]:
        """Get resource usage of a namespace"""
        cpu_query = f'sum(rate(container_cpu_usage_seconds_total{{namespace="{namespace}"}}[5m]))'
        memory_query = f'sum(container_memory_working_set_bytes{{namespace="{namespace}"}})'
        
        cpu_result = await self.query(cpu_query)
        memory_result = await self.query(memory_query)
        
        return {
            "cpu": cpu_result,
            "memory": memory_result
        }
    
    async def get_cluster_overcommit(self) -> Dict[str, Any]:
        """Check overcommit in cluster"""
        # CPU overcommit
        cpu_capacity_query = 'sum(kube_node_status_capacity{resource="cpu"})'
        cpu_requests_query = 'sum(kube_pod_container_resource_requests{resource="cpu"})'
        
        # Memory overcommit
        memory_capacity_query = 'sum(kube_node_status_capacity{resource="memory"})'
        memory_requests_query = 'sum(kube_pod_container_resource_requests{resource="memory"})'
        
        cpu_capacity = await self.query(cpu_capacity_query)
        cpu_requests = await self.query(cpu_requests_query)
        memory_capacity = await self.query(memory_capacity_query)
        memory_requests = await self.query(memory_requests_query)
        
        return {
            "cpu": {
                "capacity": cpu_capacity,
                "requests": cpu_requests
            },
            "memory": {
                "capacity": memory_capacity,
                "requests": memory_requests
            }
        }
    
    async def get_node_resource_usage(self) -> List[Dict[str, Any]]:
        """Get resource usage by node"""
        query = '''
        (
            kube_node_status_capacity{resource="cpu"} or
            kube_node_status_capacity{resource="memory"} or
            kube_pod_container_resource_requests{resource="cpu"} or
            kube_pod_container_resource_requests{resource="memory"}
        )
        '''
        
        result = await self.query(query)
        return result
    
    async def get_cluster_resource_utilization(self) -> Dict[str, Any]:
        """Get cluster resource utilization (usage vs requests)"""
        # CPU utilization queries
        cpu_usage_query = 'sum(rate(container_cpu_usage_seconds_total[5m]))'
        cpu_requests_query = 'sum(kube_pod_container_resource_requests{resource="cpu"})'
        
        # Memory utilization queries
        memory_usage_query = 'sum(container_memory_working_set_bytes)'
        memory_requests_query = 'sum(kube_pod_container_resource_requests{resource="memory"})'
        
        # Execute queries
        cpu_usage_result = await self.query(cpu_usage_query)
        cpu_requests_result = await self.query(cpu_requests_query)
        memory_usage_result = await self.query(memory_usage_query)
        memory_requests_result = await self.query(memory_requests_query)
        
        # Extract values
        cpu_usage = 0
        cpu_requests = 0
        memory_usage = 0
        memory_requests = 0
        
        if cpu_usage_result.get('status') == 'success' and cpu_usage_result.get('data', {}).get('result'):
            cpu_usage = float(cpu_usage_result['data']['result'][0]['value'][1])
        
        if cpu_requests_result.get('status') == 'success' and cpu_requests_result.get('data', {}).get('result'):
            cpu_requests = float(cpu_requests_result['data']['result'][0]['value'][1])
        
        if memory_usage_result.get('status') == 'success' and memory_usage_result.get('data', {}).get('result'):
            memory_usage = float(memory_usage_result['data']['result'][0]['value'][1])
        
        if memory_requests_result.get('status') == 'success' and memory_requests_result.get('data', {}).get('result'):
            memory_requests = float(memory_requests_result['data']['result'][0]['value'][1])
        
        # Calculate utilization percentages
        cpu_utilization = (cpu_usage / cpu_requests * 100) if cpu_requests > 0 else 0
        memory_utilization = (memory_usage / memory_requests * 100) if memory_requests > 0 else 0
        
        # Overall resource utilization (average of CPU and memory)
        overall_utilization = (cpu_utilization + memory_utilization) / 2 if (cpu_utilization > 0 or memory_utilization > 0) else 0
        
        return {
            "cpu": {
                "usage": cpu_usage,
                "requests": cpu_requests,
                "utilization_percent": cpu_utilization
            },
            "memory": {
                "usage": memory_usage,
                "requests": memory_requests,
                "utilization_percent": memory_utilization
            },
            "overall_utilization_percent": overall_utilization,
            "data_source": "prometheus"
        }
    
    def health_check(self) -> Dict[str, Any]:
        """
        Check Prometheus connectivity and health.
        
        Returns:
            Health status
        """
        try:
            if not self.initialized or not self.session:
                return {
                    'status': 'unhealthy',
                    'prometheus_url': self.prometheus_url,
                    'error': 'Prometheus not initialized'
                }
            
            # Use aiohttp session for health check
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            async def _health_check():
                async with self.session.get(f"{self.prometheus_url}/api/v1/status/config") as response:
                    if response.status == 200:
                        return {
                            'status': 'healthy',
                            'prometheus_url': self.prometheus_url,
                            'response_time': 0.1  # Placeholder
                        }
                    else:
                        return {
                            'status': 'unhealthy',
                            'prometheus_url': self.prometheus_url,
                            'error': f'HTTP {response.status}'
                        }
            
            result = loop.run_until_complete(_health_check())
            loop.close()
            return result
            
        except Exception as e:
            logger.error(f"Prometheus health check failed: {e}")
            return {
                'status': 'unhealthy',
                'prometheus_url': self.prometheus_url,
                'error': str(e)
            }
    
    async def close(self):
        """Close HTTP session"""
        if self.session:
            await self.session.close()
