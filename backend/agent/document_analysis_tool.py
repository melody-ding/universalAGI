"""
Document Analysis Tool for the agent system.
"""

import io
from typing import Dict, Any, Optional, List
from agent.tools import Tool
from services.interfaces import DocumentService, FrameworkService, AnalysisService
from services.service_container import get_document_service, get_framework_service, get_analysis_service
from utils.logging_config import get_logger

logger = get_logger(__name__)

class DocumentAnalysisTool(Tool):
    """Tool for analyzing documents against compliance frameworks."""
    
    def __init__(self, 
                 document_service: Optional[DocumentService] = None,
                 framework_service: Optional[FrameworkService] = None,
                 analysis_service: Optional[AnalysisService] = None):
        super().__init__(
            name="document_analysis",
            description="Analyze documents for compliance issues against regulatory frameworks"
        )
        
        # Use dependency injection with fallback to service container
        self.document_service = document_service or get_document_service()
        self.framework_service = framework_service or get_framework_service()
        self.analysis_service = analysis_service or get_analysis_service()
    
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
                parse_result = await self.document_service.parse_document(file_stream, filename)
                
                if not parse_result.success:
                    raise ValueError(f"Document parsing failed: {parse_result.error}")
                
                document_text = parse_result.text
            else:
                document_text = file_text
            
            if not document_text.strip():
                raise ValueError(f"Document {filename} appears to be empty or could not be parsed")
            
            # Find relevant frameworks if not specified
            if not framework_ids:
                logger.info("Finding relevant compliance frameworks")
                framework_match_result = await self.framework_service.find_relevant_frameworks(document_text)
                framework_ids = framework_match_result.framework_ids
            
            if not framework_ids:
                raise RuntimeError("No relevant compliance frameworks found for this document")
            
            logger.info(f"Analyzing document against {len(framework_ids)} frameworks")
            
            # Create file stream for analysis
            if file_content:
                file_stream = io.BytesIO(file_content)
            else:
                file_stream = io.BytesIO(document_text.encode('utf-8'))
            
            # Run analysis using the analysis service
            analysis_result = await self.analysis_service.analyze_document(
                file_stream, filename, framework_ids
            )
            
            if not analysis_result.success:
                raise RuntimeError(f"Analysis failed: {analysis_result.error}")
            
            # Format results with detailed rule-by-rule breakdown
            logger.info("Formatting detailed analysis results")
            return await self.analysis_service.format_analysis_results(
                analysis_result.framework_results, filename
            )
            
        except Exception as e:
            raise RuntimeError(f"Document analysis failed: {str(e)}")
    
