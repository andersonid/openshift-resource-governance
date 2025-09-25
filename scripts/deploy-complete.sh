#!/bin/bash

# Script completo de deploy para OpenShift Resource Governance Tool
# Para ser executado por qualquer cluster-admin
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
SECRET_NAME="docker-hub-secret"

echo -e "${BLUE}🚀 Deploy Completo - OpenShift Resource Governance Tool${NC}"
echo -e "${BLUE}====================================================${NC}"

# Verificar se está logado no OpenShift
if ! oc whoami > /dev/null 2>&1; then
    echo -e "${RED}❌ Não está logado no OpenShift. Faça login primeiro.${NC}"
    echo -e "${YELLOW}💡 Execute: oc login <cluster-url>${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Logado como: $(oc whoami)${NC}"

# Verificar se tem permissões de cluster-admin
if ! oc auth can-i create namespaces > /dev/null 2>&1; then
    echo -e "${RED}❌ Permissões insuficientes. Este script requer cluster-admin.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Permissões de cluster-admin confirmadas${NC}"

# Criar namespace
echo -e "${YELLOW}📁 Criando namespace $NAMESPACE...${NC}"
oc apply -f k8s/namespace.yaml

# Aplicar RBAC
echo -e "${YELLOW}🔐 Configurando RBAC...${NC}"
oc apply -f k8s/rbac.yaml

# Aplicar ConfigMap
echo -e "${YELLOW}⚙️  Configurando ConfigMap...${NC}"
oc apply -f k8s/configmap.yaml

# Configurar ImagePullSecret
echo -e "${YELLOW}🔑 Configurando ImagePullSecret para Docker Hub...${NC}"
echo -e "${BLUE}💡 Digite suas credenciais do Docker Hub:${NC}"
read -p "Username: " DOCKER_USERNAME
read -s -p "Password/Token: " DOCKER_PASSWORD
echo

# Criar o secret
oc create secret docker-registry $SECRET_NAME \
    --docker-server=docker.io \
    --docker-username=$DOCKER_USERNAME \
    --docker-password=$DOCKER_PASSWORD \
    --docker-email=$DOCKER_USERNAME@example.com \
    -n $NAMESPACE \
    --dry-run=client -o yaml | oc apply -f -

# Adicionar o secret ao service account
oc patch serviceaccount resource-governance-sa -n $NAMESPACE -p '{"imagePullSecrets": [{"name": "'$SECRET_NAME'"}]}'

echo -e "${GREEN}✅ ImagePullSecret configurado${NC}"

# Aplicar DaemonSet
echo -e "${YELLOW}📦 Deployando DaemonSet...${NC}"
oc apply -f k8s/daemonset.yaml

# Aplicar Service
echo -e "${YELLOW}🌐 Configurando Service...${NC}"
oc apply -f k8s/service.yaml

# Aplicar Route
echo -e "${YELLOW}🛣️  Configurando Route...${NC}"
oc apply -f k8s/route.yaml

# Aguardar pods ficarem prontos
echo -e "${YELLOW}⏳ Aguardando pods ficarem prontos...${NC}"
oc wait --for=condition=ready pod -l app.kubernetes.io/name=$APP_NAME -n $NAMESPACE --timeout=300s

# Verificar status
echo -e "${YELLOW}📊 Verificando status do deploy...${NC}"
oc get all -n $NAMESPACE

# Obter URL da aplicação
ROUTE_URL=$(oc get route $APP_NAME -n $NAMESPACE -o jsonpath='{.spec.host}' 2>/dev/null || echo "N/A")

echo -e "${GREEN}🎉 Deploy concluído com sucesso!${NC}"
echo -e "${BLUE}====================================================${NC}"
echo -e "${GREEN}✅ Namespace: $NAMESPACE${NC}"
echo -e "${GREEN}✅ DaemonSet: $APP_NAME${NC}"
echo -e "${GREEN}✅ Service: $APP_NAME${NC}"
echo -e "${GREEN}✅ Route: $APP_NAME${NC}"
if [ "$ROUTE_URL" != "N/A" ]; then
    echo -e "${GREEN}🌐 URL da aplicação: https://$ROUTE_URL${NC}"
fi
echo -e "${BLUE}====================================================${NC}"

# Mostrar comandos úteis
echo -e "${YELLOW}📋 Comandos úteis:${NC}"
echo -e "${BLUE}  Ver logs: oc logs -f daemonset/$APP_NAME -n $NAMESPACE${NC}"
echo -e "${BLUE}  Ver pods: oc get pods -n $NAMESPACE${NC}"
echo -e "${BLUE}  Ver status: oc get all -n $NAMESPACE${NC}"
echo -e "${BLUE}  Acessar API: curl https://$ROUTE_URL/api/health${NC}"

echo -e "${GREEN}🎯 Aplicação pronta para uso!${NC}"
