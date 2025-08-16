import logging
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple
from database.postgres_client import postgres_client
from services.embedding_service import embedding_service

logger = logging.getLogger(__name__)

@dataclass
class ContextBlock:
    document_id: int
    title: str
    snippets: List[str]        # a few chunk texts from the same doc (already ordered)

@dataclass
class ContextBundle:
    query: str
    context_text: str          # "{title}\n{snippet}\n{snippet}\n\n{title}\n..."
    blocks: List[ContextBlock] # structured version of the same content

def _vector_search_segments(query_embedding: List[float], limit: int = 50, document_id: Optional[int] = None) -> List[Dict]:
    """Perform vector similarity search on document segments."""
    embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'
    
    if document_id:
        # Single document search
        sql = """
        SELECT ds.id, ds.document_id, ds.segment_ordinal, ds.text, d.title,
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
    else:
        # Multi-document search
        sql = """
        SELECT ds.id, ds.document_id, ds.segment_ordinal, ds.text, d.title,
               (ds.embedding <=> :query_embedding::vector) as similarity_score
        FROM document_segments ds
        JOIN documents d ON ds.document_id = d.id
        ORDER BY ds.embedding <=> :query_embedding::vector
        LIMIT :limit
        """
        parameters = [
            {'name': 'query_embedding', 'value': {'stringValue': embedding_str}},
            {'name': 'limit', 'value': {'longValue': limit}}
        ]
    
    response = postgres_client.execute_statement(sql, parameters)
    
    results = []
    for record in response.get('records', []):
        results.append({
            'id': record[0].get('longValue'),
            'document_id': record[1].get('longValue'),
            'segment_ordinal': record[2].get('longValue'),
            'text': record[3].get('stringValue'),
            'title': record[4].get('stringValue'),
            'similarity_score': record[5].get('doubleValue', 1.0)
        })
    
    return results

def _text_search_segments(query: str, limit: int = 50, document_id: Optional[int] = None) -> List[Dict]:
    """Perform full-text search on document segments using PostgreSQL tsvector."""
    if document_id:
        # Single document search
        sql = """
        SELECT ds.id, ds.document_id, ds.segment_ordinal, ds.text, d.title,
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
    else:
        # Multi-document search
        sql = """
        SELECT ds.id, ds.document_id, ds.segment_ordinal, ds.text, d.title,
               ts_rank(ds.ts, plainto_tsquery('english', :query)) as text_score
        FROM document_segments ds
        JOIN documents d ON ds.document_id = d.id
        WHERE ds.ts @@ plainto_tsquery('english', :query)
        ORDER BY ts_rank(ds.ts, plainto_tsquery('english', :query)) DESC
        LIMIT :limit
        """
        parameters = [
            {'name': 'query', 'value': {'stringValue': query}},
            {'name': 'limit', 'value': {'longValue': limit}}
        ]
    
    response = postgres_client.execute_statement(sql, parameters)
    
    results = []
    for record in response.get('records', []):
        results.append({
            'id': record[0].get('longValue'),
            'document_id': record[1].get('longValue'),
            'segment_ordinal': record[2].get('longValue'),
            'text': record[3].get('stringValue'),
            'title': record[4].get('stringValue'),
            'text_score': record[5].get('doubleValue', 0.0)
        })
    
    return results

def _hybrid_rerank(vector_results: List[Dict], text_results: List[Dict], 
                   vector_weight: float = 0.7, text_weight: float = 0.3) -> List[Dict]:
    """Combine and rerank vector and text search results using RRF (Reciprocal Rank Fusion)."""
    # Create maps for quick lookup
    vector_map = {r['id']: (i + 1, r) for i, r in enumerate(vector_results)}
    text_map = {r['id']: (i + 1, r) for i, r in enumerate(text_results)}
    
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
            result = result.copy()
            result['rrf_score'] = rrf_score
            result['vector_rank'] = vector_rank
            result['text_rank'] = text_rank
            combined_results.append(result)
    
    # Sort by RRF score descending
    combined_results.sort(key=lambda x: x['rrf_score'], reverse=True)
    
    return combined_results

