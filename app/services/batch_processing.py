"""
Batch Processing Service for Large Clusters

This service implements intelligent batch processing to handle large clusters
efficiently by processing pods in batches of 100, reducing memory usage and
improving performance for clusters with 10,000+ pods.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, AsyncGenerator, Tuple
from dataclasses import dataclass
from datetime import datetime
import gc

from app.core.kubernetes_client import K8sClient, PodResource
from app.services.validation_service import ValidationService
from app.services.smart_recommendations import SmartRecommendationsService
from app.services.historical_analysis import HistoricalAnalysisService

logger = logging.getLogger(__name__)

@dataclass
class BatchResult:
    """Result of a batch processing operation"""
    batch_number: int
    total_batches: int
    pods_processed: int
    validations: List[Dict[str, Any]]
    recommendations: List[Dict[str, Any]]
    processing_time: float
    memory_usage: float
    errors: List[str]

@dataclass
class BatchProgress:
    """Progress tracking for batch processing"""
    current_batch: int
    total_batches: int
    pods_processed: int
    total_pods: int
    validations_found: int
    recommendations_generated: int
    processing_time: float
    estimated_completion: Optional[datetime]
    status: str  # 'running', 'completed', 'error', 'paused'

class BatchProcessingService:
    """Service for processing large clusters in batches"""
    
    def __init__(self, batch_size: int = 100):
        self.batch_size = batch_size
        self.validation_service = ValidationService()
        self.smart_recommendations_service = SmartRecommendationsService()
        self.historical_service = HistoricalAnalysisService()
        
    async def process_cluster_in_batches(
        self, 
        k8s_client: K8sClient,
        namespace: Optional[str] = None,
        include_system_namespaces: bool = False,
        progress_callback: Optional[callable] = None
    ) -> AsyncGenerator[BatchResult, None]:
        """
        Process cluster pods in batches with progress tracking
        
        Args:
            k8s_client: Kubernetes client instance
            namespace: Optional namespace filter
            include_system_namespaces: Whether to include system namespaces
            progress_callback: Optional callback for progress updates
            
        Yields:
            BatchResult: Results for each batch processed
        """
        try:
            # Get all pods
            if namespace:
                namespace_resources = await k8s_client.get_namespace_resources(namespace)
                all_pods = namespace_resources.pods
            else:
                all_pods = await k8s_client.get_all_pods(include_system_namespaces=include_system_namespaces)
            
            total_pods = len(all_pods)
            total_batches = (total_pods + self.batch_size - 1) // self.batch_size
            
            logger.info(f"Starting batch processing: {total_pods} pods in {total_batches} batches of {self.batch_size}")
            
            # Process pods in batches
            for batch_num in range(total_batches):
                start_idx = batch_num * self.batch_size
                end_idx = min(start_idx + self.batch_size, total_pods)
                batch_pods = all_pods[start_idx:end_idx]
                
                # Process this batch
                batch_result = await self._process_batch(
                    batch_num + 1, 
                    total_batches, 
                    batch_pods,
                    start_idx,
                    total_pods
                )
                
                # Update progress
                if progress_callback:
                    progress = BatchProgress(
                        current_batch=batch_num + 1,
                        total_batches=total_batches,
                        pods_processed=end_idx,
                        total_pods=total_pods,
                        validations_found=sum(len(r.validations) for r in batch_result),
                        recommendations_generated=sum(len(r.recommendations) for r in batch_result),
                        processing_time=batch_result.processing_time,
                        estimated_completion=None,  # Could calculate based on avg time
                        status='running'
                    )
                    progress_callback(progress)
                
                yield batch_result
                
                # Memory cleanup after each batch
                await self._cleanup_memory()
                
                # Small delay to prevent overwhelming the system
                await asyncio.sleep(0.1)
                
        except Exception as e:
            logger.error(f"Error in batch processing: {e}", exc_info=True)
            raise
    
    async def _process_batch(
        self, 
        batch_number: int, 
        total_batches: int, 
        pods: List[PodResource],
        start_idx: int,
        total_pods: int
    ) -> BatchResult:
        """Process a single batch of pods"""
        start_time = datetime.now()
        errors = []
        validations = []
        recommendations = []
        
        try:
            logger.info(f"Processing batch {batch_number}/{total_batches}: {len(pods)} pods")
            
            # Process validations for this batch
            for pod in pods:
                try:
                    pod_validations = self.validation_service.validate_pod_resources(pod)
                    for validation in pod_validations:
                        validations.append({
                            'pod_name': validation.pod_name,
                            'namespace': validation.namespace,
                            'container_name': validation.container_name,
                            'validation_type': validation.validation_type,
                            'severity': validation.severity,
                            'message': validation.message,
                            'recommendation': validation.recommendation,
                            'priority_score': validation.priority_score,
                            'workload_category': validation.workload_category,
                            'estimated_impact': validation.estimated_impact
                        })
                except Exception as e:
                    error_msg = f"Error validating pod {pod.name}: {str(e)}"
                    logger.warning(error_msg)
                    errors.append(error_msg)
            
            # Generate smart recommendations for this batch
            try:
                batch_recommendations = await self.smart_recommendations_service.generate_smart_recommendations(pods, [])
                for rec in batch_recommendations:
                    recommendations.append({
                        'workload_name': rec.workload_name,
                        'namespace': rec.namespace,
                        'recommendation_type': rec.recommendation_type,
                        'priority_score': rec.priority_score,
                        'title': rec.title,
                        'description': rec.description,
                        'estimated_impact': rec.estimated_impact,
                        'implementation_effort': rec.implementation_effort
                    })
            except Exception as e:
                error_msg = f"Error generating recommendations for batch {batch_number}: {str(e)}"
                logger.warning(error_msg)
                errors.append(error_msg)
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            return BatchResult(
                batch_number=batch_number,
                total_batches=total_batches,
                pods_processed=len(pods),
                validations=validations,
                recommendations=recommendations,
                processing_time=processing_time,
                memory_usage=self._get_memory_usage(),
                errors=errors
            )
            
        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            error_msg = f"Error processing batch {batch_number}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            return BatchResult(
                batch_number=batch_number,
                total_batches=total_batches,
                pods_processed=len(pods),
                validations=[],
                recommendations=[],
                processing_time=processing_time,
                memory_usage=self._get_memory_usage(),
                errors=[error_msg]
            )
    
    async def _cleanup_memory(self):
        """Clean up memory after each batch"""
        try:
            # Force garbage collection
            gc.collect()
            
            # Small delay to allow memory cleanup
            await asyncio.sleep(0.01)
            
        except Exception as e:
            logger.warning(f"Error during memory cleanup: {e}")
    
    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB"""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024  # Convert to MB
        except ImportError:
            return 0.0
        except Exception:
            return 0.0
    
    async def get_batch_statistics(self, k8s_client: K8sClient) -> Dict[str, Any]:
        """Get statistics about batch processing for the cluster"""
        try:
            all_pods = await k8s_client.get_all_pods(include_system_namespaces=False)
            total_pods = len(all_pods)
            total_batches = (total_pods + self.batch_size - 1) // self.batch_size
            
            # Group by namespace
            namespace_counts = {}
            for pod in all_pods:
                namespace_counts[pod.namespace] = namespace_counts.get(pod.namespace, 0) + 1
            
            return {
                'total_pods': total_pods,
                'total_namespaces': len(namespace_counts),
                'batch_size': self.batch_size,
                'total_batches': total_batches,
                'estimated_processing_time': total_batches * 2.0,  # 2 seconds per batch estimate
                'namespace_distribution': namespace_counts,
                'memory_efficiency': 'High' if total_batches > 10 else 'Standard',
                'recommended_batch_size': self._recommend_batch_size(total_pods)
            }
            
        except Exception as e:
            logger.error(f"Error getting batch statistics: {e}", exc_info=True)
            return {
                'error': str(e),
                'total_pods': 0,
                'total_batches': 0
            }
    
    def _recommend_batch_size(self, total_pods: int) -> int:
        """Recommend optimal batch size based on cluster size"""
        if total_pods < 1000:
            return 50
        elif total_pods < 5000:
            return 100
        elif total_pods < 10000:
            return 150
        else:
            return 200

# Global instance
batch_processing_service = BatchProcessingService()
