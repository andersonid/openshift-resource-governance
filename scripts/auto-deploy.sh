#!/bin/bash

# Script para deploy automático após GitHub Actions
# Este script pode ser executado localmente ou via webhook

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configurações
IMAGE_NAME="resource-governance"
REGISTRY="andersonid"
NAMESPACE="resource-governance"
IMAGE_TAG=${1:-latest}

echo -e "${BLUE}🚀 Auto-Deploy para OpenShift${NC}"
echo "================================"
echo "Imagem: ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
echo "Namespace: ${NAMESPACE}"
echo ""

# 1. Verificar login no OpenShift
if ! oc whoami > /dev/null 2>&1; then
  echo -e "${RED}❌ Não logado no OpenShift. Por favor, faça login com 'oc login'.${NC}"
  exit 1
fi
echo -e "${GREEN}✅ Logado no OpenShift como: $(oc whoami)${NC}"
echo ""

# 2. Verificar se a imagem existe no Docker Hub
echo -e "${BLUE}🔍 Verificando imagem no Docker Hub...${NC}"
if ! skopeo inspect docker://${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG} > /dev/null 2>&1; then
  echo -e "${RED}❌ Imagem ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG} não encontrada no Docker Hub!${NC}"
  exit 1
fi
echo -e "${GREEN}✅ Imagem encontrada no Docker Hub${NC}"
echo ""

# 3. Verificar se o namespace existe
if ! oc get namespace ${NAMESPACE} > /dev/null 2>&1; then
  echo -e "${BLUE}📋 Criando namespace ${NAMESPACE}...${NC}"
  oc create namespace ${NAMESPACE}
else
  echo -e "${GREEN}✅ Namespace ${NAMESPACE} já existe${NC}"
fi
echo ""

# 4. Aplicar manifests básicos
echo -e "${BLUE}📋 Aplicando manifests básicos...${NC}"
oc apply -f k8s/rbac.yaml -n ${NAMESPACE}
oc apply -f k8s/configmap.yaml -n ${NAMESPACE}
echo ""

# 5. Verificar se o deployment existe
if oc get deployment ${IMAGE_NAME} -n ${NAMESPACE} > /dev/null 2>&1; then
  echo -e "${BLUE}🔄 Deployment existente encontrado. Iniciando atualização...${NC}"
  
  # Obter imagem atual
  CURRENT_IMAGE=$(oc get deployment ${IMAGE_NAME} -n ${NAMESPACE} -o jsonpath='{.spec.template.spec.containers[0].image}')
  echo "Imagem atual: ${CURRENT_IMAGE}"
  echo "Nova imagem: ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
  
  # Verificar se a imagem mudou
  if [ "${CURRENT_IMAGE}" = "${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}" ]; then
    echo -e "${YELLOW}⚠️  Imagem já está atualizada. Nenhuma ação necessária.${NC}"
    exit 0
  fi
  
  # Atualizar deployment com nova imagem
  echo -e "${BLUE}🔄 Atualizando imagem do deployment...${NC}"
  oc set image deployment/${IMAGE_NAME} ${IMAGE_NAME}=${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG} -n ${NAMESPACE}
  
  # Aguardar rollout
  echo -e "${BLUE}⏳ Aguardando rollout (pode levar alguns minutos)...${NC}"
  oc rollout status deployment/${IMAGE_NAME} -n ${NAMESPACE} --timeout=300s
  echo -e "${GREEN}✅ Rollout concluído com sucesso!${NC}"
  
else
  echo -e "${BLUE}📦 Deployment não encontrado. Criando novo deployment...${NC}"
  # Aplicar deployment, service e route
  oc apply -f k8s/deployment.yaml -n ${NAMESPACE}
  oc apply -f k8s/service.yaml -n ${NAMESPACE}
  oc apply -f k8s/route.yaml -n ${NAMESPACE}
  
  # Aguardar rollout inicial
  echo -e "${BLUE}⏳ Aguardando rollout inicial...${NC}"
  oc rollout status deployment/${IMAGE_NAME} -n ${NAMESPACE} --timeout=300s
  echo -e "${GREEN}✅ Rollout inicial concluído com sucesso!${NC}"
fi
echo ""

# 6. Verificar status final
echo -e "${BLUE}📊 STATUS FINAL:${NC}"
echo "================"
oc get deployment ${IMAGE_NAME} -n ${NAMESPACE}
echo ""
oc get pods -n ${NAMESPACE} -l app.kubernetes.io/name=${IMAGE_NAME}
echo ""

# 7. Obter URLs de acesso
ROUTE_URL=$(oc get route ${IMAGE_NAME}-route -n ${NAMESPACE} -o jsonpath='{.spec.host}' 2>/dev/null || echo "")
echo -e "${BLUE}🌐 URLs de acesso:${NC}"
if [ -n "$ROUTE_URL" ]; then
  echo "   OpenShift: https://$ROUTE_URL"
else
  echo "   OpenShift: Rota não encontrada ou não disponível."
fi
echo "   Port-forward: http://localhost:8080 (se ativo)"
echo ""

echo -e "${GREEN}✅ Auto-deploy concluído com sucesso!${NC}"
echo -e "${BLUE}🔄 Estratégia: Rolling Update com maxUnavailable=0 (zero downtime)${NC}"
