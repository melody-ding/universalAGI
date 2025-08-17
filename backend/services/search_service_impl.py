"""
Concrete implementation of SearchService.
"""

from typing import List, Dict, Any, Optional
from services.interfaces import SearchService, SearchResult
from search.multi_document_search import build_grouped_context
from services.embedding_service import embedding_service
from database.postgres_client import postgres_client
from utils.logging_config import get_logger

logger = get_logger(__name__)


class SearchServiceImpl(SearchService):
    """Concrete implementation of SearchService."""
    
    def __init__(self):
        self.embedding_service = embedding_service
        self.db_client = postgres_client
    
    async def hybrid_search(self, query: str, document_id: Optional[int] = None, **kwargs) -> SearchResult:
        """Perform hybrid search across documents."""
        try:
            logger.info(f"Performing hybrid search for: {query[:100]}...")
            
            # Use the existing multi-document search
            context_bundle = await build_grouped_context(
                conn=None,  # Using global postgres_client
                query=query,
                active_document_id=document_id
            )
            
            if not context_bundle.blocks:
                logger.warning(f"No results found for query: {query}")
                return SearchResult(
                    documents_found=0,
                    total_snippets=0,
                    context_text="",
                    citations=[],
                    metadata={"query": query, "document_id": document_id}
                )
            
            # Extract citation information
            citations = []
            total_snippets = 0
            
            for block in context_bundle.blocks:
                total_snippets += len(block.snippets)
                
                # Extract citation information from snippets
                for snippet in block.snippets:
                    # Parse snippet format: "[§ordinal] text"
                    if snippet.startswith("[§") and "]" in snippet:
                        ordinal_end = snippet.find("]")
                        ordinal = snippet[2:ordinal_end]
                        text = snippet[ordinal_end + 2:]  # Skip "] "
                        
                        citations.append({
                            "document_id": block.document_id,
                            "segment_ordinal": int(ordinal),
                            "text": text.strip(),
                            "document_title": block.title
                        })
            
            result = SearchResult(
                documents_found=len(context_bundle.blocks),
                total_snippets=total_snippets,
                context_text=context_bundle.context_text,
                citations=citations,
                metadata={
                    "query": query,
                    "document_id": document_id,
                    "search_type": "hybrid"
                }
            )
            
            logger.info(f"Hybrid search completed: {result.documents_found} documents, {result.total_snippets} snippets")
            return result
            
        except Exception as e:
            logger.error(f"Hybrid search failed for query '{query}': {str(e)}")
            return SearchResult(
                documents_found=0,
                total_snippets=0,
                context_text="",
                citations=[],
                metadata={"query": query, "error": str(e)}
            )
    
    async def vector_search(self, embedding: List[float], limit: int = 20) -> List[Dict[str, Any]]:
        """Perform vector similarity search."""
        try:
            logger.info(f"Performing vector search with {len(embedding)}-dimensional embedding")
            
            # Use PostgreSQL's vector similarity search
            sql = """
            SELECT ds.document_id, ds.segment_ordinal, ds.text, d.title,
                   1 - (ds.embedding <=> %s::vector) as similarity
            FROM document_segments ds
            JOIN documents d ON ds.document_id = d.id
            WHERE ds.embedding IS NOT NULL
            ORDER BY ds.embedding <=> %s::vector
            LIMIT %s
            """
            
            # Convert embedding to PostgreSQL vector format
            embedding_str = '[' + ','.join(map(str, embedding)) + ']'
            
            response = self.db_client.execute_statement(
                sql.replace('%s', ':param'),
                [
                    {'name': 'param', 'value': {'stringValue': embedding_str}},
                    {'name': 'param', 'value': {'stringValue': embedding_str}},
                    {'name': 'param', 'value': {'longValue': limit}}
                ]
            )
            
            results = []
            for record in response.get('records', []):
                results.append({
                    "document_id": record[0].get('longValue'),
                    "segment_ordinal": record[1].get('longValue'),
                    "text": record[2].get('stringValue', ''),
                    "document_title": record[3].get('stringValue', ''),
                    "similarity": float(record[4].get('doubleValue', 0.0))
                })
            
            logger.info(f"Vector search completed: {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Vector search failed: {str(e)}")
            return []
    
    async def text_search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Perform full-text search."""
        try:
            logger.info(f"Performing text search for: {query}")
            
            # Use PostgreSQL's full-text search
            sql = """
            SELECT ds.document_id, ds.segment_ordinal, ds.text, d.title,
                   ts_rank(ds.ts, plainto_tsquery('english', :query)) as rank
            FROM document_segments ds
            JOIN documents d ON ds.document_id = d.id
            WHERE ds.ts @@ plainto_tsquery('english', :query)
            ORDER BY ts_rank(ds.ts, plainto_tsquery('english', :query)) DESC
            LIMIT :limit
            """
            
            response = self.db_client.execute_statement(sql, [
                {'name': 'query', 'value': {'stringValue': query}},
                {'name': 'limit', 'value': {'longValue': limit}}
            ])
            
            results = []
            for record in response.get('records', []):
                results.append({
                    "document_id": record[0].get('longValue'),
                    "segment_ordinal": record[1].get('longValue'),
                    "text": record[2].get('stringValue', ''),
                    "document_title": record[3].get('stringValue', ''),
                    "rank": float(record[4].get('doubleValue', 0.0))
                })
            
            logger.info(f"Text search completed: {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Text search failed for query '{query}': {str(e)}")
            return []
