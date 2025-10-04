# ORU Analyzer - Source-to-Image (S2I) Deployment

This document describes how to deploy ORU Analyzer using OpenShift Source-to-Image (S2I) as an alternative to container-based deployment.

## 🚀 S2I vs Container Build

### Container Build (Current)
- Uses Dockerfile + Quay.io + GitHub Actions
- Manual build and push process
- More control over build process

### Source-to-Image (S2I)
- Direct deployment from Git repository
- OpenShift manages build and deployment
- Simpler deployment process
- Automatic rebuilds on code changes

## 📋 Prerequisites

- OpenShift 4.x cluster
- OpenShift CLI (oc) installed and configured
- Access to the cluster with appropriate permissions
- Git repository access

## 🛠️ S2I Deployment Methods

### Method 1: Using S2I Template (Recommended)

```bash
# 1. Login to OpenShift
oc login <cluster-url>

# 2. Deploy using S2I template
./scripts/deploy-s2i.sh
```

### Method 2: Using oc new-app

```bash
# 1. Create namespace
oc new-project resource-governance

# 2. Deploy using oc new-app
oc new-app python:3.11~https://github.com/andersonid/openshift-resource-governance.git \
  --name=oru-analyzer \
  --env=PYTHON_VERSION=3.11 \
  --env=HOST=0.0.0.0 \
  --env=PORT=8080

# 3. Expose the application
oc expose service oru-analyzer

# 4. Get the route
oc get route oru-analyzer
```

### Method 3: Using Template File

```bash
# 1. Process and apply template
oc process -f openshift-s2i.yaml \
  -p NAME=oru-analyzer \
  -p NAMESPACE=resource-governance \
  -p GIT_REPOSITORY=https://github.com/andersonid/openshift-resource-governance.git \
  -p GIT_REF=main \
  -p PYTHON_VERSION=3.11 \
  | oc apply -f -

# 2. Wait for deployment
oc rollout status deploymentconfig/oru-analyzer
```

## 📁 S2I File Structure

```
├── .s2i/
│   ├── environment          # S2I environment variables
│   └── bin/
│       ├── assemble         # Build script
│       └── run              # Runtime script
├── openshift-s2i.yaml      # OpenShift S2I template
├── scripts/
│   └── deploy-s2i.sh       # S2I deployment script
└── README-S2I.md           # This file
```

## ⚙️ Configuration

### Environment Variables

The S2I configuration supports the following environment variables:

```bash
# Python Configuration
PYTHON_VERSION=3.11
PIP_INDEX_URL=https://pypi.org/simple

# Application Configuration
APP_NAME=oru-analyzer
HOST=0.0.0.0
PORT=8080
WORKERS=1

# Resource Configuration
CPU_REQUEST=100m
CPU_LIMIT=500m
MEMORY_REQUEST=256Mi
MEMORY_LIMIT=1Gi

# Health Check Configuration
HEALTH_CHECK_PATH=/health
HEALTH_CHECK_INTERVAL=30s
HEALTH_CHECK_TIMEOUT=10s
HEALTH_CHECK_RETRIES=3
```

### Template Parameters

The OpenShift template supports the following parameters:

- `NAME`: Application name (default: oru-analyzer)
- `NAMESPACE`: OpenShift namespace (default: resource-governance)
- `GIT_REPOSITORY`: Git repository URL
- `GIT_REF`: Git reference/branch (default: main)
- `PYTHON_VERSION`: Python version (default: 3.11)
- `CPU_REQUEST`: CPU request (default: 100m)
- `CPU_LIMIT`: CPU limit (default: 500m)
- `MEMORY_REQUEST`: Memory request (default: 256Mi)
- `MEMORY_LIMIT`: Memory limit (default: 1Gi)
- `REPLICAS`: Number of replicas (default: 1)
- `ROUTE_HOSTNAME`: Custom route hostname (optional)

## 🔧 S2I Build Process

### 1. Assemble Phase
- Installs Python dependencies from `requirements.txt`
- Creates application directory structure
- Copies application files
- Sets proper permissions
- Creates startup script

