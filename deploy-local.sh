#!/bin/bash

# Script de deploy local para OpenShift
# Uso: ./deploy-local.sh [TAG_DA_IMAGEM]

set -e

# Configurações
IMAGE_NAME="resource-governance"
REGISTRY="andersonid"
NAMESPACE="resource-governance"
TAG=${1:-"latest"}

echo "🚀 Deploy Local para OpenShift"
echo "================================"
echo "Imagem: $REGISTRY/$IMAGE_NAME:$TAG"
echo "Namespace: $NAMESPACE"
echo ""

# Verificar se está logado no OpenShift
if ! oc whoami > /dev/null 2>&1; then
    echo "❌ Não está logado no OpenShift. Execute: oc login"
    exit 1
fi

echo "✅ Logado no OpenShift como: $(oc whoami)"
echo ""

# Aplicar manifests
echo "📋 Aplicando manifests..."
oc apply -f k8s/namespace.yaml
oc apply -f k8s/rbac.yaml
oc apply -f k8s/configmap.yaml

# Atualizar imagem do deployment
echo "🔄 Atualizando imagem do deployment..."
oc set image deployment/$IMAGE_NAME $IMAGE_NAME=$REGISTRY/$IMAGE_NAME:$TAG -n $NAMESPACE || true

# Aplicar deployment, service e route
echo "📦 Aplicando deployment, service e route..."
oc apply -f k8s/deployment.yaml
oc apply -f k8s/service.yaml
oc apply -f k8s/route.yaml

# Aguardar rollout
echo "⏳ Aguardando rollout..."
oc rollout status deployment/$IMAGE_NAME -n $NAMESPACE --timeout=300s

# Verificar deployment
echo "✅ Verificando deployment..."
oc get deployment $IMAGE_NAME -n $NAMESPACE
oc get pods -n $NAMESPACE -l app.kubernetes.io/name=$IMAGE_NAME

# Obter URL da rota
ROUTE_URL=$(oc get route $IMAGE_NAME-route -n $NAMESPACE -o jsonpath='{.spec.host}' 2>/dev/null || echo "")
if [ -n "$ROUTE_URL" ]; then
    echo ""
    echo "🚀 Application deployed successfully!"
    echo "🌐 URL: https://$ROUTE_URL"
    echo "📊 Status: oc get pods -n $NAMESPACE -l app.kubernetes.io/name=$IMAGE_NAME"
else
    echo "⚠️  Rota não encontrada. Verifique: oc get routes -n $NAMESPACE"
fi

echo ""
echo "✅ Deploy concluído!"
