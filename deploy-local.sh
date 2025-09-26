#!/bin/bash

# Local deployment script for OpenShift
# Usage: ./deploy-local.sh [IMAGE_TAG]

set -e

# Configuration
IMAGE_NAME="resource-governance"
REGISTRY="andersonid"
NAMESPACE="resource-governance"
TAG=${1:-"latest"}

echo "Local Deploy to OpenShift"
echo "========================="
echo "Image: $REGISTRY/$IMAGE_NAME:$TAG"
echo "Namespace: $NAMESPACE"
echo ""

# Check if logged into OpenShift
if ! oc whoami > /dev/null 2>&1; then
    echo "ERROR: Not logged into OpenShift. Run: oc login"
    exit 1
fi

echo "SUCCESS: Logged into OpenShift as: $(oc whoami)"
echo ""

# Apply manifests
echo "Applying manifests..."
oc apply -f k8s/namespace.yaml
oc apply -f k8s/rbac.yaml
oc apply -f k8s/configmap.yaml

# Update deployment image
echo "Updating deployment image..."
oc set image deployment/$IMAGE_NAME $IMAGE_NAME=$REGISTRY/$IMAGE_NAME:$TAG -n $NAMESPACE || true

# Apply deployment, service and route
echo "Applying deployment, service and route..."
oc apply -f k8s/deployment.yaml
oc apply -f k8s/service.yaml
oc apply -f k8s/route.yaml

# Wait for rollout
echo "Waiting for rollout..."
oc rollout status deployment/$IMAGE_NAME -n $NAMESPACE --timeout=300s

# Verify deployment
echo "Verifying deployment..."
oc get deployment $IMAGE_NAME -n $NAMESPACE
oc get pods -n $NAMESPACE -l app.kubernetes.io/name=$IMAGE_NAME

# Get route URL
ROUTE_URL=$(oc get route $IMAGE_NAME-route -n $NAMESPACE -o jsonpath='{.spec.host}' 2>/dev/null || echo "")
if [ -n "$ROUTE_URL" ]; then
    echo ""
    echo "Application deployed successfully!"
    echo "URL: https://$ROUTE_URL"
    echo "Status: oc get pods -n $NAMESPACE -l app.kubernetes.io/name=$IMAGE_NAME"
else
    echo "WARNING: Route not found. Check: oc get routes -n $NAMESPACE"
fi

echo ""
echo "Deploy completed!"
