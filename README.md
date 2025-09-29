# OpenShift Resource Governance Tool

A resource governance tool for OpenShift clusters that goes beyond what Metrics Server and VPA offer, providing validations, reports and consolidated recommendations.

## 🚀 Features

- **Automatic Collection**: Collects requests/limits from all pods/containers in the cluster
- **Red Hat Validations**: Validates capacity management best practices with specific request/limit values
- **Historical Analysis**: Workload-based historical resource usage analysis (1d, 7d, 30d)
- **Prometheus Integration**: Collects real consumption metrics from OpenShift monitoring
- **Export Reports**: Generates reports in JSON, CSV formats
- **Web UI**: Modern interface with sidebar navigation and real-time updates
- **Cluster Agnostic**: Works on any OpenShift cluster without configuration

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

### 📋 Manual Deploy (Development)

```bash
# Build and push image
./scripts/build-and-push.sh

# Deploy to OpenShift
oc apply -f k8s/

# Wait for deployment
oc rollout status deployment/resource-governance -n resource-governance
```

### 🗑️ Undeploy

```bash
# Completely remove application
./scripts/undeploy-complete.sh
```

### 🌐 Application Access

After deploy, access the application through the created route:

```bash
# Get route URL
oc get route -n resource-governance

# Access via browser (URL will be automatically generated)
# Example: https://resource-governance-route-resource-governance.apps.your-cluster.com
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
  PROMETHEUS_URL: "http://prometheus-k8s.openshift-monitoring.svc.cluster.local:9091"
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

#### Historical Analysis
```bash
GET /api/v1/namespace/{namespace}/workload/{workload}/historical-analysis?time_range=24h
```

#### Export Report
```bash
POST /api/v1/export
Content-Type: application/json

{
  "format": "csv",
  "namespaces": ["default", "kube-system"],
  "includeVPA": true,
  "includeAnalysis": true
}
```

### Usage Examples

#### 1. Check Cluster Status
```bash
curl https://your-route-url/api/v1/cluster/status
```

#### 2. Export CSV Report
```bash
curl -X POST https://your-route-url/api/v1/export \
  -H "Content-Type: application/json" \
  -d '{"format": "csv", "includeAnalysis": true}'
```

#### 3. View Critical Validations
```bash
curl "https://your-route-url/api/v1/validations?severity=critical"
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
- **Details**: Shows specific request and limit values (e.g., "Request: 100m, Limit: 500m")

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
- Runs as non-root user (OpenShift assigns UID automatically)
- Uses SecurityContext with runAsNonRoot: true
- Limits resources with requests/limits
- Cluster-agnostic security context

## 🐛 Troubleshooting

### Check Logs
```bash
oc logs -f deployment/resource-governance -n resource-governance
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
curl https://your-route-url/health

# API test
curl https://your-route-url/api/v1/cluster/status
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
- [ ] VPA Integration and Health Monitoring
- [ ] PDF reports with charts
- [ ] Advanced filtering and search
- [ ] Alerting system (email, Slack)
- [ ] Multi-cluster support
- [ ] RBAC integration
- [ ] API documentation (OpenAPI/Swagger)

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