def _group_results_by_document(results: List[Dict], max_docs: int = 5, max_snippets_per_doc: int = 3) -> List[ContextBlock]:
    """Group search results by document and create context blocks."""
    doc_groups = {}
    
    for result in results:
        doc_id = result['document_id']
        if doc_id not in doc_groups:
            doc_groups[doc_id] = {
                'title': result['title'],
                'snippets': []
            }
        
        # Add snippet if we haven't reached the limit
        if len(doc_groups[doc_id]['snippets']) < max_snippets_per_doc:
            snippet = f"[§{result['segment_ordinal']}] {result['text']}"
            doc_groups[doc_id]['snippets'].append(snippet)
    
    # Convert to ContextBlocks, limited by max_docs
    blocks = []
    for doc_id, group in list(doc_groups.items())[:max_docs]:
        if group['snippets']:  # Only include documents with snippets
            blocks.append(ContextBlock(
                document_id=doc_id,
                title=group['title'],
                snippets=group['snippets']
            ))
    
    return blocks

def _format_context_text(blocks: List[ContextBlock]) -> str:
    """Format context blocks into a single text string."""
    context_parts = []
    
    for block in blocks:
        context_parts.append(f"{{{block.title}}}")
        for snippet in block.snippets:
            context_parts.append(snippet)
        context_parts.append("")  # Empty line between documents
    
    return "\n".join(context_parts).strip()

async def build_grouped_context(
    conn,
    query: str,
    active_document_id: Optional[int] = None,
) -> ContextBundle:
    """
    High-level helper: given a natural-language query, return grouped context blocks.

    Inputs:
      - conn: DB connection/session (unused, using global postgres_client)
      - query: user's natural-language question
      - active_document_id (optional): if provided, restricts to that document

    Behavior (internal, no extra params):
      - Embeds the query (1536-d).
      - If active_document_id is set → retrieve top chunks from that doc.
        Else → multi-document: prefilter top docs, pull a few chunks per doc, hybrid rerank.
      - Formats grouped context:
            {Document Title}
            [§ordinal] snippet
            [§ordinal] snippet

            {Next Document Title}
            ...
      - Returns both the joined `context_text` and structured `blocks`.

    Returns:
      ContextBundle(query, context_text, blocks)
    """
    logger.info(f"Building grouped context for query: {query[:100]}...")
    
    # Step 1: Generate query embedding
    query_embedding = embedding_service.generate_embedding(query)
    logger.info(f"Generated query embedding with {len(query_embedding)} dimensions")
    
    # Step 2: Perform hybrid search
    if active_document_id:
        logger.info(f"Searching within document ID: {active_document_id}")
        # Single document search - combine vector and text results
        vector_results = _vector_search_segments(query_embedding, limit=20, document_id=active_document_id)
        text_results = _text_search_segments(query, limit=20, document_id=active_document_id)
        
        # Hybrid rerank
        final_results = _hybrid_rerank(vector_results, text_results)
        
    else:
        logger.info("Performing multi-document search")
        # Multi-document search
        vector_results = _vector_search_segments(query_embedding, limit=30)
        text_results = _text_search_segments(query, limit=30)
        
        # Hybrid rerank
        final_results = _hybrid_rerank(vector_results, text_results)
    
    logger.info(f"Found {len(final_results)} total results after hybrid reranking")
    
    # Step 3: Group results by document
    max_docs = 3 if active_document_id else 5
    max_snippets = 5 if active_document_id else 3
    
    blocks = _group_results_by_document(final_results, max_docs=max_docs, max_snippets_per_doc=max_snippets)
    logger.info(f"Grouped results into {len(blocks)} document blocks")
    
    # Step 4: Format context text
    context_text = _format_context_text(blocks)
    
    return ContextBundle(
        query=query,
        context_text=context_text,
        blocks=blocks
    )