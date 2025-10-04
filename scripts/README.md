# OpenShift Resource Governance Tool - Scripts

## Overview
This directory contains scripts for building, deploying, and updating the OpenShift Resource Governance Tool.

## Scripts

### 1. `deploy-complete.sh` - Initial Deployment
**Purpose**: Complete deployment from scratch
**When to use**: First time deployment or when you need to recreate everything

**What it does**:
- Creates namespace
- Applies RBAC (ServiceAccount, ClusterRole, ClusterRoleBinding)
- Applies ConfigMap
- Creates ServiceAccount token secret
- Deploys application
- Creates Service and Route
- Configures TLS

**Usage**:
```bash
./scripts/deploy-complete.sh
```

### 2. `rollout-restart.sh` - Updates (Recommended)
**Purpose**: Update existing deployment with new image
**When to use**: After code changes and GitHub Actions has built new image

**What it does**:
- Restarts deployment to pull new image
- Waits for rollout completion
- Checks pod status and logs
- Shows application URL

**Usage**:
```bash
./scripts/rollout-restart.sh
```

### 3. `build-and-push.sh` - Manual Build
**Purpose**: Build and push image manually (when GitHub Actions is not available)
**When to use**: Manual builds or when GitHub Actions is not working

**What it does**:
- Builds container image with Podman
- Tests image
- Pushes to Quay.io registry

**Usage**:
```bash
# Login to Quay.io first
podman login quay.io

# Then build and push
./scripts/build-and-push.sh
```

### 4. `undeploy-complete.sh` - Cleanup
**Purpose**: Remove all resources
**When to use**: When you want to completely remove the application

**Usage**:
```bash
echo 'yes' | ./scripts/undeploy-complete.sh
```

## Recommended Workflow

### For Development Updates (Most Common):
1. Make code changes
2. `git add . && git commit -m "Your changes" && git push`
3. Wait for GitHub Actions to build new image
4. `./scripts/rollout-restart.sh`

### For Initial Deployment:
1. `./scripts/deploy-complete.sh`

### For Manual Build (if needed):
1. `podman login quay.io`
2. `./scripts/build-and-push.sh`
3. `./scripts/rollout-restart.sh`

## Security Notes

- **No hardcoded credentials**: All scripts require manual login to Quay.io
- **Common functions**: Shared code is in `common.sh` to avoid duplication
- **Error handling**: All scripts have proper error checking and validation

## Troubleshooting

- **Not connected to cluster**: Run `oc login` first
- **Deployment not found**: Run `./scripts/deploy-complete.sh` first
- **Image not found**: Ensure GitHub Actions completed successfully or run `./scripts/build-and-push.sh`
