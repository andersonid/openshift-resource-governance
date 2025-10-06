"""
Celery tasks for cluster analysis.
"""
from celery import current_task
from app.celery_app import celery_app
from app.core.kubernetes_client import K8sClient
from app.core.prometheus_client import PrometheusClient
from app.core.thanos_client import ThanosClient
from app.services.validation_service import ValidationService
import logging

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, name='app.tasks.cluster_analysis.analyze_cluster')
async def analyze_cluster(self, cluster_config=None):
    """
    Analyze cluster resources and generate recommendations.
    
    Args:
        cluster_config: Cluster configuration dict
        
    Returns:
        dict: Analysis results
    """
    try:
        # Update task state
        self.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': 5, 'status': 'Starting cluster analysis...'}
        )
        
        # Step 1: Initialize clients
        self.update_state(
            state='PROGRESS',
            meta={'current': 1, 'total': 5, 'status': 'Initializing Kubernetes client...'}
        )
        
        k8s_client = K8sClient()
        logger.info("Starting real cluster analysis")
        
        # Step 2: Get cluster info
        self.update_state(
            state='PROGRESS',
            meta={'current': 2, 'total': 5, 'status': 'Analyzing cluster resources...'}
        )
        
        # Get real cluster data
        await k8s_client.initialize()
        pods = await k8s_client.get_all_pods()
        
        # Step 3: Analyze workloads
        self.update_state(
            state='PROGRESS',
            meta={'current': 3, 'total': 5, 'status': 'Analyzing workloads...'}
        )
        
        # Count workloads by type and namespaces
        workload_counts = {}
        namespace_counts = {}
        for pod in pods:
            # Count by workload type
            workload_type = pod.labels.get('app.kubernetes.io/name', 'unknown')
            workload_counts[workload_type] = workload_counts.get(workload_type, 0) + 1
            
            # Count by namespace
            namespace = pod.namespace
            namespace_counts[namespace] = namespace_counts.get(namespace, 0) + 1
        
        # Step 4: Get resource utilization
        self.update_state(
            state='PROGRESS',
            meta={'current': 4, 'total': 5, 'status': 'Calculating resource utilization...'}
        )
        
        # Calculate resource requests and limits
        total_cpu_requests = 0
        total_memory_requests = 0
        total_cpu_limits = 0
        total_memory_limits = 0
        
        for pod in pods:
            for container in pod.spec.containers:
                if container.resources and container.resources.requests:
                    if 'cpu' in container.resources.requests:
                        total_cpu_requests += _parse_cpu_value(container.resources.requests['cpu'])
                    if 'memory' in container.resources.requests:
                        total_memory_requests += _parse_memory_value(container.resources.requests['memory'])
                
                if container.resources and container.resources.limits:
                    if 'cpu' in container.resources.limits:
                        total_cpu_limits += _parse_cpu_value(container.resources.limits['cpu'])
                    if 'memory' in container.resources.limits:
                        total_memory_limits += _parse_memory_value(container.resources.limits['memory'])
        
        # Step 5: Generate results
        self.update_state(
            state='PROGRESS',
            meta={'current': 5, 'total': 5, 'status': 'Generating analysis results...'}
        )
        
        # Real analysis results
        results = {
            'cluster_info': {
                'total_namespaces': len(namespace_counts),
                'total_pods': len(pods),
                'total_nodes': 0,  # Will be added later
                'workload_types': len(workload_counts)
            },
            'resource_summary': {
                'cpu_requests': total_cpu_requests,
                'memory_requests': total_memory_requests,
                'cpu_limits': total_cpu_limits,
                'memory_limits': total_memory_limits
            },
            'workload_breakdown': workload_counts,
            'namespace_breakdown': namespace_counts,
            'summary': {
                'total_errors': 0,  # Will be calculated by validation service
                'total_warnings': 0,  # Will be calculated by validation service
                'total_info': len(pods),
            },
            'status': 'completed'
        }
        
        logger.info(f"Real cluster analysis completed successfully. Found {len(namespace_counts)} namespaces, {len(pods)} pods")
        
        return results
        
    except Exception as exc:
        logger.error(f"Cluster analysis failed: {str(exc)}", exc_info=True)
        # Return error instead of raising to avoid Celery backend issues
        return {
            'error': str(exc),
            'status': 'failed',
            'cluster_info': {'total_namespaces': 0, 'total_pods': 0, 'total_nodes': 0},
            'summary': {'total_errors': 0, 'total_warnings': 0, 'total_info': 0}
        }