### 2. Run Phase
- Sets environment variables
- Changes to application directory
- Starts the FastAPI application

## 📊 Monitoring and Debugging

### Check Build Status
```bash
# List builds
oc get builds -n resource-governance

# View build logs
oc logs build/<build-name> -n resource-governance

# Watch build progress
oc logs -f buildconfig/oru-analyzer -n resource-governance
```

### Check Application Status
```bash
# Check pods
oc get pods -n resource-governance

# Check deployment
oc get deploymentconfig -n resource-governance

# View application logs
oc logs -f deploymentconfig/oru-analyzer -n resource-governance
```

### Check Routes
```bash
# List routes
oc get route -n resource-governance

# Get route URL
oc get route oru-analyzer -o jsonpath='{.spec.host}'
```

## 🔄 Automatic Rebuilds

S2I supports automatic rebuilds when:

1. **Code Changes**: Push to the Git repository
2. **Config Changes**: Update ConfigMap or environment variables
3. **Image Changes**: Update base Python image

### Trigger Rebuild
```bash
# Manual rebuild
oc start-build oru-analyzer

# Rebuild from specific Git reference
oc start-build oru-analyzer --from-repo=https://github.com/andersonid/openshift-resource-governance.git --from-commit=main
```

## 🆚 S2I vs Container Build Comparison

| Feature | S2I | Container Build |
|---------|-----|-----------------|
| **Deployment Speed** | ⚡ Fast | 🐌 Slower |
| **Build Control** | 🔒 Limited | 🎛️ Full Control |
| **Git Integration** | ✅ Native | ❌ Manual |
| **Auto Rebuilds** | ✅ Automatic | ❌ Manual |
| **Registry Dependency** | ❌ None | ✅ Required |
| **CI/CD Complexity** | 🟢 Simple | 🟡 Complex |
| **Debugging** | 🟡 Limited | 🟢 Full Access |
| **Custom Builds** | ❌ Limited | ✅ Full Support |

## 🚀 Quick Start

```bash
# 1. Clone repository
git clone https://github.com/andersonid/openshift-resource-governance.git
cd openshift-resource-governance

# 2. Login to OpenShift
oc login <cluster-url>

# 3. Deploy using S2I
./scripts/deploy-s2i.sh

# 4. Access application
# Get URL from output or run:
oc get route oru-analyzer -o jsonpath='{.spec.host}'
```

## 🐛 Troubleshooting

### Common Issues

1. **Build Fails**
   ```bash
   # Check build logs
   oc logs build/<build-name>
   
   # Check build configuration
   oc describe buildconfig oru-analyzer
   ```

2. **Application Won't Start**
   ```bash
   # Check pod logs
   oc logs deploymentconfig/oru-analyzer
   
   # Check pod status
   oc describe pod <pod-name>
   ```

3. **Route Not Accessible**
   ```bash
   # Check route configuration
   oc describe route oru-analyzer
   
   # Check service
   oc get svc oru-analyzer
   ```

### Debug Commands

```bash
# Get all resources
oc get all -n resource-governance

# Check events
oc get events -n resource-governance

# Check build configuration
oc describe buildconfig oru-analyzer

# Check deployment configuration
oc describe deploymentconfig oru-analyzer
```

## 📚 Additional Resources

- [OpenShift Source-to-Image Documentation](https://docs.openshift.com/container-platform/4.15/builds/build-strategies.html#builds-strategy-s2i_build-strategies)
- [Python S2I Builder](https://github.com/sclorg/s2i-python-container)
- [OpenShift Templates](https://docs.openshift.com/container-platform/4.15/openshift_images/using-templates.html)

## 🤝 Contributing

To contribute to the S2I configuration:

1. Modify `.s2i/environment` for environment variables
2. Update `.s2i/bin/assemble` for build process
3. Update `.s2i/bin/run` for runtime behavior
4. Modify `openshift-s2i.yaml` for OpenShift resources
5. Test with `./scripts/deploy-s2i.sh`

---

**Note**: S2I deployment is an alternative to the standard container build process. Both methods are supported and can be used interchangeably based on your requirements.
