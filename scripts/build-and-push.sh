#!/bin/bash

# Build and push script for OpenShift Resource Governance Tool using Podman
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
IMAGE_NAME="resource-governance"
TAG="${1:-latest}"
REGISTRY="${2:-quay.io/rh_ee_anobre}"
FULL_IMAGE_NAME="${REGISTRY}/${IMAGE_NAME}:${TAG}"

echo -e "${BLUE}Building and Pushing OpenShift Resource Governance Tool${NC}"
echo -e "${BLUE}Image: ${FULL_IMAGE_NAME}${NC}"

# Check if Podman is installed
if ! command -v podman &> /dev/null; then
    echo -e "${RED}ERROR: Podman is not installed. Please install Podman and try again.${NC}"
    exit 1
fi

# Buildah is optional, Podman can do the build

# Build image
echo -e "${YELLOW}Building container image with Podman...${NC}"
podman build -t "${FULL_IMAGE_NAME}" .

if [ $? -eq 0 ]; then
    echo -e "${GREEN}SUCCESS: Image built successfully!${NC}"
else
    echo -e "${RED}ERROR: Build failed!${NC}"
    exit 1
fi

# Test image
echo -e "${YELLOW}Testing image...${NC}"
podman run --rm "${FULL_IMAGE_NAME}" python -c "import app.main; print('SUCCESS: App imports successfully')"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}SUCCESS: Image test passed!${NC}"
else
    echo -e "${RED}ERROR: Image test failed!${NC}"
    exit 1
fi

# Login to Quay.io
echo -e "${YELLOW}Logging into Quay.io...${NC}"
echo -e "${YELLOW}Please ensure you have logged in with: podman login quay.io${NC}"

# Check if already logged in
if podman search quay.io/rh_ee_anobre/resource-governance > /dev/null 2>&1; then
    echo -e "${GREEN}SUCCESS: Already logged in to Quay.io${NC}"
else
    echo -e "${RED}ERROR: Not logged in to Quay.io. Please run: podman login quay.io${NC}"
    echo -e "${YELLOW}Then run this script again.${NC}"
    exit 1
fi

# Push image
echo -e "${YELLOW}Pushing image to Quay.io...${NC}"
podman push "${FULL_IMAGE_NAME}"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}SUCCESS: Image pushed successfully!${NC}"
else
    echo -e "${RED}ERROR: Push failed!${NC}"
    exit 1
fi

# Show image information
echo -e "${BLUE}Image information:${NC}"
podman images "${FULL_IMAGE_NAME}"

echo -e "${GREEN}SUCCESS: Build and push completed successfully!${NC}"
echo -e "${BLUE}Image available at: https://quay.io/repository/${REGISTRY#quay.io/}/${IMAGE_NAME}${NC}"
echo -e "${BLUE}Ready for deployment!${NC}"
echo -e "${BLUE}Registry: Quay.io (public repository)${NC}"
