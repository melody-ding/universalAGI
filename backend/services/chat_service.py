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

class ChatService:
    def __init__(self):
        # Initialize the main ReAct agent
        self.agent = ReActAgent(
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

    async def get_response(self, message: str, history: List[Message], image_file: UploadFile = None) -> str:
        # Process image if present
        has_image = image_file and image_file.filename
        image_data = None
        if has_image:
            image_data = await self._process_image(image_file)
        
        # Build context from conversation history
        context = {
            "conversation_history": [{"role": msg.role, "content": msg.content} for msg in history[-settings.MAX_CONVERSATION_HISTORY:]],
            "has_image": has_image,
            "image_data": image_data,
            "session_context": "chat_session"
        }
        
        # Use the agent for processing
        response = await self.agent.process_request(message, context, has_image)
        
        return response.content if response.success else response.error
    
    async def get_streaming_response(
        self, 
        message: str, 
        history: List[Message], 
        image_file: UploadFile = None
    ) -> AsyncGenerator[str, None]:
        
        # Process image if present
        has_image = image_file and image_file.filename
        image_data = None
        if has_image:
            image_data = await self._process_image(image_file)
        
        # Build context from conversation history
        context = {
            "conversation_history": [{"role": msg.role, "content": msg.content} for msg in history[-settings.MAX_CONVERSATION_HISTORY:]],
            "has_image": has_image,
            "image_data": image_data,
            "session_context": "chat_session"
        }
        
        # Use orchestrator to decide routing
        from agent.orchestrator import route_message, run_light_agent
        
        try:
            # Get routing decision
            routing_result = route_message(message)
            
            # Apply routing logic
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
            
            # Use heavy path (either directly routed or escalated)
            async for event in self.agent.stream_request(message, context, has_image):
                yield event.to_sse_format()
                
        except Exception as e:
            # Fallback to heavy agent on any orchestration errors
            async for event in self.agent.stream_request(message, context, has_image):
                yield event.to_sse_format()
    
    async def _process_image(self, image_file: UploadFile) -> str:
        image_content = await image_file.read()
        image_base64 = base64.b64encode(image_content).decode('utf-8')
        mime_type = image_file.content_type or 'image/jpeg'
        return f"data:{mime_type};base64,{image_base64}"
    

chat_service = ChatService()