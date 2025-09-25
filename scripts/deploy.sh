#!/bin/bash

# Script de deploy para OpenShift Resource Governance Tool
set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configurações
NAMESPACE="resource-governance"
IMAGE_NAME="resource-governance"
TAG="${1:-latest}"
REGISTRY="${2:-quay.io/openshift}"
FULL_IMAGE_NAME="${REGISTRY}/${IMAGE_NAME}:${TAG}"

echo -e "${BLUE}🚀 Deploying OpenShift Resource Governance Tool${NC}"
echo -e "${BLUE}Namespace: ${NAMESPACE}${NC}"
echo -e "${BLUE}Image: ${FULL_IMAGE_NAME}${NC}"

# Verificar se oc está instalado
if ! command -v oc &> /dev/null; then
    echo -e "${RED}❌ OpenShift CLI (oc) não está instalado.${NC}"
    echo -e "${YELLOW}Instale o oc CLI: https://docs.openshift.com/container-platform/latest/cli_reference/openshift_cli/getting-started-cli.html${NC}"
    exit 1
fi

# Verificar se está logado no OpenShift
if ! oc whoami &> /dev/null; then
    echo -e "${RED}❌ Não está logado no OpenShift.${NC}"
    echo -e "${YELLOW}Faça login com: oc login <cluster-url>${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Logado como: $(oc whoami)${NC}"

# Criar namespace se não existir
echo -e "${YELLOW}📁 Creating namespace...${NC}"
oc apply -f k8s/namespace.yaml

# Aplicar RBAC
echo -e "${YELLOW}🔐 Applying RBAC...${NC}"
oc apply -f k8s/rbac.yaml

# Aplicar ConfigMap
echo -e "${YELLOW}⚙️  Applying ConfigMap...${NC}"
oc apply -f k8s/configmap.yaml

# Atualizar imagem no DaemonSet
echo -e "${YELLOW}🔄 Updating image in DaemonSet...${NC}"
oc set image daemonset/resource-governance resource-governance="${FULL_IMAGE_NAME}" -n "${NAMESPACE}"

# Aplicar DaemonSet
echo -e "${YELLOW}📦 Applying DaemonSet...${NC}"
oc apply -f k8s/daemonset.yaml

# Aplicar Service
echo -e "${YELLOW}🌐 Applying Service...${NC}"
oc apply -f k8s/service.yaml

# Aplicar Route
echo -e "${YELLOW}🛣️  Applying Route...${NC}"
oc apply -f k8s/route.yaml

# Aguardar pods ficarem prontos
echo -e "${YELLOW}⏳ Waiting for pods to be ready...${NC}"
oc wait --for=condition=ready pod -l app.kubernetes.io/name=resource-governance -n "${NAMESPACE}" --timeout=300s

# Obter URL da rota
ROUTE_URL=$(oc get route resource-governance-route -n "${NAMESPACE}" -o jsonpath='{.spec.host}')
if [ -n "${ROUTE_URL}" ]; then
    echo -e "${GREEN}🎉 Deploy completed successfully!${NC}"
    echo -e "${BLUE}🌐 Application URL: https://${ROUTE_URL}${NC}"
else
    echo -e "${YELLOW}⚠️  Deploy completed, but route URL not found.${NC}"
    echo -e "${BLUE}Check with: oc get routes -n ${NAMESPACE}${NC}"
fi

# Mostrar status
echo -e "${BLUE}📊 Deployment status:${NC}"
oc get all -n "${NAMESPACE}"

echo -e "${BLUE}🔍 To check logs:${NC}"
echo -e "  oc logs -f daemonset/resource-governance -n ${NAMESPACE}"

echo -e "${BLUE}🧪 To test health:${NC}"
echo -e "  curl https://${ROUTE_URL}/health"
