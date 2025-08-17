import json
import time
import io
from typing import Optional
from fastapi import APIRouter, File, UploadFile, Form, Request
from fastapi.responses import StreamingResponse

from config import settings
from models import SendMessageResponse, Message, CitationRequest, CitationResponse, CitationInfo
from database.models import ComplianceGroupCreateRequest, ComplianceGroupUpdateRequest
from document_evaluation.models import DocumentEvaluationRequest, DocumentEvaluationResponse
from pydantic import BaseModel
from services import chat_service
from utils.logging_config import get_logger, log_request
from utils.error_handler import (
    raise_user_error, raise_validation_error, raise_resource_not_found,
    raise_external_service_error, raise_database_error, raise_processing_error
)
from utils.exceptions import (
    UserError, ValidationError, ResourceNotFoundError, ExternalServiceError,
    DatabaseError, ProcessingError, ConfigurationError
)

router = APIRouter()

class DocumentComplianceFrameworkUpdateRequest(BaseModel):
    compliance_framework_id: Optional[str] = None

@router.get("/")
async def root():
    return {"message": "Chat Backend API is running"}

@router.get("/health")
async def health_check():
    """Health check endpoint for load balancers and monitoring"""
    try:
        # Basic health check - can be expanded to check database connectivity
        return {
            "status": "healthy",
            "timestamp": time.time(),
            "version": "1.0.0",
            "environment": settings.environment.value
        }
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "timestamp": time.time(),
            "error": str(e)
        }


@router.post("/send-message-stream")
async def send_message_stream(
    message: str = Form(""),
    conversation_history: str = Form("[]"),
    image: UploadFile = File(None),
    document_file: UploadFile = File(None),
    document_id: int = Form(None)
):
    start_time = time.time()
    logger = get_logger(__name__)
    
    try:
        logger.info(
            "Received streaming request",
            extra_fields={
                "message_length": len(message),
                "has_image": image is not None,
                "has_document": document_file is not None,
                "history_length": len(conversation_history) if conversation_history else 0,
                "document_id": document_id
            }
        )
        
        # Validate configuration
        if not settings.is_openai_configured:
            raise ConfigurationError("OPENAI_API_KEY", "OpenAI API key not configured")
        
        # Validate input
        if not message.strip() and not image and not document_file:
            raise ValidationError("Message, image, or document file required")
        
        # Parse conversation history from JSON string
        try:
            history_data = json.loads(conversation_history) if conversation_history else []
            history = [Message(**msg) for msg in history_data]
            logger.info(f"Parsed conversation history with {len(history)} messages")
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse conversation history: {e}")
            history = []
        
        # Read files immediately to prevent closure issues
        image_content = None
        document_content = None
        
        if image and image.filename:
            try:
                image_content = await image.read()
                logger.info(f"Read image file: {image.filename} ({len(image_content)} bytes)")
            except Exception as e:
                logger.error(f"Failed to read image file: {str(e)}")
                raise ValidationError(f"Failed to read image file: {str(e)}")
        
        if document_file and document_file.filename:
            try:
                document_content = await document_file.read()
                logger.info(f"Read document file: {document_file.filename} ({len(document_content)} bytes)")
            except Exception as e:
                logger.error(f"Failed to read document file: {str(e)}")
                raise ValidationError(f"Failed to read document file: {str(e)}")
        
        async def safe_streaming_generator():
            try:
                async for chunk in chat_service.get_streaming_response(
                    message, history, 
                    (image, image_content) if image_content else None, 
                    (document_file, document_content) if document_content else None, 
                    document_id
                ):
                    yield chunk
                logger.info("Streaming completed successfully")
                yield f"data: [DONE]\n\n"
            except Exception as e:
                logger.error(f"Error in streaming generator: {str(e)}", exc_info=True)
                error_data = json.dumps({'type': 'error', 'content': f"Streaming error: {str(e)}"})
                yield f"data: {error_data}\n\n"
                yield f"data: [DONE]\n\n"
        
        response = StreamingResponse(
            safe_streaming_generator(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": settings.ALLOWED_ORIGINS[0] if settings.ALLOWED_ORIGINS else "*",
                "Access-Control-Allow-Credentials": "true",
            }
        )
        
        # Log successful request
        duration = time.time() - start_time
        log_request(logger, "POST", "/send-message-stream", 200, duration)
        
        return response
        
    except (UserError, ValidationError, ConfigurationError):
        # Re-raise user-facing errors
        raise
    except Exception as e:
        # Log and re-raise unexpected errors
        duration = time.time() - start_time
        logger.error(
            f"Unexpected error in send_message_stream: {str(e)}",
            extra_fields={"duration": duration},
            exc_info=True
        )
        raise ProcessingError("message_streaming", "request_processing", str(e))

