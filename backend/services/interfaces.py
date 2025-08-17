"""
Service interfaces for dependency injection.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, AsyncGenerator
from dataclasses import dataclass
import io


@dataclass
class SearchResult:
    """Result from document search operations."""
    documents_found: int
    total_snippets: int
    context_text: str
    citations: List[Dict[str, Any]]
    metadata: Dict[str, Any]


@dataclass
class DocumentParseResult:
    """Result from document parsing operations."""
    text: str
    metadata: Dict[str, Any]
    success: bool
    error: Optional[str] = None


@dataclass
class FrameworkMatchResult:
    """Result from framework matching operations."""
    framework_ids: List[str]
    confidence_scores: Dict[str, float]
    reasoning: str


@dataclass
class AnalysisResult:
    """Result from document analysis operations."""
    framework_results: List[Dict[str, Any]]
    overall_summary: str
    success: bool
    error: Optional[str] = None


class DocumentService(ABC):
    """Abstract service for document operations."""
    
    @abstractmethod
    async def parse_document(self, file_stream: io.BytesIO, filename: str) -> DocumentParseResult:
        """Parse a document from a file stream."""
        pass
    
    @abstractmethod
    async def get_document_metadata(self, document_id: int) -> Optional[Dict[str, Any]]:
        """Get metadata for a document by ID."""
        pass
    
    @abstractmethod
    async def validate_document(self, file_content: bytes, filename: str) -> bool:
        """Validate if a document can be processed."""
        pass


class SearchService(ABC):
    """Abstract service for search operations."""
    
    @abstractmethod
    async def hybrid_search(self, query: str, document_id: Optional[int] = None, **kwargs) -> SearchResult:
        """Perform hybrid search across documents."""
        pass
    
    @abstractmethod
    async def vector_search(self, embedding: List[float], limit: int = 20) -> List[Dict[str, Any]]:
        """Perform vector similarity search."""
        pass
    
    @abstractmethod
    async def text_search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Perform full-text search."""
        pass


class FrameworkService(ABC):
    """Abstract service for compliance framework operations."""
    
    @abstractmethod
    async def find_relevant_frameworks(self, document_text: str) -> FrameworkMatchResult:
        """Find relevant frameworks for a document."""
        pass
    
    @abstractmethod
    async def get_framework_info(self, framework_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific framework."""
        pass
    
    @abstractmethod
    async def list_available_frameworks(self) -> List[Dict[str, Any]]:
        """List all available frameworks."""
        pass


class AnalysisService(ABC):
    """Abstract service for document analysis operations."""
    
    @abstractmethod
    async def analyze_document(self, 
                             file_stream: io.BytesIO, 
                             filename: str, 
                             framework_ids: List[str]) -> AnalysisResult:
        """Analyze a document against specified frameworks."""
        pass
    
    @abstractmethod
    async def format_analysis_results(self, 
                                    results: List[Dict[str, Any]], 
                                    filename: str) -> str:
        """Format analysis results for presentation."""
        pass


class OrchestrationService(ABC):
    """Abstract service for agent orchestration."""
    
    @abstractmethod
    async def route_query(self, query: str) -> Dict[str, Any]:
        """Determine routing strategy for a query."""
        pass
    
    @abstractmethod
    async def execute_light_path(self, query: str, context: Dict[str, Any]) -> str:
        """Execute light path processing."""
        pass
    
    @abstractmethod
    async def execute_heavy_path(self, query: str, context: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """Execute heavy path processing with streaming."""
        pass


class EmbeddingService(ABC):
    """Abstract service for embedding operations."""
    
    @abstractmethod
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text."""
        pass
    
    @abstractmethod
    async def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        pass
    
    @abstractmethod
    async def compute_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """Compute similarity between two embeddings."""
        pass
