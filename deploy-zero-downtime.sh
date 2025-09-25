#!/bin/bash

# Script de deploy com ZERO DOWNTIME (Blue-Green Strategy)
# Garante que a aplicação nunca saia do ar durante atualizações

set -e

# Configurações
IMAGE_NAME="resource-governance"
REGISTRY="andersonid"
NAMESPACE="resource-governance"
TAG=${1:-"latest"}
FULL_IMAGE="$REGISTRY/$IMAGE_NAME:$TAG"

echo "🚀 Deploy ZERO DOWNTIME para OpenShift"
echo "======================================"
echo "Imagem: $FULL_IMAGE"
echo "Namespace: $NAMESPACE"
echo "Estratégia: Blue-Green (Zero Downtime)"
echo ""

# Verificar se está logado no OpenShift
if ! oc whoami > /dev/null 2>&1; then
    echo "❌ Não está logado no OpenShift. Execute: oc login"
    exit 1
fi

echo "✅ Logado no OpenShift como: $(oc whoami)"
echo ""

# Função para verificar se todos os pods estão prontos
check_pods_ready() {
    local deployment=$1
    local namespace=$2
    local timeout=${3:-300}
    
    echo "⏳ Aguardando pods do deployment $deployment ficarem prontos..."
    oc rollout status deployment/$deployment -n $namespace --timeout=${timeout}s
}

# Função para verificar se a aplicação está respondendo
check_app_health() {
    local service=$1
    local namespace=$2
    local port=${3:-8080}
    
    echo "🔍 Verificando saúde da aplicação..."
    
    # Tentar port-forward temporário para testar
    local temp_pid
    oc port-forward service/$service $port:$port -n $namespace > /dev/null 2>&1 &
    temp_pid=$!
    
    # Aguardar port-forward inicializar
    sleep 3
    
    # Testar health check
    local health_status
    health_status=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:$port/api/v1/health 2>/dev/null || echo "000")
    
    # Parar port-forward temporário
    kill $temp_pid 2>/dev/null || true
    
    if [ "$health_status" = "200" ]; then
        echo "✅ Aplicação saudável (HTTP $health_status)"
        return 0
    else
        echo "❌ Aplicação não saudável (HTTP $health_status)"
        return 1
    fi
}

# Aplicar manifests básicos
echo "📋 Aplicando manifests básicos..."
oc apply -f k8s/namespace.yaml
oc apply -f k8s/rbac.yaml
oc apply -f k8s/configmap.yaml

# Verificar se o deployment existe
if oc get deployment $IMAGE_NAME -n $NAMESPACE > /dev/null 2>&1; then
    echo "🔄 Deployment existente encontrado. Iniciando atualização zero-downtime..."
    
    # Obter número atual de réplicas
    CURRENT_REPLICAS=$(oc get deployment $IMAGE_NAME -n $NAMESPACE -o jsonpath='{.spec.replicas}')
    echo "📊 Réplicas atuais: $CURRENT_REPLICAS"
    
    # Atualizar imagem do deployment
    echo "🔄 Atualizando imagem para: $FULL_IMAGE"
    oc set image deployment/$IMAGE_NAME $IMAGE_NAME=$FULL_IMAGE -n $NAMESPACE
    
    # Aguardar rollout com timeout maior
    echo "⏳ Aguardando rollout (pode levar alguns minutos)..."
    if check_pods_ready $IMAGE_NAME $NAMESPACE 600; then
        echo "✅ Rollout concluído com sucesso!"
        
        # Verificar saúde da aplicação
        if check_app_health "${IMAGE_NAME}-service" $NAMESPACE; then
            echo "🎉 Deploy zero-downtime concluído com sucesso!"
        else
            echo "⚠️  Deploy concluído, mas aplicação pode não estar saudável"
            echo "🔍 Verifique os logs: oc logs -f deployment/$IMAGE_NAME -n $NAMESPACE"
        fi
    else
        echo "❌ Rollout falhou ou timeout"
        echo "🔍 Verificando status dos pods:"
        oc get pods -n $NAMESPACE -l app.kubernetes.io/name=$IMAGE_NAME
        exit 1
    fi
else
    echo "🆕 Deployment não existe. Criando novo deployment..."
    oc apply -f k8s/deployment.yaml
    oc apply -f k8s/service.yaml
    oc apply -f k8s/route.yaml
    
    # Aguardar pods ficarem prontos
    if check_pods_ready $IMAGE_NAME $NAMESPACE 300; then
        echo "✅ Novo deployment criado com sucesso!"
    else
        echo "❌ Falha ao criar deployment"
        exit 1
    fi
fi

# Verificar status final
echo ""
echo "📊 STATUS FINAL:"
echo "================"
oc get deployment $IMAGE_NAME -n $NAMESPACE
echo ""
oc get pods -n $NAMESPACE -l app.kubernetes.io/name=$IMAGE_NAME
echo ""

# Obter URL da rota
ROUTE_URL=$(oc get route $IMAGE_NAME-route -n $NAMESPACE -o jsonpath='{.spec.host}' 2>/dev/null || echo "")
if [ -n "$ROUTE_URL" ]; then
    echo "🌐 URLs de acesso:"
    echo "   OpenShift: https://$ROUTE_URL"
    echo "   Port-forward: http://localhost:8080 (se ativo)"
    echo ""
    echo "💡 Para iniciar port-forward: oc port-forward service/${IMAGE_NAME}-service 8080:8080 -n $NAMESPACE"
fi

echo ""
echo "✅ Deploy zero-downtime concluído!"
echo "🔄 Estratégia: Rolling Update com maxUnavailable=0 (zero downtime)"
