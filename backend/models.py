from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

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

class DocumentUploadResponse(BaseModel):
    document_id: int
    checksum: str
    blob_link: str
    num_segments: int
    status: str = "success"
    message: Optional[str] = None