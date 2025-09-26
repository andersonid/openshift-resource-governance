#!/bin/bash

# Setup script for OpenShift Resource Governance Tool
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Setting up OpenShift Resource Governance Tool${NC}"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}ERROR: Python 3 is not installed.${NC}"
    echo -e "${YELLOW}Install Python 3.11+ and try again.${NC}"
    exit 1
fi

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo -e "${RED}ERROR: pip3 is not installed.${NC}"
    echo -e "${YELLOW}Install pip3 and try again.${NC}"
    exit 1
fi

# Install Python dependencies
echo -e "${YELLOW}Installing Python dependencies...${NC}"
pip3 install -r requirements.txt

# Make scripts executable
echo -e "${YELLOW}Making scripts executable...${NC}"
chmod +x scripts/*.sh

# Create reports directory
echo -e "${YELLOW}Creating reports directory...${NC}"
mkdir -p reports

# Check if Docker is installed
if command -v docker &> /dev/null; then
    echo -e "${GREEN}SUCCESS: Docker found${NC}"
else
    echo -e "${YELLOW}WARNING: Docker not found. Install to build image.${NC}"
fi

# Check if oc is installed
if command -v oc &> /dev/null; then
    echo -e "${GREEN}SUCCESS: OpenShift CLI (oc) found${NC}"
else
    echo -e "${YELLOW}WARNING: OpenShift CLI (oc) not found. Install to deploy.${NC}"
fi

echo -e "${GREEN}SUCCESS: Setup completed successfully!${NC}"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo -e "1. ${YELLOW}Local development:${NC} make dev"
echo -e "2. ${YELLOW}Build image:${NC} make build"
echo -e "3. ${YELLOW}Deploy to OpenShift:${NC} make deploy"
echo -e "4. ${YELLOW}View documentation:${NC} cat README.md"
echo ""
echo -e "${BLUE}Useful commands:${NC}"
echo -e "  make help     - Show all commands"
echo -e "  make test     - Run tests"
echo -e "  make logs     - View application logs"
echo -e "  make status   - View application status"
