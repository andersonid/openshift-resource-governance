#!/usr/bin/env python3
"""
Celery worker startup script.
"""
import os
import sys
from celery import Celery

# Add the app directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.celery_app import celery_app

if __name__ == '__main__':
    # Start Celery worker
    celery_app.worker_main([
        'worker',
        '--loglevel=info',
        '--concurrency=4',
        '--queues=cluster_analysis,prometheus,recommendations',
        '--hostname=worker@%h'
    ])