@router.post("/upload-document")
async def upload_document(file: UploadFile = File(...)):
    start_time = time.time()
    logger = get_logger(__name__)
    
    try:
        logger.info(
            "Received document upload request",
            extra_fields={
                "filename": file.filename,
                "size": file.size,
                "content_type": file.content_type
            }
        )
        
        # Validate file presence
        if not file:
            raise ValidationError("No file provided")
        
        # Validate filename
        if not file.filename:
            raise ValidationError("File must have a filename")
        
        # Validate file type
        allowed_extensions = {'.pdf', '.docx', '.doc', '.txt'}
        file_extension = '.' + file.filename.lower().split('.')[-1]
        if file_extension not in allowed_extensions:
            raise ValidationError(
                f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}",
                {"file_extension": [f"Extension '{file_extension}' is not supported"]}
            )
        
        # Process the document upload
        from services.document_upload_service import document_upload_service
        result = await document_upload_service.process_document_upload(file)
        
        logger.info(
            "Document uploaded successfully",
            extra_fields={
                "filename": file.filename,
                "document_id": result.document_id,
                "num_segments": result.num_segments
            }
        )
        
        # Log successful request
        duration = time.time() - start_time
        log_request(logger, "POST", "/upload-document", 200, duration)
        
        return result
        
    except (UserError, ValidationError):
        # Re-raise user-facing errors
        raise
    except Exception as e:
        # Log and re-raise unexpected errors
        duration = time.time() - start_time
        logger.error(
            f"Error uploading document: {str(e)}",
            extra_fields={"duration": duration, "filename": file.filename if file else None},
            exc_info=True
        )
        raise ProcessingError("document_upload", "file_processing", str(e))

@router.get("/documents")
async def get_documents():
    start_time = time.time()
    logger = get_logger(__name__)
    
    try:
        from database.postgres_client import postgres_client
        documents = postgres_client.get_all_documents()
        
        # Convert to response format
        response_data = {
            "documents": [
                {
                    "id": doc.id,
                    "title": doc.title,
                    "checksum": doc.checksum,
                    "blob_link": doc.blob_link,
                    "created_at": doc.created_at.isoformat() if doc.created_at else None,
                    "mime_type": doc.mime_type,
                    "compliance_framework_id": doc.compliance_framework_id
                }
                for doc in documents
            ]
        }
        
        logger.info(
            "Documents fetched successfully",
            extra_fields={"document_count": len(documents)}
        )
        
        # Log successful request
        duration = time.time() - start_time
        log_request(logger, "GET", "/documents", 200, duration)
        
        return response_data
        
    except Exception as e:
        # Log and re-raise unexpected errors
        duration = time.time() - start_time
        logger.error(
            f"Error fetching documents: {str(e)}",
            extra_fields={"duration": duration},
            exc_info=True
        )
        raise DatabaseError("SELECT", "documents", e)

