# ORU Analyzer - OpenShift Resource Usage Analyzer

A comprehensive tool for analyzing user workloads and resource usage in OpenShift clusters that goes beyond what Metrics Server and VPA offer, providing validations, reports and consolidated recommendations.

## 🚀 Features

- **Automatic Collection**: Collects requests/limits from all pods/containers in the cluster
- **Red Hat Validations**: Validates capacity management best practices with specific request/limit values
- **Smart Resource Analysis**: Identifies workloads without requests/limits and provides detailed analysis
- **Detailed Problem Analysis**: Modal-based detailed view showing pod and container resource issues
- **Smart Recommendations Engine**: PatternFly-based gallery with individual workload cards and bulk selection
- **VPA CRD Integration**: Real Kubernetes API integration for Vertical Pod Autoscaler management
- **Historical Analysis**: Workload-based historical resource usage analysis with real numerical data (1h, 6h, 24h, 7d)
- **Prometheus Integration**: Collects real consumption metrics from OpenShift monitoring with OpenShift-specific queries
- **Cluster Overcommit Analysis**: Real-time cluster capacity vs requests analysis with detailed tooltips and modals
- **PromQL Query Display**: Shows raw Prometheus queries used for data collection, allowing validation in OpenShift console
- **Export Reports**: Generates reports in JSON, CSV formats
- **Modern Web UI**: PatternFly design system with professional interface and responsive layout
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

#### Option 1: Source-to-Image (S2I) - Fastest
```bash
# 1. Clone the repository
git clone https://github.com/andersonid/openshift-resource-governance.git
cd openshift-resource-governance

# 2. Login to OpenShift
oc login <cluster-url>

# 3. Deploy using S2I (complete deployment with all resources)
./scripts/deploy-s2i.sh
```

#### Option 2: Container Build (Traditional)
```bash
# 1. Clone the repository
git clone https://github.com/andersonid/openshift-resource-governance.git
cd openshift-resource-governance

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
# Example: https://oru.apps.your-cluster.com
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

#### Namespace Resource Distribution
```bash
GET /api/v1/namespace-distribution
```

#### Overcommit Status by Namespace
```bash
GET /api/v1/overcommit-by-namespace
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
# Build and push to Quay.io
./scripts/build-and-push.sh

# Deploy to OpenShift
./scripts/deploy-complete.sh
```

### Available Scripts
```bash
# Essential scripts (only 4 remaining after cleanup)
./setup.sh                    # Initial environment setup
./scripts/build-and-push.sh   # Build and push to Quay.io
./scripts/deploy-complete.sh  # Complete OpenShift deployment (Container Build)
./scripts/deploy-s2i.sh       # Complete S2I deployment (Source-to-Image + All Resources)
./scripts/undeploy-complete.sh # Complete application removal
```

## 🚀 Source-to-Image (S2I) Support

ORU Analyzer now supports **Source-to-Image (S2I)** deployment as an alternative to container-based deployment.

### S2I Benefits
- ⚡ **Faster deployment** - Direct from Git repository
- 🔄 **Automatic rebuilds** - When code changes
- 🎯 **No external registry** - OpenShift manages everything
- 🔧 **Simpler CI/CD** - No GitHub Actions + Quay.io needed

### S2I vs Container Build

| Feature | S2I | Container Build |
|---------|-----|-----------------|
| **Deployment Speed** | ⚡ Fast | 🐌 Slower |
| **Auto Rebuilds** | ✅ Yes | ❌ No |
| **Git Integration** | ✅ Native | ❌ Manual |
| **Registry Dependency** | ❌ None | ✅ Quay.io |
| **Build Control** | 🔒 Limited | 🎛️ Full Control |

### S2I Quick Start (Complete & Self-Service)
```bash
# Deploy using S2I with ALL resources automatically
./scripts/deploy-s2i.sh

# This single command creates:
# - Namespace
# - RBAC (ServiceAccount, ClusterRole, ClusterRoleBinding)
# - ConfigMap with all configurations
# - S2I Build and Deployment
# - Service and Route
# - Resource limits and requests
# - No additional commands needed!
```

For detailed S2I deployment information, see the S2I section above.

### Tests
```bash
# Test import
python -c "import app.main; print('OK')"

