from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage
from langchain.callbacks.base import BaseCallbackHandler
import os
import base64
import json
import asyncio
from typing import List, Optional, AsyncGenerator
from queue import Queue
import threading
import time

app = FastAPI(title="Chat Backend API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Message(BaseModel):
    content: str
    role: str = "user"

class SendMessageRequest(BaseModel):
    message: str
    conversation_history: Optional[List[Message]] = []
    image: str

class SendMessageResponse(BaseModel):
    response: str
    status: str = "success"

class StreamingCallbackHandler(BaseCallbackHandler):
    def __init__(self, queue: Queue):
        self.queue = queue
        self.current_step = 0
        
    def on_llm_start(self, serialized, prompts, **kwargs):
        self.queue.put({"type": "thinking_start", "content": "Starting to think..."})
        
    def on_llm_new_token(self, token: str, **kwargs):
        # For streaming the final response
        if hasattr(self, 'in_final_response') and self.in_final_response:
            self.queue.put({"type": "response_token", "content": token})

llm = ChatOpenAI(
    model="gpt-4o",
    temperature=0.7,
    openai_api_key=os.getenv("OPENAI_API_KEY"),
    streaming=True
)

@app.get("/")
async def root():
    return {"message": "Chat Backend API is running"}

@app.post("/send-message", response_model=SendMessageResponse)
async def send_message(
    message: str = Form(""),
    conversation_history: str = Form("[]"),
    image: UploadFile = File(None)
):
    try:
        if not os.getenv("OPENAI_API_KEY"):
            raise HTTPException(status_code=500, detail="OpenAI API key not configured")
        
        # Parse conversation history from JSON string
        import json
        try:
            history = json.loads(conversation_history) if conversation_history else []
        except json.JSONDecodeError:
            history = []
        
        # Build conversation messages
        content = """
You are an expert reasoning assistant. For every request, you may perform detailed step-by-step reasoning (“chain of thought”) privately to yourself to arrive at the best answer. 

Rules:
1. Perform internal reasoning before responding if it will help accuracy, clarity, or creativity.
2. Do NOT include the private reasoning in your final answer unless explicitly asked to show it.
3. Your final answer should be clear, concise, and directly address the user’s request.
4. If the request involves multiple steps, break them down in your internal reasoning before producing the answer.

Begin reasoning privately when needed, then provide the final response.
"""
        messages = [
            SystemMessage(content=content)
        ]
        
        # Add conversation history
        for msg in history[-5:]:  # Keep last 5 messages for context
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            if role == 'user':
                messages.append(HumanMessage(content=content))
            else:
                messages.append(SystemMessage(content=content))
        
        # Handle image if present
        if image and image.filename:
            # Read and encode the image
            image_content = await image.read()
            image_base64 = base64.b64encode(image_content).decode('utf-8')
            mime_type = image.content_type or 'image/jpeg'
            data_url = f"data:{mime_type};base64,{image_base64}"
            
            # Create multimodal message with both text and image
            if message.strip():
                # If there's both text and image
                messages.append(HumanMessage(content=[
                    {"type": "text", "text": message},
                    {"type": "image_url", "image_url": {"url": data_url}}
                ]))
            else:
                # If there's only image
                messages.append(HumanMessage(content=[
                    {"type": "text", "text": "Please analyze this image."},
                    {"type": "image_url", "image_url": {"url": data_url}}
                ]))
        else:
            # Text-only message
            messages.append(HumanMessage(content=message))
        
        # Get response from LLM
        response = llm.invoke(messages)
        
        return SendMessageResponse(
            response=response.content,
            status="success"
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}")

async def simulate_thinking_process(queue: Queue, user_message: str, has_image: bool = False):
    """Simulate chain-of-thought reasoning steps"""
    thinking_steps = []
    
    # Analyze the message type and complexity
    if has_image:
        thinking_steps = [
            "Analyzing the uploaded image...",
            "Identifying key visual elements and patterns...",
            "Considering the context of your question...",
            "Connecting visual information with your request...",
            "Formulating a comprehensive response..."
        ]
    elif "?" in user_message:
        thinking_steps = [
            "Understanding your question...",
            "Breaking down the problem into components...",
            "Considering different approaches...",
            "Evaluating the best solution path...",
            "Preparing a detailed response..."
        ]
    elif len(user_message.split()) > 20:
        thinking_steps = [
            "Processing your detailed message...",
            "Identifying key points and requirements...",
            "Structuring my approach...",
            "Considering multiple perspectives...",
            "Organizing my response..."
        ]
    else:
        thinking_steps = [
            "Processing your message...",
            "Considering the best response...",
            "Formulating my answer..."
        ]
    
    # Stream thinking steps with realistic delays
    for i, step in enumerate(thinking_steps):
        await asyncio.sleep(0.8)  # Realistic thinking delay
        queue.put({
            "type": "thinking_step", 
            "content": step,
            "step": i + 1,
            "total_steps": len(thinking_steps)
        })
    
    # Signal thinking completion
    await asyncio.sleep(0.3)
    queue.put({"type": "thinking_complete", "content": "Thinking complete, generating response..."})

async def stream_generator(
    message: str,
    conversation_history: str,
    image_file: UploadFile = None
) -> AsyncGenerator[str, None]:
    queue = Queue()
    
    try:
        if not os.getenv("OPENAI_API_KEY"):
            yield f"data: {json.dumps({'type': 'error', 'content': 'OpenAI API key not configured'})}\n\n"
            return
        
        # Parse conversation history
        try:
            history = json.loads(conversation_history) if conversation_history else []
        except json.JSONDecodeError:
            history = []
        
        # Start thinking process
        has_image = image_file and image_file.filename
        thinking_task = asyncio.create_task(
            simulate_thinking_process(queue, message, has_image)
        )
        
        # Stream thinking steps
        await thinking_task
        
        # Process queue items that accumulated during thinking
        while not queue.empty():
            item = queue.get()
            yield f"data: {json.dumps(item)}\n\n"
        
        # Build messages for LLM
        system_content = """You are an expert reasoning assistant. You have just completed detailed internal reasoning about the user's request. Now provide your final, well-reasoned response that addresses their question comprehensively. Be clear, helpful, and direct."""
        
        messages = [SystemMessage(content=system_content)]
        
        # Add conversation history
        for msg in history[-5:]:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            if role == 'user':
                messages.append(HumanMessage(content=content))
            else:
                messages.append(SystemMessage(content=content))
        
        # Handle image if present
        if has_image:
            image_content = await image_file.read()
            image_base64 = base64.b64encode(image_content).decode('utf-8')
            mime_type = image_file.content_type or 'image/jpeg'
            data_url = f"data:{mime_type};base64,{image_base64}"
            
            if message.strip():
                messages.append(HumanMessage(content=[
                    {"type": "text", "text": message},
                    {"type": "image_url", "image_url": {"url": data_url}}
                ]))
            else:
                messages.append(HumanMessage(content=[
                    {"type": "text", "text": "Please analyze this image."},
                    {"type": "image_url", "image_url": {"url": data_url}}
                ]))
        else:
            messages.append(HumanMessage(content=message))
        
        # Signal start of response generation
        yield f"data: {json.dumps({'type': 'response_start', 'content': 'Generating response...'})}\n\n"
        
        # Use streamEvents for token-level streaming
        response_content = ""
        async for event in llm.astream_events(messages, version="v2"):
            if event["event"] == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if hasattr(chunk, 'content') and chunk.content:
                    response_content += chunk.content
                    # Stream each token
                    yield f"data: {json.dumps({'type': 'response_token', 'content': chunk.content})}\n\n"
        
        # Stream the complete response for fallback
        yield f"data: {json.dumps({'type': 'response_complete', 'content': response_content})}\n\n"
        
        # Signal end of stream
        yield f"data: {json.dumps({'type': 'stream_end'})}\n\n"
        
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'content': f'Error: {str(e)}'})}\n\n"

@app.post("/send-message-stream")
async def send_message_stream(
    message: str = Form(""),
    conversation_history: str = Form("[]"),
    image: UploadFile = File(None)
):
    return StreamingResponse(
        stream_generator(message, conversation_history, image),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "http://localhost:3000",
            "Access-Control-Allow-Credentials": "true",
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)