@router.get("/documents/{document_id}")
async def get_document(document_id: int):
    start_time = time.time()
    logger = get_logger(__name__)
    
    try:
        from database.postgres_client import postgres_client
        document = postgres_client.get_document_by_id(document_id)
        
        if not document:
            raise ResourceNotFoundError("Document", str(document_id))
        
        # Get segment count for additional metadata
        segment_count = postgres_client.get_document_segments_count(document_id)
        
        # Convert to response format
        response_data = {
            "id": document.id,
            "title": document.title,
            "checksum": document.checksum,
            "blob_link": document.blob_link,
            "created_at": document.created_at.isoformat() if document.created_at else None,
            "num_segments": segment_count,
            "mime_type": document.mime_type,
            "compliance_framework_id": document.compliance_framework_id
        }
        
        logger.info(
            "Document fetched successfully",
            extra_fields={"document_id": document_id}
        )
        
        # Log successful request
        duration = time.time() - start_time
        log_request(logger, "GET", f"/documents/{document_id}", 200, duration)
        
        return response_data
        
    except (ResourceNotFoundError):
        # Re-raise user-facing errors
        raise
    except Exception as e:
        # Log and re-raise unexpected errors
        duration = time.time() - start_time
        logger.error(
            f"Error fetching document {document_id}: {str(e)}",
            extra_fields={"duration": duration, "document_id": document_id},
            exc_info=True
        )
        raise DatabaseError("SELECT", "documents", e)

@router.get("/documents/{document_id}/viewer-url")
async def get_document_viewer_url(document_id: int):
    start_time = time.time()
    logger = get_logger(__name__)
    
    try:
        from database.postgres_client import postgres_client
        from database.s3_client import s3_client
        
        # Get document details
        document = postgres_client.get_document_by_id(document_id)
        
        if not document:
            raise ResourceNotFoundError("Document", str(document_id))
        
        # Get S3 key from document hash
        s3_key = s3_client.get_s3_key_from_document(document.checksum)
        
        # Generate fresh signed URL for viewing with correct content type
        viewer_url = s3_client.generate_viewer_url(s3_key, document.mime_type)
        
        logger.info(
            "Generated viewer URL successfully",
            extra_fields={"document_id": document_id}
        )
        
        # Log successful request
        duration = time.time() - start_time
        log_request(logger, "GET", f"/documents/{document_id}/viewer-url", 200, duration)
        
        return {"viewer_url": viewer_url}
        
    except (ResourceNotFoundError):
        # Re-raise user-facing errors
        raise
    except Exception as e:
        # Log and re-raise unexpected errors
        duration = time.time() - start_time
        logger.error(
            f"Error generating viewer URL for document {document_id}: {str(e)}",
            extra_fields={"duration": duration, "document_id": document_id},
            exc_info=True
        )
        raise ExternalServiceError("s3", "generate_presigned_url", str(e))

@router.delete("/documents/{document_id}")
async def delete_document(document_id: int):
    start_time = time.time()
    logger = get_logger(__name__)
    
    try:
        from database.postgres_client import postgres_client
        
        # Check if document exists
        doc_response = postgres_client.execute_statement(
            "SELECT id FROM documents WHERE id = :document_id",
            [{'name': 'document_id', 'value': {'longValue': document_id}}]
        )
        
        if not doc_response['records']:
            raise ResourceNotFoundError("Document", str(document_id))
        
        # Delete the document and all related data
        postgres_client.delete_document_and_segments(document_id, include_s3_cleanup=True)
        
        logger.info(
            "Document deleted successfully",
            extra_fields={"document_id": document_id}
        )
        
        # Log successful request
        duration = time.time() - start_time
        log_request(logger, "DELETE", f"/documents/{document_id}", 200, duration)
        
        return {"message": f"Document {document_id} deleted successfully"}
        
    except (UserError, ValidationError, ResourceNotFoundError):
        # Re-raise user-facing errors
        raise
    except Exception as e:
        # Log and re-raise unexpected errors
        duration = time.time() - start_time
        logger.error(
            f"Error deleting document {document_id}: {str(e)}",
            extra_fields={"duration": duration, "document_id": document_id},
            exc_info=True
        )
        raise DatabaseError("DELETE", "documents", e)

