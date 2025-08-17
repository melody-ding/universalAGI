"""
Concrete implementation of DocumentService.
"""

import io
from typing import Dict, Any, Optional
from services.interfaces import DocumentService, DocumentParseResult
from services.document_parser import document_parser
from database.postgres_client import postgres_client
from utils.logging_config import get_logger

logger = get_logger(__name__)


class DocumentServiceImpl(DocumentService):
    """Concrete implementation of DocumentService."""
    
    def __init__(self):
        self.parser = document_parser
        self.db_client = postgres_client
    
    async def parse_document(self, file_stream: io.BytesIO, filename: str) -> DocumentParseResult:
        """Parse a document from a file stream."""
        try:
            logger.info(f"Parsing document: {filename}")
            
            # Validate file stream
            if not file_stream:
                return DocumentParseResult(
                    text="",
                    metadata={},
                    success=False,
                    error="File stream is empty"
                )
            
            # Parse the document
            document_text = self.parser.parse_document(file_stream, filename)
            
            if not document_text.strip():
                return DocumentParseResult(
                    text="",
                    metadata={"filename": filename},
                    success=False,
                    error="Document appears to be empty or could not be parsed"
                )
            
            # Extract metadata
            metadata = {
                "filename": filename,
                "text_length": len(document_text),
                "word_count": len(document_text.split()),
                "file_extension": filename.split('.')[-1] if '.' in filename else ""
            }
            
            logger.info(f"Successfully parsed document: {filename} ({len(document_text)} characters)")
            
            return DocumentParseResult(
                text=document_text,
                metadata=metadata,
                success=True
            )
            
        except Exception as e:
            logger.error(f"Failed to parse document {filename}: {str(e)}")
            return DocumentParseResult(
                text="",
                metadata={"filename": filename},
                success=False,
                error=str(e)
            )
    
    async def get_document_metadata(self, document_id: int) -> Optional[Dict[str, Any]]:
        """Get metadata for a document by ID."""
        try:
            logger.info(f"Retrieving metadata for document ID: {document_id}")
            
            document = self.db_client.get_document_by_id(document_id)
            if not document:
                logger.warning(f"Document not found: {document_id}")
                return None
            
            # Get additional metadata
            segment_count = self.db_client.get_document_segments_count(document_id)
            
            metadata = {
                "id": document.id,
                "title": document.title,
                "checksum": document.checksum,
                "blob_link": document.blob_link,
                "mime_type": document.mime_type,
                "created_at": document.created_at.isoformat() if document.created_at else None,
                "compliance_framework_id": document.compliance_framework_id,
                "segment_count": segment_count
            }
            
            logger.info(f"Retrieved metadata for document {document_id}")
            return metadata
            
        except Exception as e:
            logger.error(f"Failed to get metadata for document {document_id}: {str(e)}")
            return None
    
    async def validate_document(self, file_content: bytes, filename: str) -> bool:
        """Validate if a document can be processed."""
        try:
            # Check file size (e.g., max 50MB)
            max_size = 50 * 1024 * 1024  # 50MB
            if len(file_content) > max_size:
                logger.warning(f"Document {filename} exceeds size limit: {len(file_content)} bytes")
                return False
            
            # Check file extension
            allowed_extensions = {'.pdf', '.docx', '.doc', '.txt'}
            file_extension = '.' + filename.lower().split('.')[-1] if '.' in filename else ''
            
            if file_extension not in allowed_extensions:
                logger.warning(f"Unsupported file type: {file_extension}")
                return False
            
            # Try a quick parse test
            file_stream = io.BytesIO(file_content)
            try:
                test_text = self.parser.parse_document(file_stream, filename)
                if not test_text.strip():
                    logger.warning(f"Document {filename} appears to be empty")
                    return False
            except Exception as parse_error:
                logger.warning(f"Document {filename} failed parse test: {str(parse_error)}")
                return False
            
            logger.info(f"Document {filename} passed validation")
            return True
            
        except Exception as e:
            logger.error(f"Error validating document {filename}: {str(e)}")
            return False
