import base64
import json
import asyncio
from typing import List, AsyncGenerator
from fastapi import UploadFile
from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage

from config import settings
from models import Message
from agent import ReActAgent
from agent.agent_factory import create_react_agent
from agent.orchestrator import route_message, run_light_agent
from agent.smart_orchestrator import smart_handle_message
import logging
from agent.streaming_orchestrator import stream_smart_orchestration

logger = logging.getLogger(__name__)

class ChatService:
    def __init__(self):
        # Initialize the main ReAct agent using dependency injection
        self.agent = create_react_agent(
            model_name=settings.MODEL_NAME,
            planner_temperature=0.1,  # Lower temperature for consistent planning
            executor_temperature=settings.MODEL_TEMPERATURE  # Normal temperature for execution
        )
        
        # Keep a backup LLM for non-agent responses if needed
        self.llm = ChatOpenAI(
            model=settings.MODEL_NAME,
            temperature=settings.MODEL_TEMPERATURE,
            openai_api_key=settings.OPENAI_API_KEY,
            streaming=True
        )
    
    def _get_system_prompt(self, is_streaming: bool = False) -> str:
        if is_streaming:
            return """You are an expert reasoning assistant. You have just completed detailed internal reasoning about the user's request. Now provide your final, well-reasoned response that addresses their question comprehensively. Be clear, helpful, and direct."""
        else:
            return """
You are an expert reasoning assistant. For every request, you may perform detailed step-by-step reasoning ("chain of thought") privately to yourself to arrive at the best answer. 

Rules:
1. Perform internal reasoning before responding if it will help accuracy, clarity, or creativity.
2. Do NOT include the private reasoning in your final answer unless explicitly asked to show it.
3. Your final answer should be clear, concise, and directly address the user's request.
4. If the request involves multiple steps, break them down in your internal reasoning before producing the answer.

Begin reasoning privately when needed, then provide the final response.
"""
    
    def _build_messages(self, message: str, history: List[Message], image_data: str = None) -> List:
        messages = [SystemMessage(content=self._get_system_prompt())]
        
        # Add conversation history
        for msg in history[-settings.MAX_CONVERSATION_HISTORY:]:
            role = msg.role
            content = msg.content
            if role == 'user':
                messages.append(HumanMessage(content=content))
            else:
                messages.append(SystemMessage(content=content))
        
        # Handle image if present
        if image_data:
            if message.strip():
                messages.append(HumanMessage(content=[
                    {"type": "text", "text": message},
                    {"type": "image_url", "image_url": {"url": image_data}}
                ]))
            else:
                messages.append(HumanMessage(content=[
                    {"type": "text", "text": "Please analyze this image."},
                    {"type": "image_url", "image_url": {"url": image_data}}
                ]))
        else:
            messages.append(HumanMessage(content=message))
        
        return messages
    
    def _build_streaming_messages(self, message: str, history: List[Message], image_data: str = None) -> List:
        messages = [SystemMessage(content=self._get_system_prompt(is_streaming=True))]
        
        # Add conversation history
        for msg in history[-settings.MAX_CONVERSATION_HISTORY:]:
            role = msg.role
            content = msg.content
            if role == 'user':
                messages.append(HumanMessage(content=content))
            else:
                messages.append(SystemMessage(content=content))
        
        # Handle image if present
        if image_data:
            if message.strip():
                messages.append(HumanMessage(content=[
                    {"type": "text", "text": message},
                    {"type": "image_url", "image_url": {"url": image_data}}
                ]))
            else:
                messages.append(HumanMessage(content=[
                    {"type": "text", "text": "Please analyze this image."},
                    {"type": "image_url", "image_url": {"url": image_data}}
                ]))
        else:
            messages.append(HumanMessage(content=message))
        
        return messages

    
    async def get_streaming_response(
        self, 
        message: str, 
        history: List[Message], 
        image_data_tuple: tuple = None,
        document_data_tuple: tuple = None,
        document_id: int = None
    ) -> AsyncGenerator[str, None]:
        
        # Process image if present - content already read in routes
        has_image = image_data_tuple is not None
        image_data = None
        if has_image:
            try:
                image_file, image_content = image_data_tuple
                image_base64 = base64.b64encode(image_content).decode('utf-8')
                mime_type = image_file.content_type or 'image/jpeg'
                image_data = f"data:{mime_type};base64,{image_base64}"
                logger.info(f"Successfully processed image of size {len(image_content)} bytes")
            except Exception as e:
                logger.error(f"Failed to process image: {str(e)}")
                raise ValueError(f"Image processing failed: {str(e)}")
        
        # Process document file if present - content already read in routes
        file_context = None
        if document_data_tuple is not None:
            try:
                document_file, document_content = document_data_tuple
                file_context = await self._build_file_context_from_content(
                    document_content, 
                    document_file.filename, 
                    document_file.content_type
                )
                logger.info(f"Successfully processed document of size {len(document_content)} bytes")
            except Exception as e:
                logger.error(f"Failed to process document file: {str(e)}")
                raise ValueError(f"Document processing failed: {str(e)}")
        
        # Build context from conversation history
        context = {
            "conversation_history": [{"role": msg.role, "content": msg.content} for msg in history[-settings.MAX_CONVERSATION_HISTORY:]],
            "has_image": has_image,
            "image_data": image_data,
            "session_context": "chat_session",
            "document_id": document_id
        }
        

        
        try:
            # First try the old light routing for simple responses
            routing_result = route_message(message)
            
            # Apply routing logic for simple chitchat
            should_use_light = (
                routing_result["route"] == "LIGHT" and
                routing_result["intent"] in ["chitchat", "faq"] and
                routing_result["confidence"] >= 0.65
            )
            
            if should_use_light:
                # Try light path first
                light_response = run_light_agent(
                    message,
                    routing_result["intent"],
                    routing_result["query"],
                    routing_result["light_draft"]
                )
                
                if light_response != "ESCALATE":
                    # Yield light response as a single event
                    yield f"data: {json.dumps({'type': 'response_complete', 'content': light_response})}\n\n"
                    return
            
            # For heavy processing, use streaming smart orchestrator
            logger.info("STREAMING: Using smart orchestrator for heavy processing")
            
            
            # Stream the smart orchestration process with file context and document_id
            async for event in stream_smart_orchestration(message, document_id=document_id, file_context=file_context):
                # Ensure each streamed event is valid JSON
                from agent.token_manager import ensure_json_validity
                # Extract the JSON part after "data: "
                if event.startswith("data: ") and not event.startswith("data: [DONE]"):
                    json_part = event[6:].strip()
                    if json_part and not json_part.startswith("[DONE]"):
                        validated_json = ensure_json_validity(json_part)
                        yield f"data: {validated_json}\n\n"
                    else:
                        yield event
                else:
                    yield event
            
            # Yield stream end
            yield f"data: {json.dumps({'type': 'stream_end', 'content': 'Response complete'})}\n\n"
                
        except Exception as e:
            logger.error(f"Smart orchestrator streaming failed: {e}")
            # Fallback to heavy agent streaming on any orchestration errors
            async for event in self.agent.stream_request(message, context, has_image):
                yield event.to_sse_format()
    

    
    async def _build_file_context_from_content(
        self, 
        content: bytes, 
        filename: str, 
        content_type: str = None
    ) -> dict[str, any]:
        """Build file context for document analysis from file content in memory."""
        from agent.file_context import file_context_builder
        import io
        
        try:
            # Create a BytesIO stream from the content
            content_stream = io.BytesIO(content)
            
            # Validate file extension directly
            file_ext = self._get_file_extension(filename)
            supported_extensions = {'.pdf'}
            if file_ext not in supported_extensions:
                raise ValueError(f"Unsupported file type: {file_ext}. Only PDF files are supported.")
            
            # Validate file size
            file_size = len(content)
            max_file_size = 50 * 1024 * 1024  # 50MB
            if file_size > max_file_size:
                raise ValueError(f"File too large: {file_size} bytes. Maximum allowed: {max_file_size} bytes")
            
            if file_size == 0:
                raise ValueError("File is empty")
            
            # Create file context directly from content
            from agent.file_context import FileContext
            file_context_obj = FileContext(
                filename=filename,
                file_content=content,
                mime_type=content_type,
                file_size=file_size
            )
            
            if not file_context_obj:
                raise ValueError("Failed to build file context")
            
            return {
                'filename': file_context_obj.filename,
                'file_content': file_context_obj.file_content,
                'mime_type': file_context_obj.mime_type,
                'file_size': file_context_obj.file_size,
                'has_file': True
            }
        except Exception as e:
            logger.error(f"Failed to build file context from content: {str(e)}")
            raise ValueError(f"File processing failed: {str(e)}")
    
    def _get_file_extension(self, filename: str) -> str:
        """Extract file extension from filename."""
        if '.' not in filename:
            return ''
        return '.' + filename.split('.')[-1].lower()
    
    async def _build_file_context(self, document_file: UploadFile) -> dict[str, any]:
        """Build file context for document analysis."""
        from agent.file_context import file_context_builder
        
        try:
            # Reset file pointer before processing
            await document_file.seek(0)
            file_context_obj = await file_context_builder.build_file_context(document_file)
            if not file_context_obj:
                raise ValueError("Failed to build file context")
            
            # Reset file pointer after processing for potential future reads
            await document_file.seek(0)
            
            return {
                'filename': file_context_obj.filename,
                'file_content': file_context_obj.file_content,
                'mime_type': file_context_obj.mime_type,
                'file_size': file_context_obj.file_size,
                'has_file': True
            }
        except Exception as e:
            logger.error(f"Failed to build file context: {str(e)}")
            raise ValueError(f"File processing failed: {str(e)}")
    

chat_service = ChatService()