@router.post("/resolve-citations")
async def resolve_citations(citation_request: CitationRequest, request: Request):
    """
    Resolve citation tokens to document URLs and exact text.
    
    Takes a list of (document_id, segment_ordinal) pairs and returns
    the exact text, document title, and URL for each citation.
    """
    start_time = time.time()
    logger = get_logger(__name__)
    
    try:
        from database.postgres_client import postgres_client
        
        logger.info(
            "Resolving citations",
            extra_fields={"citation_count": len(citation_request.citations)}
        )
        
        resolved_citations = []
        
        # Get the hostname from the request and convert backend port to frontend port
        host = request.headers.get("host", "localhost:8000")
        import re
        frontend_url = re.sub(r':8000$', ':3000', f"http://{host}")
        
        for citation_ref in citation_request.citations:
            document_id = citation_ref["document_id"]
            segment_ordinal = citation_ref["segment_ordinal"]
            
            # Get document info
            document = postgres_client.get_document_by_id(document_id)
            if not document:
                logger.warning(f"Document {document_id} not found")
                continue
            
            # Get segment text
            sql = """
            SELECT ds.text
            FROM document_segments ds
            WHERE ds.document_id = :document_id AND ds.segment_ordinal = :segment_ordinal
            """
            parameters = [
                {'name': 'document_id', 'value': {'longValue': document_id}},
                {'name': 'segment_ordinal', 'value': {'longValue': segment_ordinal}}
            ]
            
            response = postgres_client.execute_statement(sql, parameters)
            
            if response.get('records'):
                segment_text = response['records'][0][0].get('stringValue', '')
                
                citation_info = CitationInfo(
                    document_id=document_id,
                    segment_ordinal=segment_ordinal,
                    text=segment_text,
                    document_title=document.title,
                    document_url=f"{frontend_url}/documents/{document_id}"
                )
                resolved_citations.append(citation_info)
            else:
                logger.warning(f"Segment {segment_ordinal} not found for document {document_id}")
        
        logger.info(
            "Citations resolved successfully",
            extra_fields={"resolved_count": len(resolved_citations)}
        )
        
        # Log successful request
        duration = time.time() - start_time
        log_request(logger, "POST", "/resolve-citations", 200, duration)
        
        return CitationResponse(citations=resolved_citations)
        
    except Exception as e:
        # Log and re-raise unexpected errors
        duration = time.time() - start_time
        logger.error(
            f"Error resolving citations: {str(e)}",
            extra_fields={"duration": duration},
            exc_info=True
        )
        raise DatabaseError("SELECT", "document_segments", e)

@router.get("/compliance-groups")
async def get_compliance_groups():
    """Get all compliance groups."""
    start_time = time.time()
    logger = get_logger(__name__)
    
    try:
        from database.postgres_client import postgres_client
        compliance_groups = postgres_client.get_all_compliance_groups()
        
        # Convert to response format
        response_data = {
            "compliance_groups": [
                {
                    "id": group.id,
                    "name": group.name,
                    "description": group.description,
                    "created_at": group.created_at.isoformat() if group.created_at else None,
                    "updated_at": group.updated_at.isoformat() if group.updated_at else None
                }
                for group in compliance_groups
            ]
        }
        
        logger.info(
            "Compliance groups fetched successfully",
            extra_fields={"group_count": len(compliance_groups)}
        )
        
        # Log successful request
        duration = time.time() - start_time
        log_request(logger, "GET", "/compliance-groups", 200, duration)
        
        return response_data
        
    except Exception as e:
        # Log and re-raise unexpected errors
        duration = time.time() - start_time
        logger.error(
            f"Error fetching compliance groups: {str(e)}",
            extra_fields={"duration": duration},
            exc_info=True
        )
        raise DatabaseError("SELECT", "compliance_frameworks", e)

