#!/bin/bash
# Ultra-simple S2I deployment - just run this one command!

set -e

echo "🚀 Ultra-Simple ORU Analyzer S2I Deployment"
echo "============================================="

# Check if logged in
if ! oc whoami >/dev/null 2>&1; then
    echo "❌ Not logged in to OpenShift. Please run 'oc login' first"
    exit 1
fi

# Create namespace
echo "📦 Creating namespace..."
oc new-project resource-governance 2>/dev/null || echo "Namespace already exists"

# Deploy with oc new-app (super simple!)
echo "🚀 Deploying with oc new-app..."
oc new-app python:3.11~https://github.com/andersonid/openshift-resource-governance.git \
  --name=oru-analyzer \
  --env=PYTHON_VERSION=3.11 \
  --env=APP_ROOT=/app

# Configure resources
echo "⚙️  Configuring resources..."
oc patch deploymentconfig/oru-analyzer -p '{
  "spec": {
    "template": {
      "spec": {
        "containers": [{
          "name": "oru-analyzer",
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
oc logs -f buildconfig/oru-analyzer &
BUILD_PID=$!

# Wait for build to complete
oc wait --for=condition=Complete buildconfig/oru-analyzer --timeout=600s
kill $BUILD_PID 2>/dev/null || true

# Wait for deployment
oc rollout status deploymentconfig/oru-analyzer --timeout=300s

# Get URL
ROUTE_URL=$(oc get route oru-analyzer -o jsonpath='{.spec.host}' 2>/dev/null || echo "")

echo ""
echo "✅ Deployment Complete!"
echo "🌐 Application URL: https://$ROUTE_URL"
echo ""
echo "📊 Check status:"
echo "   oc get pods -n resource-governance"
echo "   oc logs -f deploymentconfig/oru-analyzer -n resource-governance"
