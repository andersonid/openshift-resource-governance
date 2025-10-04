#!/bin/bash

# Script completo de undeploy para OpenShift Resource Governance Tool
set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configurações
NAMESPACE="resource-governance"

echo -e "${BLUE}🗑️  Undeploy - OpenShift Resource Governance Tool${NC}"
echo -e "${BLUE}===============================================${NC}"

# Verificar se está logado no OpenShift
if ! oc whoami > /dev/null 2>&1; then
    echo -e "${RED}❌ Não está logado no OpenShift. Faça login primeiro.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Logado como: $(oc whoami)${NC}"

# Confirmar remoção
echo -e "${YELLOW}⚠️  Tem certeza que deseja remover a aplicação do namespace '$NAMESPACE'?${NC}"
read -p "Digite 'yes' para confirmar: " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo -e "${YELLOW}❌ Operação cancelada.${NC}"
    exit 0
fi

# Remover recursos
echo -e "${YELLOW}🗑️  Removendo recursos...${NC}"

# Remover Route
echo -e "${YELLOW}  🛣️  Removendo Route...${NC}"
oc delete -f k8s/route.yaml --ignore-not-found=true

# Remover Service
echo -e "${YELLOW}  🌐 Removendo Service...${NC}"
oc delete -f k8s/service.yaml --ignore-not-found=true

# Remover Deployment
echo -e "${YELLOW}  📦 Removendo Deployment...${NC}"
oc delete -f k8s/deployment.yaml --ignore-not-found=true

# Aguardar pods serem removidos
echo -e "${YELLOW}  ⏳ Aguardando pods serem removidos...${NC}"
oc wait --for=delete pod -l app.kubernetes.io/name=resource-governance -n $NAMESPACE --timeout=60s || true

# Remover ConfigMap
echo -e "${YELLOW}  ⚙️  Removendo ConfigMap...${NC}"
oc delete -f k8s/configmap.yaml --ignore-not-found=true

# Remover RBAC
echo -e "${YELLOW}  🔐 Removendo RBAC...${NC}"
oc delete -f k8s/rbac.yaml --ignore-not-found=true

# Remover namespace (opcional)
echo -e "${YELLOW}  📁 Removendo namespace...${NC}"
oc delete -f k8s/namespace.yaml --ignore-not-found=true

echo -e "${GREEN}✅ Undeploy concluído com sucesso!${NC}"
echo -e "${BLUE}===============================================${NC}"
echo -e "${GREEN}✅ Todos os recursos foram removidos${NC}"
echo -e "${GREEN}✅ Namespace '$NAMESPACE' foi removido${NC}"
echo -e "${BLUE}===============================================${NC}"
