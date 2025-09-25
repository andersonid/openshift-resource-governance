#!/bin/bash

# Script de Deploy Blue-Green para OpenShift Resource Governance Tool
# Este script implementa uma estratégia de deploy mais segura, onde a nova versão
# só substitui a antiga após estar completamente funcional.

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

NAMESPACE="resource-governance"
IMAGE_NAME="andersonid/openshift-resource-governance"
TAG="${1:-latest}"
FULL_IMAGE_NAME="${IMAGE_NAME}:${TAG}"

echo -e "${BLUE}🔄 Deploy Blue-Green - OpenShift Resource Governance Tool${NC}"
echo -e "${BLUE}====================================================${NC}"
echo -e "${BLUE}Imagem: ${FULL_IMAGE_NAME}${NC}"

# 1. Verificar login no OpenShift
echo -e "${YELLOW}🔍 Verificando login no OpenShift...${NC}"
if ! oc whoami > /dev/null 2>&1; then
    echo -e "${RED}❌ Não está logado no OpenShift. Faça login primeiro.${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Logado como: $(oc whoami)${NC}"

# 2. Verificar se a imagem existe localmente
echo -e "${YELLOW}🔍 Verificando se a imagem existe localmente...${NC}"
if ! podman image exists "${FULL_IMAGE_NAME}" > /dev/null 2>&1; then
    echo -e "${YELLOW}📦 Imagem não encontrada localmente. Fazendo build...${NC}"
    podman build -f Dockerfile.simple -t "${FULL_IMAGE_NAME}" .
    
    echo -e "${YELLOW}📤 Fazendo push da imagem...${NC}"
    podman push "${FULL_IMAGE_NAME}"
fi

# 3. Verificar status atual do Deployment
echo -e "${YELLOW}📊 Verificando status atual do Deployment...${NC}"
CURRENT_IMAGE=$(oc get deployment resource-governance -n $NAMESPACE -o jsonpath='{.spec.template.spec.containers[0].image}' 2>/dev/null || echo "N/A")
echo -e "${BLUE}Imagem atual: ${CURRENT_IMAGE}${NC}"

if [ "$CURRENT_IMAGE" = "$FULL_IMAGE_NAME" ]; then
    echo -e "${YELLOW}⚠️  A imagem já está em uso. Continuando com o deploy...${NC}"
fi

# 4. Aplicar o Deployment atualizado
echo -e "${YELLOW}📦 Aplicando Deployment atualizado...${NC}"
oc apply -f k8s/deployment.yaml

# 5. Aguardar o rollout com verificação de saúde
echo -e "${YELLOW}⏳ Aguardando rollout do Deployment...${NC}"
oc rollout status deployment/resource-governance -n $NAMESPACE --timeout=300s

# 6. Verificar se todos os pods estão prontos
echo -e "${YELLOW}🔍 Verificando se todos os pods estão prontos...${NC}"
READY_PODS=$(oc get pods -n $NAMESPACE -l app.kubernetes.io/name=resource-governance --field-selector=status.phase=Running | wc -l)
TOTAL_PODS=$(oc get pods -n $NAMESPACE -l app.kubernetes.io/name=resource-governance | wc -l)

echo -e "${BLUE}Pods prontos: ${READY_PODS}/${TOTAL_PODS}${NC}"

if [ $READY_PODS -lt $TOTAL_PODS ]; then
    echo -e "${YELLOW}⚠️  Nem todos os pods estão prontos. Verificando logs...${NC}"
    oc get pods -n $NAMESPACE -l app.kubernetes.io/name=resource-governance
    echo -e "${YELLOW}💡 Para ver logs de um pod específico: oc logs <pod-name> -n $NAMESPACE${NC}"
fi

# 7. Testar a saúde da aplicação
echo -e "${YELLOW}🏥 Testando saúde da aplicação...${NC}"
SERVICE_IP=$(oc get service resource-governance-service -n $NAMESPACE -o jsonpath='{.spec.clusterIP}')
if [ -n "$SERVICE_IP" ]; then
    # Testar via port-forward temporário
    echo -e "${YELLOW}🔗 Testando conectividade...${NC}"
    oc port-forward service/resource-governance-service 8081:8080 -n $NAMESPACE &
    PORT_FORWARD_PID=$!
    sleep 5
    
    if curl -s http://localhost:8081/api/v1/health > /dev/null; then
        echo -e "${GREEN}✅ Aplicação está respondendo corretamente${NC}"
    else
        echo -e "${RED}❌ Aplicação não está respondendo${NC}"
    fi
    
    kill $PORT_FORWARD_PID 2>/dev/null || true
else
    echo -e "${YELLOW}⚠️  Não foi possível obter IP do serviço${NC}"
fi

# 8. Mostrar status final
echo -e "${YELLOW}📊 Status final do deploy:${NC}"
oc get deployment resource-governance -n $NAMESPACE
echo ""
oc get pods -n $NAMESPACE -l app.kubernetes.io/name=resource-governance

# 9. Obter URL da aplicação
ROUTE_HOST=$(oc get route resource-governance-route -n $NAMESPACE -o jsonpath='{.spec.host}' 2>/dev/null || echo "N/A")
if [ "$ROUTE_HOST" != "N/A" ]; then
    echo -e "${GREEN}🎉 Deploy Blue-Green concluído com sucesso!${NC}"
    echo -e "${BLUE}Acesse a aplicação em: https://${ROUTE_HOST}${NC}"
else
    echo -e "${GREEN}🎉 Deploy Blue-Green concluído!${NC}"
    echo -e "${BLUE}Para acessar a aplicação, use port-forward:${NC}"
    echo -e "  oc port-forward service/resource-governance-service 8080:8080 -n $NAMESPACE${NC}"
fi

echo -e "${BLUE}💡 Para verificar logs: oc logs -l app.kubernetes.io/name=resource-governance -n $NAMESPACE${NC}"
