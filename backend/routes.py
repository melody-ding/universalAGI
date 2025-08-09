import json
from fastapi import APIRouter, HTTPException, File, UploadFile, Form
from fastapi.responses import StreamingResponse

from config import settings
from models import SendMessageResponse, Message
from services import chat_service

router = APIRouter()

@router.get("/")
async def root():
    return {"message": "Chat Backend API is running"}

@router.post("/send-message", response_model=SendMessageResponse)
async def send_message(
    message: str = Form(""),
    conversation_history: str = Form("[]"),
    image: UploadFile = File(None)
):
    try:
        if not settings.is_openai_configured:
            raise HTTPException(status_code=500, detail="OpenAI API key not configured")
        
        # Parse conversation history from JSON string
        try:
            history_data = json.loads(conversation_history) if conversation_history else []
            history = [Message(**msg) for msg in history_data]
        except (json.JSONDecodeError, ValueError):
            history = []
        
        # Get response from service
        response_content = await chat_service.get_response(message, history, image)
        
        return SendMessageResponse(
            response=response_content,
            status="success"
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}")

@router.post("/send-message-stream")
async def send_message_stream(
    message: str = Form(""),
    conversation_history: str = Form("[]"),
    image: UploadFile = File(None)
):
    try:
        if not settings.is_openai_configured:
            raise HTTPException(status_code=500, detail="OpenAI API key not configured")
        
        # Parse conversation history from JSON string
        try:
            history_data = json.loads(conversation_history) if conversation_history else []
            history = [Message(**msg) for msg in history_data]
        except (json.JSONDecodeError, ValueError):
            history = []
        
        return StreamingResponse(
            chat_service.get_streaming_response(message, history, image),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": settings.ALLOWED_ORIGINS[0],
                "Access-Control-Allow-Credentials": "true",
            }
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}")