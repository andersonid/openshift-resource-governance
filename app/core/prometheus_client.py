"""
Cliente Prometheus para coleta de métricas
"""
import logging
import aiohttp
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from app.core.config import settings

logger = logging.getLogger(__name__)

class PrometheusClient:
    """Cliente para interação com Prometheus"""
    
    def __init__(self):
        self.base_url = settings.prometheus_url
        self.session = None
        self.initialized = False
    
    async def initialize(self):
        """Inicializar cliente Prometheus"""
        try:
            self.session = aiohttp.ClientSession()
            
            # Testar conexão
            async with self.session.get(f"{self.base_url}/api/v1/query?query=up") as response:
                if response.status == 200:
                    self.initialized = True
                    logger.info("Cliente Prometheus inicializado com sucesso")
                else:
                    logger.warning(f"Prometheus retornou status {response.status}")
                    
        except Exception as e:
            logger.error(f"Erro ao inicializar cliente Prometheus: {e}")
            # Prometheus pode não estar disponível, continuar sem ele
            self.initialized = False
    
    async def query(self, query: str, time: Optional[datetime] = None) -> Dict[str, Any]:
        """Executar query no Prometheus"""
        if not self.initialized or not self.session:
            return {"status": "error", "message": "Prometheus não disponível"}
        
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
                    logger.error(f"Erro na query Prometheus: {response.status}")
                    return {"status": "error", "message": f"HTTP {response.status}"}
                    
        except Exception as e:
            logger.error(f"Erro ao executar query Prometheus: {e}")
            return {"status": "error", "message": str(e)}
    
    async def get_pod_cpu_usage(self, namespace: str, pod_name: str) -> Dict[str, Any]:
        """Obter uso de CPU de um pod específico"""
        query = f'rate(container_cpu_usage_seconds_total{{namespace="{namespace}", pod="{pod_name}"}}[5m])'
        return await self.query(query)
    
    async def get_pod_memory_usage(self, namespace: str, pod_name: str) -> Dict[str, Any]:
        """Obter uso de memória de um pod específico"""
        query = f'container_memory_working_set_bytes{{namespace="{namespace}", pod="{pod_name}"}}'
        return await self.query(query)
    
    async def get_namespace_resource_usage(self, namespace: str) -> Dict[str, Any]:
        """Obter uso de recursos de um namespace"""
        cpu_query = f'sum(rate(container_cpu_usage_seconds_total{{namespace="{namespace}"}}[5m]))'
        memory_query = f'sum(container_memory_working_set_bytes{{namespace="{namespace}"}})'
        
        cpu_result = await self.query(cpu_query)
        memory_result = await self.query(memory_query)
        
        return {
            "cpu": cpu_result,
            "memory": memory_result
        }
    
    async def get_cluster_overcommit(self) -> Dict[str, Any]:
        """Verificar overcommit no cluster"""
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
        """Obter uso de recursos por nó"""
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
        """Fechar sessão HTTP"""
        if self.session:
            await self.session.close()
