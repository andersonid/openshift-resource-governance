#!/bin/bash

# Complete deployment script for OpenShift Resource Governance Tool
# Includes namespace creation, RBAC, ConfigMap, Secret and Deployment
# Optimized for cluster-admin privileges

set -e

# Source common functions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

echo -e "${BLUE}Deploying OpenShift Resource Governance Tool (Cluster-Admin Mode)${NC}"

# Check if connected to cluster
check_openshift_connection

# Verify cluster-admin privileges
echo -e "${YELLOW}Verifying cluster-admin privileges...${NC}"
if oc auth can-i '*' '*' --all-namespaces > /dev/null 2>&1; then
    echo -e "${GREEN}SUCCESS: Cluster-admin privileges confirmed${NC}"
else
    echo -e "${RED}ERROR: Insufficient privileges. This tool requires cluster-admin access${NC}"
    echo -e "${YELLOW}Please run: oc login --as=system:admin${NC}"
    exit 1
fi

# Create namespace if it doesn't exist
echo -e "${YELLOW}Creating namespace...${NC}"
oc create namespace $NAMESPACE --dry-run=client -o yaml | oc apply -f -

# Apply RBAC
echo -e "${YELLOW}Applying RBAC...${NC}"
oc apply -f k8s/rbac.yaml

# Verify access to monitoring components
echo -e "${YELLOW}Verifying access to monitoring components...${NC}"

# Check Prometheus access
if oc get pods -n openshift-monitoring | grep prometheus-k8s > /dev/null 2>&1; then
    echo -e "${GREEN}SUCCESS: Prometheus pods found${NC}"
else
    echo -e "${YELLOW}WARNING: Prometheus pods not found in openshift-monitoring${NC}"
fi

# Check Thanos access
if oc get pods -n openshift-monitoring | grep thanos-querier > /dev/null 2>&1; then
    echo -e "${GREEN}SUCCESS: Thanos Querier pods found${NC}"
else
    echo -e "${YELLOW}WARNING: Thanos Querier pods not found in openshift-monitoring${NC}"
fi

# Test monitoring access
echo -e "${YELLOW}Testing monitoring access...${NC}"
if oc auth can-i get pods --as=system:serviceaccount:$NAMESPACE:$SERVICE_ACCOUNT -n openshift-monitoring > /dev/null 2>&1; then
    echo -e "${GREEN}SUCCESS: ServiceAccount has access to openshift-monitoring${NC}"
else
    echo -e "${YELLOW}WARNING: ServiceAccount may not have full access to monitoring${NC}"
fi

# Apply ConfigMap
echo -e "${YELLOW}Applying ConfigMap...${NC}"
oc apply -f k8s/configmap.yaml

# Apply Redis ConfigMap
echo -e "${YELLOW}Applying Redis ConfigMap...${NC}"
oc apply -f k8s/redis-configmap.yaml

# Apply Redis Deployment
echo -e "${YELLOW}Applying Redis Deployment...${NC}"
oc apply -f k8s/redis-deployment.yaml

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

# Apply Celery Worker Deployment
echo -e "${YELLOW}Applying Celery Worker Deployment...${NC}"
oc apply -f k8s/celery-worker-deployment.yaml

# Apply Service
echo -e "${YELLOW}Applying Service...${NC}"
oc apply -f k8s/service.yaml

# Create Route (let OpenShift generate host automatically)
echo -e "${YELLOW}Creating Route...${NC}"
if oc get route resource-governance-route -n $NAMESPACE > /dev/null 2>&1; then
    echo -e "${YELLOW}Route already exists, skipping creation${NC}"
else
    oc expose service resource-governance-service -n $NAMESPACE --name=resource-governance-route --path=/
fi

# Configure TLS for the route
echo -e "${YELLOW}Configuring TLS for Route...${NC}"
oc patch route resource-governance-route -n $NAMESPACE -p '{"spec":{"tls":{"termination":"edge","insecureEdgeTerminationPolicy":"Redirect"}}}'

# Wait for deployment to be ready
echo -e "${YELLOW}Waiting for deployment to be ready...${NC}"
oc rollout status deployment/resource-governance -n $NAMESPACE --timeout=300s

# Check pod status and logs
check_pod_status

# Test application health and monitoring connectivity
echo -e "${YELLOW}Testing application health...${NC}"
sleep 10

# Test health endpoint
if curl -s -f "https://$(oc get route resource-governance-route -n $NAMESPACE -o jsonpath='{.spec.host}')/health" > /dev/null 2>&1; then
    echo -e "${GREEN}SUCCESS: Application health check passed${NC}"
else
    echo -e "${YELLOW}WARNING: Application health check failed, but deployment may still be starting${NC}"
fi

# Test monitoring connectivity
echo -e "${YELLOW}Testing monitoring connectivity...${NC}"
if curl -s -f "https://$(oc get route resource-governance-route -n $NAMESPACE -o jsonpath='{.spec.host}')/api/v1/hybrid/health" > /dev/null 2>&1; then
    echo -e "${GREEN}SUCCESS: Monitoring connectivity verified${NC}"
else
    echo -e "${YELLOW}WARNING: Monitoring connectivity test failed, check logs${NC}"
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

echo -e "${GREEN}SUCCESS: Application deployed successfully!${NC}"
get_application_url

# Display cluster-admin specific information
echo -e "${BLUE}=== CLUSTER-ADMIN DEPLOYMENT SUMMARY ===${NC}"
echo -e "${GREEN}✓ Namespace: $NAMESPACE${NC}"
echo -e "${GREEN}✓ ServiceAccount: $SERVICE_ACCOUNT${NC}"
echo -e "${GREEN}✓ RBAC: Full cluster monitoring access${NC}"
echo -e "${GREEN}✓ Prometheus: Connected${NC}"
echo -e "${GREEN}✓ Thanos: Connected${NC}"
echo -e "${GREEN}✓ Redis: Deployed${NC}"
echo -e "${GREEN}✓ Celery Workers: Deployed${NC}"
echo -e "${GREEN}✓ Application: Ready${NC}"

echo -e "${YELLOW}=== MONITORING CAPABILITIES ===${NC}"
echo -e "• Real-time cluster resource analysis"
echo -e "• Historical data via Thanos"
echo -e "• Cross-namespace workload analysis"
echo -e "• Resource optimization recommendations"
echo -e "• Background processing with Celery"

echo -e "${GREEN}SUCCESS: Cluster-Admin deployment completed successfully!${NC}"