@router.get("/compliance-groups/{group_id}")
async def get_compliance_group(group_id: str):
    """Get a single compliance group by ID."""
    start_time = time.time()
    logger = get_logger(__name__)
    
    try:
        from database.postgres_client import postgres_client
        compliance_group = postgres_client.get_compliance_group_by_id(group_id)
        
        if not compliance_group:
            raise ResourceNotFoundError("Compliance Group", group_id)
        
        # Convert to response format
        response_data = {
            "id": compliance_group.id,
            "name": compliance_group.name,
            "description": compliance_group.description,
            "created_at": compliance_group.created_at.isoformat() if compliance_group.created_at else None,
            "updated_at": compliance_group.updated_at.isoformat() if compliance_group.updated_at else None
        }
        
        logger.info(
            "Compliance group fetched successfully",
            extra_fields={"group_id": group_id}
        )
        
        # Log successful request
        duration = time.time() - start_time
        log_request(logger, "GET", f"/compliance-groups/{group_id}", 200, duration)
        
        return response_data
        
    except (ResourceNotFoundError):
        # Re-raise user-facing errors
        raise
    except Exception as e:
        # Log and re-raise unexpected errors
        duration = time.time() - start_time
        logger.error(
            f"Error fetching compliance group {group_id}: {str(e)}",
            extra_fields={"duration": duration, "group_id": group_id},
            exc_info=True
        )
        raise DatabaseError("SELECT", "compliance_frameworks", e)

@router.post("/compliance-groups")
async def create_compliance_group(request: ComplianceGroupCreateRequest):
    """Create a new compliance group."""
    start_time = time.time()
    logger = get_logger(__name__)
    
    try:
        # Validate input
        if not request.name or not request.name.strip():
            raise ValidationError("Compliance group name is required")
        
        from database.postgres_client import postgres_client
        
        # Create the compliance group
        try:
            group_id = postgres_client.create_compliance_group(
                name=request.name.strip(),
                description=request.description.strip() if request.description else None
            )
        except Exception as db_error:
            # Check if it's a unique constraint violation
            error_str = str(db_error)
            if "compliance_frameworks_name_key" in error_str or "duplicate key value" in error_str:
                raise ValidationError(f"A compliance group with the name '{request.name.strip()}' already exists. Please choose a different name.")
            else:
                # Re-raise other database errors
                raise
        
        # Fetch the created group to return full details
        created_group = postgres_client.get_compliance_group_by_id(group_id)
        
        response_data = {
            "id": created_group.id,
            "name": created_group.name,
            "description": created_group.description,
            "created_at": created_group.created_at.isoformat() if created_group.created_at else None,
            "updated_at": created_group.updated_at.isoformat() if created_group.updated_at else None,
            "status": "success"
        }
        
        logger.info(
            "Compliance group created successfully",
            extra_fields={"group_id": group_id, "name": request.name}
        )
        
        # Log successful request
        duration = time.time() - start_time
        log_request(logger, "POST", "/compliance-groups", 201, duration)
        
        return response_data
        
    except (ValidationError):
        # Re-raise user-facing errors
        raise
    except Exception as e:
        # Log and re-raise unexpected errors
        duration = time.time() - start_time
        logger.error(
            f"Error creating compliance group: {str(e)}",
            extra_fields={"duration": duration, "name": request.name if request else None},
            exc_info=True
        )
        raise DatabaseError("INSERT", "compliance_frameworks", e)

