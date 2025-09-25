#!/bin/bash

# Script de setup para OpenShift Resource Governance Tool
set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Setting up OpenShift Resource Governance Tool${NC}"

# Verificar se Python está instalado
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 não está instalado.${NC}"
    echo -e "${YELLOW}Instale Python 3.11+ e tente novamente.${NC}"
    exit 1
fi

# Verificar se pip está instalado
if ! command -v pip3 &> /dev/null; then
    echo -e "${RED}❌ pip3 não está instalado.${NC}"
    echo -e "${YELLOW}Instale pip3 e tente novamente.${NC}"
    exit 1
fi

# Instalar dependências Python
echo -e "${YELLOW}📦 Installing Python dependencies...${NC}"
pip3 install -r requirements.txt

# Tornar scripts executáveis
echo -e "${YELLOW}🔧 Making scripts executable...${NC}"
chmod +x scripts/*.sh

# Criar diretório de relatórios
echo -e "${YELLOW}📁 Creating reports directory...${NC}"
mkdir -p reports

# Verificar se Docker está instalado
if command -v docker &> /dev/null; then
    echo -e "${GREEN}✅ Docker encontrado${NC}"
else
    echo -e "${YELLOW}⚠️  Docker não encontrado. Instale para fazer build da imagem.${NC}"
fi

# Verificar se oc está instalado
if command -v oc &> /dev/null; then
    echo -e "${GREEN}✅ OpenShift CLI (oc) encontrado${NC}"
else
    echo -e "${YELLOW}⚠️  OpenShift CLI (oc) não encontrado. Instale para fazer deploy.${NC}"
fi

echo -e "${GREEN}🎉 Setup completed successfully!${NC}"
echo ""
echo -e "${BLUE}Próximos passos:${NC}"
echo -e "1. ${YELLOW}Desenvolvimento local:${NC} make dev"
echo -e "2. ${YELLOW}Build da imagem:${NC} make build"
echo -e "3. ${YELLOW}Deploy no OpenShift:${NC} make deploy"
echo -e "4. ${YELLOW}Ver documentação:${NC} cat README.md"
echo ""
echo -e "${BLUE}Comandos úteis:${NC}"
echo -e "  make help     - Mostrar todos os comandos"
echo -e "  make test     - Executar testes"
echo -e "  make logs     - Ver logs da aplicação"
echo -e "  make status   - Ver status da aplicação"
