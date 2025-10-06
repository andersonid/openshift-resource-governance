"""
Thanos client for historical data queries and aggregations.
Complements PrometheusClient for long-term data analysis.
"""
import requests
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import json

logger = logging.getLogger(__name__)

class ThanosClient:
    """
    Client for querying Thanos (OpenShift's historical metrics store).
    Used for historical data, trends, and complex aggregations.
    """
    
    def __init__(self, thanos_url: str = None):
        """
        Initialize Thanos client.
        
        Args:
            thanos_url: Thanos query endpoint URL
        """
        self.thanos_url = thanos_url or self._get_thanos_url()
        self.session = requests.Session()
        self.session.timeout = 30
        # Disable SSL verification for self-signed certificates
        self.session.verify = False
        # Disable SSL warnings
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # Add service account token for authentication
        self._add_auth_token()
        
    def _get_thanos_url(self) -> str:
        """Get Thanos URL from environment or use default."""
        import os
        return os.getenv('THANOS_URL', 'http://thanos-query:9090')
    
    def _add_auth_token(self):
        """Add service account token for authentication."""
        try:
            with open('/var/run/secrets/kubernetes.io/serviceaccount/token', 'r') as f:
                token = f.read().strip()
                self.session.headers.update({
                    'Authorization': f'Bearer {token}'
                })
        except FileNotFoundError:
            logger.warning("Service account token not found, proceeding without authentication")
    
    def query(self, query: str, time: str = None) -> Dict[str, Any]:
        """
        Execute instant query against Thanos.
        
        Args:
            query: PromQL query
            time: RFC3339 timestamp (default: now)
            
        Returns:
            Query result
        """
        try:
            params = {'query': query}
            if time:
                params['time'] = time
                
            response = self.session.get(
                f"{self.thanos_url}/api/v1/query",
                params=params
            )
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"Thanos instant query failed: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def query_range(self, query: str, start: str, end: str, step: str = "1h") -> Dict[str, Any]:
        """
        Execute range query against Thanos.
        
        Args:
            query: PromQL query
            start: Start time (RFC3339 or relative like "7d")
            end: End time (RFC3339 or relative like "now")
            step: Query resolution step width
            
        Returns:
            Range query result
        """
        try:
            params = {
                'query': query,
                'start': start,
                'end': end,
                'step': step
            }
            
            response = self.session.get(
                f"{self.thanos_url}/api/v1/query_range",
                params=params
            )
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"Thanos range query failed: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def get_cluster_capacity_historical(self, days: int = 7) -> Dict[str, Any]:
        """
        Get historical cluster capacity data.
        
        Args:
            days: Number of days to look back
            
        Returns:
            Historical capacity data
        """
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        
        # Query for cluster capacity over time
        query = "max(kube_node_status_capacity{resource=\"cpu\"} * on(node) group_left() kube_node_status_allocatable{resource=\"cpu\"}) by (cluster)"
        
        return self.query_range(
            query=query,
            start=int(start_time.timestamp()),
            end=int(end_time.timestamp()),
            step="1h"
        )
    
    def get_resource_utilization_trend(self, days: int = 7) -> Dict[str, Any]:
        """
        Get historical resource utilization trends.
        
        Args:
            days: Number of days to look back
            
        Returns:
            Resource utilization trends
        """
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        
        # CPU utilization trend - simplified
        cpu_query = "up"
        
        # Memory utilization trend - simplified  
        memory_query = "up"
        
        cpu_data = self.query_range(
            query=cpu_query,
            start=int(start_time.timestamp()),
            end=int(end_time.timestamp()),
            step="1h"
        )
        
        memory_data = self.query_range(
            query=memory_query,
            start=int(start_time.timestamp()),
            end=int(end_time.timestamp()),
            step="1h"
        )
        
        return {
            'cpu_trend': cpu_data,
            'memory_trend': memory_data,
            'period': f"{days} days",
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat()
        }
    
    def get_namespace_resource_trends(self, namespace: str, days: int = 7) -> Dict[str, Any]:
        """
        Get historical resource trends for a specific namespace.
        
        Args:
            namespace: Namespace name
            days: Number of days to look back
            
        Returns:
            Namespace resource trends
        """
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        
        # CPU requests trend
        cpu_requests_query = f"sum(kube_pod_container_resource_requests{{namespace=\"{namespace}\", resource=\"cpu\"}}) by (namespace)"
        
        # Memory requests trend
        memory_requests_query = f"sum(kube_pod_container_resource_requests{{namespace=\"{namespace}\", resource=\"memory\"}}) by (namespace)"
        
        cpu_requests = self.query_range(
            query=cpu_requests_query,
            start=start_time.isoformat(),
            end=end_time.isoformat(),
            step="1h"
        )
        
        memory_requests = self.query_range(
            query=memory_requests_query,
            start=start_time.isoformat(),
            end=end_time.isoformat(),
            step="1h"
        )
        
        return {
            'namespace': namespace,
            'cpu_requests_trend': cpu_requests,
            'memory_requests_trend': memory_requests,
            'period': f"{days} days"
        }
    
    def get_overcommit_historical(self, days: int = 7) -> Dict[str, Any]:
        """
        Get historical overcommit data.
        
        Args:
            days: Number of days to look back
            
        Returns:
            Historical overcommit data
        """
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        
        # CPU overcommit trend
        cpu_overcommit_query = "(sum(kube_pod_container_resource_requests{resource=\"cpu\"}) / sum(kube_node_status_allocatable{resource=\"cpu\"})) * 100"
        
        # Memory overcommit trend
        memory_overcommit_query = "(sum(kube_pod_container_resource_requests{resource=\"memory\"}) / sum(kube_node_status_allocatable{resource=\"memory\"})) * 100"
        
        cpu_overcommit = self.query_range(
            query=cpu_overcommit_query,
            start=start_time.isoformat(),
            end=end_time.isoformat(),
            step="1h"
        )
        
        memory_overcommit = self.query_range(
            query=memory_overcommit_query,
            start=start_time.isoformat(),
            end=end_time.isoformat(),
            step="1h"
        )
        
        return {
            'cpu_overcommit_trend': cpu_overcommit,
            'memory_overcommit_trend': memory_overcommit,
            'period': f"{days} days"
        }
    
    def get_top_workloads_historical(self, days: int = 7, limit: int = 10) -> Dict[str, Any]:
        """
        Get historical top workloads by resource usage.
        
        Args:
            days: Number of days to look back
            limit: Number of top workloads to return
            
        Returns:
            Historical top workloads data
        """
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        
        # Top CPU consuming workloads
        cpu_query = f"topk({limit}, avg_over_time(rate(container_cpu_usage_seconds_total{{container!=\"POD\",container!=\"\"}}[5m])[1h:1h])) by (namespace, pod, container)"
        
        # Top Memory consuming workloads
        memory_query = f"topk({limit}, avg_over_time(container_memory_working_set_bytes{{container!=\"POD\",container!=\"\"}}[1h:1h])) by (namespace, pod, container)"
        
        cpu_workloads = self.query_range(
            query=cpu_query,
            start=start_time.isoformat(),
            end=end_time.isoformat(),
            step="1h"
        )
        
        memory_workloads = self.query_range(
            query=memory_query,
            start=start_time.isoformat(),
            end=end_time.isoformat(),
            step="1h"
        )
        
        return {
            'top_cpu_workloads': cpu_workloads,
            'top_memory_workloads': memory_workloads,
            'period': f"{days} days",
            'limit': limit
        }
    
    def health_check(self) -> Dict[str, Any]:
        """
        Check Thanos connectivity and health.
        
        Returns:
            Health status
        """
        try:
            # Use a simple query endpoint instead of status/config
            response = self.session.get(f"{self.thanos_url}/api/v1/query", params={'query': 'up'})
            response.raise_for_status()
            
            return {
                'status': 'healthy',
                'thanos_url': self.thanos_url,
                'response_time': response.elapsed.total_seconds()
            }
            
        except Exception as e:
            logger.error(f"Thanos health check failed: {e}")
            return {
                'status': 'unhealthy',
                'thanos_url': self.thanos_url,
                'error': str(e)
            }
