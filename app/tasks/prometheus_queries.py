"""
Celery tasks for Prometheus queries.
"""
from celery import current_task
from app.celery_app import celery_app
from app.core.prometheus_client import PrometheusClient
from app.services.historical_analysis import HistoricalAnalysisService
import logging

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, name='app.tasks.prometheus_queries.query_historical_data')
def query_historical_data(self, namespace, workload, time_range='24h'):
    """
    Query historical data for a specific workload.
    
    Args:
        namespace: Namespace name
        workload: Workload name
        time_range: Time range for analysis
        
    Returns:
        dict: Historical analysis results
    """
    try:
        # Update task state
        self.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': 4, 'status': f'Starting historical analysis for {namespace}/{workload}...'}
        )
        
        prometheus_client = PrometheusClient()
        historical_service = HistoricalAnalysisService()
        
        # Step 1: Query CPU metrics
        self.update_state(
            state='PROGRESS',
            meta={'current': 1, 'total': 4, 'status': f'Querying CPU metrics for {namespace}/{workload}...'}
        )
        
        cpu_data = historical_service.get_workload_cpu_metrics(namespace, workload, time_range)
        
        # Step 2: Query Memory metrics
        self.update_state(
            state='PROGRESS',
            meta={'current': 2, 'total': 4, 'status': f'Querying Memory metrics for {namespace}/{workload}...'}
        )
        
        memory_data = historical_service.get_workload_memory_metrics(namespace, workload, time_range)
        
        # Step 3: Analyze patterns
        self.update_state(
            state='PROGRESS',
            meta={'current': 3, 'total': 4, 'status': f'Analyzing usage patterns for {namespace}/{workload}...'}
        )
        
        analysis = historical_service.analyze_workload_patterns(cpu_data, memory_data)
        
        # Step 4: Generate recommendations
        self.update_state(
            state='PROGRESS',
            meta={'current': 4, 'total': 4, 'status': f'Generating recommendations for {namespace}/{workload}...'}
        )
        
        recommendations = historical_service.generate_recommendations(analysis)
        
        results = {
            'namespace': namespace,
            'workload': workload,
            'time_range': time_range,
            'cpu_data': cpu_data,
            'memory_data': memory_data,
            'analysis': analysis,
            'recommendations': recommendations
        }
        
        logger.info(f"Historical analysis completed for {namespace}/{workload}")
        
        return results
        
    except Exception as exc:
        logger.error(f"Historical analysis failed for {namespace}/{workload}: {str(exc)}")
        self.update_state(
            state='FAILURE',
            meta={'error': str(exc), 'status': f'Historical analysis failed for {namespace}/{workload}'}
        )
        raise exc

@celery_app.task(bind=True, name='app.tasks.prometheus_queries.query_cluster_metrics')
def query_cluster_metrics(self):
    """
    Query cluster-wide metrics from Prometheus.
    
    Returns:
        dict: Cluster metrics
    """
    try:
        self.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': 3, 'status': 'Querying cluster metrics...'}
        )
        
        prometheus_client = PrometheusClient()
        
        # Step 1: Query CPU metrics
        self.update_state(
            state='PROGRESS',
            meta={'current': 1, 'total': 3, 'status': 'Querying CPU cluster metrics...'}
        )
        
        cpu_metrics = prometheus_client.query_cluster_cpu_metrics()
        
        # Step 2: Query Memory metrics
        self.update_state(
            state='PROGRESS',
            meta={'current': 2, 'total': 3, 'status': 'Querying Memory cluster metrics...'}
        )
        
        memory_metrics = prometheus_client.query_cluster_memory_metrics()
        
        # Step 3: Query overcommit data
        self.update_state(
            state='PROGRESS',
            meta={'current': 3, 'total': 3, 'status': 'Querying overcommit metrics...'}
        )
        
        overcommit_data = prometheus_client.get_cluster_overcommit()
        
        results = {
            'cpu_metrics': cpu_metrics,
            'memory_metrics': memory_metrics,
            'overcommit': overcommit_data,
            'timestamp': '2024-01-04T10:00:00Z'
        }
        
        logger.info("Cluster metrics query completed successfully")
        
        return results
        
    except Exception as exc:
        logger.error(f"Cluster metrics query failed: {str(exc)}")
        self.update_state(
            state='FAILURE',
            meta={'error': str(exc), 'status': 'Cluster metrics query failed'}
        )
        raise exc

@celery_app.task(bind=True, name='app.tasks.prometheus_queries.batch_query_workloads')
def batch_query_workloads(self, workloads):
    """
    Batch query multiple workloads for efficiency.
    
    Args:
        workloads: List of workload dicts with namespace and workload name
        
    Returns:
        dict: Batch query results
    """
    try:
        total_workloads = len(workloads)
        
        self.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': total_workloads, 'status': f'Starting batch query for {total_workloads} workloads...'}
        )
        
        prometheus_client = PrometheusClient()
        historical_service = HistoricalAnalysisService()
        
        results = []
        
        for i, workload in enumerate(workloads):
            namespace = workload['namespace']
            workload_name = workload['workload']
            
            self.update_state(
                state='PROGRESS',
                meta={'current': i + 1, 'total': total_workloads, 'status': f'Querying {namespace}/{workload_name}...'}
            )
            
            try:
                # Query workload metrics
                cpu_data = historical_service.get_workload_cpu_metrics(namespace, workload_name, '24h')
                memory_data = historical_service.get_workload_memory_metrics(namespace, workload_name, '24h')
                
                results.append({
                    'namespace': namespace,
                    'workload': workload_name,
                    'cpu_data': cpu_data,
                    'memory_data': memory_data,
                    'status': 'success'
                })
                
            except Exception as exc:
                logger.warning(f"Failed to query {namespace}/{workload_name}: {str(exc)}")
                results.append({
                    'namespace': namespace,
                    'workload': workload_name,
                    'error': str(exc),
                    'status': 'failed'
                })
        
        logger.info(f"Batch query completed for {total_workloads} workloads")
        
        return {
            'total_workloads': total_workloads,
            'successful': len([r for r in results if r['status'] == 'success']),
            'failed': len([r for r in results if r['status'] == 'failed']),
            'results': results
        }
        
    except Exception as exc:
        logger.error(f"Batch query failed: {str(exc)}")
        self.update_state(
            state='FAILURE',
            meta={'error': str(exc), 'status': 'Batch query failed'}
        )
        raise exc
