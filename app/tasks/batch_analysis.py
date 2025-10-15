"""
Celery tasks for batch processing of large clusters
"""

import asyncio
import logging
from typing import Dict, Any, List
from datetime import datetime
import os

from app.celery_app import celery_app
from app.services.batch_processing import batch_processing_service, BatchProgress
from app.core.kubernetes_client import K8sClient

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, name='app.tasks.batch_analysis.process_cluster_batch')
def process_cluster_batch(self, cluster_config: Dict[str, Any] = None):
    """
    Process cluster analysis in batches for large clusters
    
    Args:
        cluster_config: Cluster configuration dict
        
    Returns:
        dict: Batch processing results
    """
    try:
        # Update task state
        self.update_state(
            state='PROGRESS',
            meta={
                'current': 0, 
                'total': 1, 
                'status': 'Starting batch processing...',
                'batch_number': 0,
                'total_batches': 0,
                'pods_processed': 0,
                'total_pods': 0
            }
        )
        
        # Initialize clients
        k8s_client = K8sClient()
        
        # Run async processing
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(_process_cluster_async(self, k8s_client, cluster_config))
            return result
        finally:
            loop.close()
            
    except Exception as exc:
        logger.error(f"Batch processing failed: {str(exc)}", exc_info=True)
        return {
            'error': str(exc),
            'status': 'failed',
            'timestamp': datetime.now().isoformat()
        }

async def _process_cluster_async(task, k8s_client: K8sClient, cluster_config: Dict[str, Any]):
    """Async processing function"""
    try:
        # Initialize K8s client
        await k8s_client.initialize()
        
        # Get batch statistics
        batch_stats = await batch_processing_service.get_batch_statistics(k8s_client)
        
        # Update task with statistics
        task.update_state(
            state='PROGRESS',
            meta={
                'current': 1,
                'total': batch_stats.get('total_batches', 1),
                'status': f"Processing {batch_stats.get('total_pods', 0)} pods in {batch_stats.get('total_batches', 0)} batches...",
                'batch_number': 0,
                'total_batches': batch_stats.get('total_batches', 0),
                'pods_processed': 0,
                'total_pods': batch_stats.get('total_pods', 0),
                'statistics': batch_stats
            }
        )
        
        # Process in batches
        all_validations = []
        all_recommendations = []
        total_errors = []
        total_processing_time = 0
        
        batch_count = 0
        
        async for batch_result in batch_processing_service.process_cluster_in_batches(
            k8s_client,
            namespace=cluster_config.get('namespace') if cluster_config else None,
            include_system_namespaces=cluster_config.get('include_system_namespaces', False) if cluster_config else False,
            progress_callback=lambda progress: _update_task_progress(task, progress)
        ):
            batch_count += 1
            
            # Collect results
            all_validations.extend(batch_result.validations)
            all_recommendations.extend(batch_result.recommendations)
            total_errors.extend(batch_result.errors)
            total_processing_time += batch_result.processing_time
            
            # Update task progress
            task.update_state(
                state='PROGRESS',
                meta={
                    'current': batch_count,
                    'total': batch_result.total_batches,
                    'status': f"Completed batch {batch_count}/{batch_result.total_batches} - {len(all_validations)} validations found",
                    'batch_number': batch_count,
                    'total_batches': batch_result.total_batches,
                    'pods_processed': batch_count * batch_processing_service.batch_size,
                    'total_pods': batch_stats.get('total_pods', 0),
                    'validations_found': len(all_validations),
                    'recommendations_generated': len(all_recommendations),
                    'processing_time': total_processing_time,
                    'memory_usage': batch_result.memory_usage,
                    'errors': len(total_errors)
                }
            )
        
        # Final results
        results = {
            'timestamp': datetime.now().isoformat(),
            'total_pods': batch_stats.get('total_pods', 0),
            'total_batches': batch_count,
            'batch_size': batch_processing_service.batch_size,
            'total_validations': len(all_validations),
            'total_recommendations': len(all_recommendations),
            'total_errors': len(total_errors),
            'processing_time': total_processing_time,
            'statistics': batch_stats,
            'validations': all_validations,
            'recommendations': all_recommendations,
            'errors': total_errors,
            'status': 'completed'
        }
        
        logger.info(f"Batch processing completed: {len(all_validations)} validations, {len(all_recommendations)} recommendations in {total_processing_time:.2f}s")
        
        return results
        
    except Exception as e:
        logger.error(f"Error in async batch processing: {e}", exc_info=True)
        raise

def _update_task_progress(task, progress: BatchProgress):
    """Update Celery task progress"""
    try:
        task.update_state(
            state='PROGRESS',
            meta={
                'current': progress.current_batch,
                'total': progress.total_batches,
                'status': f"Processing batch {progress.current_batch}/{progress.total_batches} - {progress.pods_processed}/{progress.total_pods} pods",
                'batch_number': progress.current_batch,
                'total_batches': progress.total_batches,
                'pods_processed': progress.pods_processed,
                'total_pods': progress.total_pods,
                'validations_found': progress.validations_found,
                'recommendations_generated': progress.recommendations_generated,
                'processing_time': progress.processing_time,
                'estimated_completion': progress.estimated_completion.isoformat() if progress.estimated_completion else None
            }
        )
    except Exception as e:
        logger.warning(f"Error updating task progress: {e}")

@celery_app.task(bind=True, name='app.tasks.batch_analysis.get_batch_statistics')
def get_batch_statistics(self, cluster_config: Dict[str, Any] = None):
    """
    Get batch processing statistics for the cluster
    
    Args:
        cluster_config: Cluster configuration dict
        
    Returns:
        dict: Batch statistics
    """
    try:
        # Initialize clients
        k8s_client = K8sClient()
        
        # Run async processing
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(_get_statistics_async(k8s_client, cluster_config))
            return result
        finally:
            loop.close()
            
    except Exception as exc:
        logger.error(f"Error getting batch statistics: {str(exc)}", exc_info=True)
        return {
            'error': str(exc),
            'status': 'failed',
            'timestamp': datetime.now().isoformat()
        }

async def _get_statistics_async(k8s_client: K8sClient, cluster_config: Dict[str, Any]):
    """Async function to get batch statistics"""
    try:
        # Initialize K8s client
        await k8s_client.initialize()
        
        # Get batch statistics
        batch_stats = await batch_processing_service.get_batch_statistics(k8s_client)
        
        return {
            'timestamp': datetime.now().isoformat(),
            'statistics': batch_stats,
            'status': 'completed'
        }
        
    except Exception as e:
        logger.error(f"Error in async statistics: {e}", exc_info=True)
        raise
