# AI Agents Support - OpenShift Resource Governance Tool

## 📋 Project Status Overview

**Current State**: ✅ **PRODUCTION READY** - Application is fully functional and cluster-agnostic

**Last Updated**: 2025-09-30
**Current Version**: 1.0.0
**Deployment Status**: 
- ✅ OCP 4.18: Working
- ✅ OCP 4.19: Working

## 🎯 Project Description

**OpenShift Resource Governance Tool** is a comprehensive web application that analyzes Kubernetes/OpenShift cluster resource usage, validates resource requests and limits against Red Hat best practices, and provides historical analysis using Prometheus metrics.

### Core Features
- **Resource Analysis**: Real-time analysis of CPU/memory requests and limits
- **Smart Problem Detection**: Identifies workloads without requests/limits and provides detailed analysis
- **Modal-based Analysis**: Professional interface with detailed pod and container analysis
- **Historical Analysis**: Workload-based historical resource usage (1d, 7d, 30d)
- **VPA Integration**: Vertical Pod Autoscaler recommendations (planned)
- **Export Reports**: Generate reports in XLS, CSV, PDF formats
- **Cluster Agnostic**: Works on any OpenShift cluster without configuration

## 🏗️ Architecture

### Backend (FastAPI)
- **Main App**: `app/main.py` - FastAPI application with lifespan management
- **API Routes**: `app/api/routes.py` - REST endpoints for cluster data
- **Core Services**:
  - `app/core/kubernetes_client.py` - K8s/OpenShift API client
  - `app/core/prometheus_client.py` - Prometheus metrics client
  - `app/services/validation_service.py` - Resource validation rules
  - `app/services/historical_analysis.py` - Historical data analysis
  - `app/services/report_service.py` - Report generation
- **Models**: `app/models/resource_models.py` - Pydantic data models

### Frontend (HTML/CSS/JavaScript)
- **Static Files**: `app/static/index.html` - Single-page application
- **Features**:
  - Pragmatic dashboard with single view
  - Modal-based detailed analysis for namespace problems
  - Problem Summary table showing namespace issues
  - Real-time cluster data display
  - Professional interface without browser alerts
  - Responsive design with Bootstrap

### Infrastructure
- **Container**: Docker with Python 3.11
- **Deployment**: Kubernetes/OpenShift with rolling updates
- **Monitoring**: Prometheus integration for metrics
- **Security**: RBAC with cluster-monitoring-view permissions

## 🚀 Current Deployment Status

### Working Clusters
1. **OCP 4.18**: `resource-governance.apps.shrocp4upi418ovn.lab.upshift.rdu2.redhat.com`
2. **OCP 4.19**: `resource-governance-route-resource-governance.apps.shrocp4upi419ovn.lab.upshift.rdu2.redhat.com`

### Deployment Process
```bash
# Quick deploy (recommended)
./scripts/deploy-complete.sh

# Manual deploy
./scripts/build-and-push.sh
oc apply -f k8s/
```

## ✅ Completed Features

### 1. Core Application
- [x] FastAPI backend with async support
- [x] Kubernetes/OpenShift API integration
- [x] Prometheus metrics collection
- [x] Resource validation with Red Hat best practices
- [x] Real-time cluster status dashboard

### 2. Smart Resource Analysis
- [x] Problem identification for namespaces with resource issues
- [x] Detailed pod and container analysis
- [x] Modal-based detailed view with recommendations
- [x] Issue categorization (missing requests, missing limits, wrong ratios)
- [x] Clear recommendations for each problem

### 3. UI/UX
- [x] Pragmatic dashboard with single view
- [x] Modal-based detailed analysis
- [x] Problem Summary table showing namespace issues
- [x] Professional interface without browser alerts
- [x] Responsive design with Bootstrap
- [x] Real-time data updates

### 4. Deployment & Infrastructure
- [x] Cluster-agnostic deployment
- [x] SSL/TLS support with fallback
- [x] RBAC configuration
- [x] Rolling update strategy
- [x] Route exposure for internet access
- [x] Docker Hub image publishing

### 5. Documentation & Localization
- [x] Complete translation from Portuguese to English
- [x] All comments, docstrings, and strings translated
- [x] README.md, DOCUMENTATION.md, AIAgents-Support.md in English
- [x] Clean documentation structure with only current files

## 🔧 Technical Implementation Details

### Key Files Modified
- `app/core/kubernetes_client.py` - SSL fallback for cluster compatibility
- `app/core/prometheus_client.py` - ServiceAccount token authentication
- `app/services/validation_service.py` - Enhanced resource validation engine
- `app/static/index.html` - Pragmatic dashboard with modal-based analysis
- `app/models/resource_models.py` - Updated models for container data structure
- `k8s/deployment.yaml` - Cluster-agnostic security context
- `k8s/route.yaml` - Dynamic hostname generation

