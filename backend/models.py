from pydantic import BaseModel
from typing import List, Optional

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