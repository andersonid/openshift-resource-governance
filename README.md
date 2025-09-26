# OpenShift Resource Governance Tool

A resource governance tool for OpenShift clusters that goes beyond what Metrics Server and VPA offer, providing validations, reports and consolidated recommendations.

## 🚀 Features

- **Automatic Collection**: Collects requests/limits from all pods/containers in the cluster
- **Red Hat Validations**: Validates capacity management best practices
- **VPA Integration**: Consumes VPA recommendations in Off mode
- **Prometheus Integration**: Collects real consumption metrics
- **Consolidated Reports**: Generates reports in JSON, CSV and PDF
- **Web UI**: Simple interface for visualization and interaction
- **Recommendation Application**: Allows approving and applying recommendations

## 📋 Requirements

- OpenShift 4.x
- Prometheus (native in OCP)
- VPA (optional, for recommendations)
- Python 3.11+
- Docker
- OpenShift CLI (oc)

## 🛠️ Installation

### 🚀 Quick Deploy (Recommended)

```bash
# 1. Clone the repository
git clone <repository-url>
cd RequestsAndLimits

# 2. Login to OpenShift
oc login <cluster-url>

# 3. Complete deploy (creates everything automatically)
./scripts/deploy-complete.sh
```

### 📋 Manual Deploy

#### 1. Image Build

```bash
# Local build
./scripts/build.sh

# Build with specific tag
./scripts/build.sh v1.0.0

# Build for specific registry
./scripts/build.sh latest your-username
```

#### 2. Deploy to OpenShift

```bash
# Apply all resources
oc apply -f k8s/

# Wait for deployment
oc rollout status deployment/resource-governance -n resource-governance
```

#### 🚀 Automatic CI/CD (Recommended for Production)
```bash
# 1. Configure GitHub secrets
./scripts/setup-github-secrets.sh

# 2. Commit and push
git add .
git commit -m "New feature"
git push origin main

# 3. GitHub Actions will do automatic deploy!
```

**Automatic Flow:**
- ✅ **Push to main** → GitHub Actions detects change
- ✅ **Automatic build** → New image on Docker Hub
- ✅ **Automatic deploy** → OpenShift updates deployment
- ✅ **Rolling Update** → Zero downtime
- ✅ **Health Checks** → Automatic validation

#### 🔧 Manual Deploy (Development)
```bash
# Deploy with Blue-Green strategy
./scripts/blue-green-deploy.sh

# Deploy with specific tag
./scripts/blue-green-deploy.sh v1.2.0

# Test CI/CD flow locally
./scripts/test-ci-cd.sh
```

**Development Scripts:**
- ✅ **Full control** over the process
- ✅ **Fast iteration** during development
- ✅ **Easier debugging**
- ✅ **Local tests** before pushing

#### Complete Deploy (Initial)
```bash
# Complete deploy with ImagePullSecret (first time)
./scripts/deploy-complete.sh
```

This script will:
- ✅ Create namespace and RBAC
- ✅ Configure ImagePullSecret for Docker Hub
- ✅ Deploy application
- ✅ Configure Service and Route
- ✅ Verify everything is working

#### Manual Deploy
```bash
# Default deploy
./scripts/deploy.sh

# Deploy with specific tag
./scripts/deploy.sh v1.0.0

# Deploy to specific registry
./scripts/deploy.sh latest your-username
```

#### Undeploy
```bash
# Completely remove application
./scripts/undeploy-complete.sh
```

### 3. Application Access

After deploy, access the application through the created route:

```bash
# Get route URL
oc get route resource-governance-route -n resource-governance

# Access via browser
# https://resource-governance-route-resource-governance.apps.openshift.local
```

## 🔧 Configuration

### ConfigMap

The application is configured through the ConfigMap `resource-governance-config`:

```yaml
data:
  CPU_LIMIT_RATIO: "3.0"                    # Default limit:request ratio for CPU
  MEMORY_LIMIT_RATIO: "3.0"                 # Default limit:request ratio for memory
  MIN_CPU_REQUEST: "10m"                    # Minimum CPU request
  MIN_MEMORY_REQUEST: "32Mi"                # Minimum memory request
  CRITICAL_NAMESPACES: |                    # Critical namespaces for VPA
    openshift-monitoring
    openshift-ingress
    openshift-apiserver
  PROMETHEUS_URL: "http://prometheus.openshift-monitoring.svc.cluster.local:9090"
```

### Environment Variables

- `KUBECONFIG`: Path to kubeconfig (used in development)
- `PROMETHEUS_URL`: Prometheus URL
- `CPU_LIMIT_RATIO`: CPU limit:request ratio
- `MEMORY_LIMIT_RATIO`: Memory limit:request ratio
- `MIN_CPU_REQUEST`: Minimum CPU request
- `MIN_MEMORY_REQUEST`: Minimum memory request