def _parse_cpu_value(cpu_str):
    """Parse CPU value from string to float (cores)"""
    if cpu_str.endswith('m'):
        return float(cpu_str[:-1]) / 1000
    elif cpu_str.endswith('n'):
        return float(cpu_str[:-1]) / 1000000000
    else:
        return float(cpu_str)

def _parse_memory_value(memory_str):
    """Parse memory value from string to float (bytes)"""
    if memory_str.endswith('Ki'):
        return float(memory_str[:-2]) * 1024
    elif memory_str.endswith('Mi'):
        return float(memory_str[:-2]) * 1024 * 1024
    elif memory_str.endswith('Gi'):
        return float(memory_str[:-2]) * 1024 * 1024 * 1024
    elif memory_str.endswith('K'):
        return float(memory_str[:-1]) * 1000
    elif memory_str.endswith('M'):
        return float(memory_str[:-1]) * 1000 * 1000
    elif memory_str.endswith('G'):
        return float(memory_str[:-1]) * 1000 * 1000 * 1000
    else:
        return float(memory_str)

@celery_app.task(name='app.tasks.cluster_analysis.health_check')
def health_check():
    """
    Health check task for monitoring.
    
    Returns:
        dict: Health status
    """
    try:
        k8s_client = K8sClient()
        # Simple health check - try to get namespaces
        namespaces = k8s_client.get_namespaces()
        
        return {
            'status': 'healthy',
            'namespaces_count': len(namespaces),
            'timestamp': '2024-01-04T10:00:00Z'
        }
    except Exception as exc:
        logger.error(f"Health check failed: {str(exc)}")
        return {
            'status': 'unhealthy',
            'error': str(exc),
            'timestamp': '2024-01-04T10:00:00Z'
        }

@celery_app.task(bind=True, name='app.tasks.cluster_analysis.analyze_namespace')
def analyze_namespace(self, namespace):
    """
    Analyze specific namespace resources.
    
    Args:
        namespace: Namespace name
        
    Returns:
        dict: Namespace analysis results
    """
    try:
        self.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': 3, 'status': f'Analyzing namespace {namespace}...'}
        )
        
        k8s_client = K8sClient()
        validation_service = ValidationService()
        
        # Get namespace pods
        self.update_state(
            state='PROGRESS',
            meta={'current': 1, 'total': 3, 'status': f'Getting pods in namespace {namespace}...'}
        )
        
        pods = k8s_client.get_pods(namespace=namespace)
        
        # Validate resources
        self.update_state(
            state='PROGRESS',
            meta={'current': 2, 'total': 3, 'status': f'Validating resources in namespace {namespace}...'}
        )
        
        validations = validation_service.validate_cluster_resources(pods)
        
        # Prepare results
        results = {
            'namespace': namespace,
            'pods_count': len(pods),
            'validations': validations,
            'summary': {
                'total_errors': len([v for v in validations if v.get('severity') == 'error']),
                'total_warnings': len([v for v in validations if v.get('severity') == 'warning']),
            }
        }
        
        logger.info(f"Namespace {namespace} analysis completed. Found {results['summary']['total_errors']} errors, {results['summary']['total_warnings']} warnings")
        
        return results
        
    except Exception as exc:
        logger.error(f"Namespace {namespace} analysis failed: {str(exc)}")
        self.update_state(
            state='FAILURE',
            meta={'error': str(exc), 'status': f'Namespace {namespace} analysis failed', 'exception_type': type(exc).__name__}
        )
        raise exc
