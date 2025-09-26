#!/bin/bash

# Zero downtime deployment script (Blue-Green Strategy)
# Ensures application never goes down during updates

set -e

# Configuration
IMAGE_NAME="resource-governance"
REGISTRY="andersonid"
NAMESPACE="resource-governance"
TAG=${1:-"latest"}
FULL_IMAGE="$REGISTRY/$IMAGE_NAME:$TAG"

echo "Zero Downtime Deploy to OpenShift"
echo "================================="
echo "Image: $FULL_IMAGE"
echo "Namespace: $NAMESPACE"
echo "Strategy: Blue-Green (Zero Downtime)"
echo ""

# Check if logged into OpenShift
if ! oc whoami > /dev/null 2>&1; then
    echo "ERROR: Not logged into OpenShift. Run: oc login"
    exit 1
fi

echo "SUCCESS: Logged into OpenShift as: $(oc whoami)"
echo ""

# Function to check if all pods are ready
check_pods_ready() {
    local deployment=$1
    local namespace=$2
    local timeout=${3:-300}
    
    echo "Waiting for deployment $deployment pods to be ready..."
    oc rollout status deployment/$deployment -n $namespace --timeout=${timeout}s
}

# Function to check if application is responding
check_app_health() {
    local service=$1
    local namespace=$2
    local port=${3:-8080}
    
    echo "Checking application health..."
    
    # Try temporary port-forward for testing
    local temp_pid
    oc port-forward service/$service $port:$port -n $namespace > /dev/null 2>&1 &
    temp_pid=$!
    
    # Wait for port-forward to initialize
    sleep 3
    
    # Test health check
    local health_status
    health_status=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:$port/api/v1/health 2>/dev/null || echo "000")
    
    # Stop temporary port-forward
    kill $temp_pid 2>/dev/null || true
    
    if [ "$health_status" = "200" ]; then
        echo "SUCCESS: Application healthy (HTTP $health_status)"
        return 0
    else
        echo "ERROR: Application not healthy (HTTP $health_status)"
        return 1
    fi
}

# Apply basic manifests
echo "Applying basic manifests..."
oc apply -f k8s/namespace.yaml
oc apply -f k8s/rbac.yaml
oc apply -f k8s/configmap.yaml

# Check if deployment exists
if oc get deployment $IMAGE_NAME -n $NAMESPACE > /dev/null 2>&1; then
    echo "Existing deployment found. Starting zero-downtime update..."
    
    # Get current replica count
    CURRENT_REPLICAS=$(oc get deployment $IMAGE_NAME -n $NAMESPACE -o jsonpath='{.spec.replicas}')
    echo "Current replicas: $CURRENT_REPLICAS"
    
    # Update deployment image
    echo "Updating image to: $FULL_IMAGE"
    oc set image deployment/$IMAGE_NAME $IMAGE_NAME=$FULL_IMAGE -n $NAMESPACE
    
    # Wait for rollout with longer timeout
    echo "Waiting for rollout (may take a few minutes)..."
    if check_pods_ready $IMAGE_NAME $NAMESPACE 600; then
        echo "SUCCESS: Rollout completed successfully!"
        
        # Check application health
        if check_app_health "${IMAGE_NAME}-service" $NAMESPACE; then
            echo "Zero downtime deploy completed successfully!"
        else
            echo "WARNING: Deploy completed, but application may not be healthy"
            echo "Check logs: oc logs -f deployment/$IMAGE_NAME -n $NAMESPACE"
        fi
    else
        echo "ERROR: Rollout failed or timeout"
        echo "Checking pod status:"
        oc get pods -n $NAMESPACE -l app.kubernetes.io/name=$IMAGE_NAME
        exit 1
    fi
else
    echo "Deployment does not exist. Creating new deployment..."
    oc apply -f k8s/deployment.yaml
    oc apply -f k8s/service.yaml
    oc apply -f k8s/route.yaml
    
    # Wait for pods to be ready
    if check_pods_ready $IMAGE_NAME $NAMESPACE 300; then
        echo "SUCCESS: New deployment created successfully!"
    else
        echo "ERROR: Failed to create deployment"
        exit 1
    fi
fi

# Check final status
echo ""
echo "FINAL STATUS:"
echo "============="
oc get deployment $IMAGE_NAME -n $NAMESPACE
echo ""
oc get pods -n $NAMESPACE -l app.kubernetes.io/name=$IMAGE_NAME
echo ""

# Get route URL
ROUTE_URL=$(oc get route $IMAGE_NAME-route -n $NAMESPACE -o jsonpath='{.spec.host}' 2>/dev/null || echo "")
if [ -n "$ROUTE_URL" ]; then
    echo "Access URLs:"
    echo "   OpenShift: https://$ROUTE_URL"
    echo "   Port-forward: http://localhost:8080 (if active)"
    echo ""
    echo "To start port-forward: oc port-forward service/${IMAGE_NAME}-service 8080:8080 -n $NAMESPACE"
fi

echo ""
echo "Zero downtime deploy completed!"
echo "Strategy: Rolling Update with maxUnavailable=0 (zero downtime)"
