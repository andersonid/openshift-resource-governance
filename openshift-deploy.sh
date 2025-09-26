#!/bin/bash

# Deploy script for OpenShift using GitHub
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REPO_URL="https://github.com/andersonid/openshift-resource-governance.git"
IMAGE_NAME="resource-governance"
REGISTRY="andersonid"
TAG="${1:-latest}"
NAMESPACE="resource-governance"

echo -e "${BLUE}Deploying OpenShift Resource Governance Tool from GitHub${NC}"
echo -e "${BLUE}Repository: ${REPO_URL}${NC}"
echo -e "${BLUE}Image: ${REGISTRY}/${IMAGE_NAME}:${TAG}${NC}"

# Check if oc is installed
if ! command -v oc &> /dev/null; then
    echo -e "${RED}ERROR: OpenShift CLI (oc) is not installed.${NC}"
    echo -e "${YELLOW}Install oc CLI: https://docs.openshift.com/container-platform/latest/cli_reference/openshift_cli/getting-started-cli.html${NC}"
    exit 1
fi

# Check if logged into OpenShift
if ! oc whoami &> /dev/null; then
    echo -e "${RED}ERROR: Not logged into OpenShift.${NC}"
    echo -e "${YELLOW}Login with: oc login <cluster-url>${NC}"
    exit 1
fi

echo -e "${GREEN}SUCCESS: Logged in as: $(oc whoami)${NC}"

# Create namespace if it doesn't exist
echo -e "${YELLOW}Creating namespace...${NC}"
oc apply -f k8s/namespace.yaml

# Apply RBAC
echo -e "${YELLOW}Applying RBAC...${NC}"
oc apply -f k8s/rbac.yaml

# Apply ConfigMap
echo -e "${YELLOW}Applying ConfigMap...${NC}"
oc apply -f k8s/configmap.yaml

# Update image in DaemonSet
echo -e "${YELLOW}Updating image in DaemonSet...${NC}"
oc set image daemonset/${IMAGE_NAME} ${IMAGE_NAME}="${REGISTRY}/${IMAGE_NAME}:${TAG}" -n "${NAMESPACE}" || true

# Apply DaemonSet
echo -e "${YELLOW}Applying DaemonSet...${NC}"
oc apply -f k8s/daemonset.yaml

# Apply Service
echo -e "${YELLOW}Applying Service...${NC}"
oc apply -f k8s/service.yaml

# Apply Route
echo -e "${YELLOW}Applying Route...${NC}"
oc apply -f k8s/route.yaml

# Wait for pods to be ready
echo -e "${YELLOW}Waiting for pods to be ready...${NC}"
oc wait --for=condition=ready pod -l app.kubernetes.io/name=${IMAGE_NAME} -n "${NAMESPACE}" --timeout=300s

# Get route URL
ROUTE_URL=$(oc get route ${IMAGE_NAME}-route -n "${NAMESPACE}" -o jsonpath='{.spec.host}')
if [ -n "${ROUTE_URL}" ]; then
    echo -e "${GREEN}SUCCESS: Deploy completed successfully!${NC}"
    echo -e "${BLUE}Application URL: https://${ROUTE_URL}${NC}"
    echo -e "${BLUE}GitHub Repository: ${REPO_URL}${NC}"
else
    echo -e "${YELLOW}WARNING: Deploy completed, but route URL not found.${NC}"
    echo -e "${BLUE}Check with: oc get routes -n ${NAMESPACE}${NC}"
fi

# Show status
echo -e "${BLUE}Deployment status:${NC}"
oc get all -n "${NAMESPACE}"

echo -e "${BLUE}To check logs:${NC}"
echo -e "  oc logs -f daemonset/${IMAGE_NAME} -n ${NAMESPACE}"

echo -e "${BLUE}To test health:${NC}"
echo -e "  curl https://${ROUTE_URL}/health"

echo -e "${BLUE}To update from GitHub:${NC}"
echo -e "  git pull origin main"
echo -e "  ./openshift-deploy.sh <new-tag>"
