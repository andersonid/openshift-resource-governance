#!/usr/bin/env python3
"""
Celery beat scheduler startup script.
"""
import os
import sys
from celery import Celery

# Add the app directory to Python path
sys.path.insert(0, '/app')

from app.celery_app import celery_app

if __name__ == '__main__':
    # Start Celery beat scheduler
    celery_app.start([
        'beat',
        '--loglevel=info',
        '--scheduler=celery.beat:PersistentScheduler'
    ])
