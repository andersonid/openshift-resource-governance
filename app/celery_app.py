"""
Celery configuration for background task processing.
"""
from celery import Celery
import os

# Redis configuration
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# Create Celery instance
celery_app = Celery(
    'oru_analyzer',
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        'app.tasks.cluster_analysis',
        'app.tasks.prometheus_queries',
        'app.tasks.recommendations'
    ]
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Task routing
    task_routes={
        'app.tasks.cluster_analysis.*': {'queue': 'cluster_analysis'},
        'app.tasks.prometheus_queries.*': {'queue': 'prometheus'},
        'app.tasks.recommendations.*': {'queue': 'recommendations'},
    },
    
    # Task execution
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    
    # Result settings
    result_expires=3600,  # 1 hour
    result_persistent=True,
    
    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,
    
    # Retry settings
    task_default_retry_delay=60,  # 1 minute
    task_max_retries=3,
    
    # Task time limits
    task_soft_time_limit=300,  # 5 minutes
    task_time_limit=600,       # 10 minutes
)

# Optional: Configure periodic tasks
celery_app.conf.beat_schedule = {
    'health-check': {
        'task': 'app.tasks.cluster_analysis.health_check',
        'schedule': 60.0,  # Every minute
    },
}

if __name__ == '__main__':
    celery_app.start()