# Test API
curl http://localhost:8080/health
```

## 🆕 Recent Updates

### **Latest Version (v2.1.1) - Dashboard Charts Fixed**

**📊 Dashboard Charts Fixed:**
- ✅ **Real Data Integration**: All dashboard charts now use real cluster data instead of mock data
- ✅ **Namespace Resource Distribution**: Pie chart with real namespace data and proper labels
- ✅ **Overcommit Status by Namespace**: Real overcommit percentages based on cluster capacity
- ✅ **Resource Utilization Trend**: Real historical data with simulated 24h trends
- ✅ **Issues by Severity Timeline**: Real validation data with timeline simulation

**🚀 Source-to-Image (S2I) Support:**
- ✅ **S2I Deployment**: Alternative deployment method using OpenShift Source-to-Image
- ✅ **Automatic Builds**: Direct deployment from Git repository with auto-rebuilds
- ✅ **Simplified CI/CD**: No external registry dependency (Quay.io optional)
- ✅ **Faster Deployment**: S2I deployment is significantly faster than container builds
- ✅ **Git Integration**: Native OpenShift integration with Git repositories
- ✅ **Complete S2I Stack**: Custom assemble/run scripts, OpenShift templates, and deployment automation

**🎨 Previous Version (v2.0.0) - PatternFly UI Revolution:**
- ✅ **PatternFly Design System**: Modern, enterprise-grade UI components
- ✅ **Smart Recommendations Gallery**: Individual workload cards with bulk selection
- ✅ **VPA CRD Integration**: Real Kubernetes API for Vertical Pod Autoscaler management
- ✅ **Application Branding**: "ORU Analyzer" - OpenShift Resource Usage Analyzer
- ✅ **Resource Utilization Formatting**: Human-readable percentages (1 decimal place)
- ✅ **Quay.io Registry**: Migrated from Docker Hub to Quay.io for better reliability

**🔧 Infrastructure Improvements:**
- ✅ **GitHub Actions**: Automated build and push to Quay.io
- ✅ **Script Cleanup**: Removed 19 obsolete scripts, kept only essential ones
- ✅ **Codebase Organization**: Clean, maintainable code structure
- ✅ **Documentation**: Updated all documentation files
- ✅ **API Endpoints**: Added `/api/v1/namespace-distribution` and `/api/v1/overcommit-by-namespace` for real data

**🚀 Deployment Ready:**
- ✅ **Zero Downtime**: Rolling updates with proper health checks
- ✅ **Cluster Agnostic**: Works on any OpenShift 4.x cluster
- ✅ **Production Tested**: Deployed on OCP 4.15, 4.18, and 4.19

### **Performance Analysis & Optimization Roadmap**

**📊 Current Performance Analysis:**
- **Query Efficiency**: Currently using individual queries per workload (6 queries × N workloads)
- **Response Time**: 30-60 seconds for 10 workloads
- **Cache Strategy**: No caching implemented
- **Batch Processing**: Sequential workload processing

**🎯 Performance Optimization Plan:**
- **Phase 1**: Aggregated Queries (10x performance improvement)
- **Phase 2**: Intelligent Caching (5x performance improvement)  
- **Phase 3**: Batch Processing (3x performance improvement)
- **Phase 4**: Advanced Queries with MAX_OVER_TIME and percentiles

**Expected Results**: 10-20x faster response times (from 30-60s to 3-6s)

## 🤖 **AI AGENT CONTEXT - CRITICAL INFORMATION**

### **📋 Current Project Status (2025-01-03)**
- **Application**: ORU Analyzer (OpenShift Resource Usage Analyzer)
- **Version**: 2.0.0 - PatternFly UI Revolution
- **Status**: PRODUCTION READY - Fully functional and cluster-agnostic
- **Deployment**: Working on OCP 4.15, 4.18, and 4.19
- **Registry**: Quay.io (migrated from Docker Hub)
- **CI/CD**: GitHub Actions with automated build and push

### **🎯 Current Focus: Performance Optimization**
**IMMEDIATE PRIORITY**: Implement aggregated Prometheus queries to improve performance from 30-60s to 3-6s response times.

**Key Performance Issues Identified:**
1. **Query Multiplication**: Currently using 6 queries per workload (60 queries for 10 workloads)
2. **No Caching**: Every request refetches all data from Prometheus
3. **Sequential Processing**: Workloads processed one by one
4. **Missing Advanced Features**: No MAX_OVER_TIME, percentiles, or batch processing

### **🔧 Technical Architecture**
- **Backend**: FastAPI with async support
- **Frontend**: Single-page HTML with PatternFly design system
- **Database**: Prometheus for metrics, Kubernetes API for cluster data
- **Container**: Podman (NOT Docker) with Python 3.11
- **Registry**: Quay.io/rh_ee_anobre/resource-governance:latest
- **Deployment**: OpenShift with rolling updates

### **📁 Key Files Structure**
```
app/
├── main.py                    # FastAPI application
├── api/routes.py             # REST endpoints
├── core/
│   ├── kubernetes_client.py  # K8s/OpenShift API client
│   └── prometheus_client.py  # Prometheus metrics client
├── services/
│   ├── historical_analysis.py # Historical data analysis (NEEDS OPTIMIZATION)
│   ├── validation_service.py  # Resource validation rules
│   └── report_service.py     # Report generation
├── models/resource_models.py # Pydantic data models
└── static/index.html         # Frontend (PatternFly UI)
```

### **🚀 Deployment Process (STANDARD WORKFLOW)**
```bash
# 1. Make changes to code
# 2. Commit and push
git add .
git commit -m "Description of changes"
git push

