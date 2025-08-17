"""
RAG Tool - Document Retrieval for Heavy Agent
"""

import logging
from typing import Dict, Any, Optional, List
from .tools import Tool
from services.interfaces import SearchService
from services.service_container import get_search_service

logger = logging.getLogger(__name__)


class RAGTool(Tool):
    """
    Simplified RAG tool focused only on document retrieval and search.
    """
    
    def __init__(self, search_service: Optional[SearchService] = None):
        name = "search_documents"
        description = """Search through uploaded documents to find relevant information.

This tool performs hybrid search (semantic + keyword) across all uploaded documents.

Parameters:
- query: Natural language search query describing what information you need
- document_id (optional): Specific document ID to search within

Returns relevant document excerpts with source information."""
        super().__init__(name, description)
        
        # Use dependency injection with fallback to service container
        self.search_service = search_service or get_search_service()

    async def execute(self, query: str, document_id: Optional[int] = None, **kwargs) -> Dict[str, Any]:
        """
        Execute document search and return relevant context.
        
        Args:
            query: Natural language search query
            document_id: Optional specific document ID to search within
            
        Returns:
            Dict containing search results and formatted context
            
        Raises:
            Exception: If document search fails or no documents found
        """
        logger.info(f"Searching documents for: {query[:100]}...")
        
        # Use the search service
        search_result = await self.search_service.hybrid_search(query, document_id)
        
        if search_result.documents_found == 0:
            raise Exception(f"No relevant documents found for query: {query}")
        
        # Create summary of what was found
        doc_summary = f"Found relevant information in {search_result.documents_found} document(s) with {search_result.total_snippets} sections"
        
        return {
            "success": True,
            "result": doc_summary,
            "context": search_result.context_text,
            "documents_found": search_result.documents_found,
            "total_snippets": search_result.total_snippets,
            "search_query": query,
            "citations": search_result.citations
        }