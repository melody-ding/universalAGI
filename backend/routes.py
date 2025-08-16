import json
import logging
from fastapi import APIRouter, HTTPException, File, UploadFile, Form
from fastapi.responses import StreamingResponse

from config import settings
from models import SendMessageResponse, Message
from services import chat_service

logger = logging.getLogger(__name__)

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
    try:
        logger.info(f"Received streaming request: message='{message[:100]}...', has_image={image is not None}")
        
        if not settings.is_openai_configured:
            logger.error("OpenAI API key not configured")
            raise HTTPException(status_code=500, detail="OpenAI API key not configured")
        
        if not message.strip() and not image:
            logger.warning("Empty message and no image provided")
            raise HTTPException(status_code=400, detail="Message or image required")
        
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
                    logger.debug(f"Yielding chunk: {chunk[:100]}...")
                    yield chunk
                logger.info("Streaming completed successfully")
                yield f"data: [DONE]\n\n"
            except Exception as e:
                logger.error(f"Error in streaming generator: {str(e)}", exc_info=True)
                error_data = json.dumps({'type': 'error', 'content': f"Streaming error: {str(e)}"})
                yield f"data: {error_data}\n\n"
                yield f"data: [DONE]\n\n"
        
        return StreamingResponse(
            safe_streaming_generator(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": settings.ALLOWED_ORIGINS[0] if settings.ALLOWED_ORIGINS else "*",
                "Access-Control-Allow-Credentials": "true",
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in send_message_stream: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}")

@router.post("/upload-document")
async def upload_document(file: UploadFile = File(...)):
    try:
        logger.info(f"Received document upload request: filename='{file.filename}', size={file.size}")
        
        if not file:
            raise HTTPException(status_code=400, detail="No file provided")
        
        if not file.filename:
            raise HTTPException(status_code=400, detail="File must have a filename")
        
        # Validate file type
        allowed_extensions = {'.pdf', '.docx', '.doc', '.txt'}
        file_extension = '.' + file.filename.lower().split('.')[-1]
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}"
            )
        
        # Process the document upload
        from services.document_upload_service import document_upload_service
        result = await document_upload_service.process_document_upload(file)
        
        logger.info(f"Document uploaded successfully: {file.filename}, doc_id: {result.document_id}")
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading document: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error uploading document: {str(e)}")

@router.get("/documents")
async def get_documents():
    try:
        from database.postgres_client import postgres_client
        documents = postgres_client.get_all_documents()
        
        # Convert to response format
        return {
            "documents": [
                {
                    "id": doc.id,
                    "title": doc.title,
                    "checksum": doc.checksum,
                    "blob_link": doc.blob_link,
                    "created_at": doc.created_at.isoformat() if doc.created_at else None
                }
                for doc in documents
            ]
        }
        
    except Exception as e:
        logger.error(f"Error fetching documents: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching documents: {str(e)}")

@router.delete("/documents/{document_id}")
async def delete_document(document_id: int):
    try:
        from database.postgres_client import postgres_client
        
        # Check if document exists
        doc_response = postgres_client.execute_statement(
            "SELECT id FROM documents WHERE id = :document_id",
            [{'name': 'document_id', 'value': {'longValue': document_id}}]
        )
        
        if not doc_response['records']:
            raise HTTPException(status_code=404, detail=f"Document with ID {document_id} not found")
        
        # Delete the document and all related data
        postgres_client.delete_document_and_segments(document_id, include_s3_cleanup=True)
        
        logger.info(f"Successfully deleted document {document_id}")
        return {"message": f"Document {document_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document {document_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error deleting document: {str(e)}")