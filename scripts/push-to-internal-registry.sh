#!/bin/bash

# Script para fazer push da imagem para o registry interno do OpenShift
set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

NAMESPACE="resource-governance"
IMAGE_NAME="resource-governance"
TAG="latest"

echo -e "${BLUE}🚀 Push para registry interno do OpenShift${NC}"

# Verificar se está logado no OpenShift
if ! oc whoami > /dev/null 2>&1; then
    echo -e "${RED}❌ Não está logado no OpenShift. Faça login primeiro.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Logado como: $(oc whoami)${NC}"

# Fazer login no registry interno
echo -e "${YELLOW}🔐 Fazendo login no registry interno...${NC}"
oc registry login

# Obter a URL do registry
REGISTRY_URL=$(oc get route -n openshift-image-registry default-route -o jsonpath='{.spec.host}' 2>/dev/null || echo "image-registry.openshift-image-registry.svc:5000")
echo -e "${BLUE}📦 Registry URL: $REGISTRY_URL${NC}"

# Tag da imagem
FULL_IMAGE_NAME="$REGISTRY_URL/$NAMESPACE/$IMAGE_NAME:$TAG"
echo -e "${YELLOW}🏷️  Criando tag: $FULL_IMAGE_NAME${NC}"
podman tag andersonid/resource-governance:simple $FULL_IMAGE_NAME

# Push da imagem
echo -e "${YELLOW}📤 Fazendo push da imagem...${NC}"
podman push $FULL_IMAGE_NAME --tls-verify=false

# Atualizar o DaemonSet
echo -e "${YELLOW}🔄 Atualizando DaemonSet...${NC}"
oc set image daemonset/$IMAGE_NAME $IMAGE_NAME=$FULL_IMAGE_NAME -n $NAMESPACE

echo -e "${GREEN}✅ Push concluído com sucesso!${NC}"
echo -e "${BLUE}📊 Verificando status dos pods...${NC}"
oc get pods -n $NAMESPACE
