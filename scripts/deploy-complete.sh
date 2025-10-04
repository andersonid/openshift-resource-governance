#!/bin/bash

# Complete deployment script for OpenShift Resource Governance Tool
# Includes namespace creation, RBAC, ConfigMap, Secret and Deployment

set -e

# Source common functions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

echo -e "${BLUE}Deploying OpenShift Resource Governance Tool${NC}"

# Check if connected to cluster
check_openshift_connection

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

# Check pod status and logs
check_pod_status

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

echo -e "${GREEN}SUCCESS: Application deployed successfully!${NC}"
get_application_url

echo -e "${GREEN}SUCCESS: Deployment completed successfully!${NC}"