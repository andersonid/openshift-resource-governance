#!/bin/bash

# ORU Analyzer - S2I Deployment Script
# This script deploys the application with ALL required resources automatically
# No additional commands needed - completely self-service

set -e

echo "🚀 ORU Analyzer S2I Deployment"
echo "==============================="
echo "📦 This will deploy the application with ALL required resources"
echo "   - RBAC (ServiceAccount, ClusterRole, ClusterRoleBinding)"
echo "   - ConfigMap with all configurations"
echo "   - S2I Build and Deployment"
echo "   - Service and Route"
echo "   - Resource limits and requests"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Default values
NAMESPACE="resource-governance"
APP_NAME="resource-governance"
GIT_REPO="https://github.com/andersonid/openshift-resource-governance.git"

# Check if oc is available
if ! command -v oc &> /dev/null; then
    print_error "OpenShift CLI (oc) is not installed or not in PATH"
    exit 1
fi

# Check if user is logged in
if ! oc whoami &> /dev/null; then
    print_error "Not logged in to OpenShift. Please run 'oc login' first"
    exit 1
fi

print_success "OpenShift CLI is available and user is logged in"

# Get current directory (should be project root)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
K8S_DIR="$PROJECT_ROOT/k8s"

print_status "Project root: $PROJECT_ROOT"
print_status "K8s manifests: $K8S_DIR"

# Check if k8s directory exists
if [ ! -d "$K8S_DIR" ]; then
    print_error "K8s directory not found: $K8S_DIR"
    exit 1
fi

# Check if required manifest files exist
REQUIRED_FILES=("rbac.yaml" "configmap.yaml" "service.yaml" "route.yaml")
for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$K8S_DIR/$file" ]; then
        print_error "Required manifest file not found: $K8S_DIR/$file"
        exit 1
    fi
done

print_success "All required manifest files found"

# Step 1: Create namespace
print_status "Step 1: Creating namespace..."
if oc get namespace "$NAMESPACE" &> /dev/null; then
    print_warning "Namespace '$NAMESPACE' already exists"
else
    oc new-project "$NAMESPACE"
    print_success "Namespace '$NAMESPACE' created"
fi

# Step 2: Apply RBAC
print_status "Step 2: Applying RBAC (ServiceAccount, ClusterRole, ClusterRoleBinding)..."
oc apply -f "$K8S_DIR/rbac.yaml"
print_success "RBAC applied successfully"

# Step 3: Apply ConfigMap
print_status "Step 3: Applying ConfigMap with application configurations..."
oc apply -f "$K8S_DIR/configmap.yaml"
print_success "ConfigMap applied successfully"

# Step 4: Deploy S2I application
print_status "Step 4: Deploying application using S2I..."
print_status "   - Using Python 3.12 UBI9 base image"
print_status "   - Building from GitHub repository"
print_status "   - Configuring with ServiceAccount and ConfigMap"

# Deploy using S2I with proper configuration
oc new-app python:3.12-ubi9~"$GIT_REPO" \
  --name="$APP_NAME" \
  --namespace="$NAMESPACE" \
  --labels="app.kubernetes.io/name=resource-governance,app.kubernetes.io/component=governance" \
  --env=PYTHON_VERSION=3.12 \
  --env=APP_ROOT=/app \
  --env=HOST=0.0.0.0 \
  --env=PORT=8080 \
  --env=WORKERS=1

print_success "S2I application deployed"

# Step 5: Configure ServiceAccount and ConfigMap
print_status "Step 5: Configuring ServiceAccount and ConfigMap..."
oc patch deployment/"$APP_NAME" -p '{
  "spec": {
    "template": {
      "spec": {
        "serviceAccountName": "resource-governance-sa"
      }
    }
  }
}' -n "$NAMESPACE"

# Mount ConfigMap as environment variables
oc set env deployment/"$APP_NAME" --from=configmap/resource-governance-config -n "$NAMESPACE"

print_success "ServiceAccount and ConfigMap configured"

# Step 6: Configure replicas
print_status "Step 6: Configuring replicas..."
oc scale deployment/"$APP_NAME" --replicas=1 -n "$NAMESPACE"
print_success "Replicas configured (1 replica)"

# Step 7: Configure resources (CPU/Memory)
print_status "Step 7: Configuring resource requests and limits..."
oc patch deployment/"$APP_NAME" -p '{
  "spec": {
    "template": {
      "spec": {
        "containers": [{
          "name": "'"$APP_NAME"'",
          "resources": {
            "requests": {
              "cpu": "50m",
              "memory": "64Mi"
            },
            "limits": {
              "cpu": "200m",
              "memory": "256Mi"
            }
          }
        }]
      }
    }
  }
}' -n "$NAMESPACE"

print_success "Resource limits configured (CPU: 50m-200m, Memory: 64Mi-256Mi)"

# Step 8: Wait for deployment to be ready
print_status "Step 8: Waiting for deployment to be ready..."
oc rollout status deployment/"$APP_NAME" -n "$NAMESPACE" --timeout=300s
print_success "Deployment is ready"

# Step 9: Apply Service (use the correct service from manifests)
print_status "Step 9: Applying Service..."
oc apply -f "$K8S_DIR/service.yaml"
print_success "Service applied successfully"

# Step 10: Apply Route (use the correct route from manifests)
print_status "Step 10: Applying Route..."
oc apply -f "$K8S_DIR/route.yaml"
print_success "Route applied successfully"

# Step 11: Get application URL
print_status "Step 11: Getting application URL..."
ROUTE_URL=$(oc get route resource-governance-route -o jsonpath='{.spec.host}' -n "$NAMESPACE" 2>/dev/null)

if [ -z "$ROUTE_URL" ]; then
    print_warning "Could not get route URL automatically"
    print_status "You can get the URL manually with: oc get route -n $NAMESPACE"
else
    print_success "Application URL: https://$ROUTE_URL"
fi

# Step 12: Verify deployment
print_status "Step 12: Verifying deployment..."
print_status "Checking pod status..."
oc get pods -n "$NAMESPACE"

print_status "Checking service status..."
oc get svc -n "$NAMESPACE"

print_status "Checking route status..."
oc get route -n "$NAMESPACE"

# Final status
echo ""
echo "🎉 DEPLOYMENT COMPLETED SUCCESSFULLY!"
echo "====================================="
echo "✅ All resources deployed:"
echo "   - Namespace: $NAMESPACE"
echo "   - RBAC: ServiceAccount, ClusterRole, ClusterRoleBinding"
echo "   - ConfigMap: resource-governance-config"
echo "   - S2I Build: $APP_NAME"
echo "   - Deployment: $APP_NAME"
echo "   - Service: resource-governance-service"
echo "   - Route: resource-governance-route"
echo ""
echo "🌐 Application Access:"
if [ -n "$ROUTE_URL" ]; then
    echo "   URL: https://$ROUTE_URL"
    echo "   Health: https://$ROUTE_URL/health"
    echo "   API: https://$ROUTE_URL/api/v1/cluster/status"
else
    echo "   Get URL: oc get route -n $NAMESPACE"
fi
echo ""
echo "🔧 Management Commands:"
echo "   View logs: oc logs -f deployment/$APP_NAME -n $NAMESPACE"
echo "   Check status: oc get all -n $NAMESPACE"
echo "   Restart: oc rollout restart deployment/$APP_NAME -n $NAMESPACE"
echo ""
echo "📚 The application is now fully functional and self-service!"
echo "   No additional configuration needed."
