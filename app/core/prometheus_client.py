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
            self.session = aiohttp.ClientSession()
            
            # Test connection
            async with self.session.get(f"{self.base_url}/api/v1/query?query=up") as response:
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
                params=params
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
    
    async def close(self):
        """Close HTTP session"""
        if self.session:
            await self.session.close()
