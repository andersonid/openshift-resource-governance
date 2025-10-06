"""
Celery tasks for cluster analysis.
"""
from celery import current_task
from app.celery_app import celery_app
from app.core.kubernetes_client import K8sClient
from app.core.prometheus_client import PrometheusClient
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
            meta={'current': 0, 'total': 5, 'status': 'Starting cluster analysis...'}
        )
        
        # Step 1: Initialize clients
        self.update_state(
            state='PROGRESS',
            meta={'current': 1, 'total': 5, 'status': 'Connecting to Kubernetes API...'}
        )
        
        k8s_client = K8sClient()
        prometheus_client = PrometheusClient()
        validation_service = ValidationService()
        
        # Step 2: Discover cluster resources
        self.update_state(
            state='PROGRESS',
            meta={'current': 2, 'total': 5, 'status': 'Discovering cluster resources...'}
        )
        
        # Get cluster resources
        namespaces = k8s_client.get_namespaces()
        pods = k8s_client.get_pods()
        nodes = k8s_client.get_nodes()
        
        logger.info(f"Discovered {len(namespaces)} namespaces, {len(pods)} pods, {len(nodes)} nodes")
        
        # Step 3: Analyze resource configurations
        self.update_state(
            state='PROGRESS',
            meta={'current': 3, 'total': 5, 'status': 'Analyzing resource configurations...'}
        )
        
        # Validate resource configurations
        validations = validation_service.validate_cluster_resources(pods)
        
        # Step 4: Query Prometheus metrics
        self.update_state(
            state='PROGRESS',
            meta={'current': 4, 'total': 5, 'status': 'Querying Prometheus metrics...'}
        )
        
        # Get cluster overcommit data
        overcommit_data = prometheus_client.get_cluster_overcommit()
        
        # Step 5: Generate recommendations
        self.update_state(
            state='PROGRESS',
            meta={'current': 5, 'total': 5, 'status': 'Generating recommendations...'}
        )
        
        # Prepare results
        results = {
            'cluster_info': {
                'total_namespaces': len(namespaces),
                'total_pods': len(pods),
                'total_nodes': len(nodes),
            },
            'validations': validations,
            'overcommit': overcommit_data,
            'summary': {
                'total_errors': len([v for v in validations if v.get('severity') == 'error']),
                'total_warnings': len([v for v in validations if v.get('severity') == 'warning']),
                'total_info': len([v for v in validations if v.get('severity') == 'info']),
            }
        }
        
        logger.info(f"Cluster analysis completed successfully. Found {results['summary']['total_errors']} errors, {results['summary']['total_warnings']} warnings")
        
        return results
        
    except Exception as exc:
        logger.error(f"Cluster analysis failed: {str(exc)}")
        self.update_state(
            state='FAILURE',
            meta={'error': str(exc), 'status': 'Analysis failed', 'exception_type': type(exc).__name__}
        )
        raise exc

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
