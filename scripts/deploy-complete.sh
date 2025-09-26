#!/bin/bash

# Script completo de deploy do OpenShift Resource Governance Tool
# Inclui criação de namespace, RBAC, ConfigMap, Secret e Deployment

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configurações
NAMESPACE="resource-governance"
SERVICE_ACCOUNT="resource-governance-sa"
SECRET_NAME="resource-governance-sa-token"

echo -e "${BLUE}🚀 Deploying OpenShift Resource Governance Tool${NC}"

# Verificar se está conectado ao cluster
if ! oc whoami > /dev/null 2>&1; then
    echo -e "${RED}❌ Not connected to OpenShift cluster. Please run 'oc login' first.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Connected to OpenShift cluster as $(oc whoami)${NC}"

# Criar namespace se não existir
echo -e "${YELLOW}📦 Creating namespace...${NC}"
oc create namespace $NAMESPACE --dry-run=client -o yaml | oc apply -f -

# Aplicar RBAC
echo -e "${YELLOW}🔐 Applying RBAC...${NC}"
oc apply -f k8s/rbac.yaml

# Aplicar ConfigMap
echo -e "${YELLOW}⚙️  Applying ConfigMap...${NC}"
oc apply -f k8s/configmap.yaml

# Criar secret do token do ServiceAccount
echo -e "${YELLOW}🔑 Creating ServiceAccount token...${NC}"

# Verificar se o secret já existe
if oc get secret $SECRET_NAME -n $NAMESPACE > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Secret $SECRET_NAME already exists, skipping creation${NC}"
else
    # Criar token do ServiceAccount
    TOKEN=$(oc create token $SERVICE_ACCOUNT -n $NAMESPACE --duration=8760h)
    
    # Criar secret com o token
    oc create secret generic $SECRET_NAME -n $NAMESPACE \
        --from-literal=token="$TOKEN" \
        --from-literal=ca.crt="$(oc get secret -n $NAMESPACE -o jsonpath='{.items[0].data.ca\.crt}' | base64 -d)" \
        --from-literal=namespace="$NAMESPACE"
    
    echo -e "${GREEN}✅ ServiceAccount token created${NC}"
fi

# Aplicar Deployment
echo -e "${YELLOW}🚀 Applying Deployment...${NC}"
oc apply -f k8s/deployment.yaml

# Aplicar Service
echo -e "${YELLOW}🌐 Applying Service...${NC}"
oc apply -f k8s/service.yaml

# Aplicar Route
echo -e "${YELLOW}🛣️  Applying Route...${NC}"
oc apply -f k8s/route.yaml

# Aguardar deployment estar pronto
echo -e "${YELLOW}⏳ Waiting for deployment to be ready...${NC}"
oc rollout status deployment/resource-governance -n $NAMESPACE --timeout=300s

# Verificar status dos pods
echo -e "${YELLOW}📊 Checking pod status...${NC}"
oc get pods -n $NAMESPACE -l app.kubernetes.io/name=resource-governance

# Verificar logs para erros
echo -e "${YELLOW}📋 Checking application logs...${NC}"
POD_NAME=$(oc get pods -n $NAMESPACE -l app.kubernetes.io/name=resource-governance -o jsonpath='{.items[0].metadata.name}')
if [ -n "$POD_NAME" ]; then
    echo -e "${BLUE}Recent logs from $POD_NAME:${NC}"
    oc logs $POD_NAME -n $NAMESPACE --tail=10
fi

# Obter URL da aplicação
echo -e "${YELLOW}🌍 Getting application URL...${NC}"
ROUTE_URL=$(oc get route resource-governance -n $NAMESPACE -o jsonpath='{.spec.host}')
if [ -n "$ROUTE_URL" ]; then
    echo -e "${GREEN}✅ Application deployed successfully!${NC}"
    echo -e "${GREEN}🌐 URL: https://$ROUTE_URL${NC}"
    echo -e "${GREEN}📊 Health check: https://$ROUTE_URL/api/v1/health${NC}"
else
    echo -e "${YELLOW}⚠️  Route not found, checking service...${NC}"
    oc get svc -n $NAMESPACE
fi

echo -e "${GREEN}🎉 Deployment completed successfully!${NC}"