# 3. Wait for GitHub Actions (builds and pushes to Quay.io)
# 4. Deploy to OpenShift
oc rollout restart deployment/resource-governance -n resource-governance

# 5. Wait for rollout completion
oc rollout status deployment/resource-governance -n resource-governance

# 6. Test with Playwright
```

### **⚠️ CRITICAL RULES FOR AI AGENTS**
1. **ALWAYS use podman, NEVER docker** - All container operations use podman
2. **ALWAYS build with 'latest' tag** - Never create version tags
3. **ALWAYS ask for confirmation** before commit/push/build/deploy
4. **ALWAYS test with Playwright** after deployment
5. **NEVER use browser alerts** - Use professional modals instead
6. **ALWAYS update documentation** after significant changes
7. **ALWAYS use English** - No Portuguese in code or documentation

### **🔍 Performance Analysis: ORU Analyzer vs thanos-metrics-analyzer**

**Our Current Approach:**
```python
# ✅ STRENGTHS:
# - Dynamic step calculation based on time range
# - Async queries with aiohttp
# - Individual workload precision
# - OpenShift-specific queries

# ❌ WEAKNESSES:
# - 6 queries per workload (60 queries for 10 workloads)
# - No caching mechanism
# - Sequential processing
# - No batch optimization
```

**thanos-metrics-analyzer Approach:**
```python
# ✅ STRENGTHS:
# - MAX_OVER_TIME for peak usage analysis
# - Batch processing with cluster grouping
# - Aggregated queries for multiple workloads
# - Efficient data processing with pandas

# ❌ WEAKNESSES:
# - Synchronous queries (prometheus_api_client)
# - Fixed resolution (10m step)
# - No intelligent caching
# - Less granular workload analysis
```

**🚀 Optimization Strategy:**
1. **Aggregated Queries**: Single query for all workloads instead of N×6 queries
2. **Intelligent Caching**: 5-minute TTL cache for repeated queries
3. **Batch Processing**: Process workloads in groups of 5
4. **Advanced Queries**: Implement MAX_OVER_TIME and percentiles like thanos
5. **Async + Batch**: Combine our async approach with thanos batch processing

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

### **Phase 2: Smart Recommendations Engine (COMPLETED ✅)**

#### 2.1 Recommendation Dashboard
- [x] **Dedicated Recommendations Section**
  - Replaced generic "VPA Recommendations" with "Smart Recommendations"
  - PatternFly Service Card gallery with individual workload cards
  - Bulk selection functionality for batch operations
  - Priority-based visual indicators and scoring

#### 2.2 Recommendation Types
- [x] **Resource Configuration Recommendations**
  - "Add CPU requests: 200m (based on 7-day P95 usage)"
  - "Increase memory limits: 512Mi (current usage peaks at 400Mi)"
  - "Fix CPU ratio: 3:1 instead of 5:1 (current: 500m limit, 100m request)"

- [x] **VPA Activation Recommendations**
  - "Activate VPA for new workload 'example' (insufficient historical data)"
  - "Enable VPA for outlier workload 'high-cpu-app' (unpredictable usage patterns)"

#### 2.3 Priority Scoring System
- [x] **Impact-Based Prioritization**
  - **Critical**: Missing limits on high-resource workloads
  - **High**: Missing requests on production workloads
  - **Medium**: Suboptimal ratios on established workloads
  - **Low**: New workloads needing VPA activation

#### 2.4 VPA CRD Integration
- [x] **Real Kubernetes API Integration**
  - Direct VPA CRD management using Kubernetes CustomObjectsApi
  - VPA creation, listing, and deletion functionality
  - Real-time VPA status and recommendations
  - YAML generation and application capabilities

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
