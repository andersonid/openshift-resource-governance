# UWRU Scanner - User Workloads and Resource Usage Scanner

A comprehensive tool for analyzing user workloads and resource usage in OpenShift clusters that goes beyond what Metrics Server and VPA offer, providing validations, reports and consolidated recommendations.

## 🚀 Features

- **Automatic Collection**: Collects requests/limits from all pods/containers in the cluster
- **Red Hat Validations**: Validates capacity management best practices with specific request/limit values
- **Smart Resource Analysis**: Identifies workloads without requests/limits and provides detailed analysis
- **Detailed Problem Analysis**: Modal-based detailed view showing pod and container resource issues
- **Historical Analysis**: Workload-based historical resource usage analysis with real numerical data (1h, 6h, 24h, 7d)
- **Prometheus Integration**: Collects real consumption metrics from OpenShift monitoring with OpenShift-specific queries
- **Cluster Overcommit Analysis**: Real-time cluster capacity vs requests analysis with detailed tooltips and modals
- **PromQL Query Display**: Shows raw Prometheus queries used for data collection, allowing validation in OpenShift console
- **Export Reports**: Generates reports in JSON, CSV formats
- **Modern Web UI**: Pragmatic dashboard with modal-based analysis and professional interface
- **Cluster Agnostic**: Works on any OpenShift cluster without configuration

## 📋 Requirements

- OpenShift 4.x
- Prometheus (native in OCP)
- VPA (optional, for recommendations)
- Python 3.11+
- Podman (preferred)
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

#### Workload Metrics with PromQL Queries
```bash
GET /api/v1/workloads/{namespace}/{workload}/metrics?time_range=24h
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

### 6. Insufficient Historical Data
- **Problem**: Workloads with limited historical data for analysis
- **Severity**: Warning
- **Recommendation**: Wait for more data points or enable VPA for new workloads

### 7. Seasonal Pattern Detection
- **Problem**: Workloads with unpredictable usage patterns
- **Severity**: Info
- **Recommendation**: Consider VPA for dynamic resource adjustments

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

### Run with Podman (Recommended)
```bash
# Build
podman build -t resource-governance .

# Run
podman run -p 8080:8080 resource-governance
```

### Run with Podman (Alternative)
```bash
# Build
podman build -t resource-governance .

# Run
podman run -p 8080:8080 resource-governance
```

### Tests
```bash
# Test import
python -c "import app.main; print('OK')"

