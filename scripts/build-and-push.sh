#!/bin/bash

# Script de build e push para OpenShift Resource Governance Tool usando Podman
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

echo -e "${BLUE}🚀 Building and Pushing OpenShift Resource Governance Tool${NC}"
echo -e "${BLUE}Image: ${FULL_IMAGE_NAME}${NC}"

# Verificar se Podman está instalado
if ! command -v podman &> /dev/null; then
    echo -e "${RED}❌ Podman não está instalado. Instale o Podman e tente novamente.${NC}"
    exit 1
fi

# Buildah é opcional, Podman pode fazer o build

# Build da imagem
echo -e "${YELLOW}📦 Building container image with Podman...${NC}"
podman build -t "${FULL_IMAGE_NAME}" .

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Image built successfully!${NC}"
else
    echo -e "${RED}❌ Build failed!${NC}"
    exit 1
fi

# Testar a imagem
echo -e "${YELLOW}🧪 Testing image...${NC}"
podman run --rm "${FULL_IMAGE_NAME}" python -c "import app.main; print('✅ App imports successfully')"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Image test passed!${NC}"
else
    echo -e "${RED}❌ Image test failed!${NC}"
    exit 1
fi

# Login no Docker Hub
echo -e "${YELLOW}🔐 Logging into Docker Hub...${NC}"
podman login docker.io

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Login successful!${NC}"
else
    echo -e "${RED}❌ Login failed!${NC}"
    exit 1
fi

# Push da imagem
echo -e "${YELLOW}📤 Pushing image to Docker Hub...${NC}"
podman push "${FULL_IMAGE_NAME}"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Image pushed successfully!${NC}"
else
    echo -e "${RED}❌ Push failed!${NC}"
    exit 1
fi

# Mostrar informações da imagem
echo -e "${BLUE}📊 Image information:${NC}"
podman images "${FULL_IMAGE_NAME}"

echo -e "${GREEN}🎉 Build and push completed successfully!${NC}"
echo -e "${BLUE}🌐 Image available at: https://hub.docker.com/r/${REGISTRY}/${IMAGE_NAME}${NC}"
echo -e "${BLUE}🚀 Ready for deployment!${NC}"
