#!/bin/bash

# Script for deploying OpenShift Resource Governance application
# Works with any OpenShift cluster (public or private)

# Variables
IMAGE_NAME="resource-governance"
NAMESPACE="resource-governance"
IMAGE_TAG=${1:-latest} # Use first argument as tag, or 'latest' by default

echo "Deploy to OpenShift Cluster"
echo "==========================="
echo "Image: ${IMAGE_TAG}"
echo "Namespace: ${NAMESPACE}"
echo ""

# 1. Check OpenShift login
if ! oc whoami > /dev/null 2>&1; then
  echo "ERROR: Not logged into OpenShift. Please login with 'oc login'."
  echo "Example: oc login https://your-cluster.com"
  exit 1
fi
echo "SUCCESS: Logged into OpenShift as: $(oc whoami)"
echo ""

# 2. Check if namespace exists, create if not
if ! oc get namespace ${NAMESPACE} > /dev/null 2>&1; then
  echo "Creating namespace ${NAMESPACE}..."
  oc create namespace ${NAMESPACE}
else
  echo "SUCCESS: Namespace ${NAMESPACE} already exists"
fi
echo ""

# 3. Apply basic manifests (rbac, configmap)
echo "Applying manifests..."
oc apply -f k8s/rbac.yaml
oc apply -f k8s/configmap.yaml
echo ""

# 4. Update deployment with new image
echo "Updating deployment image..."
oc set image deployment/${IMAGE_NAME} ${IMAGE_NAME}=${IMAGE_TAG} -n ${NAMESPACE} || true
echo ""

# 5. Apply deployment, service and route
echo "Applying deployment, service and route..."
oc apply -f k8s/deployment.yaml
oc apply -f k8s/service.yaml
oc apply -f k8s/route.yaml
echo ""

# 6. Wait for rollout
echo "Waiting for rollout..."
oc rollout status deployment/${IMAGE_NAME} -n ${NAMESPACE} --timeout=300s
echo "SUCCESS: Rollout completed successfully!"
echo ""

# 7. Verify deployment
echo "Verifying deployment..."
oc get deployment ${IMAGE_NAME} -n ${NAMESPACE}
oc get pods -n ${NAMESPACE} -l app.kubernetes.io/name=${IMAGE_NAME}
echo ""

# 8. Get route URL
ROUTE_URL=$(oc get route ${IMAGE_NAME}-route -n ${NAMESPACE} -o jsonpath='{.spec.host}' 2>/dev/null || echo "")
if [ -n "$ROUTE_URL" ]; then
  echo "Application deployed successfully!"
  echo "URL: https://$ROUTE_URL"
  echo "Status: oc get pods -n ${NAMESPACE} -l app.kubernetes.io/name=${IMAGE_NAME}"
else
  echo "WARNING: Route not found. Check if cluster supports Routes."
  echo "For local access: oc port-forward service/${IMAGE_NAME}-service 8080:8080 -n ${NAMESPACE}"
fi
echo ""

echo "Deploy completed!"
echo ""
echo "Useful commands:"
echo "   View logs: oc logs -f deployment/${IMAGE_NAME} -n ${NAMESPACE}"
echo "   Port-forward: oc port-forward service/${IMAGE_NAME}-service 8080:8080 -n ${NAMESPACE}"
echo "   Status: oc get pods -n ${NAMESPACE} -l app.kubernetes.io/name=${IMAGE_NAME}"