### Critical Fixes Applied
1. **SSL Connection**: Fallback to disable SSL verification when CA cert is empty
2. **SCC Compatibility**: Removed hardcoded UIDs, let OpenShift assign them
3. **Route Agnostic**: Removed hardcoded hostname, let OpenShift generate it
4. **Image Pull**: Docker Hub secret configuration
5. **Prometheus Integration**: ServiceAccount token authentication
6. **Data Structure Fix**: Updated PodResource model to handle container dictionaries
7. **Validation Engine**: Fixed container resource access in validation_service.py
8. **UI/UX**: Replaced browser alerts with professional modals

## 🐛 Known Issues

### 1. Historical Analysis Data
**Status**: ⚠️ **SHOWING ZEROS**
**Issue**: Prometheus queries return zero values for CPU/memory usage
**Location**: `app/services/historical_analysis.py`
**Impact**: Historical analysis appears empty
**Next Steps**: Debug PromQL queries and metric availability

### 2. Export Functionality
**Status**: ⚠️ **NEEDS TESTING**
**Issue**: Export functionality needs validation with current implementation
**Location**: `app/services/report_service.py`
**Impact**: Users may not get proper export files
**Next Steps**: Test and fix file download mechanism

## 📋 Roadmap & Next Steps

### 🎯 **PRAGMATIC ROADMAP - Resource Governance Focus**

**Core Mission**: List projects without requests/limits + provide smart recommendations based on historical analysis + VPA integration

---

### **Phase 1: Enhanced Validation & Categorization (IN PROGRESS 🔄)**

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
- [ ] **Smart Historical Analysis**
  - Use historical data to suggest realistic requests/limits
  - Calculate P95/P99 percentiles for recommendations
  - Identify seasonal patterns and trends
  - Flag workloads with insufficient historical data

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

## 🔍 Development Guidelines

### Code Standards
- **Language**: English only (no Portuguese)
- **Comments**: Comprehensive docstrings
- **Error Handling**: Proper exception handling with logging
- **Testing**: Use Playwright for UI testing

### Git Workflow
- **Commits**: Descriptive messages without emojis
- **Branches**: Feature branches for major changes
- **Releases**: Tag stable versions

### Deployment Checklist
1. Test in development environment
2. Build and push Docker image
3. Deploy to test cluster
4. Verify all functionality
5. Deploy to production
6. Update documentation

## 🛠️ Troubleshooting Guide

### Common Issues
1. **SSL Certificate Errors**: Check `kubernetes_client.py` fallback logic
2. **SCC Permission Denied**: Verify `deployment.yaml` security context
3. **Image Pull Errors**: Check Docker Hub secret configuration
4. **Route Not Accessible**: Verify route hostname generation
5. **Prometheus Connection**: Check ServiceAccount token and RBAC

### Debug Commands
```bash
# Check pod logs
oc logs -f deployment/resource-governance -n resource-governance

# Check service status
oc get svc -n resource-governance

# Check route
oc get route -n resource-governance

# Test API
curl -k https://<route-url>/api/v1/health

# Test cluster status
curl -k https://<route-url>/api/v1/cluster/status

# Check deployment status
oc rollout status deployment/resource-governance -n resource-governance
```

## 📞 Support Information

### Key Contacts
- **Developer**: Anderson Nobre
- **Repository**: https://github.com/andersonid/openshift-resource-governance
- **Docker Hub**: andersonid/resource-governance:latest

### Resources
- **Main Documentation**: README.md
- **Documentation Index**: DOCUMENTATION.md
- **AI Agents Support**: AIAgents-Support.md (this file)
- **Deployment Scripts**: scripts/ directory
- **Kubernetes Manifests**: k8s/ directory

---

## 🎯 Current Session Context

**Last Action**: Implemented modal-based detailed analysis and professional interface
**Current Focus**: Enhanced validation engine with detailed pod/container analysis
**Next Priority**: Implement smart recommendations dashboard and VPA integration
**Status**: Phase 1 in progress - Enhanced Validation & Categorization partially completed

**Recent Achievements**:
- ✅ Modal-based detailed analysis for namespace problems
- ✅ Professional interface without browser alerts
- ✅ Problem Summary table with namespace issues
- ✅ Detailed pod and container analysis with recommendations
- ✅ Clear issue categorization and recommendations

**Note**: This file should be updated after each significant change to maintain project context for AI agents.
