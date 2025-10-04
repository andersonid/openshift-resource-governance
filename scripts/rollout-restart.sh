#!/bin/bash

# Simple rollout restart script for OpenShift Resource Governance Tool
# Use this for updates after GitHub Actions has built the new image

set -e

# Source common functions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

echo -e "${BLUE}Rolling out new image for OpenShift Resource Governance Tool${NC}"

# Check if connected to cluster
check_openshift_connection

# Check if deployment exists
check_deployment_exists

# Restart deployment to pull new image
echo -e "${YELLOW}Restarting deployment to pull new image...${NC}"
oc rollout restart deployment/$DEPLOYMENT_NAME -n $NAMESPACE

# Wait for rollout to complete
echo -e "${YELLOW}Waiting for rollout to complete...${NC}"
oc rollout status deployment/$DEPLOYMENT_NAME -n $NAMESPACE --timeout=300s

# Check pod status and logs
check_pod_status

# Get application URL
get_application_url

echo -e "${GREEN}SUCCESS: Rollout completed successfully!${NC}"

echo -e "${BLUE}Process completed!${NC}"
echo -e "${YELLOW}Note: This script only restarts the deployment.${NC}"
echo -e "${YELLOW}For initial deployment, use: ./scripts/deploy-complete.sh${NC}"
