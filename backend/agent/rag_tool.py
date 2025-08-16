"""
RAG Tool - Document Retrieval for Heavy Agent
"""

import logging
from typing import Dict, Any, Optional
from .tools import Tool
from search.multi_document_search import build_grouped_context

logger = logging.getLogger(__name__)


class RAGTool(Tool):
    """
    Simplified RAG tool focused only on document retrieval and search.
    """
    
    def __init__(self):
        name = "search_documents"
        description = """Search through uploaded documents to find relevant information.

This tool performs hybrid search (semantic + keyword) across all uploaded documents.

Parameters:
- query: Natural language search query describing what information you need
- document_id (optional): Specific document ID to search within

Returns relevant document excerpts with source information."""
        super().__init__(name, description)

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
        
        # Use hybrid search to get grouped context
        context_bundle = await build_grouped_context(
            conn=None,  # Using global postgres_client
            query=query,
            active_document_id=document_id
        )
        
        if not context_bundle.blocks:
            raise Exception(f"No relevant documents found for query: {query}")
        
        # Create summary of what was found
        doc_summary = []
        total_snippets = 0
        
        for block in context_bundle.blocks:
            doc_summary.append(f"• {block.title} ({len(block.snippets)} sections)")
            total_snippets += len(block.snippets)
        
        summary = f"Found relevant information in {len(context_bundle.blocks)} document(s):\n" + "\n".join(doc_summary)
        
        return {
            "success": True,
            "result": summary,
            "context": context_bundle.context_text,
            "documents_found": len(context_bundle.blocks),
            "total_snippets": total_snippets,
            "search_query": query
        }