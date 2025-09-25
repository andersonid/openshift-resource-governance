#!/bin/bash

# Script de undeploy para OpenShift Resource Governance Tool
set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configurações
NAMESPACE="resource-governance"

echo -e "${BLUE}🗑️  Undeploying OpenShift Resource Governance Tool${NC}"
echo -e "${BLUE}Namespace: ${NAMESPACE}${NC}"

# Verificar se oc está instalado
if ! command -v oc &> /dev/null; then
    echo -e "${RED}❌ OpenShift CLI (oc) não está instalado.${NC}"
    exit 1
fi

# Verificar se está logado no OpenShift
if ! oc whoami &> /dev/null; then
    echo -e "${RED}❌ Não está logado no OpenShift.${NC}"
    echo -e "${YELLOW}Faça login com: oc login <cluster-url>${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Logado como: $(oc whoami)${NC}"

# Confirmar remoção
read -p "Tem certeza que deseja remover a aplicação? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}❌ Operação cancelada.${NC}"
    exit 0
fi

# Remover Route
echo -e "${YELLOW}🛣️  Removing Route...${NC}"
oc delete -f k8s/route.yaml --ignore-not-found=true

# Remover Service
echo -e "${YELLOW}🌐 Removing Service...${NC}"
oc delete -f k8s/service.yaml --ignore-not-found=true

# Remover DaemonSet
echo -e "${YELLOW}📦 Removing DaemonSet...${NC}"
oc delete -f k8s/daemonset.yaml --ignore-not-found=true

# Aguardar pods serem removidos
echo -e "${YELLOW}⏳ Waiting for pods to be terminated...${NC}"
oc wait --for=delete pod -l app.kubernetes.io/name=resource-governance -n "${NAMESPACE}" --timeout=60s || true

# Remover ConfigMap
echo -e "${YELLOW}⚙️  Removing ConfigMap...${NC}"
oc delete -f k8s/configmap.yaml --ignore-not-found=true

# Remover RBAC
echo -e "${YELLOW}🔐 Removing RBAC...${NC}"
oc delete -f k8s/rbac.yaml --ignore-not-found=true

# Remover namespace (opcional)
read -p "Deseja remover o namespace também? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}📁 Removing namespace...${NC}"
    oc delete -f k8s/namespace.yaml --ignore-not-found=true
    echo -e "${GREEN}✅ Namespace removed.${NC}"
else
    echo -e "${YELLOW}⚠️  Namespace mantido.${NC}"
fi

echo -e "${GREEN}🎉 Undeploy completed successfully!${NC}"

# Verificar se ainda há recursos
echo -e "${BLUE}🔍 Checking remaining resources:${NC}"
oc get all -n "${NAMESPACE}" 2>/dev/null || echo -e "${GREEN}✅ No resources found in namespace.${NC}"
