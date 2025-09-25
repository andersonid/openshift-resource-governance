#!/bin/bash

# Script para migrar de DaemonSet para Deployment
# Este script remove o DaemonSet e cria um Deployment mais eficiente

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

NAMESPACE="resource-governance"

echo -e "${BLUE}🔄 Migração DaemonSet → Deployment${NC}"
echo -e "${BLUE}====================================${NC}"

# 1. Verificar login no OpenShift
echo -e "${YELLOW}🔍 Verificando login no OpenShift...${NC}"
if ! oc whoami > /dev/null 2>&1; then
    echo -e "${RED}❌ Não está logado no OpenShift. Faça login primeiro.${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Logado como: $(oc whoami)${NC}"

# 2. Verificar status atual
echo -e "${YELLOW}📊 Status atual do DaemonSet...${NC}"
oc get daemonset resource-governance -n $NAMESPACE 2>/dev/null || echo "DaemonSet não encontrado"

# 3. Criar Deployment
echo -e "${YELLOW}📦 Criando Deployment...${NC}"
oc apply -f k8s/deployment.yaml

# 4. Aguardar Deployment ficar pronto
echo -e "${YELLOW}⏳ Aguardando Deployment ficar pronto...${NC}"
oc rollout status deployment/resource-governance -n $NAMESPACE --timeout=120s

# 5. Verificar se pods estão rodando
echo -e "${YELLOW}🔍 Verificando pods do Deployment...${NC}"
oc get pods -n $NAMESPACE -l app.kubernetes.io/name=resource-governance

# 6. Testar aplicação
echo -e "${YELLOW}🏥 Testando aplicação...${NC}"
oc port-forward service/resource-governance-service 8081:8080 -n $NAMESPACE &
PORT_FORWARD_PID=$!
sleep 5

if curl -s http://localhost:8081/api/v1/health > /dev/null; then
    echo -e "${GREEN}✅ Aplicação está funcionando corretamente${NC}"
else
    echo -e "${RED}❌ Aplicação não está respondendo${NC}"
fi

kill $PORT_FORWARD_PID 2>/dev/null || true

# 7. Remover DaemonSet (se existir)
echo -e "${YELLOW}🗑️  Removendo DaemonSet...${NC}"
oc delete daemonset resource-governance -n $NAMESPACE --ignore-not-found=true

# 8. Status final
echo -e "${YELLOW}📊 Status final:${NC}"
echo -e "${BLUE}Deployment:${NC}"
oc get deployment resource-governance -n $NAMESPACE
echo ""
echo -e "${BLUE}Pods:${NC}"
oc get pods -n $NAMESPACE -l app.kubernetes.io/name=resource-governance

# 9. Mostrar benefícios
echo -e "${GREEN}🎉 Migração concluída com sucesso!${NC}"
echo -e "${BLUE}💡 Benefícios do Deployment:${NC}"
echo -e "  ✅ Mais eficiente (2 pods vs 6 pods)"
echo -e "  ✅ Escalável (pode ajustar replicas)"
echo -e "  ✅ Rolling Updates nativos"
echo -e "  ✅ Health checks automáticos"
echo -e "  ✅ Menor consumo de recursos"

echo -e "${BLUE}🔧 Para escalar: oc scale deployment resource-governance --replicas=3 -n $NAMESPACE${NC}"
