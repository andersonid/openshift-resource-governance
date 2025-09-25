#!/usr/bin/env python3
"""
Webhook para deploy automático após GitHub Actions
Este script pode ser executado como um serviço para detectar mudanças no Docker Hub
"""

import os
import json
import subprocess
import logging
from flask import Flask, request, jsonify
from datetime import datetime

# Configuração do logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configurações
IMAGE_NAME = os.getenv('IMAGE_NAME', 'resource-governance')
REGISTRY = os.getenv('REGISTRY', 'andersonid')
NAMESPACE = os.getenv('NAMESPACE', 'resource-governance')
SCRIPT_PATH = os.getenv('AUTO_DEPLOY_SCRIPT', './scripts/auto-deploy.sh')

@app.route('/webhook/dockerhub', methods=['POST'])
def dockerhub_webhook():
    """Webhook para receber notificações do Docker Hub"""
    try:
        data = request.get_json()
        
        # Verificar se é uma notificação de push
        if data.get('push_data', {}).get('tag') == 'latest':
            logger.info(f"Recebida notificação de push para {REGISTRY}/{IMAGE_NAME}:latest")
            
            # Executar deploy automático
            result = run_auto_deploy('latest')
            
            return jsonify({
                'status': 'success',
                'message': 'Deploy automático iniciado',
                'result': result
            }), 200
        else:
            logger.info(f"Push ignorado - tag: {data.get('push_data', {}).get('tag')}")
            return jsonify({'status': 'ignored', 'message': 'Tag não é latest'}), 200
            
    except Exception as e:
        logger.error(f"Erro no webhook: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/webhook/github', methods=['POST'])
def github_webhook():
    """Webhook para receber notificações do GitHub"""
    try:
        # Verificar se é um push para main
        if request.headers.get('X-GitHub-Event') == 'push':
            data = request.get_json()
            
            if data.get('ref') == 'refs/heads/main':
                logger.info("Recebida notificação de push para main branch")
                
                # Executar deploy automático
                result = run_auto_deploy('latest')
                
                return jsonify({
                    'status': 'success',
                    'message': 'Deploy automático iniciado',
                    'result': result
                }), 200
            else:
                logger.info(f"Push ignorado - branch: {data.get('ref')}")
                return jsonify({'status': 'ignored', 'message': 'Branch não é main'}), 200
        else:
            logger.info(f"Evento ignorado: {request.headers.get('X-GitHub-Event')}")
            return jsonify({'status': 'ignored', 'message': 'Evento não é push'}), 200
            
    except Exception as e:
        logger.error(f"Erro no webhook: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/deploy/<tag>', methods=['POST'])
def manual_deploy(tag):
    """Deploy manual com tag específica"""
    try:
        logger.info(f"Deploy manual solicitado para tag: {tag}")
        
        result = run_auto_deploy(tag)
        
        return jsonify({
            'status': 'success',
            'message': f'Deploy manual iniciado para tag: {tag}',
            'result': result
        }), 200
        
    except Exception as e:
        logger.error(f"Erro no deploy manual: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

def run_auto_deploy(tag):
    """Executar script de deploy automático"""
    try:
        logger.info(f"Executando deploy automático para tag: {tag}")
        
        # Executar script de deploy
        result = subprocess.run(
            [SCRIPT_PATH, tag],
            capture_output=True,
            text=True,
            timeout=600  # 10 minutos timeout
        )
        
        if result.returncode == 0:
            logger.info("Deploy automático concluído com sucesso")
            return {
                'success': True,
                'stdout': result.stdout,
                'stderr': result.stderr
            }
        else:
            logger.error(f"Deploy automático falhou: {result.stderr}")
            return {
                'success': False,
                'stdout': result.stdout,
                'stderr': result.stderr
            }
            
    except subprocess.TimeoutExpired:
        logger.error("Deploy automático timeout")
        return {
            'success': False,
            'error': 'Timeout'
        }
    except Exception as e:
        logger.error(f"Erro ao executar deploy automático: {e}")
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
    """Status do serviço"""
    try:
        # Verificar se está logado no OpenShift
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
    
    logger.info(f"Iniciando webhook server na porta {port}")
    logger.info(f"Configurações: IMAGE_NAME={IMAGE_NAME}, REGISTRY={REGISTRY}, NAMESPACE={NAMESPACE}")
    
    app.run(host='0.0.0.0', port=port, debug=debug)
