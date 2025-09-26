#!/bin/bash

# Build script for OpenShift Resource Governance Tool
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
REGISTRY="${2:-andersonid}"
FULL_IMAGE_NAME="${REGISTRY}/${IMAGE_NAME}:${TAG}"

echo -e "${BLUE}Building OpenShift Resource Governance Tool${NC}"
echo -e "${BLUE}Image: ${FULL_IMAGE_NAME}${NC}"

# Check if Podman is installed
if ! command -v podman &> /dev/null; then
    echo -e "${RED}ERROR: Podman is not installed. Install Podman and try again.${NC}"
    exit 1
fi

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

# Show image information
echo -e "${BLUE}Image information:${NC}"
podman images "${FULL_IMAGE_NAME}"

echo -e "${GREEN}SUCCESS: Build completed successfully!${NC}"
echo -e "${BLUE}To push to registry:${NC}"
echo -e "  podman push ${FULL_IMAGE_NAME}"
echo -e "${BLUE}To run locally:${NC}"
echo -e "  podman run -p 8080:8080 ${FULL_IMAGE_NAME}"
