#!/bin/bash

# Script de deploy para OpenShift usando GitHub
set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configurações
REPO_URL="https://github.com/andersonid/openshift-resource-governance.git"
IMAGE_NAME="resource-governance"
REGISTRY="quay.io/andersonid"
TAG="${1:-latest}"
NAMESPACE="resource-governance"

echo -e "${BLUE}🚀 Deploying OpenShift Resource Governance Tool from GitHub${NC}"
echo -e "${BLUE}Repository: ${REPO_URL}${NC}"
echo -e "${BLUE}Image: ${REGISTRY}/${IMAGE_NAME}:${TAG}${NC}"

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
oc set image daemonset/${IMAGE_NAME} ${IMAGE_NAME}="${REGISTRY}/${IMAGE_NAME}:${TAG}" -n "${NAMESPACE}" || true

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
oc wait --for=condition=ready pod -l app.kubernetes.io/name=${IMAGE_NAME} -n "${NAMESPACE}" --timeout=300s

# Obter URL da rota
ROUTE_URL=$(oc get route ${IMAGE_NAME}-route -n "${NAMESPACE}" -o jsonpath='{.spec.host}')
if [ -n "${ROUTE_URL}" ]; then
    echo -e "${GREEN}🎉 Deploy completed successfully!${NC}"
    echo -e "${BLUE}🌐 Application URL: https://${ROUTE_URL}${NC}"
    echo -e "${BLUE}📊 GitHub Repository: ${REPO_URL}${NC}"
else
    echo -e "${YELLOW}⚠️  Deploy completed, but route URL not found.${NC}"
    echo -e "${BLUE}Check with: oc get routes -n ${NAMESPACE}${NC}"
fi

# Mostrar status
echo -e "${BLUE}📊 Deployment status:${NC}"
oc get all -n "${NAMESPACE}"

echo -e "${BLUE}🔍 To check logs:${NC}"
echo -e "  oc logs -f daemonset/${IMAGE_NAME} -n ${NAMESPACE}"

echo -e "${BLUE}🧪 To test health:${NC}"
echo -e "  curl https://${ROUTE_URL}/health"

echo -e "${BLUE}📝 To update from GitHub:${NC}"
echo -e "  git pull origin main"
echo -e "  ./openshift-deploy.sh <new-tag>"