# Test API
curl http://localhost:8080/health
```

## 📝 Roadmap

### 🎯 **PRAGMATIC ROADMAP - Resource Governance Focus**

**Core Mission**: List projects without requests/limits + provide smart recommendations based on historical analysis + VPA integration

---

### **Phase 0: UI/UX Simplification (COMPLETED ✅)**

#### 0.1 Interface Simplification
- [x] **Group similar validations** in a single card
- [x] **Show only essential** in main view
- [x] **Technical details** in modal or expandable section
- [x] **Color coding**: 🔴 Critical, 🟡 Warning, 🔵 Info
- [x] **Specific icons**: ⚡ CPU, 💾 Memory, 📊 Ratio
- [x] **Collapsible cards** to reduce visual pollution

#### 0.2 Improve Visual Hierarchy
- [x] **Pragmatic dashboard** with single view
- [x] **Direct actions**: "Analyze" and "Fix" buttons
- [x] **Problem Summary table** showing namespace issues
- [x] **Modal-based analysis** for detailed views
- [x] **Professional interface** without browser alerts

#### 0.3 Advanced Features
- [x] **Modal-based analysis** for detailed problem inspection
- [x] **Detailed pod and container analysis** with recommendations
- [x] **Namespace comparison** through Problem Summary table

---

### **Phase 1: Enhanced Validation & Categorization (COMPLETED ✅)**

#### 1.1 Smart Resource Detection
- [x] **Enhanced Validation Engine**
  - Better categorization of resource issues (missing requests, missing limits, wrong ratios)
  - Severity scoring based on impact and risk
  - Detailed analysis of pod and container resource configurations

- [x] **Workload Analysis System**
  - **Problem Identification**: Namespaces with resource configuration issues
  - **Detailed Analysis**: Pod-by-pod breakdown with container details
  - **Issue Categorization**: Missing requests, missing limits, wrong ratios
  - **Recommendations**: Clear guidance on how to fix each issue

#### 1.2 Historical Analysis Integration
- [x] **Smart Historical Analysis**
  - Use historical data to suggest realistic requests/limits
  - Calculate P95/P99 percentiles for recommendations
  - Identify seasonal patterns and trends
  - Flag workloads with insufficient historical data
  - Real numerical consumption data with cluster percentages
  - OpenShift-specific Prometheus queries for better accuracy
  - Workload selector with time ranges (1h, 6h, 24h, 7d)
  - Simulated data fallback for demonstration
  - PromQL query display for validation in OpenShift console

#### 1.3 Cluster Overcommit Analysis
- [x] **Real-time Overcommit Monitoring**
  - CPU and Memory capacity vs requests analysis
  - Detailed tooltips with capacity, requests, and available resources
  - Modal-based detailed breakdown of overcommit calculations
  - Resource utilization tracking
  - Professional UI with info icons and modal interactions

---

### **Phase 2: Smart Recommendations Engine (SHORT TERM - 2-3 weeks)**

#### 2.1 Recommendation Dashboard
- [ ] **Dedicated Recommendations Section**
  - Replace generic "VPA Recommendations" with "Smart Recommendations"
  - Show actionable insights with priority levels
  - Display estimated impact of changes
  - Group by namespace and severity

#### 2.2 Recommendation Types
- [ ] **Resource Configuration Recommendations**
  - "Add CPU requests: 200m (based on 7-day P95 usage)"
  - "Increase memory limits: 512Mi (current usage peaks at 400Mi)"
  - "Fix CPU ratio: 3:1 instead of 5:1 (current: 500m limit, 100m request)"

- [ ] **VPA Activation Recommendations**
  - "Activate VPA for new workload 'example' (insufficient historical data)"
  - "Enable VPA for outlier workload 'high-cpu-app' (unpredictable usage patterns)"

#### 2.3 Priority Scoring System
- [ ] **Impact-Based Prioritization**
  - **Critical**: Missing limits on high-resource workloads
  - **High**: Missing requests on production workloads
  - **Medium**: Suboptimal ratios on established workloads
  - **Low**: New workloads needing VPA activation

---

### **Phase 3: VPA Integration & Automation (MEDIUM TERM - 3-4 weeks)**

#### 3.1 VPA Detection & Management
- [ ] **VPA Status Detection**
  - Detect existing VPAs in cluster
  - Show VPA health and status
  - Display current VPA recommendations
  - Compare VPA suggestions with current settings

#### 3.2 Smart VPA Activation
- [ ] **Automatic VPA Suggestions**
  - Suggest VPA activation for new workloads (< 7 days)
  - Recommend VPA for outlier workloads
  - Provide VPA YAML configurations
  - Show estimated benefits of VPA activation

#### 3.3 VPA Recommendation Integration
- [ ] **VPA Data Integration**
  - Fetch VPA recommendations from cluster
  - Compare VPA suggestions with historical analysis
  - Show confidence levels for recommendations
  - Display VPA update modes and policies

---

### **Phase 4: Action Planning & Implementation (LONG TERM - 4-6 weeks)**

#### 4.1 Action Plan Generation
- [ ] **Step-by-Step Action Plans**
  - Generate specific kubectl/oc commands
  - Show before/after resource configurations
  - Estimate implementation time and effort
  - Provide rollback procedures

#### 4.2 Implementation Tracking
- [ ] **Progress Monitoring**
  - Track which recommendations have been implemented
  - Show improvement metrics after changes
  - Alert on new issues or regressions
  - Generate implementation reports

#### 4.3 Advanced Analytics
- [ ] **Cost Optimization Insights**
  - Show potential cost savings from recommendations
  - Identify over-provisioned resources
  - Suggest right-sizing opportunities
  - Display resource utilization trends

---

### **Phase 5: Enterprise Features (FUTURE - 6+ weeks)**

#### 5.1 Advanced Governance
- [ ] **Policy Enforcement**
  - Custom resource policies per namespace
  - Automated compliance checking
  - Policy violation alerts
  - Governance reporting

#### 5.2 Multi-Cluster Support
- [ ] **Cross-Cluster Analysis**
  - Compare resource usage across clusters
  - Centralized recommendation management
  - Cross-cluster best practices
  - Unified reporting

---

## 🎯 **IMMEDIATE NEXT STEPS (This Week)**

### Priority 1: Enhanced Validation Engine
1. **Improve Resource Detection**
   - Better categorization of missing requests/limits
   - Add workload age detection
   - Implement severity scoring

2. **Smart Categorization**
   - New workloads (< 7 days) → VPA candidates
   - Established workloads (> 7 days) → Historical analysis
   - Outlier workloads → Special attention needed

### Priority 2: Recommendation Dashboard
1. **Create Recommendations Section**
   - Replace generic VPA section
   - Show actionable insights
   - Display priority levels

2. **Historical Analysis Integration**
   - Use Prometheus data for recommendations
   - Calculate realistic resource suggestions
   - Show confidence levels

### Priority 3: VPA Integration
1. **VPA Detection**
   - Find existing VPAs in cluster
   - Show VPA status and health
   - Display current recommendations

2. **Smart VPA Suggestions**
   - Identify VPA candidates
   - Generate VPA configurations
   - Show estimated benefits

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
