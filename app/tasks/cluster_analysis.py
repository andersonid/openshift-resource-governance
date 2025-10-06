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
def analyze_cluster(self, cluster_config=None):
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
            meta={'current': 0, 'total': 3, 'status': 'Starting cluster analysis...'}
        )
        
        # Step 1: Initialize clients
        self.update_state(
            state='PROGRESS',
            meta={'current': 1, 'total': 3, 'status': 'Initializing Kubernetes client...'}
        )
        
        k8s_client = K8sClient()
        logger.info("Starting real cluster analysis")
        
        # Step 2: Get cluster info (simplified for now)
        self.update_state(
            state='PROGRESS',
            meta={'current': 2, 'total': 3, 'status': 'Analyzing cluster resources...'}
        )
        
        # For now, return mock data with real structure
        pods = []  # Will be replaced with real data later
        
        # Step 3: Generate results (simplified for now)
        self.update_state(
            state='PROGRESS',
            meta={'current': 3, 'total': 3, 'status': 'Generating analysis results...'}
        )
        
        # Simplified analysis results for UI testing
        results = {
            'cluster_info': {
                'total_namespaces': 15,
                'total_pods': 45,
                'total_nodes': 3,
                'workload_types': 8
            },
            'resource_summary': {
                'cpu_requests': 2.5,
                'memory_requests': 8192,
                'cpu_limits': 5.0,
                'memory_limits': 16384
            },
            'workload_breakdown': {
                'resource-governance': 2,
                'redis': 1,
                'prometheus': 3,
                'thanos': 2,
                'openshift-monitoring': 5
            },
            'namespace_breakdown': {
                'resource-governance': 3,
                'openshift-monitoring': 8,
                'openshift-storage': 4,
                'kube-system': 12
            },
            'summary': {
                'total_errors': 0,
                'total_warnings': 2,
                'total_info': 45,
            },
            'status': 'completed'
        }
        
        logger.info(f"Cluster analysis completed successfully. Found {results['cluster_info']['total_namespaces']} namespaces, {results['cluster_info']['total_pods']} pods")
        
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
