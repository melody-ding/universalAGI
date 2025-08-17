"""
Document Analysis Tool for the agent system.
"""

import io
from typing import Dict, Any, Optional, List
from agent.tools import Tool
from services.framework_matcher import framework_matcher
from services.analysis_formatter import analysis_formatter
from document_evaluation.service import document_evaluation_service
from services.document_parser import document_parser
from utils.logging_config import get_logger

logger = get_logger(__name__)

class DocumentAnalysisTool(Tool):
    """Tool for analyzing documents against compliance frameworks."""
    
    def __init__(self):
        super().__init__(
            name="document_analysis",
            description="Analyze documents for compliance issues against regulatory frameworks"
        )
    
    async def execute(self, parameters: Dict[str, Any]) -> str:
        """
        Execute document analysis.
        
        Args:
            parameters: Dict containing:
                - file_content: bytes of the file
                - filename: name of the file
                - file_text: pre-parsed text (optional)
                - framework_ids: specific frameworks to use (optional)
        
        Returns:
            Formatted analysis results string
        
        Raises:
            ValueError: If required parameters are missing
            RuntimeError: If analysis fails
        """
        # Validate required parameters
        file_content = parameters.get("file_content")
        filename = parameters.get("filename")
        file_text = parameters.get("file_text")
        framework_ids = parameters.get("framework_ids")
        
        if not filename:
            raise ValueError("filename parameter is required")
        
        if not file_content and not file_text:
            raise ValueError("Either file_content or file_text parameter is required")
        
        try:
            # Parse document if text not provided
            if not file_text:
                if not file_content:
                    raise ValueError("file_content is required when file_text is not provided")
                
                logger.info(f"Parsing document: {filename}")
                file_stream = io.BytesIO(file_content)
                document_text = document_parser.parse_document(file_stream, filename)
            else:
                document_text = file_text
            
            if not document_text.strip():
                raise ValueError(f"Document {filename} appears to be empty or could not be parsed")
            
            # Find relevant frameworks if not specified
            if not framework_ids:
                logger.info("Finding relevant compliance frameworks")
                framework_ids = await framework_matcher.find_relevant_frameworks(document_text)
            
            if not framework_ids:
                raise RuntimeError("No relevant compliance frameworks found for this document")
            
            logger.info(f"Analyzing document against {len(framework_ids)} frameworks")
            
            # Run analysis against each framework
            results = []
            for framework_id in framework_ids:
                try:
                    logger.info(f"Running analysis against framework: {framework_id}")
                    
                    # Create fresh file stream for each analysis
                    if file_content:
                        file_stream = io.BytesIO(file_content)
                    else:
                        file_stream = io.BytesIO(document_text.encode('utf-8'))
                    
                    result = document_evaluation_service.evaluate_document(
                        file_stream, filename, framework_id
                    )
                    results.append(result)
                    
                except Exception as e:
                    logger.error(f"Analysis failed for framework {framework_id}: {str(e)}")
                    results.append({
                        "framework_id": framework_id,
                        "error": f"Analysis failed: {str(e)}"
                    })
            
            # Check if all analyses failed
            successful_results = [r for r in results if not isinstance(r, dict) or "error" not in r]
            if not successful_results:
                raise RuntimeError("All framework analyses failed")
            
            # Format results with detailed rule-by-rule breakdown
            logger.info("Formatting detailed analysis results")
            return self._format_detailed_analysis_results(results, filename)
            
        except Exception as e:
            raise RuntimeError(f"Document analysis failed: {str(e)}")
    
    def _format_detailed_analysis_results(self, results: list, filename: str) -> str:
        """
        Format analysis results with detailed rule-by-rule breakdown matching the analysis component.
        
        Args:
            results: List of DocumentEvaluationResponse objects or error dicts
            filename: Name of the analyzed file
            
        Returns:
            Formatted string with detailed analysis results
        """
        if not results:
            return f"❌ **No analysis results available for {filename}**"
        
        output_sections = []
        output_sections.append(f"# 📋 Compliance Analysis: {filename}\n")
        
        # Process each framework
        for i, result in enumerate(results, 1):
            if isinstance(result, dict) and "error" in result:
                output_sections.append(f"❌ **Framework {i}**: Analysis failed - {result['error']}\n")
                continue
            
            framework_section = self._format_detailed_framework_result(result)
            output_sections.append(framework_section)
        
        # Add overall summary
        overall_summary = self._generate_detailed_overall_summary(results)
        output_sections.append(overall_summary)
        
        return "\n".join(output_sections)
    
    def _format_detailed_framework_result(self, result) -> str:
        """Format individual framework with detailed rule-by-rule analysis."""
        try:
            from database.postgres_client import postgres_client
            framework = postgres_client.get_compliance_group_by_id(result.framework_id)
            framework_name = framework.name if framework else f"Framework {result.framework_id}"
        except Exception as e:
            logger.error(f"Failed to get framework name for {result.framework_id}: {str(e)}")
            framework_name = f"Framework {result.framework_id}"
        
        output = []
        
        # Framework header with overall stats
        compliance_percent = int(result.overall_compliance_score * 100)
        status_emoji = "✅" if compliance_percent >= 80 else "⚠️" if compliance_percent >= 60 else "❌"
        
        output.append(f"## {status_emoji} {framework_name}")
        output.append(f"**Overall Compliance Score**: {compliance_percent}% ({result.segments_processed}/{result.total_segments} segments)")
        output.append("")
        
        # Detailed segment analysis
        if result.segment_results:
            output.append("### 📊 Detailed Segment Analysis")
            
            for segment in result.segment_results:
                segment_section = self._format_segment_details(segment)
                output.append(segment_section)
        
        # Summary
        output.append(f"**📝 Summary**: {result.summary}")
        output.append("")
        
        return "\n".join(output)
    
    def _format_segment_details(self, segment) -> str:
        """Format detailed analysis for a specific segment."""
        segment_num = segment.segment_ordinal + 1
        confidence = int(segment.confidence_score * 100)
        
        # Status emoji and formatting
        if segment.compliance_status == 'compliant':
            status_emoji = "✅"
            status_text = "COMPLIANT"
        elif segment.compliance_status == 'needs_review':
            status_emoji = "⚠️"
            status_text = "NEEDS REVIEW"
        else:
            status_emoji = "❌"
            status_text = "NON-COMPLIANT"
        
        output = []
        output.append(f"#### {status_emoji} Segment {segment_num} - {status_text} ({confidence}% confidence)")
        
        # Show segment preview
        preview = segment.segment_preview[:150] + "..." if len(segment.segment_preview) > 150 else segment.segment_preview
        output.append(f"*Preview*: \"{preview}\"")
        output.append("")
        
        # Show applicable rules
        if hasattr(segment, 'applicable_rules') and segment.applicable_rules:
            output.append("**📋 Applicable Rules:**")
            for rule in segment.applicable_rules:
                rule_status = "✅ PASS" if segment.compliance_status == 'compliant' else "❌ FAIL"
                output.append(f"- **{rule.get('code', 'Unknown')}**: {rule.get('title', 'Unknown rule')} - {rule_status}")
                if rule.get('requirement'):
                    output.append(f"  *Requirement*: {rule['requirement']}")
        
        # Show specific issues if any
        if hasattr(segment, 'issues_found') and segment.issues_found:
            output.append("")
            output.append("**🚨 Issues Found:**")
            for issue in segment.issues_found:
                output.append(f"- **{issue.rule_code}**: {issue.description}")
                output.append(f"  *Issue Type*: {issue.issue_type.replace('_', ' ').title()}")
        
        output.append("")
        return "\n".join(output)
    
    def _generate_detailed_overall_summary(self, results: list) -> str:
        """Generate detailed overall assessment with recommendations."""
        valid_results = [r for r in results if hasattr(r, 'overall_compliance_score')]
        
        if not valid_results:
            return "## ❌ Overall Assessment\nUnable to determine compliance status due to analysis failures."
        
        # Calculate statistics
        total_segments = sum(r.total_segments for r in valid_results)
        processed_segments = sum(r.segments_processed for r in valid_results)
        avg_score = sum(r.overall_compliance_score for r in valid_results) / len(valid_results)
        
        # Count issues across all frameworks
        total_issues = 0
        
        for result in valid_results:
            if hasattr(result, 'segment_results'):
                for segment in result.segment_results:
                    if hasattr(segment, 'issues_found'):
                        total_issues += len(segment.issues_found)
        
        # Overall status
        if avg_score >= 0.8:
            status_emoji = "✅"
            status_text = "LARGELY COMPLIANT"
            recommendation = "Document meets most compliance requirements. Address any remaining issues for full compliance."
        elif avg_score >= 0.6:
            status_emoji = "⚠️"
            status_text = "PARTIALLY COMPLIANT"
            recommendation = "Document has compliance gaps that need attention. Review and address identified issues."
        else:
            status_emoji = "❌"
            status_text = "NON-COMPLIANT"
            recommendation = "Document has significant compliance issues requiring immediate attention and remediation."
        
        output = []
        output.append(f"## {status_emoji} Overall Assessment: {status_text}")
        output.append("")
        output.append(f"**📊 Summary Statistics:**")
        output.append(f"- Overall Compliance Score: **{avg_score:.1%}**")
        output.append(f"- Segments Analyzed: **{processed_segments}/{total_segments}**")
        output.append(f"- Total Issues Found: **{total_issues}**")
        output.append("")
        output.append(f"**💡 Recommendation:** {recommendation}")
        
        return "\n".join(output)