import logging
from dataclasses import dataclass
from typing import List, Optional, Dict
from database.postgres_client import postgres_client
from services.embedding_service import embedding_service

logger = logging.getLogger(__name__)

@dataclass
class SingleDocumentResult:
    segment_id: int
    segment_ordinal: int
    text: str
    similarity_score: float
    text_score: Optional[float] = None
    rrf_score: Optional[float] = None

@dataclass
class SingleDocumentContext:
    query: str
    document_id: int
    document_title: str
    context_text: str
    results: List[SingleDocumentResult]

def _vector_search_single_document(query_embedding: List[float], document_id: int, limit: int = 20) -> List[SingleDocumentResult]:
    """Perform vector similarity search on segments within a single document."""
    embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'
    
    sql = """
    SELECT ds.id, ds.segment_ordinal, ds.text, d.title,
           (ds.embedding <=> :query_embedding::vector) as similarity_score
    FROM document_segments ds
    JOIN documents d ON ds.document_id = d.id
    WHERE ds.document_id = :document_id
    ORDER BY ds.embedding <=> :query_embedding::vector
    LIMIT :limit
    """
    
    parameters = [
        {'name': 'query_embedding', 'value': {'stringValue': embedding_str}},
        {'name': 'document_id', 'value': {'longValue': document_id}},
        {'name': 'limit', 'value': {'longValue': limit}}
    ]
    
    response = postgres_client.execute_statement(sql, parameters)
    
    results = []
    for record in response.get('records', []):
        results.append(SingleDocumentResult(
            segment_id=record[0].get('longValue'),
            segment_ordinal=record[1].get('longValue'),
            text=record[2].get('stringValue'),
            similarity_score=record[4].get('doubleValue', 1.0)
        ))
    
    return results

def _text_search_single_document(query: str, document_id: int, limit: int = 20) -> List[SingleDocumentResult]:
    """Perform full-text search on segments within a single document."""
    sql = """
    SELECT ds.id, ds.segment_ordinal, ds.text, d.title,
           ts_rank(ds.ts, plainto_tsquery('english', :query)) as text_score
    FROM document_segments ds
    JOIN documents d ON ds.document_id = d.id
    WHERE ds.document_id = :document_id
      AND ds.ts @@ plainto_tsquery('english', :query)
    ORDER BY ts_rank(ds.ts, plainto_tsquery('english', :query)) DESC
    LIMIT :limit
    """
    
    parameters = [
        {'name': 'query', 'value': {'stringValue': query}},
        {'name': 'document_id', 'value': {'longValue': document_id}},
        {'name': 'limit', 'value': {'longValue': limit}}
    ]
    
    response = postgres_client.execute_statement(sql, parameters)
    
    results = []
    for record in response.get('records', []):
        results.append(SingleDocumentResult(
            segment_id=record[0].get('longValue'),
            segment_ordinal=record[1].get('longValue'),
            text=record[2].get('stringValue'),
            similarity_score=0.0,  # Not used in text search
            text_score=record[4].get('doubleValue', 0.0)
        ))
    
    return results

def _hybrid_rerank_single_document(vector_results: List[SingleDocumentResult], 
                                 text_results: List[SingleDocumentResult],
                                 vector_weight: float = 0.7, 
                                 text_weight: float = 0.3) -> List[SingleDocumentResult]:
    """Combine and rerank vector and text search results using RRF (Reciprocal Rank Fusion)."""
    # Create maps for quick lookup
    vector_map = {r.segment_id: (i + 1, r) for i, r in enumerate(vector_results)}
    text_map = {r.segment_id: (i + 1, r) for i, r in enumerate(text_results)}
    
    # Get all unique segment IDs
    all_ids = set(vector_map.keys()) | set(text_map.keys())
    
    combined_results = []
    k = 60  # RRF parameter
    
    for seg_id in all_ids:
        # Get ranks (default to len + 1 if not found)
        vector_rank = vector_map.get(seg_id, (len(vector_results) + 1, None))[0]
        text_rank = text_map.get(seg_id, (len(text_results) + 1, None))[0]
        
        # Calculate RRF score
        rrf_score = (vector_weight / (k + vector_rank)) + (text_weight / (k + text_rank))
        
        # Get the result object (prefer vector result if available)
        result = vector_map.get(seg_id, (None, None))[1] or text_map.get(seg_id, (None, None))[1]
        
        if result:
            # Create a new result with combined scores
            combined_result = SingleDocumentResult(
                segment_id=result.segment_id,
                segment_ordinal=result.segment_ordinal,
                text=result.text,
                similarity_score=result.similarity_score,
                text_score=text_map.get(seg_id, (None, None))[1].text_score if text_map.get(seg_id) else None,
                rrf_score=rrf_score
            )
            combined_results.append(combined_result)
    
    # Sort by RRF score descending
    combined_results.sort(key=lambda x: x.rrf_score, reverse=True)
    
    return combined_results

def _get_document_title(document_id: int) -> str:
    """Get the title of a document by ID."""
    sql = "SELECT title FROM documents WHERE id = :document_id"
    parameters = [{'name': 'document_id', 'value': {'longValue': document_id}}]
    
    response = postgres_client.execute_statement(sql, parameters)
    
    if response.get('records'):
        return response['records'][0][0].get('stringValue', f"Document {document_id}")
    else:
        return f"Document {document_id}"

def _format_single_document_context(results: List[SingleDocumentResult], document_title: str) -> str:
    """Format search results into a context string for a single document."""
    if not results:
        return f"{{{document_title}}}\nNo relevant content found."
    
    context_parts = [f"{{{document_title}}}"]
    
    for result in results:
        snippet = f"[§{result.segment_ordinal}] {result.text}"
        context_parts.append(snippet)
    
    return "\n".join(context_parts)

async def search_single_document(
    query: str,
    document_id: int,
    limit: int = 10
) -> SingleDocumentContext:
    """
    Search for relevant content within a single document using natural language query.
    
    Args:
        query: Natural language search query
        document_id: ID of the document to search within
        limit: Maximum number of results to return (default: 10)
    
    Returns:
        SingleDocumentContext containing query, document info, formatted context, and results
    """
    logger.info(f"Searching document {document_id} for query: {query[:100]}...")
    
    # Get document title
    document_title = _get_document_title(document_id)
    logger.info(f"Document title: {document_title}")
    
    # Generate query embedding
    query_embedding = embedding_service.generate_embedding(query)
    logger.info(f"Generated query embedding with {len(query_embedding)} dimensions")
    
    # Perform hybrid search
    vector_results = _vector_search_single_document(query_embedding, document_id, limit=limit)
    text_results = _text_search_single_document(query, document_id, limit=limit)
    
    logger.info(f"Vector search found {len(vector_results)} results")
    logger.info(f"Text search found {len(text_results)} results")
    
    # Hybrid rerank
    final_results = _hybrid_rerank_single_document(vector_results, text_results)
    
    # Limit final results
    final_results = final_results[:limit]
    
    logger.info(f"Final results after hybrid reranking: {len(final_results)}")
    
    # Format context text
    context_text = _format_single_document_context(final_results, document_title)
    
    return SingleDocumentContext(
        query=query,
        document_id=document_id,
        document_title=document_title,
        context_text=context_text,
        results=final_results
    )

# Convenience function that matches the multi_document_search API for compatibility
async def build_single_document_context(
    conn,  # Unused, kept for API compatibility
    query: str,
    document_id: int,
    limit: int = 10
) -> SingleDocumentContext:
    """
    Build context for a single document search.
    
    This function provides API compatibility with the multi-document search interface.
    """
    return await search_single_document(query, document_id, limit)
