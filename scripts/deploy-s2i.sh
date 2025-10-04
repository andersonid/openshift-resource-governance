#!/bin/bash
# Deploy ORU Analyzer using Source-to-Image (S2I)

set -e

echo "🚀 ORU Analyzer S2I Deployment"
echo "==============================="

# Default values
NAMESPACE="resource-governance"
APP_NAME="oru-analyzer"
GIT_REPO="https://github.com/andersonid/openshift-resource-governance.git"

# Check prerequisites
if ! command -v oc >/dev/null 2>&1; then
    echo "❌ OpenShift CLI (oc) not found. Please install it first."
    exit 1
fi

if ! oc whoami >/dev/null 2>&1; then
    echo "❌ Not logged in to OpenShift. Please run 'oc login' first"
    exit 1
fi

# Create namespace
echo "📦 Creating namespace..."
oc new-project "$NAMESPACE" 2>/dev/null || echo "Namespace already exists"

# Deploy with oc new-app
echo "🚀 Deploying with oc new-app..."
oc new-app python:3.11~"$GIT_REPO" \
  --name="$APP_NAME" \
  --env=PYTHON_VERSION=3.11 \
  --env=APP_ROOT=/app \
  --namespace="$NAMESPACE"

# Configure resources
echo "⚙️  Configuring resources..."
oc patch deploymentconfig/"$APP_NAME" -p '{
  "spec": {
    "template": {
      "spec": {
        "containers": [{
          "name": "'"$APP_NAME"'",
          "resources": {
            "requests": {"cpu": "50m", "memory": "64Mi"},
            "limits": {"cpu": "200m", "memory": "256Mi"}
          }
        }]
      }
    }
  }
}'

# Wait for build and deployment
echo "⏳ Waiting for build and deployment..."
oc logs -f buildconfig/"$APP_NAME" &
BUILD_PID=$!

# Wait for build to complete
oc wait --for=condition=Complete buildconfig/"$APP_NAME" --timeout=600s
kill $BUILD_PID 2>/dev/null || true

# Wait for deployment
oc rollout status deploymentconfig/"$APP_NAME" --timeout=300s

# Get URL
ROUTE_URL=$(oc get route "$APP_NAME" -o jsonpath='{.spec.host}' 2>/dev/null || echo "")

echo ""
echo "✅ Deployment Complete!"
echo "🌐 Application URL: https://$ROUTE_URL"
echo ""
echo "📊 Check status:"
echo "   oc get pods -n $NAMESPACE"
echo "   oc logs -f deploymentconfig/$APP_NAME -n $NAMESPACE"
