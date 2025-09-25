#!/bin/bash

# Script de teste de deploy (sem input interativo)
set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configurações
NAMESPACE="resource-governance"
APP_NAME="resource-governance"

echo -e "${BLUE}🧪 Teste de Deploy - OpenShift Resource Governance Tool${NC}"
echo -e "${BLUE}====================================================${NC}"

# Verificar se está logado no OpenShift
if ! oc whoami > /dev/null 2>&1; then
    echo -e "${RED}❌ Não está logado no OpenShift. Faça login primeiro.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Logado como: $(oc whoami)${NC}"

# Aplicar manifests
echo -e "${YELLOW}📁 Aplicando manifests...${NC}"
oc apply -f k8s/namespace.yaml
oc apply -f k8s/rbac.yaml
oc apply -f k8s/configmap.yaml

# Criar ImagePullSecret temporário (sem credenciais reais)
echo -e "${YELLOW}🔐 Criando ImagePullSecret temporário...${NC}"
oc create secret docker-registry docker-hub-secret \
    --docker-server=docker.io \
    --docker-username=andersonid \
    --docker-password=temp \
    --docker-email=andersonid@example.com \
    -n $NAMESPACE \
    --dry-run=client -o yaml | oc apply -f -

# Adicionar o secret ao service account
oc patch serviceaccount resource-governance-sa -n $NAMESPACE -p '{"imagePullSecrets": [{"name": "docker-hub-secret"}]}'

# Aplicar DaemonSet
echo -e "${YELLOW}📦 Aplicando DaemonSet...${NC}"
oc apply -f k8s/daemonset.yaml

# Aplicar Service
echo -e "${YELLOW}🌐 Aplicando Service...${NC}"
oc apply -f k8s/service.yaml

# Aplicar Route
echo -e "${YELLOW}🛣️  Aplicando Route...${NC}"
oc apply -f k8s/route.yaml

# Verificar status
echo -e "${YELLOW}📊 Verificando status...${NC}"
oc get all -n $NAMESPACE

echo -e "${GREEN}✅ Deploy de teste concluído!${NC}"
echo -e "${BLUE}💡 Para configurar credenciais reais do Docker Hub, execute:${NC}"
echo -e "${BLUE}   ./scripts/setup-docker-secret.sh${NC}"