@router.put("/compliance-groups/{group_id}")
async def update_compliance_group(group_id: str, request: ComplianceGroupUpdateRequest):
    """Update an existing compliance group."""
    start_time = time.time()
    logger = get_logger(__name__)
    
    try:
        from database.postgres_client import postgres_client
        
        # Check if group exists
        existing_group = postgres_client.get_compliance_group_by_id(group_id)
        if not existing_group:
            raise ResourceNotFoundError("Compliance Group", group_id)
        
        # Update the compliance group
        updated = postgres_client.update_compliance_group(
            group_id=group_id,
            name=request.name.strip() if request.name else None,
            description=request.description.strip() if request.description else None
        )
        
        if not updated:
            raise ValidationError("No fields provided for update")
        
        # Fetch the updated group to return full details
        updated_group = postgres_client.get_compliance_group_by_id(group_id)
        
        response_data = {
            "id": updated_group.id,
            "name": updated_group.name,
            "description": updated_group.description,
            "created_at": updated_group.created_at.isoformat() if updated_group.created_at else None,
            "updated_at": updated_group.updated_at.isoformat() if updated_group.updated_at else None,
            "status": "success"
        }
        
        logger.info(
            "Compliance group updated successfully",
            extra_fields={"group_id": group_id}
        )
        
        # Log successful request
        duration = time.time() - start_time
        log_request(logger, "PUT", f"/compliance-groups/{group_id}", 200, duration)
        
        return response_data
        
    except (ValidationError, ResourceNotFoundError):
        # Re-raise user-facing errors
        raise
    except Exception as e:
        # Log and re-raise unexpected errors
        duration = time.time() - start_time
        logger.error(
            f"Error updating compliance group {group_id}: {str(e)}",
            extra_fields={"duration": duration, "group_id": group_id},
            exc_info=True
        )
        raise DatabaseError("UPDATE", "compliance_frameworks", e)

@router.delete("/compliance-groups/{group_id}")
async def delete_compliance_group(group_id: str):
    """Delete a compliance group."""
    start_time = time.time()
    logger = get_logger(__name__)
    
    try:
        from database.postgres_client import postgres_client
        
        # Check if group exists
        existing_group = postgres_client.get_compliance_group_by_id(group_id)
        if not existing_group:
            raise ResourceNotFoundError("Compliance Group", group_id)
        
        # Delete the compliance group
        deleted = postgres_client.delete_compliance_group(group_id)
        
        if not deleted:
            raise ProcessingError("compliance_group_deletion", "database_operation", "Failed to delete compliance group")
        
        logger.info(
            "Compliance group deleted successfully",
            extra_fields={"group_id": group_id}
        )
        
        # Log successful request
        duration = time.time() - start_time
        log_request(logger, "DELETE", f"/compliance-groups/{group_id}", 200, duration)
        
        return {"message": f"Compliance group {group_id} deleted successfully", "status": "success"}
        
    except (ResourceNotFoundError):
        # Re-raise user-facing errors
        raise
    except Exception as e:
        # Log and re-raise unexpected errors
        duration = time.time() - start_time
        logger.error(
            f"Error deleting compliance group {group_id}: {str(e)}",
            extra_fields={"duration": duration, "group_id": group_id},
            exc_info=True
        )
        raise DatabaseError("DELETE", "compliance_frameworks", e)

