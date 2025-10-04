#!/bin/bash

# Common functions and variables for OpenShift Resource Governance Tool scripts
# This file is sourced by other scripts to avoid duplication

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Common configuration
NAMESPACE="resource-governance"
DEPLOYMENT_NAME="resource-governance"
SERVICE_ACCOUNT="resource-governance-sa"
SECRET_NAME="resource-governance-sa-token"

# Function to check if connected to OpenShift cluster
check_openshift_connection() {
    if ! oc whoami > /dev/null 2>&1; then
        echo -e "${RED}ERROR: Not connected to OpenShift cluster. Please run 'oc login' first.${NC}"
        exit 1
    fi
    echo -e "${GREEN}SUCCESS: Connected to OpenShift cluster as $(oc whoami)${NC}"
}

# Function to check if deployment exists
check_deployment_exists() {
    if ! oc get deployment $DEPLOYMENT_NAME -n $NAMESPACE > /dev/null 2>&1; then
        echo -e "${RED}ERROR: Deployment $DEPLOYMENT_NAME not found in namespace $NAMESPACE${NC}"
        echo -e "${YELLOW}Please run ./scripts/deploy-complete.sh first for initial deployment${NC}"
        exit 1
    fi
}

# Function to check pod status and logs
check_pod_status() {
    echo -e "${YELLOW}Checking pod status...${NC}"
    oc get pods -n $NAMESPACE -l app.kubernetes.io/name=resource-governance

    echo -e "${YELLOW}Checking application logs...${NC}"
    POD_NAME=$(oc get pods -n $NAMESPACE -l app.kubernetes.io/name=resource-governance -o jsonpath='{.items[0].metadata.name}')
    if [ -n "$POD_NAME" ]; then
        echo -e "${BLUE}Recent logs from $POD_NAME:${NC}"
        oc logs $POD_NAME -n $NAMESPACE --tail=10
    fi
}

# Function to get application URL
get_application_url() {
    ROUTE_URL=$(oc get route resource-governance-route -n $NAMESPACE -o jsonpath='{.spec.host}' 2>/dev/null)
    if [ -n "$ROUTE_URL" ]; then
        echo -e "${GREEN}URL: https://$ROUTE_URL${NC}"
        echo -e "${GREEN}Health check: https://$ROUTE_URL/health${NC}"
    else
        echo -e "${YELLOW}WARNING: Route not found${NC}"
    fi
}
