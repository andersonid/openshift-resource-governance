"""
Report generation service
"""
import logging
import json
import csv
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from io import StringIO

from app.models.resource_models import (
    ClusterReport, NamespaceReport, ResourceValidation, 
    VPARecommendation, ExportRequest
)
from app.core.config import settings

logger = logging.getLogger(__name__)

class ReportService:
    """Service for report generation"""
    
    def __init__(self):
        self.export_path = settings.report_export_path
        os.makedirs(self.export_path, exist_ok=True)
    
    def generate_cluster_report(
        self,
        pods: List[Any],
        validations: List[ResourceValidation],
        vpa_recommendations: List[VPARecommendation],
        overcommit_info: Dict[str, Any],
        nodes_info: List[Dict[str, Any]]
    ) -> ClusterReport:
        """Generate cluster report"""
        
        # Count unique namespaces
        namespaces = set(pod.namespace for pod in pods)
        
        # Generate summary
        summary = self._generate_summary(validations, vpa_recommendations, overcommit_info)
        
        report = ClusterReport(
            timestamp=datetime.now().isoformat(),
            total_pods=len(pods),
            total_namespaces=len(namespaces),
            total_nodes=len(nodes_info),
            validations=validations,
            vpa_recommendations=vpa_recommendations,
            overcommit_info=overcommit_info,
            summary=summary
        )
        
        return report
    
    def generate_namespace_report(
        self,
        namespace: str,
        pods: List[Any],
        validations: List[ResourceValidation],
        resource_usage: Dict[str, Any]
    ) -> NamespaceReport:
        """Generate namespace report"""
        
        # Filter validations for the namespace
        namespace_validations = [
            v for v in validations if v.namespace == namespace
        ]
        
        # Generate recommendations
        recommendations = self._generate_namespace_recommendations(namespace_validations)
        
        report = NamespaceReport(
            namespace=namespace,
            timestamp=datetime.now().isoformat(),
            total_pods=len(pods),
            validations=namespace_validations,
            resource_usage=resource_usage,
            recommendations=recommendations
        )
        
        return report
    
    def _generate_summary(
        self,
        validations: List[ResourceValidation],
        vpa_recommendations: List[VPARecommendation],
        overcommit_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate report summary"""
        
        # Count validations by severity
        severity_counts = {}
        for validation in validations:
            severity = validation.severity
            if severity not in severity_counts:
                severity_counts[severity] = 0
            severity_counts[severity] += 1
        
        # Count validations by type
        type_counts = {}
        for validation in validations:
            validation_type = validation.validation_type
            if validation_type not in type_counts:
                type_counts[validation_type] = 0
            type_counts[validation_type] += 1
        
        return {
            "total_validations": len(validations),
            "severity_breakdown": severity_counts,
            "validation_types": type_counts,
            "vpa_recommendations_count": len(vpa_recommendations),
            "overcommit_detected": overcommit_info.get("overcommit_detected", False),
            "critical_issues": severity_counts.get("critical", 0),
            "warnings": severity_counts.get("warning", 0),
            "errors": severity_counts.get("error", 0)
        }
    
    def _generate_namespace_recommendations(
        self, 
        validations: List[ResourceValidation]
    ) -> List[str]:
        """Generate recommendations for a namespace"""
        recommendations = []
        
        # Group by problem type
        problems = {}
        for validation in validations:
            problem_type = validation.validation_type
            if problem_type not in problems:
                problems[problem_type] = []
            problems[problem_type].append(validation)
        
        # Generate specific recommendations
        if "missing_requests" in problems:
            count = len(problems["missing_requests"])
            recommendations.append(
                f"Create LimitRange to define default requests "
                f"({count} containers without requests)"
            )
        
        if "missing_limits" in problems:
            count = len(problems["missing_limits"])
            recommendations.append(
                f"Define limits for {count} containers to avoid excessive consumption"
            )
        
        if "invalid_ratio" in problems:
            count = len(problems["invalid_ratio"])
            recommendations.append(
                f"Adjust limit:request ratio for {count} containers"
            )
        
        if "overcommit" in problems:
            recommendations.append(
                "Resolve resource overcommit in namespace"
            )
        
        return recommendations
    
    async def export_report(
        self, 
        report: ClusterReport, 
        export_request: ExportRequest
    ) -> str:
        """Export report in different formats"""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if export_request.format == "json":
            return await self._export_json(report, timestamp)
        elif export_request.format == "csv":
            return await self._export_csv(report, timestamp)
        elif export_request.format == "pdf":
            return await self._export_pdf(report, timestamp)
        else:
            raise ValueError(f"Unsupported format: {export_request.format}")
    
    async def _export_json(self, report: ClusterReport, timestamp: str) -> str:
        """Export report in JSON"""
        filename = f"cluster_report_{timestamp}.json"
        filepath = os.path.join(self.export_path, filename)
        
        # Converter para dict para serialização
        report_dict = report.dict()
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report_dict, f, indent=2, ensure_ascii=False)
        
        logger.info(f"JSON report exported: {filepath}")
        return filepath
    
    async def _export_csv(self, report: ClusterReport, timestamp: str) -> str:
        """Export report in CSV"""
        filename = f"cluster_report_{timestamp}.csv"
        filepath = os.path.join(self.export_path, filename)
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Cabeçalho
            writer.writerow([
                "Pod Name", "Namespace", "Container Name", 
                "Validation Type", "Severity", "Message", "Recommendation"
            ])
            
            # Validation data
            for validation in report.validations:
                writer.writerow([
                    validation.pod_name,
                    validation.namespace,
                    validation.container_name,
                    validation.validation_type,
                    validation.severity,
                    validation.message,
                    validation.recommendation or ""
                ])
        
        logger.info(f"CSV report exported: {filepath}")
        return filepath
    
    async def _export_pdf(self, report: ClusterReport, timestamp: str) -> str:
        """Export report in PDF"""
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib import colors
            
            filename = f"cluster_report_{timestamp}.pdf"
            filepath = os.path.join(self.export_path, filename)
            
            doc = SimpleDocTemplate(filepath, pagesize=letter)
            styles = getSampleStyleSheet()
            story = []
            
            # Título
            title = Paragraph("OpenShift Resource Governance Report", styles['Title'])
            story.append(title)
            story.append(Spacer(1, 12))
            
            # Resumo
            summary_text = f"""
            <b>Cluster Summary:</b><br/>
            Total Pods: {report.total_pods}<br/>
            Total Namespaces: {report.total_namespaces}<br/>
            Total Nodes: {report.total_nodes}<br/>
            Total Validations: {report.summary['total_validations']}<br/>
            Critical Issues: {report.summary['critical_issues']}<br/>
            """
            story.append(Paragraph(summary_text, styles['Normal']))
            story.append(Spacer(1, 12))
            
            # Validations table
            if report.validations:
                data = [["Pod", "Namespace", "Container", "Type", "Severity", "Message"]]
                for validation in report.validations[:50]:  # Limit to 50 for PDF
                    data.append([
                        validation.pod_name,
                        validation.namespace,
                        validation.container_name,
                        validation.validation_type,
                        validation.severity,
                        validation.message[:50] + "..." if len(validation.message) > 50 else validation.message
                    ])
                
                table = Table(data)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 14),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                
                story.append(Paragraph("<b>Validações:</b>", styles['Heading2']))
                story.append(table)
            
            doc.build(story)
            logger.info(f"PDF report exported: {filepath}")
            return filepath
            
        except ImportError:
            logger.error("reportlab not installed. Install with: pip install reportlab")
            raise ValueError("PDF export requires reportlab")
    
    def get_exported_reports(self) -> List[Dict[str, str]]:
        """List exported reports"""
        reports = []
        
        for filename in os.listdir(self.export_path):
            if filename.endswith(('.json', '.csv', '.pdf')):
                filepath = os.path.join(self.export_path, filename)
                stat = os.stat(filepath)
                reports.append({
                    "filename": filename,
                    "filepath": filepath,
                    "size": stat.st_size,
                    "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "format": filename.split('.')[-1]
                })
        
        return sorted(reports, key=lambda x: x["created"], reverse=True)
