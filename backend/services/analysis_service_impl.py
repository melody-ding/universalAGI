"""
Concrete implementation of AnalysisService.
"""

import io
from typing import List, Dict, Any
from services.interfaces import AnalysisService, AnalysisResult
from document_evaluation.service import document_evaluation_service
from utils.logging_config import get_logger

logger = get_logger(__name__)


class AnalysisServiceImpl(AnalysisService):
    """Concrete implementation of AnalysisService."""
    
    def __init__(self):
        self.evaluation_service = document_evaluation_service
    
    async def analyze_document(self, 
                             file_stream: io.BytesIO, 
                             filename: str, 
                             framework_ids: List[str]) -> AnalysisResult:
        """Analyze a document against specified frameworks."""
        try:
            logger.info(f"Analyzing document {filename} against {len(framework_ids)} frameworks")
            
            if not framework_ids:
                return AnalysisResult(
                    framework_results=[],
                    overall_summary="No frameworks specified for analysis.",
                    success=False,
                    error="No frameworks provided"
                )
            
            # Run analysis against each framework
            results = []
            successful_results = []
            
            for framework_id in framework_ids:
                try:
                    logger.info(f"Running analysis against framework: {framework_id}")
                    
                    # Create fresh file stream for each analysis
                    file_stream.seek(0)  # Reset stream position
                    
                    result = self.evaluation_service.evaluate_document(
                        file_stream, filename, framework_id
                    )
                    
                    results.append({
                        "framework_id": framework_id,
                        "result": result,
                        "success": True
                    })
                    successful_results.append(result)
                    
                except Exception as e:
                    logger.error(f"Analysis failed for framework {framework_id}: {str(e)}")
                    results.append({
                        "framework_id": framework_id,
                        "error": str(e),
                        "success": False
                    })
            
            # Check if all analyses failed
            if not successful_results:
                return AnalysisResult(
                    framework_results=results,
                    overall_summary="All framework analyses failed.",
                    success=False,
                    error="All analyses failed"
                )
            
            # Generate overall summary
            overall_summary = self._generate_overall_summary(successful_results, filename)
            
            logger.info(f"Document analysis completed: {len(successful_results)}/{len(framework_ids)} frameworks succeeded")
            
            return AnalysisResult(
                framework_results=results,
                overall_summary=overall_summary,
                success=True
            )
            
        except Exception as e:
            logger.error(f"Document analysis failed for {filename}: {str(e)}")
            return AnalysisResult(
                framework_results=[],
                overall_summary=f"Analysis failed: {str(e)}",
                success=False,
                error=str(e)
            )
    
    async def format_analysis_results(self, 
                                    results: List[Dict[str, Any]], 
                                    filename: str) -> str:
        """Format analysis results for presentation."""
        try:
            logger.info(f"Formatting analysis results for {filename}")
            
            if not results:
                return f"❌ **No analysis results available for {filename}**"
            
            output_sections = []
            output_sections.append(f"# 📋 Compliance Analysis: {filename}\n")
            
            # Process each framework result
            successful_results = []
            for i, result_data in enumerate(results, 1):
                if not result_data.get("success", False):
                    error_msg = result_data.get("error", "Unknown error")
                    output_sections.append(f"❌ **Framework {i}**: Analysis failed - {error_msg}\n")
                    continue
                
                result = result_data.get("result")
                if result:
                    framework_section = self._format_framework_result(result)
                    output_sections.append(framework_section)
                    successful_results.append(result)
            
            # Add overall summary if we have successful results
            if successful_results:
                overall_summary = self._format_overall_summary(successful_results)
                output_sections.append(overall_summary)
            
            formatted_result = "\n".join(output_sections)
            logger.info(f"Successfully formatted analysis results for {filename}")
            
            return formatted_result
            
        except Exception as e:
            logger.error(f"Failed to format analysis results: {str(e)}")
            return f"❌ **Error formatting analysis results**: {str(e)}"
    
    def _generate_overall_summary(self, results: List[Any], filename: str) -> str:
        """Generate overall summary from analysis results."""
        if not results:
            return "No successful analyses to summarize."
        
        # Calculate statistics
        total_segments = sum(getattr(r, 'total_segments', 0) for r in results)
        processed_segments = sum(getattr(r, 'segments_processed', 0) for r in results)
        avg_score = sum(getattr(r, 'overall_compliance_score', 0) for r in results) / len(results)
        
        # Determine overall status
        if avg_score >= 0.8:
            status = "LARGELY COMPLIANT"
        elif avg_score >= 0.6:
            status = "PARTIALLY COMPLIANT"
        else:
            status = "NON-COMPLIANT"
        
        return f"Overall Status: {status} (Average Score: {avg_score:.1%}, Segments: {processed_segments}/{total_segments})"
    
    def _format_framework_result(self, result) -> str:
        """Format individual framework result with detailed policy failures."""
        try:
            from database.postgres_client import postgres_client
            framework = postgres_client.get_compliance_group_by_id(result.framework_id)
            framework_name = framework.name if framework else f"Framework {result.framework_id}"
        except Exception:
            framework_name = f"Framework {result.framework_id}"
        
        compliance_percent = int(getattr(result, 'overall_compliance_score', 0) * 100)
        status_emoji = "✅" if compliance_percent >= 80 else "⚠️" if compliance_percent >= 60 else "❌"
        
        output = []
        output.append(f"## {status_emoji} {framework_name}")
        output.append(f"**Overall Compliance Score**: {compliance_percent}% ({getattr(result, 'segments_processed', 0)}/{getattr(result, 'total_segments', 0)} segments)")
        
        # Add summary if available
        summary = getattr(result, 'summary', 'No summary available')
        output.append(f"**📝 Summary**: {summary}")
        output.append("")
        
        # Add detailed policy failures
        policy_failures = self._extract_policy_failures(result)
        if policy_failures:
            output.append("### 🚨 Policy Failures Identified:")
            output.append("")
            for i, failure in enumerate(policy_failures, 1):
                output.append(f"**{i}. {failure['rule_code']}**")
                output.append(f"   - **Issue Type**: {failure['issue_type'].replace('_', ' ').title()}")
                output.append(f"   - **Description**: {failure['description']}")
                output.append(f"   - **Segment**: {failure['segment_info']}")
                output.append("")
        else:
            output.append("### ✅ No Policy Failures Identified")
            output.append("The document appears to meet all applicable compliance requirements for this framework.")
            output.append("")
        
        return "\n".join(output)
    
    def _extract_policy_failures(self, result) -> List[Dict[str, str]]:
        """Extract detailed policy failures from analysis result."""
        policy_failures = []
        
        # Check if result has segment_results attribute
        segment_results = getattr(result, 'segment_results', [])
        
        for segment in segment_results:
            if hasattr(segment, 'issues_found') and segment.issues_found:
                segment_preview = getattr(segment, 'segment_preview', f"Segment {getattr(segment, 'segment_ordinal', '?')}")
                segment_info = f"Segment {getattr(segment, 'segment_ordinal', '?')}: {segment_preview[:100]}..."
                
                for issue in segment.issues_found:
                    policy_failures.append({
                        'rule_code': getattr(issue, 'rule_code', 'Unknown Rule'),
                        'issue_type': getattr(issue, 'issue_type', 'compliance_violation'),
                        'description': getattr(issue, 'description', 'No description available'),
                        'severity': getattr(issue, 'severity', 'medium'),
                        'segment_info': segment_info
                    })
        
        # Sort by severity (high, medium, low)
        severity_order = {'high': 0, 'medium': 1, 'low': 2}
        policy_failures.sort(key=lambda x: severity_order.get(x['severity'], 1))
        
        return policy_failures
    
    def _format_overall_summary(self, results: List[Any]) -> str:
        """Format overall summary section."""
        if not results:
            return "## ❌ Overall Assessment\nNo results to assess."
        
        # Calculate statistics
        total_segments = sum(getattr(r, 'total_segments', 0) for r in results)
        processed_segments = sum(getattr(r, 'segments_processed', 0) for r in results)
        avg_score = sum(getattr(r, 'overall_compliance_score', 0) for r in results) / len(results)
        
        # Overall status
        if avg_score >= 0.8:
            status_emoji = "✅"
            status_text = "LARGELY COMPLIANT"
            recommendation = "Document meets most compliance requirements."
        elif avg_score >= 0.6:
            status_emoji = "⚠️"
            status_text = "PARTIALLY COMPLIANT"
            recommendation = "Document has compliance gaps that need attention."
        else:
            status_emoji = "❌"
            status_text = "NON-COMPLIANT"
            recommendation = "Document has significant compliance issues."
        
        output = []
        output.append(f"## {status_emoji} Overall Assessment: {status_text}")
        output.append("")
        output.append(f"**📊 Summary Statistics:**")
        output.append(f"- Overall Compliance Score: **{avg_score:.1%}**")
        output.append(f"- Segments Analyzed: **{processed_segments}/{total_segments}**")
        output.append("")
        output.append(f"**💡 Recommendation:** {recommendation}")
        
        # Add summary of all policy failures
        all_failures = []
        for result in results:
            failures = self._extract_policy_failures(result)
            all_failures.extend(failures)
        
        if all_failures:
            output.append("")
            output.append("### 🚨 Key Policy Failures Across All Frameworks:")
            
            # Group failures by rule code to avoid duplicates
            unique_failures = {}
            for failure in all_failures:
                rule_code = failure['rule_code']
                if rule_code not in unique_failures or failure['severity'] == 'high':
                    unique_failures[rule_code] = failure
            
            # Show top failures (max 5)
            top_failures = sorted(unique_failures.values(), 
                                key=lambda x: {'high': 0, 'medium': 1, 'low': 2}.get(x['severity'], 1))[:5]
            
            for i, failure in enumerate(top_failures, 1):
                output.append(f"**{i}. {failure['rule_code']}**")
                output.append(f"   {failure['description']}")
            
            if len(all_failures) > 5:
                output.append(f"   *... and {len(all_failures) - 5} additional policy issues*")
        
        return "\n".join(output)
