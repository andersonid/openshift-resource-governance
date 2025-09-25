#!/bin/bash

# Script para configurar ImagePullSecret para Docker Hub
set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

NAMESPACE="resource-governance"
SECRET_NAME="docker-hub-secret"

echo -e "${BLUE}🔐 Configurando ImagePullSecret para Docker Hub${NC}"

# Verificar se está logado no OpenShift
if ! oc whoami > /dev/null 2>&1; then
    echo -e "${RED}❌ Não está logado no OpenShift. Faça login primeiro.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Logado como: $(oc whoami)${NC}"

# Verificar se o namespace existe
if ! oc get namespace $NAMESPACE > /dev/null 2>&1; then
    echo -e "${YELLOW}📁 Criando namespace $NAMESPACE...${NC}"
    oc create namespace $NAMESPACE
fi

# Solicitar credenciais do Docker Hub
echo -e "${YELLOW}🔑 Digite suas credenciais do Docker Hub:${NC}"
read -p "Username: " DOCKER_USERNAME
read -s -p "Password/Token: " DOCKER_PASSWORD
echo

# Criar o secret
echo -e "${YELLOW}🔐 Criando ImagePullSecret...${NC}"
oc create secret docker-registry $SECRET_NAME \
    --docker-server=docker.io \
    --docker-username=$DOCKER_USERNAME \
    --docker-password=$DOCKER_PASSWORD \
    --docker-email=$DOCKER_USERNAME@example.com \
    -n $NAMESPACE

# Adicionar o secret ao service account
echo -e "${YELLOW}🔗 Adicionando secret ao ServiceAccount...${NC}"
oc patch serviceaccount resource-governance-sa -n $NAMESPACE -p '{"imagePullSecrets": [{"name": "'$SECRET_NAME'"}]}'

echo -e "${GREEN}✅ ImagePullSecret configurado com sucesso!${NC}"
echo -e "${BLUE}📋 Secret criado: $SECRET_NAME${NC}"
echo -e "${BLUE}📋 Namespace: $NAMESPACE${NC}"
echo -e "${BLUE}📋 ServiceAccount atualizado: resource-governance-sa${NC}"