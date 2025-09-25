#!/bin/bash

# Script para testar o fluxo CI/CD localmente
# Simula o que o GitHub Actions fará

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

NAMESPACE="resource-governance"
IMAGE_NAME="resource-governance"
REGISTRY="andersonid"
TAG="test-$(date +%s)"

echo -e "${BLUE}🧪 Teste do Fluxo CI/CD${NC}"
echo -e "${BLUE}========================${NC}"
echo -e "${BLUE}Tag: ${TAG}${NC}"

# 1. Verificar login no OpenShift
echo -e "${YELLOW}🔍 Verificando login no OpenShift...${NC}"
if ! oc whoami > /dev/null 2>&1; then
    echo -e "${RED}❌ Não está logado no OpenShift. Faça login primeiro.${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Logado como: $(oc whoami)${NC}"

# 2. Build da imagem
echo -e "${YELLOW}📦 Buildando imagem...${NC}"
podman build -f Dockerfile.simple -t "${REGISTRY}/${IMAGE_NAME}:${TAG}" .
podman build -f Dockerfile.simple -t "${REGISTRY}/${IMAGE_NAME}:latest" .

# 3. Push da imagem
echo -e "${YELLOW}📤 Fazendo push da imagem...${NC}"
podman push "${REGISTRY}/${IMAGE_NAME}:${TAG}"
podman push "${REGISTRY}/${IMAGE_NAME}:latest"

# 4. Atualizar deployment
echo -e "${YELLOW}🔄 Atualizando deployment...${NC}"
oc set image deployment/${IMAGE_NAME} ${IMAGE_NAME}=${REGISTRY}/${IMAGE_NAME}:${TAG} -n ${NAMESPACE}

# 5. Aguardar rollout
echo -e "${YELLOW}⏳ Aguardando rollout...${NC}"
oc rollout status deployment/${IMAGE_NAME} -n ${NAMESPACE} --timeout=120s

# 6. Verificar status
echo -e "${YELLOW}📊 Verificando status...${NC}"
oc get deployment ${IMAGE_NAME} -n ${NAMESPACE}
oc get pods -n ${NAMESPACE} -l app.kubernetes.io/name=${IMAGE_NAME}

# 7. Testar aplicação
echo -e "${YELLOW}🏥 Testando aplicação...${NC}"
oc port-forward service/${IMAGE_NAME}-service 8081:8080 -n ${NAMESPACE} &
PORT_FORWARD_PID=$!
sleep 5

if curl -s http://localhost:8081/api/v1/health > /dev/null; then
    echo -e "${GREEN}✅ Aplicação está funcionando com a nova imagem!${NC}"
else
    echo -e "${RED}❌ Aplicação não está respondendo${NC}"
fi

kill $PORT_FORWARD_PID 2>/dev/null || true

# 8. Mostrar informações
echo -e "${GREEN}🎉 Teste CI/CD concluído!${NC}"
echo -e "${BLUE}📊 Status do deployment:${NC}"
oc get deployment ${IMAGE_NAME} -n ${NAMESPACE} -o wide

echo -e "${BLUE}🔍 Imagem atual:${NC}"
oc get deployment ${IMAGE_NAME} -n ${NAMESPACE} -o jsonpath='{.spec.template.spec.containers[0].image}'
echo ""

echo -e "${BLUE}💡 Para reverter para latest:${NC}"
echo -e "   oc set image deployment/${IMAGE_NAME} ${IMAGE_NAME}=${REGISTRY}/${IMAGE_NAME}:latest -n ${NAMESPACE}"
