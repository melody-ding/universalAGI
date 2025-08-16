import json
import time
from fastapi import APIRouter, File, UploadFile, Form
from fastapi.responses import StreamingResponse

from config import settings
from models import SendMessageResponse, Message
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

@router.get("/")
async def root():
    return {"message": "Chat Backend API is running"}


@router.post("/send-message-stream")
async def send_message_stream(
    message: str = Form(""),
    conversation_history: str = Form("[]"),
    image: UploadFile = File(None)
):
    start_time = time.time()
    logger = get_logger(__name__)
    
    try:
        logger.info(
            "Received streaming request",
            extra_fields={
                "message_length": len(message),
                "has_image": image is not None,
                "history_length": len(conversation_history) if conversation_history else 0
            }
        )
        
        # Validate configuration
        if not settings.is_openai_configured:
            raise ConfigurationError("OPENAI_API_KEY", "OpenAI API key not configured")
        
        # Validate input
        if not message.strip() and not image:
            raise ValidationError("Message or image required")
        
        # Parse conversation history from JSON string
        try:
            history_data = json.loads(conversation_history) if conversation_history else []
            history = [Message(**msg) for msg in history_data]
            logger.info(f"Parsed conversation history with {len(history)} messages")
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse conversation history: {e}")
            history = []
        
        async def safe_streaming_generator():
            try:
                async for chunk in chat_service.get_streaming_response(message, history, image):
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
                    "mime_type": doc.mime_type
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
            "mime_type": document.mime_type
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