@router.put("/documents/{document_id}/compliance-framework")
async def update_document_compliance_framework(
    document_id: int, 
    request: DocumentComplianceFrameworkUpdateRequest
):
    """Update a document's compliance framework assignment."""
    start_time = time.time()
    logger = get_logger(__name__)
    
    try:
        from database.postgres_client import postgres_client
        
        # Check if document exists
        document = postgres_client.get_document_by_id(document_id)
        if not document:
            raise ResourceNotFoundError("Document", str(document_id))
        
        # If compliance_framework_id is provided, check if it exists
        if request.compliance_framework_id:
            compliance_group = postgres_client.get_compliance_group_by_id(request.compliance_framework_id)
            if not compliance_group:
                raise ResourceNotFoundError("Compliance Group", request.compliance_framework_id)
        
        # Update the document's compliance framework
        updated = postgres_client.update_document_compliance_framework(
            document_id=document_id,
            compliance_framework_id=request.compliance_framework_id
        )
        
        if not updated:
            raise ProcessingError("document_compliance_update", "database_operation", "Failed to update document compliance framework")
        
        # Trigger rule extraction if compliance framework was assigned (not removed)
        extraction_result = None
        if request.compliance_framework_id:
            from document_ingestion.trigger import extract_rules_for_framework_trigger
            logger.info(f"Triggering rule extraction for framework {request.compliance_framework_id}")
            extraction_result = extract_rules_for_framework_trigger(request.compliance_framework_id)
            logger.info(f"Rule extraction completed: {extraction_result.get('rules_extracted', 0)} rules extracted")
        
        # Fetch updated document to return full details
        updated_document = postgres_client.get_document_by_id(document_id)
        
        response_data = {
            "id": updated_document.id,
            "title": updated_document.title,
            "compliance_framework_id": updated_document.compliance_framework_id,
            "status": "success"
        }
        
        # Include rule extraction results if applicable
        if extraction_result:
            response_data["rule_extraction"] = {
                "success": extraction_result.get("success", False),
                "rules_extracted": extraction_result.get("rules_extracted", 0),
                "error": extraction_result.get("error")
            }
        
        logger.info(
            "Document compliance framework updated successfully",
            extra_fields={"document_id": document_id, "compliance_framework_id": request.compliance_framework_id}
        )
        
        # Log successful request
        duration = time.time() - start_time
        log_request(logger, "PUT", f"/documents/{document_id}/compliance-framework", 200, duration)
        
        return response_data
        
    except (ValidationError, ResourceNotFoundError):
        # Re-raise user-facing errors
        raise
    except Exception as e:
        # Log and re-raise unexpected errors
        duration = time.time() - start_time
        logger.error(
            f"Error updating document compliance framework: {str(e)}",
            extra_fields={"duration": duration, "document_id": document_id},
            exc_info=True
        )
        raise DatabaseError("UPDATE", "documents", e)

@router.get("/compliance-groups/{group_id}/documents")
async def get_compliance_group_documents(group_id: str):
    """Get all documents associated with a compliance group."""
    start_time = time.time()
    logger = get_logger(__name__)
    
    try:
        from database.postgres_client import postgres_client
        
        # Check if compliance group exists
        compliance_group = postgres_client.get_compliance_group_by_id(group_id)
        if not compliance_group:
            raise ResourceNotFoundError("Compliance Group", group_id)
        
        # Get documents for this compliance framework
        documents = postgres_client.get_documents_by_compliance_framework(group_id)
        
        # Convert to response format
        response_data = {
            "documents": [
                {
                    "id": doc.id,
                    "title": doc.title,
                    "checksum": doc.checksum,
                    "blob_link": doc.blob_link,
                    "created_at": doc.created_at.isoformat() if doc.created_at else None,
                    "mime_type": doc.mime_type,
                    "compliance_framework_id": doc.compliance_framework_id
                }
                for doc in documents
            ],
            "compliance_group": {
                "id": compliance_group.id,
                "name": compliance_group.name
            }
        }
        
        logger.info(
            "Compliance group documents fetched successfully",
            extra_fields={"group_id": group_id, "document_count": len(documents)}
        )
        
        # Log successful request
        duration = time.time() - start_time
        log_request(logger, "GET", f"/compliance-groups/{group_id}/documents", 200, duration)
        
        return response_data
        
    except (ResourceNotFoundError):
        # Re-raise user-facing errors
        raise
    except Exception as e:
        # Log and re-raise unexpected errors
        duration = time.time() - start_time
        logger.error(
            f"Error fetching compliance group documents: {str(e)}",
            extra_fields={"duration": duration, "group_id": group_id},
            exc_info=True
        )
        raise DatabaseError("SELECT", "documents", e)

