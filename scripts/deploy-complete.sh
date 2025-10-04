#!/bin/bash

# Complete deployment script for OpenShift Resource Governance Tool
# Includes namespace creation, RBAC, ConfigMap, Secret and Deployment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="resource-governance"
SERVICE_ACCOUNT="resource-governance-sa"
SECRET_NAME="resource-governance-sa-token"

echo -e "${BLUE}Deploying OpenShift Resource Governance Tool${NC}"

# Check if connected to cluster
if ! oc whoami > /dev/null 2>&1; then
    echo -e "${RED}ERROR: Not connected to OpenShift cluster. Please run 'oc login' first.${NC}"
    exit 1
fi

echo -e "${GREEN}SUCCESS: Connected to OpenShift cluster as $(oc whoami)${NC}"

# Create namespace if it doesn't exist
echo -e "${YELLOW}Creating namespace...${NC}"
oc create namespace $NAMESPACE --dry-run=client -o yaml | oc apply -f -

# Apply RBAC
echo -e "${YELLOW}Applying RBAC...${NC}"
oc apply -f k8s/rbac.yaml

# Apply ConfigMap
echo -e "${YELLOW}Applying ConfigMap...${NC}"
oc apply -f k8s/configmap.yaml

# Create ServiceAccount token secret
echo -e "${YELLOW}Creating ServiceAccount token...${NC}"

# Check if secret already exists
if oc get secret $SECRET_NAME -n $NAMESPACE > /dev/null 2>&1; then
    echo -e "${YELLOW}WARNING: Secret $SECRET_NAME already exists, skipping creation${NC}"
else
    # Create ServiceAccount token
    TOKEN=$(oc create token $SERVICE_ACCOUNT -n $NAMESPACE --duration=8760h)
    
    # Create secret with token
    oc create secret generic $SECRET_NAME -n $NAMESPACE \
        --from-literal=token="$TOKEN" \
        --from-literal=ca.crt="$(oc get secret -n $NAMESPACE -o jsonpath='{.items[0].data.ca\.crt}' | base64 -d)" \
        --from-literal=namespace="$NAMESPACE"
    
    echo -e "${GREEN}SUCCESS: ServiceAccount token created${NC}"
fi

# Apply Deployment
echo -e "${YELLOW}Applying Deployment...${NC}"
oc apply -f k8s/deployment.yaml

# Apply Service
echo -e "${YELLOW}Applying Service...${NC}"
oc apply -f k8s/service.yaml

# Create Route (let OpenShift generate host automatically)
echo -e "${YELLOW}Creating Route...${NC}"
oc expose service resource-governance-service -n $NAMESPACE --name=resource-governance-route --path=/

# Configure TLS for the route
echo -e "${YELLOW}Configuring TLS for Route...${NC}"
oc patch route resource-governance-route -n $NAMESPACE -p '{"spec":{"tls":{"termination":"edge","insecureEdgeTerminationPolicy":"Redirect"}}}'

# Wait for deployment to be ready
echo -e "${YELLOW}Waiting for deployment to be ready...${NC}"
oc rollout status deployment/resource-governance -n $NAMESPACE --timeout=300s

# Check pod status
echo -e "${YELLOW}Checking pod status...${NC}"
oc get pods -n $NAMESPACE -l app.kubernetes.io/name=resource-governance

# Check logs for errors
echo -e "${YELLOW}Checking application logs...${NC}"
POD_NAME=$(oc get pods -n $NAMESPACE -l app.kubernetes.io/name=resource-governance -o jsonpath='{.items[0].metadata.name}')
if [ -n "$POD_NAME" ]; then
    echo -e "${BLUE}Recent logs from $POD_NAME:${NC}"
    oc logs $POD_NAME -n $NAMESPACE --tail=10
fi

# Get application URL
echo -e "${YELLOW}Getting application URL...${NC}"

# Wait a bit to ensure route is ready
sleep 5

# Check if route exists and get URL
if oc get route resource-governance-route -n $NAMESPACE > /dev/null 2>&1; then
    ROUTE_URL=$(oc get route resource-governance-route -n $NAMESPACE -o jsonpath='{.spec.host}')
    echo -e "${GREEN}SUCCESS: Route created with host: $ROUTE_URL${NC}"
else
    echo -e "${YELLOW}WARNING: Route not found, checking available routes...${NC}"
    oc get routes -n $NAMESPACE
    ROUTE_URL=""
fi
if [ -n "$ROUTE_URL" ]; then
    echo -e "${GREEN}SUCCESS: Application deployed successfully!${NC}"
    echo -e "${GREEN}URL: https://$ROUTE_URL${NC}"
    echo -e "${GREEN}Health check: https://$ROUTE_URL/health${NC}"
else
    echo -e "${YELLOW}WARNING: Route not found, checking service...${NC}"
    oc get svc -n $NAMESPACE
fi

echo -e "${GREEN}SUCCESS: Deployment completed successfully!${NC}"