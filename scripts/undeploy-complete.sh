#!/bin/bash

# Complete undeploy script for OpenShift Resource Governance Tool
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="resource-governance"

echo -e "${BLUE}Undeploy - OpenShift Resource Governance Tool${NC}"
echo -e "${BLUE}============================================${NC}"

# Check if logged into OpenShift
if ! oc whoami > /dev/null 2>&1; then
    echo -e "${RED}ERROR: Not logged into OpenShift. Please login first.${NC}"
    exit 1
fi

echo -e "${GREEN}SUCCESS: Logged in as: $(oc whoami)${NC}"

# Confirm removal
echo -e "${YELLOW}WARNING: Are you sure you want to remove the application from namespace '$NAMESPACE'?${NC}"
read -p "Type 'yes' to confirm: " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo -e "${YELLOW}Operation cancelled.${NC}"
    exit 0
fi

# Remove resources
echo -e "${YELLOW}Removing resources...${NC}"

# Remove Route
echo -e "${YELLOW}  Removing Route...${NC}"
oc delete -f k8s/route.yaml --ignore-not-found=true

# Remove Service
echo -e "${YELLOW}  Removing Service...${NC}"
oc delete -f k8s/service.yaml --ignore-not-found=true

# Remove Deployment
echo -e "${YELLOW}  Removing Deployment...${NC}"
oc delete -f k8s/deployment.yaml --ignore-not-found=true

# Wait for pods to be removed
echo -e "${YELLOW}  Waiting for pods to be removed...${NC}"
oc wait --for=delete pod -l app.kubernetes.io/name=resource-governance -n $NAMESPACE --timeout=60s || true

# Remove ConfigMap
echo -e "${YELLOW}  Removing ConfigMap...${NC}"
oc delete -f k8s/configmap.yaml --ignore-not-found=true

# Remove RBAC (cluster resources)
echo -e "${YELLOW}  Removing RBAC (ServiceAccount, ClusterRole, ClusterRoleBinding)...${NC}"
oc delete -f k8s/rbac.yaml --ignore-not-found=true

# Remove cluster resources manually (in case namespace was already removed)
echo -e "${YELLOW}  Removing ClusterRole and ClusterRoleBinding...${NC}"
oc delete clusterrole resource-governance-role --ignore-not-found=true
oc delete clusterrolebinding resource-governance-binding --ignore-not-found=true
oc delete clusterrolebinding resource-governance-monitoring --ignore-not-found=true

# Remove ServiceAccount (if still exists)
echo -e "${YELLOW}  Removing ServiceAccount...${NC}"
oc delete serviceaccount resource-governance-sa -n $NAMESPACE --ignore-not-found=true

# Remove namespace (optional)
echo -e "${YELLOW}  Removing namespace...${NC}"
oc delete -f k8s/namespace.yaml --ignore-not-found=true

echo -e "${GREEN}SUCCESS: Undeploy completed successfully!${NC}"
echo -e "${BLUE}============================================${NC}"
echo -e "${GREEN}SUCCESS: All resources have been removed${NC}"
echo -e "${GREEN}SUCCESS: Namespace '$NAMESPACE' has been removed${NC}"
echo -e "${BLUE}============================================${NC}"
