#!/usr/bin/env python3
"""
Celery worker startup script.
"""
import os
import sys
from celery import Celery

# Add the app directory to Python path
sys.path.insert(0, '/app')

from app.celery_app import celery_app

# Import tasks to register them
from app.tasks.cluster_analysis import analyze_cluster
from app.tasks.batch_analysis import process_cluster_batch, get_batch_statistics

if __name__ == '__main__':
    # Start Celery worker
    celery_app.worker_main([
        'worker',
        '--loglevel=info',
        '--concurrency=4',
        '--queues=cluster_analysis,prometheus,recommendations',
        '--hostname=worker@%h'
    ])
