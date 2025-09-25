#!/bin/bash

# Script de build para OpenShift Resource Governance Tool
set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configurações
IMAGE_NAME="resource-governance"
TAG="${1:-latest}"
REGISTRY="${2:-andersonid}"
FULL_IMAGE_NAME="${REGISTRY}/${IMAGE_NAME}:${TAG}"

echo -e "${BLUE}🚀 Building OpenShift Resource Governance Tool${NC}"
echo -e "${BLUE}Image: ${FULL_IMAGE_NAME}${NC}"

# Verificar se Docker está rodando
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ Docker não está rodando. Inicie o Docker e tente novamente.${NC}"
    exit 1
fi

# Build da imagem
echo -e "${YELLOW}📦 Building Docker image...${NC}"
docker build -t "${FULL_IMAGE_NAME}" .

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Image built successfully!${NC}"
else
    echo -e "${RED}❌ Build failed!${NC}"
    exit 1
fi

# Testar a imagem
echo -e "${YELLOW}🧪 Testing image...${NC}"
docker run --rm "${FULL_IMAGE_NAME}" python -c "import app.main; print('✅ App imports successfully')"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Image test passed!${NC}"
else
    echo -e "${RED}❌ Image test failed!${NC}"
    exit 1
fi

# Mostrar informações da imagem
echo -e "${BLUE}📊 Image information:${NC}"
docker images "${FULL_IMAGE_NAME}"

echo -e "${GREEN}🎉 Build completed successfully!${NC}"
echo -e "${BLUE}To push to registry:${NC}"
echo -e "  docker push ${FULL_IMAGE_NAME}"
echo -e "${BLUE}To run locally:${NC}"
echo -e "  docker run -p 8080:8080 ${FULL_IMAGE_NAME}"
