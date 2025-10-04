#!/bin/bash
# Deploy ORU Analyzer using Source-to-Image (S2I)
# Alternative deployment method for OpenShift

set -e

echo "=== ORU Analyzer S2I Deployment Script ==="
echo "Deploying ORU Analyzer using Source-to-Image..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
NAMESPACE="resource-governance"
APP_NAME="oru-analyzer"
GIT_REPO="https://github.com/andersonid/openshift-resource-governance.git"
GIT_REF="main"
PYTHON_VERSION="3.11"

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

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    if ! command_exists oc; then
        print_error "OpenShift CLI (oc) is not installed or not in PATH"
        exit 1
    fi
    
    # Check if logged in to OpenShift
    if ! oc whoami >/dev/null 2>&1; then
        print_error "Not logged in to OpenShift. Please run 'oc login' first"
        exit 1
    fi
    
    print_success "Prerequisites check passed"
}

# Create namespace if it doesn't exist
create_namespace() {
    print_status "Creating namespace '$NAMESPACE' if it doesn't exist..."
    
    if oc get namespace "$NAMESPACE" >/dev/null 2>&1; then
        print_warning "Namespace '$NAMESPACE' already exists"
    else
        oc new-project "$NAMESPACE"
        print_success "Namespace '$NAMESPACE' created"
    fi
}

# Deploy using oc new-app (simpler S2I)
deploy_s2i() {
    print_status "Deploying using oc new-app S2I..."
    
    # Use oc new-app for simple S2I deployment
    oc new-app python:3.11~"$GIT_REPO" \
        --name="$APP_NAME" \
        --env=PYTHON_VERSION=3.11 \
        --env=APP_ROOT=/app \
        --namespace="$NAMESPACE"
    
    print_success "S2I application created successfully"
    
    # Configure resource requests and limits
    print_status "Configuring resource requests and limits..."
    oc patch deploymentconfig/"$APP_NAME" -p '{
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
    }'
    
    print_success "Resource configuration applied"
}

# Wait for build to complete
wait_for_build() {
    print_status "Waiting for build to complete..."
    
    # Wait for build to start
    print_status "Waiting for build to start..."
    oc wait --for=condition=Running buildconfig/"$APP_NAME" --timeout=60s || true
    
    # Get the latest build
    BUILD_NAME=$(oc get builds -l buildconfig="$APP_NAME" --sort-by=.metadata.creationTimestamp -o jsonpath='{.items[-1].metadata.name}')
    
    if [ -n "$BUILD_NAME" ]; then
        print_status "Waiting for build '$BUILD_NAME' to complete..."
        oc logs -f build/"$BUILD_NAME" || true
        
        # Wait for build to complete
        oc wait --for=condition=Complete build/"$BUILD_NAME" --timeout=600s || {
            print_error "Build failed or timed out"
            print_status "Build logs:"
            oc logs build/"$BUILD_NAME"
            exit 1
        }
        
        print_success "Build completed successfully"
    else
        print_warning "No build found, continuing..."
    fi
}

# Wait for deployment to be ready
wait_for_deployment() {
    print_status "Waiting for deployment to be ready..."
    
    # Wait for deployment to complete
    oc rollout status deploymentconfig/"$APP_NAME" --timeout=300s || {
        print_error "Deployment failed or timed out"
        print_status "Deployment logs:"
        oc logs deploymentconfig/"$APP_NAME"
        exit 1
    }
    
    print_success "Deployment completed successfully"
}

# Get application URL
get_application_url() {
    print_status "Getting application URL..."
    
    ROUTE_URL=$(oc get route "$APP_NAME" -o jsonpath='{.spec.host}' 2>/dev/null || echo "")
    
    if [ -n "$ROUTE_URL" ]; then
        print_success "Application deployed successfully!"
        echo ""
        echo "=========================================="
        echo "🚀 ORU Analyzer is now available at:"
        echo "   https://$ROUTE_URL"
        echo "=========================================="
        echo ""
        echo "📊 To check the application status:"
        echo "   oc get pods -n $NAMESPACE"
        echo "   oc logs -f deploymentconfig/$APP_NAME -n $NAMESPACE"
        echo ""
        echo "🔧 To check the build status:"
        echo "   oc get builds -n $NAMESPACE"
        echo "   oc logs build/<build-name> -n $NAMESPACE"
        echo ""
    else
        print_warning "Could not determine application URL"
        print_status "Check the route manually:"
        echo "   oc get route -n $NAMESPACE"
    fi
}

# Main deployment function
main() {
    echo "Starting ORU Analyzer S2I deployment..."
    echo "=========================================="
    echo "Namespace: $NAMESPACE"
    echo "App Name: $APP_NAME"
    echo "Git Repository: $GIT_REPO"
    echo "Git Reference: $GIT_REF"
    echo "Python Version: $PYTHON_VERSION"
    echo "Method: oc new-app (simplified S2I)"
    echo "=========================================="
    echo ""
    
    check_prerequisites
    create_namespace
    deploy_s2i
    wait_for_build
    wait_for_deployment
    get_application_url
    
    print_success "ORU Analyzer S2I deployment completed!"
}

# Run main function
main "$@"
