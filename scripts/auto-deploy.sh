#!/bin/bash

# Auto-deploy script after GitHub Actions
# This script can be executed locally or via webhook

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
IMAGE_NAME="resource-governance"
REGISTRY="andersonid"
NAMESPACE="resource-governance"
IMAGE_TAG=${1:-latest}

echo -e "${BLUE}Auto-Deploy to OpenShift${NC}"
echo "================================"
echo "Image: ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
echo "Namespace: ${NAMESPACE}"
echo ""

# 1. Check OpenShift login
if ! oc whoami > /dev/null 2>&1; then
  echo -e "${RED}ERROR: Not logged into OpenShift. Please login with 'oc login'.${NC}"
  exit 1
fi
echo -e "${GREEN}SUCCESS: Logged into OpenShift as: $(oc whoami)${NC}"
echo ""

# 2. Check if image exists on Docker Hub
echo -e "${BLUE}Checking image on Docker Hub...${NC}"
if ! skopeo inspect docker://${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG} > /dev/null 2>&1; then
  echo -e "${RED}ERROR: Image ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG} not found on Docker Hub!${NC}"
  exit 1
fi
echo -e "${GREEN}SUCCESS: Image found on Docker Hub${NC}"
echo ""

# 3. Check if namespace exists
if ! oc get namespace ${NAMESPACE} > /dev/null 2>&1; then
  echo -e "${BLUE}Creating namespace ${NAMESPACE}...${NC}"
  oc create namespace ${NAMESPACE}
else
  echo -e "${GREEN}SUCCESS: Namespace ${NAMESPACE} already exists${NC}"
fi
echo ""

# 4. Apply basic manifests
echo -e "${BLUE}Applying basic manifests...${NC}"
oc apply -f k8s/rbac.yaml -n ${NAMESPACE}
oc apply -f k8s/configmap.yaml -n ${NAMESPACE}
echo ""

# 5. Check if deployment exists
if oc get deployment ${IMAGE_NAME} -n ${NAMESPACE} > /dev/null 2>&1; then
  echo -e "${BLUE}Existing deployment found. Starting update...${NC}"
  
  # Get current image
  CURRENT_IMAGE=$(oc get deployment ${IMAGE_NAME} -n ${NAMESPACE} -o jsonpath='{.spec.template.spec.containers[0].image}')
  echo "Current image: ${CURRENT_IMAGE}"
  echo "New image: ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
  
  # Check if image changed
  if [ "${CURRENT_IMAGE}" = "${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}" ]; then
    echo -e "${YELLOW}WARNING: Image already up to date. No action needed.${NC}"
    exit 0
  fi
  
  # Update deployment with new image
  echo -e "${BLUE}Updating deployment image...${NC}"
  oc set image deployment/${IMAGE_NAME} ${IMAGE_NAME}=${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG} -n ${NAMESPACE}
  
  # Wait for rollout
  echo -e "${BLUE}Waiting for rollout (may take a few minutes)...${NC}"
  oc rollout status deployment/${IMAGE_NAME} -n ${NAMESPACE} --timeout=300s
  echo -e "${GREEN}SUCCESS: Rollout completed successfully!${NC}"
  
else
  echo -e "${BLUE}Deployment not found. Creating new deployment...${NC}"
  # Apply deployment, service and route
  oc apply -f k8s/deployment.yaml -n ${NAMESPACE}
  oc apply -f k8s/service.yaml -n ${NAMESPACE}
  oc apply -f k8s/route.yaml -n ${NAMESPACE}
  
  # Wait for initial rollout
  echo -e "${BLUE}Waiting for initial rollout...${NC}"
  oc rollout status deployment/${IMAGE_NAME} -n ${NAMESPACE} --timeout=300s
  echo -e "${GREEN}SUCCESS: Initial rollout completed successfully!${NC}"
fi
echo ""

# 6. Check final status
echo -e "${BLUE}FINAL STATUS:${NC}"
echo "================"
oc get deployment ${IMAGE_NAME} -n ${NAMESPACE}
echo ""
oc get pods -n ${NAMESPACE} -l app.kubernetes.io/name=${IMAGE_NAME}
echo ""

# 7. Get access URLs
ROUTE_URL=$(oc get route ${IMAGE_NAME}-route -n ${NAMESPACE} -o jsonpath='{.spec.host}' 2>/dev/null || echo "")
echo -e "${BLUE}Access URLs:${NC}"
if [ -n "$ROUTE_URL" ]; then
  echo "   OpenShift: https://$ROUTE_URL"
else
  echo "   OpenShift: Route not found or not available."
fi
echo "   Port-forward: http://localhost:8080 (if active)"
echo ""

echo -e "${GREEN}SUCCESS: Auto-deploy completed successfully!${NC}"
echo -e "${BLUE}Strategy: Rolling Update with maxUnavailable=0 (zero downtime)${NC}"
