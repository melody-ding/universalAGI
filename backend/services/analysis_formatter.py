from typing import List, Dict, Any
from database.postgres_client import postgres_client
from utils.logging_config import get_logger

logger = get_logger(__name__)

class AnalysisFormatter:
    """Service for formatting document analysis results for chat display."""
    
    def format_analysis_results(self, results: List[Any], filename: str) -> str:
        """
        Format analysis results into readable chat response.
        
        Args:
            results: List of DocumentEvaluationResponse objects or error dicts
            filename: Name of the analyzed file
            
        Returns:
            Formatted string for chat display
        """
        if not results:
            raise ValueError(f"No analysis results provided for {filename}")
        
        output = [f"## Compliance Analysis Results for {filename}\n"]
        
        for i, result in enumerate(results, 1):
            if isinstance(result, dict) and "error" in result:
                output.append(f"**Framework {i}**: Analysis failed - {result['error']}\n")
                continue
            
            framework_section = self._format_framework_result(result, i)
            output.append(framework_section)
        
        # Add overall assessment
        overall_assessment = self._generate_overall_assessment(results)
        output.append(overall_assessment)
        
        return "\n".join(output)
    
    def _format_framework_result(self, result: Any, framework_number: int) -> str:
        """Format individual framework analysis result."""
        try:
            # Get framework name
            framework = postgres_client.get_compliance_group_by_id(result.framework_id)
            framework_name = framework.name if framework else f"Framework {result.framework_id}"
        except Exception as e:
            logger.error(f"Failed to get framework name for {result.framework_id}: {str(e)}")
            framework_name = f"Framework {result.framework_id}"
        
        output = [f"### {framework_name}"]
        output.append(f"**Overall Compliance Score**: {result.overall_compliance_score:.1%}")
        output.append(f"**Segments Analyzed**: {result.segments_processed}/{result.total_segments}")
        
        # Count and categorize issues
        issue_counts = self._count_issues_by_type(result.segment_results)
        if issue_counts['total'] > 0:
            output.append(f"**Issues Found**: {issue_counts['total']} total")
            if issue_counts['non_compliant'] > 0:
                output.append(f"  - {issue_counts['non_compliant']} non-compliant segments")
            if issue_counts['needs_review'] > 0:
                output.append(f"  - {issue_counts['needs_review']} segments need review")
        else:
            output.append("**Issues Found**: None")
        
        # Add summary
        output.append(f"**Summary**: {result.summary}")
        output.append("")
        
        return "\n".join(output)
    
    def _count_issues_by_type(self, segment_results: List[Any]) -> Dict[str, int]:
        """Count issues by compliance status."""
        counts = {
            'total': 0,
            'non_compliant': 0,
            'needs_review': 0,
            'compliant': 0
        }
        
        for segment in segment_results:
            if hasattr(segment, 'compliance_status'):
                status = segment.compliance_status
                if status == 'non_compliant':
                    counts['non_compliant'] += 1
                    counts['total'] += len(segment.issues_found) if hasattr(segment, 'issues_found') else 1
                elif status == 'needs_review':
                    counts['needs_review'] += 1
                    counts['total'] += len(segment.issues_found) if hasattr(segment, 'issues_found') else 1
                elif status == 'compliant':
                    counts['compliant'] += 1
        
        return counts
    
    def _generate_overall_assessment(self, results: List[Any]) -> str:
        """Generate overall assessment across all frameworks."""
        valid_results = [r for r in results if hasattr(r, 'overall_compliance_score')]
        
        if not valid_results:
            return "**Overall Assessment**: Unable to determine compliance status"
        
        avg_score = sum(r.overall_compliance_score for r in valid_results) / len(valid_results)
        
        if avg_score >= 0.8:
            assessment = "Document appears largely compliant across analyzed frameworks"
        elif avg_score >= 0.6:
            assessment = "Document has some compliance issues that need attention"
        else:
            assessment = "Document has significant compliance issues requiring review"
        
        return f"**Overall Assessment**: {assessment} (Average score: {avg_score:.1%})"

# Singleton instance
analysis_formatter = AnalysisFormatter()