#!/usr/bin/env python3
"""
Webhook for automatic deployment after GitHub Actions
This script can be run as a service to detect changes on Docker Hub
"""

import os
import json
import subprocess
import logging
from flask import Flask, request, jsonify
from datetime import datetime

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
IMAGE_NAME = os.getenv('IMAGE_NAME', 'resource-governance')
REGISTRY = os.getenv('REGISTRY', 'andersonid')
NAMESPACE = os.getenv('NAMESPACE', 'resource-governance')
SCRIPT_PATH = os.getenv('AUTO_DEPLOY_SCRIPT', './scripts/auto-deploy.sh')

@app.route('/webhook/dockerhub', methods=['POST'])
def dockerhub_webhook():
    """Webhook to receive Docker Hub notifications"""
    try:
        data = request.get_json()
        
        # Check if it's a push notification
        if data.get('push_data', {}).get('tag') == 'latest':
            logger.info(f"Received push notification for {REGISTRY}/{IMAGE_NAME}:latest")
            
            # Execute automatic deployment
            result = run_auto_deploy('latest')
            
            return jsonify({
                'status': 'success',
                'message': 'Automatic deployment started',
                'result': result
            }), 200
        else:
            logger.info(f"Push ignored - tag: {data.get('push_data', {}).get('tag')}")
            return jsonify({'status': 'ignored', 'message': 'Tag is not latest'}), 200
            
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/webhook/github', methods=['POST'])
def github_webhook():
    """Webhook to receive GitHub notifications"""
    try:
        # Check if it's a push to main
        if request.headers.get('X-GitHub-Event') == 'push':
            data = request.get_json()
            
            if data.get('ref') == 'refs/heads/main':
                logger.info("Received push notification for main branch")
                
                # Execute automatic deployment
                result = run_auto_deploy('latest')
                
                return jsonify({
                    'status': 'success',
                    'message': 'Automatic deployment started',
                    'result': result
                }), 200
            else:
                logger.info(f"Push ignored - branch: {data.get('ref')}")
                return jsonify({'status': 'ignored', 'message': 'Branch is not main'}), 200
        else:
            logger.info(f"Event ignored: {request.headers.get('X-GitHub-Event')}")
            return jsonify({'status': 'ignored', 'message': 'Event is not push'}), 200
            
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/deploy/<tag>', methods=['POST'])
def manual_deploy(tag):
    """Manual deployment with specific tag"""
    try:
        logger.info(f"Manual deployment requested for tag: {tag}")
        
        result = run_auto_deploy(tag)
        
        return jsonify({
            'status': 'success',
            'message': f'Manual deployment started for tag: {tag}',
            'result': result
        }), 200
        
    except Exception as e:
        logger.error(f"Manual deployment error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

def run_auto_deploy(tag):
    """Execute automatic deployment script"""
    try:
        logger.info(f"Executing automatic deployment for tag: {tag}")
        
        # Execute deployment script
        result = subprocess.run(
            [SCRIPT_PATH, tag],
            capture_output=True,
            text=True,
            timeout=600  # 10 minutes timeout
        )
        
        if result.returncode == 0:
            logger.info("Automatic deployment completed successfully")
            return {
                'success': True,
                'stdout': result.stdout,
                'stderr': result.stderr
            }
        else:
            logger.error(f"Automatic deployment failed: {result.stderr}")
            return {
                'success': False,
                'stdout': result.stdout,
                'stderr': result.stderr
            }
            
    except subprocess.TimeoutExpired:
        logger.error("Automatic deployment timeout")
        return {
            'success': False,
            'error': 'Timeout'
        }
    except Exception as e:
        logger.error(f"Error executing automatic deployment: {e}")
        return {
            'success': False,
            'error': str(e)
        }

@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'image': f'{REGISTRY}/{IMAGE_NAME}',
        'namespace': NAMESPACE
    }), 200

@app.route('/status', methods=['GET'])
def status():
    """Service status"""
    try:
        # Check if logged into OpenShift
        result = subprocess.run(['oc', 'whoami'], capture_output=True, text=True)
        
        return jsonify({
            'status': 'running',
            'timestamp': datetime.now().isoformat(),
            'openshift_user': result.stdout.strip() if result.returncode == 0 else 'Not logged in',
            'image': f'{REGISTRY}/{IMAGE_NAME}',
            'namespace': NAMESPACE,
            'script_path': SCRIPT_PATH
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    debug = os.getenv('DEBUG', 'false').lower() == 'true'
    
    logger.info(f"Starting webhook server on port {port}")
    logger.info(f"Configuration: IMAGE_NAME={IMAGE_NAME}, REGISTRY={REGISTRY}, NAMESPACE={NAMESPACE}")
    
    app.run(host='0.0.0.0', port=port, debug=debug)
