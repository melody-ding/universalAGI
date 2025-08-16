from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel

class DocumentModel(BaseModel):
    id: Optional[int] = None
    title: Optional[str] = None
    checksum: Optional[str] = None
    blob_link: Optional[str] = None
    mime_type: Optional[str] = None
    embedding: Optional[List[float]] = None
    created_at: Optional[datetime] = None

class DocumentSegmentModel(BaseModel):
    id: Optional[int] = None
    document_id: int
    segment_ordinal: int
    text: str
    ts: Optional[str] = None  # tsvector field
    embedding: Optional[List[float]] = None
    created_at: Optional[datetime] = None

class DocumentUploadResponse(BaseModel):
    document_id: int
    checksum: str
    blob_link: str
    num_segments: int
    status: str = "success"
    message: Optional[str] = None