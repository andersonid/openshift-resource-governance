"""
Celery tasks for generating recommendations.
"""
from celery import current_task
from app.celery_app import celery_app
from app.services.validation_service import ValidationService
from app.services.historical_analysis import HistoricalAnalysisService
import logging

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, name='app.tasks.recommendations.generate_smart_recommendations')
def generate_smart_recommendations(self, cluster_data):
    """
    Generate smart recommendations based on cluster analysis.
    
    Args:
        cluster_data: Cluster analysis data
        
    Returns:
        dict: Smart recommendations
    """
    try:
        self.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': 4, 'status': 'Starting smart recommendations generation...'}
        )
        
        validation_service = ValidationService()
        historical_service = HistoricalAnalysisService()
        
        # Step 1: Analyze resource configurations
        self.update_state(
            state='PROGRESS',
            meta={'current': 1, 'total': 4, 'status': 'Analyzing resource configurations...'}
        )
        
        resource_recommendations = validation_service.generate_resource_recommendations(cluster_data.get('validations', []))
        
        # Step 2: Analyze historical patterns
        self.update_state(
            state='PROGRESS',
            meta={'current': 2, 'total': 4, 'status': 'Analyzing historical patterns...'}
        )
        
        historical_recommendations = historical_service.generate_historical_recommendations(cluster_data)
        
        # Step 3: Generate VPA recommendations
        self.update_state(
            state='PROGRESS',
            meta={'current': 3, 'total': 4, 'status': 'Generating VPA recommendations...'}
        )
        
        vpa_recommendations = validation_service.generate_vpa_recommendations(cluster_data)
        
        # Step 4: Prioritize recommendations
        self.update_state(
            state='PROGRESS',
            meta={'current': 4, 'total': 4, 'status': 'Prioritizing recommendations...'}
        )
        
        all_recommendations = resource_recommendations + historical_recommendations + vpa_recommendations
        
        # Sort by priority
        priority_order = {'critical': 1, 'high': 2, 'medium': 3, 'low': 4}
        all_recommendations.sort(key=lambda x: priority_order.get(x.get('priority', 'low'), 4))
        
        results = {
            'total_recommendations': len(all_recommendations),
            'by_priority': {
                'critical': len([r for r in all_recommendations if r.get('priority') == 'critical']),
                'high': len([r for r in all_recommendations if r.get('priority') == 'high']),
                'medium': len([r for r in all_recommendations if r.get('priority') == 'medium']),
                'low': len([r for r in all_recommendations if r.get('priority') == 'low']),
            },
            'recommendations': all_recommendations,
            'summary': {
                'resource_config': len(resource_recommendations),
                'historical_analysis': len(historical_recommendations),
                'vpa_activation': len(vpa_recommendations),
            }
        }
        
        logger.info(f"Generated {len(all_recommendations)} smart recommendations")
        
        return results
        
    except Exception as exc:
        logger.error(f"Smart recommendations generation failed: {str(exc)}")
        self.update_state(
            state='FAILURE',
            meta={'error': str(exc), 'status': 'Smart recommendations generation failed'}
        )
        raise exc

@celery_app.task(bind=True, name='app.tasks.recommendations.generate_namespace_recommendations')
def generate_namespace_recommendations(self, namespace, namespace_data):
    """
    Generate recommendations for a specific namespace.
    
    Args:
        namespace: Namespace name
        namespace_data: Namespace analysis data
        
    Returns:
        dict: Namespace recommendations
    """
    try:
        self.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': 3, 'status': f'Generating recommendations for namespace {namespace}...'}
        )
        
        validation_service = ValidationService()
        
        # Step 1: Analyze namespace validations
        self.update_state(
            state='PROGRESS',
            meta={'current': 1, 'total': 3, 'status': f'Analyzing validations for namespace {namespace}...'}
        )
        
        validations = namespace_data.get('validations', [])
        resource_recommendations = validation_service.generate_resource_recommendations(validations)
        
        # Step 2: Generate namespace-specific recommendations
        self.update_state(
            state='PROGRESS',
            meta={'current': 2, 'total': 3, 'status': f'Generating namespace-specific recommendations for {namespace}...'}
        )
        
        namespace_recommendations = validation_service.generate_namespace_recommendations(namespace, namespace_data)
        
        # Step 3: Prioritize and format recommendations
        self.update_state(
            state='PROGRESS',
            meta={'current': 3, 'total': 3, 'status': f'Prioritizing recommendations for namespace {namespace}...'}
        )
        
        all_recommendations = resource_recommendations + namespace_recommendations
        
        # Add namespace context to recommendations
        for rec in all_recommendations:
            rec['namespace'] = namespace
            rec['context'] = f"Namespace: {namespace}"
        
        results = {
            'namespace': namespace,
            'total_recommendations': len(all_recommendations),
            'recommendations': all_recommendations,
            'summary': {
                'errors': len([v for v in validations if v.get('severity') == 'error']),
                'warnings': len([v for v in validations if v.get('severity') == 'warning']),
                'pods_analyzed': namespace_data.get('pods_count', 0),
            }
        }
        
        logger.info(f"Generated {len(all_recommendations)} recommendations for namespace {namespace}")
        
        return results
        
    except Exception as exc:
        logger.error(f"Namespace recommendations generation failed for {namespace}: {str(exc)}")
        self.update_state(
            state='FAILURE',
            meta={'error': str(exc), 'status': f'Namespace recommendations generation failed for {namespace}'}
        )
        raise exc