## 📊 Usage

### API Endpoints

#### Cluster Status
```bash
GET /api/v1/cluster/status
```

#### Namespace Status
```bash
GET /api/v1/namespace/{namespace}/status
```

#### Validations
```bash
GET /api/v1/validations?namespace=default&severity=error
```

#### VPA Recommendations
```bash
GET /api/v1/vpa/recommendations?namespace=default
```

#### Export Report
```bash
POST /api/v1/export
Content-Type: application/json

{
  "format": "json",
  "namespaces": ["default", "kube-system"],
  "includeVPA": true,
  "includeValidations": true
}
```

### Usage Examples

#### 1. Check Cluster Status
```bash
curl https://resource-governance-route-resource-governance.apps.openshift.local/api/v1/cluster/status
```

#### 2. Export CSV Report
```bash
curl -X POST https://resource-governance-route-resource-governance.apps.openshift.local/api/v1/export \
  -H "Content-Type: application/json" \
  -d '{"format": "csv", "includeVPA": true}'
```

#### 3. View Critical Validations
```bash
curl "https://resource-governance-route-resource-governance.apps.openshift.local/api/v1/validations?severity=critical"
```

## 🔍 Implemented Validations

### 1. Required Requests
- **Problem**: Pods without defined requests
- **Severity**: Error
- **Recommendation**: Define CPU and memory requests

### 2. Recommended Limits
- **Problem**: Pods without defined limits
- **Severity**: Warning
- **Recommendation**: Define limits to avoid excessive consumption

### 3. Limit:Request Ratio
- **Problem**: Ratio too high or low
- **Severity**: Warning/Error
- **Recommendation**: Adjust to 3:1 ratio

### 4. Minimum Values
- **Problem**: Requests too low
- **Severity**: Warning
- **Recommendation**: Increase to minimum values

### 5. Overcommit
- **Problem**: Requests exceed cluster capacity
- **Severity**: Critical
- **Recommendation**: Reduce requests or add nodes

## 📈 Reports

### JSON Format
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "total_pods": 150,
  "total_namespaces": 25,
  "total_nodes": 3,
  "validations": [...],
  "vpa_recommendations": [...],
  "summary": {
    "total_validations": 45,
    "critical_issues": 5,
    "warnings": 25,
    "errors": 15
  }
}
```

### CSV Format
```csv
Pod Name,Namespace,Container Name,Validation Type,Severity,Message,Recommendation
pod-1,default,nginx,missing_requests,error,Container without defined requests,Define CPU and memory requests
```

## 🔐 Security

### RBAC
The application uses a dedicated ServiceAccount with minimal permissions:

- **Pods**: get, list, watch, patch, update
- **Namespaces**: get, list, watch
- **Nodes**: get, list, watch
- **VPA**: get, list, watch
- **Deployments/ReplicaSets**: get, list, watch, patch, update

### Security Context
- Runs as non-root user (UID 1000)
- Uses SecurityContext with runAsNonRoot: true
- Limits resources with requests/limits

## 🐛 Troubleshooting

### Check Logs
```bash
oc logs -f daemonset/resource-governance -n resource-governance
```

### Check Pod Status
```bash
oc get pods -n resource-governance
oc describe pod <pod-name> -n resource-governance
```

### Check RBAC
```bash
oc auth can-i get pods --as=system:serviceaccount:resource-governance:resource-governance-sa
```

### Test Connectivity
```bash
# Health check
curl https://resource-governance-route-resource-governance.apps.openshift.local/health

# API test
curl https://resource-governance-route-resource-governance.apps.openshift.local/api/v1/cluster/status
```

## 🚀 Development

### Run Locally
```bash
# Install dependencies
pip install -r requirements.txt

# Run application
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

### Run with Docker
```bash
# Build
docker build -t resource-governance .

# Run
docker run -p 8080:8080 resource-governance
```

### Tests
```bash
# Test import
python -c "import app.main; print('OK')"

# Test API
curl http://localhost:8080/health
```

## 📝 Roadmap

### Upcoming Versions
- [ ] Web UI with interactive charts
- [ ] PDF reports with charts
- [ ] Custom rules per namespace
- [ ] GitOps integration (ArgoCD)
- [ ] Slack/Teams notifications
- [ ] Custom Prometheus metrics
- [ ] Multi-cluster support

## 🤝 Contributing

1. Fork the project
2. Create a branch for your feature (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is under the MIT license. See the [LICENSE](LICENSE) file for details.

## 📞 Support

For support and questions:
- Open an issue on GitHub
- Consult OpenShift documentation
- Check application logs
