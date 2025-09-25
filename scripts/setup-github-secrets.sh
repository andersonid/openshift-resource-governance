#!/bin/bash

# Script para configurar secrets do GitHub Actions
# Este script ajuda a configurar os secrets necessários para CI/CD

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔐 Configuração de Secrets para GitHub Actions${NC}"
echo -e "${BLUE}============================================${NC}"

echo -e "${YELLOW}📋 Secrets necessários no GitHub:${NC}"
echo ""
echo -e "${BLUE}1. DOCKERHUB_USERNAME${NC}"
echo -e "   Seu usuário do Docker Hub"
echo ""
echo -e "${BLUE}2. DOCKERHUB_TOKEN${NC}"
echo -e "   Token de acesso do Docker Hub (não a senha!)"
echo "   Crie em: https://hub.docker.com/settings/security"
echo ""
echo -e "${BLUE}3. OPENSHIFT_SERVER${NC}"
echo -e "   URL do seu cluster OpenShift"
echo "   Exemplo: https://api.openshift.example.com:6443"
echo ""
echo -e "${BLUE}4. OPENSHIFT_TOKEN${NC}"
echo -e "   Token de acesso do OpenShift"
echo "   Obtenha com: oc whoami -t"
echo ""

# Verificar se está logado no OpenShift
if oc whoami > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Logado no OpenShift como: $(oc whoami)${NC}"
    
    # Obter informações do cluster
    CLUSTER_SERVER=$(oc config view --minify -o jsonpath='{.clusters[0].cluster.server}' 2>/dev/null || echo "N/A")
    if [ "$CLUSTER_SERVER" != "N/A" ]; then
        echo -e "${BLUE}🌐 Servidor OpenShift: ${CLUSTER_SERVER}${NC}"
    fi
    
    # Obter token
    OPENSHIFT_TOKEN=$(oc whoami -t 2>/dev/null || echo "N/A")
    if [ "$OPENSHIFT_TOKEN" != "N/A" ]; then
        echo -e "${BLUE}🔑 Token OpenShift: ${OPENSHIFT_TOKEN:0:20}...${NC}"
    fi
else
    echo -e "${RED}❌ Não está logado no OpenShift${NC}"
    echo -e "${YELLOW}💡 Faça login primeiro: oc login <server>${NC}"
fi

echo ""
echo -e "${YELLOW}📝 Como configurar os secrets no GitHub:${NC}"
echo ""
echo -e "${BLUE}1. Acesse: https://github.com/andersonid/openshift-resource-governance/settings/secrets/actions${NC}"
echo ""
echo -e "${BLUE}2. Clique em 'New repository secret' para cada um:${NC}"
echo ""
echo -e "${GREEN}DOCKERHUB_USERNAME${NC}"
echo -e "   Valor: seu-usuario-dockerhub"
echo ""
echo -e "${GREEN}DOCKERHUB_TOKEN${NC}"
echo -e "   Valor: dckr_pat_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
echo ""
echo -e "${GREEN}OPENSHIFT_SERVER${NC}"
echo -e "   Valor: ${CLUSTER_SERVER}"
echo ""
echo -e "${GREEN}OPENSHIFT_TOKEN${NC}"
echo -e "   Valor: ${OPENSHIFT_TOKEN}"
echo ""

echo -e "${YELLOW}🚀 Após configurar os secrets:${NC}"
echo ""
echo -e "${BLUE}1. Faça commit e push das mudanças:${NC}"
echo -e "   git add ."
echo -e "   git commit -m 'Add GitHub Actions for auto-deploy'"
echo -e "   git push origin main"
echo ""
echo -e "${BLUE}2. O GitHub Actions irá:${NC}"
echo -e "   ✅ Buildar a imagem automaticamente"
echo -e "   ✅ Fazer push para Docker Hub"
echo -e "   ✅ Fazer deploy no OpenShift"
echo -e "   ✅ Atualizar o deployment com a nova imagem"
echo ""

echo -e "${GREEN}🎉 Configuração concluída!${NC}"
echo -e "${BLUE}💡 Para testar: faça uma mudança no código e faça push para main${NC}"
