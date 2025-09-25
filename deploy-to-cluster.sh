#!/bin/bash

# Script para deploy da aplicação OpenShift Resource Governance
# Funciona com qualquer cluster OpenShift (público ou privado)

# Variáveis
IMAGE_NAME="resource-governance"
NAMESPACE="resource-governance"
IMAGE_TAG=${1:-latest} # Usa o primeiro argumento como tag, ou 'latest' por padrão

echo "🚀 Deploy para OpenShift Cluster"
echo "================================"
echo "Imagem: ${IMAGE_TAG}"
echo "Namespace: ${NAMESPACE}"
echo ""

# 1. Verificar login no OpenShift
if ! oc whoami > /dev/null 2>&1; then
  echo "❌ Não logado no OpenShift. Por favor, faça login com 'oc login'."
  echo "💡 Exemplo: oc login https://your-cluster.com"
  exit 1
fi
echo "✅ Logado no OpenShift como: $(oc whoami)"
echo ""

# 2. Verificar se o namespace existe, senão criar
if ! oc get namespace ${NAMESPACE} > /dev/null 2>&1; then
  echo "📋 Criando namespace ${NAMESPACE}..."
  oc create namespace ${NAMESPACE}
else
  echo "✅ Namespace ${NAMESPACE} já existe"
fi
echo ""

# 3. Aplicar manifests básicos (rbac, configmap)
echo "📋 Aplicando manifests..."
oc apply -f k8s/rbac.yaml
oc apply -f k8s/configmap.yaml
echo ""

# 4. Atualizar deployment com a nova imagem
echo "🔄 Atualizando imagem do deployment..."
oc set image deployment/${IMAGE_NAME} ${IMAGE_NAME}=${IMAGE_TAG} -n ${NAMESPACE} || true
echo ""

# 5. Aplicar deployment, service e route
echo "📦 Aplicando deployment, service e route..."
oc apply -f k8s/deployment.yaml
oc apply -f k8s/service.yaml
oc apply -f k8s/route.yaml
echo ""

# 6. Aguardar rollout
echo "⏳ Aguardando rollout..."
oc rollout status deployment/${IMAGE_NAME} -n ${NAMESPACE} --timeout=300s
echo "✅ Rollout concluído com sucesso!"
echo ""

# 7. Verificar deployment
echo "✅ Verificando deployment..."
oc get deployment ${IMAGE_NAME} -n ${NAMESPACE}
oc get pods -n ${NAMESPACE} -l app.kubernetes.io/name=${IMAGE_NAME}
echo ""

# 8. Obter URL da rota
ROUTE_URL=$(oc get route ${IMAGE_NAME}-route -n ${NAMESPACE} -o jsonpath='{.spec.host}' 2>/dev/null || echo "")
if [ -n "$ROUTE_URL" ]; then
  echo "🚀 Application deployed successfully!"
  echo "🌐 URL: https://$ROUTE_URL"
  echo "📊 Status: oc get pods -n ${NAMESPACE} -l app.kubernetes.io/name=${IMAGE_NAME}"
else
  echo "⚠️  Rota não encontrada. Verifique se o cluster suporta Routes."
  echo "💡 Para acessar localmente: oc port-forward service/${IMAGE_NAME}-service 8080:8080 -n ${NAMESPACE}"
fi
echo ""

echo "✅ Deploy concluído!"
echo ""
echo "🔧 Comandos úteis:"
echo "   Ver logs: oc logs -f deployment/${IMAGE_NAME} -n ${NAMESPACE}"
echo "   Port-forward: oc port-forward service/${IMAGE_NAME}-service 8080:8080 -n ${NAMESPACE}"
echo "   Status: oc get pods -n ${NAMESPACE} -l app.kubernetes.io/name=${IMAGE_NAME}"