@celery_app.task(bind=True, name='app.tasks.recommendations.generate_export_report')
def generate_export_report(self, cluster_data, format='json'):
    """
    Generate export report in specified format.
    
    Args:
        cluster_data: Cluster analysis data
        format: Export format (json, csv, pdf)
        
    Returns:
        dict: Export report data
    """
    try:
        self.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': 3, 'status': f'Generating {format.upper()} export report...'}
        )
        
        # Step 1: Prepare data
        self.update_state(
            state='PROGRESS',
            meta={'current': 1, 'total': 3, 'status': 'Preparing export data...'}
        )
        
        export_data = {
            'timestamp': '2024-01-04T10:00:00Z',
            'cluster_info': cluster_data.get('cluster_info', {}),
            'validations': cluster_data.get('validations', []),
            'overcommit': cluster_data.get('overcommit', {}),
            'summary': cluster_data.get('summary', {}),
        }
        
        # Step 2: Generate recommendations
        self.update_state(
            state='PROGRESS',
            meta={'current': 2, 'total': 3, 'status': 'Generating recommendations for export...'}
        )
        
        recommendations_task = generate_smart_recommendations.delay(cluster_data)
        recommendations = recommendations_task.get()
        
        export_data['recommendations'] = recommendations.get('recommendations', [])
        
        # Step 3: Format export
        self.update_state(
            state='PROGRESS',
            meta={'current': 3, 'total': 3, 'status': f'Formatting {format.upper()} export...'}
        )
        
        if format == 'csv':
            # Convert to CSV format
            csv_data = convert_to_csv(export_data)
            export_data['csv_data'] = csv_data
        elif format == 'pdf':
            # Convert to PDF format
            pdf_data = convert_to_pdf(export_data)
            export_data['pdf_data'] = pdf_data
        
        results = {
            'format': format,
            'data': export_data,
            'size': len(str(export_data)),
            'timestamp': '2024-01-04T10:00:00Z'
        }
        
        logger.info(f"Generated {format.upper()} export report successfully")
        
        return results
        
    except Exception as exc:
        logger.error(f"Export report generation failed: {str(exc)}")
        self.update_state(
            state='FAILURE',
            meta={'error': str(exc), 'status': f'Export report generation failed'}
        )
        raise exc

def convert_to_csv(data):
    """Convert data to CSV format."""
    # Simple CSV conversion - in real implementation, use pandas or csv module
    return "namespace,workload,severity,message,recommendation\n" + \
           "\n".join([f"{v.get('namespace', '')},{v.get('workload', '')},{v.get('severity', '')},{v.get('message', '')},{v.get('recommendation', '')}" 
                     for v in data.get('validations', [])])

def convert_to_pdf(data):
    """Convert data to PDF format."""
    # Simple PDF conversion - in real implementation, use reportlab
    return f"PDF Report for Cluster Analysis\n\n" + \
           f"Total Namespaces: {data.get('cluster_info', {}).get('total_namespaces', 0)}\n" + \
           f"Total Pods: {data.get('cluster_info', {}).get('total_pods', 0)}\n" + \
           f"Total Errors: {data.get('summary', {}).get('total_errors', 0)}\n" + \
           f"Total Warnings: {data.get('summary', {}).get('total_warnings', 0)}\n"
