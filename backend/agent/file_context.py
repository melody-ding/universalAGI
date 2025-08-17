"""
File context handling for the orchestrator system.
"""

import io
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from fastapi import UploadFile
from utils.logging_config import get_logger

logger = get_logger(__name__)

@dataclass
class FileContext:
    """Container for file-related context in chat."""
    filename: str
    file_content: bytes
    mime_type: Optional[str]
    file_size: int
    has_file: bool = True

class FileContextBuilder:
    """Builds file context from uploaded files."""
    
    SUPPORTED_EXTENSIONS = {
        '.pdf'
    }
    
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    
    async def build_file_context(self, file: Optional[UploadFile]) -> Optional[FileContext]:
        """
        Build file context from uploaded file.
        
        Args:
            file: FastAPI UploadFile object
            
        Returns:
            FileContext object or None if no file
            
        Raises:
            ValueError: If file is invalid or too large
        """
        if not file or not file.filename:
            return None
            
        # Validate file extension
        file_ext = self._get_file_extension(file.filename)
        if file_ext not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file type: {file_ext}. Only PDF files are supported.")
        
        try:
            # Read file content
            file_content = await file.read()
            file_size = len(file_content)
            
            # Validate file size
            if file_size > self.MAX_FILE_SIZE:
                raise ValueError(f"File too large: {file_size} bytes. Maximum allowed: {self.MAX_FILE_SIZE} bytes")
            
            if file_size == 0:
                raise ValueError("File is empty")
            
            logger.info(f"Built file context for {file.filename} ({file_size} bytes)")
            
            return FileContext(
                filename=file.filename,
                file_content=file_content,
                mime_type=file.content_type,
                file_size=file_size
            )
            
        except Exception as e:
            logger.error(f"Failed to build file context for {file.filename}: {str(e)}")
            raise ValueError(f"Failed to process file {file.filename}: {str(e)}")
    
    def _get_file_extension(self, filename: str) -> str:
        """Extract file extension from filename."""
        if '.' not in filename:
            return ''
        return '.' + filename.split('.')[-1].lower()

class DocumentAnalysisDetector:
    """Detects when user wants to perform document analysis."""
    
    ANALYSIS_KEYWORDS = [
        'analyze', 'analysis', 'check', 'review', 'evaluate', 'assess',
        'compliance', 'compliant', 'regulation', 'regulatory', 'standard',
        'audit', 'inspect', 'examine', 'validate', 'verify', 'test'
    ]
    
    ANALYSIS_PHRASES = [
        'analyze this document',
        'check compliance',
        'review against',
        'is this compliant',
        'does this meet',
        'evaluate document',
        'check this file',
        'analyze file',
        'compliance check',
        'regulatory review'
    ]
    
    def should_analyze_document(self, message: str, file_context: Optional[FileContext]) -> bool:
        """
        Determine if user wants document analysis.
        
        Args:
            message: User's message text
            file_context: File context if file is present
            
        Returns:
            True if document analysis should be performed
        """
        if not file_context:
            return False
            
        message_lower = message.lower()
        
        # Strong indicators
        phrase_matches = sum(1 for phrase in self.ANALYSIS_PHRASES if phrase in message_lower)
        keyword_matches = sum(1 for keyword in self.ANALYSIS_KEYWORDS if keyword in message_lower)
        
        # File + analysis keywords = document analysis intent
        if phrase_matches > 0:
            logger.info(f"Document analysis detected: phrase matches ({phrase_matches})")
            return True
            
        if keyword_matches >= 2:
            logger.info(f"Document analysis detected: keyword matches ({keyword_matches})")
            return True
            
        # File with minimal text could be analysis request
        if len(message.strip()) < 50 and keyword_matches >= 1:
            logger.info("Document analysis detected: short message with analysis keyword")
            return True
            
        return False
    
    def get_analysis_confidence(self, message: str, file_context: Optional[FileContext]) -> float:
        """Get confidence score for document analysis intent."""
        if not file_context:
            return 0.0
            
        message_lower = message.lower()
        phrase_matches = sum(1 for phrase in self.ANALYSIS_PHRASES if phrase in message_lower)
        keyword_matches = sum(1 for keyword in self.ANALYSIS_KEYWORDS if keyword in message_lower)
        
        if phrase_matches >= 2:
            return 0.95
        elif phrase_matches >= 1:
            return 0.85
        elif keyword_matches >= 3:
            return 0.80
        elif keyword_matches >= 2:
            return 0.70
        elif keyword_matches >= 1 and len(message.strip()) < 50:
            return 0.60
        else:
            return 0.0

# Singleton instances
file_context_builder = FileContextBuilder()
document_analysis_detector = DocumentAnalysisDetector()