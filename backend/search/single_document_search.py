import logging
from dataclasses import dataclass
from typing import List, Optional, Dict
from database.postgres_client import postgres_client
from services.embedding_service import embedding_service
from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage
from config import settings

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

def _get_all_document_segments(document_id: int) -> List[Dict]:
    """Retrieve all segments from a document in order."""
    sql = """
    SELECT ds.id, ds.segment_ordinal, ds.text
    FROM document_segments ds
    WHERE ds.document_id = :document_id
    ORDER BY ds.segment_ordinal
    """
    
    parameters = [{'name': 'document_id', 'value': {'longValue': document_id}}]
    response = postgres_client.execute_statement(sql, parameters)
    
    segments = []
    for record in response.get('records', []):
        segments.append({
            'id': record[0].get('longValue'),
            'segment_ordinal': record[1].get('longValue'),
            'text': record[2].get('stringValue')
        })
    
    return segments

def _chunk_segments(segments: List[Dict], chunk_size: int = 8) -> List[List[Dict]]:
    """Split segments into smaller chunks for map-reduce processing."""
    chunks = []
    for i in range(0, len(segments), chunk_size):
        chunks.append(segments[i:i + chunk_size])
    return chunks

async def _map_extract_answers(chunk: List[Dict], query: str) -> str:
    """Extract relevant information from a chunk of segments to answer the query."""
    llm = ChatOpenAI(
        model=settings.MODEL_NAME,
        temperature=0.1,
        openai_api_key=settings.OPENAI_API_KEY,
        max_tokens=400
    )
    
    chunk_text = "\n\n".join([f"[§{seg['segment_ordinal']}] {seg['text']}" for seg in chunk])
    
    system_prompt = """You are an expert document analyzer. Extract information or summaries from the given text segments that would help the user answer their question.

IMPORTANT:
- Extract any information that could be useful for answering the question
- Include relevant facts, definitions, explanations, examples, or context
- If no useful information is found, respond with "No useful information found"
- Be comprehensive - include anything that might help answer the question
- Summarize key points when segments contain relevant content"""
    
    user_prompt = f"""Question: {query}

Text segments to analyze:
{chunk_text}

Extract any information from these segments that helps answer the question."""
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ]
    
    try:
        response = llm.invoke(messages)
        return response.content
    except Exception as e:
        logger.error(f"Map extraction failed: {e}")
        return f"Error extracting from segments {chunk[0]['segment_ordinal']}-{chunk[-1]['segment_ordinal']}: {str(e)}"

async def _reduce_answers(extracted_info: List[str], query: str, document_title: str) -> str:
    """Synthesize extracted information into a comprehensive answer."""
    llm = ChatOpenAI(
        model=settings.MODEL_NAME,
        temperature=0.2,
        openai_api_key=settings.OPENAI_API_KEY,
        max_tokens=800
    )
    
    # Filter out empty or "no useful information" responses
    relevant_info = [info for info in extracted_info if info.strip() and "no useful information" not in info.lower()]
    
    if not relevant_info:
        return "Based on my analysis of all document segments, I could not find useful information to help answer your question."
    
    combined_info = "\n\n".join([f"Extract {i+1}:\n{info}" for i, info in enumerate(relevant_info)])
    
    system_prompt = """You are an expert analyst tasked with synthesizing extracted information into a comprehensive, well-structured answer. 

REQUIREMENTS:
- Provide a direct answer to the question using the extracted information
- Structure the response logically and clearly
- Synthesize information across extracts to provide the most complete answer possible
- If information is contradictory, note the discrepancies
- Be precise and stick to what's explicitly stated in the extracts"""
    
    user_prompt = f"""Question: {query}
Document: {document_title}

Extracted relevant information:
{combined_info}

Synthesize this information into a comprehensive answer to the question."""
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ]
    
    try:
        response = llm.invoke(messages)
        return response.content
    except Exception as e:
        logger.error(f"Reduce synthesis failed: {e}")
        return f"Unable to synthesize answer: {str(e)}"

async def map_reduce_single_document(
    query: str,
    document_id: int,
    chunk_size: int = 8
) -> SingleDocumentContext:
    """
    Use map-reduce to analyze all segments of a document and answer a specific question.
    
    Args:
        query: The question to answer
        document_id: ID of the document to analyze
        chunk_size: Number of segments to process in each map operation
    
    Returns:
        SingleDocumentContext with comprehensive answer based on entire document
    """
    logger.info(f"Starting map-reduce analysis of document {document_id} for query: {query[:100]}...")
    
    # Get document title
    document_title = _get_document_title(document_id)
    logger.info(f"Document title: {document_title}")
    
    # Retrieve all segments
    all_segments = _get_all_document_segments(document_id)
    logger.info(f"Retrieved {len(all_segments)} segments from document")
    
    if not all_segments:
        logger.warning(f"No segments found for document {document_id}")
        return SingleDocumentContext(
            query=query,
            document_id=document_id,
            document_title=document_title,
            context_text=f"{{{document_title}}}\nNo content found in this document.",
            results=[]
        )
    
    # Map phase: chunk segments and extract relevant information from each chunk
    chunks = _chunk_segments(all_segments, chunk_size)
    logger.info(f"Split segments into {len(chunks)} chunks of size {chunk_size}")
    
    extracted_info = []
    for i, chunk in enumerate(chunks):
        logger.info(f"Analyzing chunk {i+1}/{len(chunks)} (segments {chunk[0]['segment_ordinal']}-{chunk[-1]['segment_ordinal']})")
        info = await _map_extract_answers(chunk, query)
        extracted_info.append(info)
    
    # Reduce phase: synthesize extracted information into final answer
    logger.info("Synthesizing extracted information into comprehensive answer")
    final_answer = await _reduce_answers(extracted_info, query, document_title)
    
    # Format as context
    context_text = f"{{{document_title}}}\n{final_answer}"
    
    # Convert to SingleDocumentResult format for compatibility
    results = []
    for segment in all_segments:
        results.append(SingleDocumentResult(
            segment_id=segment['id'],
            segment_ordinal=segment['segment_ordinal'],
            text=segment['text'],
            similarity_score=1.0  # All segments processed
        ))
    
    logger.info(f"Map-reduce analysis completed for document {document_id}")
    
    return SingleDocumentContext(
        query=query,
        document_id=document_id,
        document_title=document_title,
        context_text=context_text,
        results=results
    )
