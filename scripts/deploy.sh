#!/bin/bash

# Deploy script for OpenShift Resource Governance Tool
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="resource-governance"
IMAGE_NAME="resource-governance"
TAG="${1:-latest}"
REGISTRY="${2:-andersonid}"
FULL_IMAGE_NAME="${REGISTRY}/${IMAGE_NAME}:${TAG}"

echo -e "${BLUE}Deploying OpenShift Resource Governance Tool${NC}"
echo -e "${BLUE}Namespace: ${NAMESPACE}${NC}"
echo -e "${BLUE}Image: ${FULL_IMAGE_NAME}${NC}"

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
oc set image daemonset/resource-governance resource-governance="${FULL_IMAGE_NAME}" -n "${NAMESPACE}"

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
oc wait --for=condition=ready pod -l app.kubernetes.io/name=resource-governance -n "${NAMESPACE}" --timeout=300s

# Get route URL
ROUTE_URL=$(oc get route resource-governance-route -n "${NAMESPACE}" -o jsonpath='{.spec.host}')
if [ -n "${ROUTE_URL}" ]; then
    echo -e "${GREEN}SUCCESS: Deploy completed successfully!${NC}"
    echo -e "${BLUE}Application URL: https://${ROUTE_URL}${NC}"
else
    echo -e "${YELLOW}WARNING: Deploy completed, but route URL not found.${NC}"
    echo -e "${BLUE}Check with: oc get routes -n ${NAMESPACE}${NC}"
fi

# Show status
echo -e "${BLUE}Deployment status:${NC}"
oc get all -n "${NAMESPACE}"

echo -e "${BLUE}To check logs:${NC}"
echo -e "  oc logs -f daemonset/resource-governance -n ${NAMESPACE}"

echo -e "${BLUE}To test health:${NC}"
echo -e "  curl https://${ROUTE_URL}/health"