@router.post("/evaluate-document")
async def evaluate_document(
    file: UploadFile = File(...),
    framework_id: str = Form(...)
):
    """Evaluate a document against compliance rules without persisting it."""
    start_time = time.time()
    logger = get_logger(__name__)
    
    try:
        logger.info(
            "Received document evaluation request",
            extra_fields={
                "filename": file.filename,
                "framework_id": framework_id,
                "content_type": file.content_type
            }
        )
        
        # Validate file presence
        if not file:
            raise ValidationError("No file provided")
        
        # Validate filename
        if not file.filename:
            raise ValidationError("File must have a filename")
        
        # Validate file type
        allowed_extensions = {'.pdf', '.docx', '.doc', '.txt'}
        file_extension = '.' + file.filename.lower().split('.')[-1]
        if file_extension not in allowed_extensions:
            raise ValidationError(
                f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}",
                {"file_extension": [f"Extension '{file_extension}' is not supported"]}
            )
        
        # Validate framework_id
        if not framework_id or not framework_id.strip():
            raise ValidationError("Framework ID is required")
        
        # Check if framework exists
        from database.postgres_client import postgres_client
        compliance_group = postgres_client.get_compliance_group_by_id(framework_id.strip())
        if not compliance_group:
            raise ResourceNotFoundError("Compliance Group", framework_id.strip())
        
        # Read file content into memory
        file_content = await file.read()
        file_stream = io.BytesIO(file_content)
        
        # Evaluate the document
        from document_evaluation.service import document_evaluation_service
        result = document_evaluation_service.evaluate_document(
            file_stream,
            file.filename,
            framework_id.strip()
        )
        
        logger.info(
            "Document evaluation completed",
            extra_fields={
                "filename": file.filename,
                "framework_id": framework_id,
                "segments_processed": result.segments_processed,
                "overall_score": result.overall_compliance_score
            }
        )
        
        # Log successful request
        duration = time.time() - start_time
        log_request(logger, "POST", "/evaluate-document", 200, duration)
        
        return result
        
    except (UserError, ValidationError, ResourceNotFoundError):
        # Re-raise user-facing errors
        raise
    except Exception as e:
        # Log and re-raise unexpected errors
        duration = time.time() - start_time
        logger.error(
            f"Error evaluating document: {str(e)}",
            extra_fields={
                "duration": duration, 
                "filename": file.filename if file else None,
                "framework_id": framework_id if 'framework_id' in locals() else None
            },
            exc_info=True
        )
        raise ProcessingError("document_evaluation", "evaluation_processing", str(e))

@router.post("/debug-framework-matching")
async def debug_framework_matching(file: UploadFile = File(...)):
    """Debug endpoint to show framework matching details."""
    start_time = time.time()
    logger = get_logger(__name__)
    
    try:
        logger.info("Received framework matching debug request")
        
        # Validate file
        if not file:
            raise ValidationError("No file provided")
        
        if not file.filename:
            raise ValidationError("File must have a filename")
        
        # Read and parse file
        file_content = await file.read()
        
        # Parse document
        from services.document_parser import document_parser
        file_stream = io.BytesIO(file_content)
        document_text = document_parser.parse_document(file_stream, file.filename)
        
        if not document_text.strip():
            raise ValidationError("Document appears to be empty or could not be parsed")
        
        # Run debug analysis
        from services.framework_matcher import framework_matcher
        debug_info = await framework_matcher.debug_framework_matching(document_text)
        
        logger.info("Framework matching debug completed")
        
        # Log successful request
        duration = time.time() - start_time
        log_request(logger, "POST", "/debug-framework-matching", 200, duration)
        
        return debug_info
        
    except (UserError, ValidationError):
        raise
    except Exception as e:
        duration = time.time() - start_time
        logger.error(
            f"Error in framework matching debug: {str(e)}",
            extra_fields={"duration": duration, "filename": file.filename if file else None},
            exc_info=True
        )
        raise ProcessingError("framework_debug", "debug_processing", str(e))