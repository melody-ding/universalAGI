"""
SHORT Path - Optimized single-pass RAG for simple queries
"""

import logging
import asyncio
from typing import Dict, Any, Optional
from dataclasses import dataclass

from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage
from config import settings

from search.multi_document_search import ContextBundle
from database.postgres_client import postgres_client
from services.embedding_service import embedding_service
from .smart_routing_config import SmartRoutingConfig
from .smart_probe import ProbeSignals

logger = logging.getLogger(__name__)


@dataclass
class ShortPathResult:
    """Result from SHORT path execution"""
    answer: str
    context: ContextBundle
    debug_info: Dict[str, Any]
    success: bool = True
    error: Optional[str] = None


def _vector_search_segments_optimized(query_embedding: list, config: SmartRoutingConfig, document_id: Optional[int] = None) -> list:
    """Optimized vector search with configurable parameters"""
    embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'
    
    if document_id:
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
            {'name': 'limit', 'value': {'longValue': config.short_vector_limit}}
        ]
    else:
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
            {'name': 'limit', 'value': {'longValue': config.short_vector_limit}}
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


def _text_search_segments_optimized(query: str, config: SmartRoutingConfig, document_id: Optional[int] = None) -> list:
    """Optimized text search with configurable parameters"""
    if document_id:
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
            {'name': 'limit', 'value': {'longValue': config.short_text_limit}}
        ]
    else:
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
            {'name': 'limit', 'value': {'longValue': config.short_text_limit}}
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


def _hybrid_rerank_optimized(vector_results: list, text_results: list, alpha: float = 0.6) -> list:
    """Optimized hybrid reranking with configurable alpha"""
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
        
        # Calculate RRF score with configurable alpha
        rrf_score = (alpha / (k + vector_rank)) + ((1 - alpha) / (k + text_rank))
        
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


def _group_results_optimized(results: list, config: SmartRoutingConfig) -> list:
    """Group search results by document with configurable limits"""
    from search.multi_document_search import ContextBlock
    
    doc_groups = {}
    
    for result in results:
        doc_id = result['document_id']
        if doc_id not in doc_groups:
            doc_groups[doc_id] = {
                'title': result['title'],
                'snippets': []
            }
        
        # Add snippet if we haven't reached the limit
        if len(doc_groups[doc_id]['snippets']) < config.short_per_doc:
            snippet = f"[§{result['segment_ordinal']}] {result['text']}"
            doc_groups[doc_id]['snippets'].append(snippet)
    
    # Convert to ContextBlocks, limited by max_docs
    blocks = []
    for doc_id, group in list(doc_groups.items())[:config.short_top_docs]:
        if group['snippets']:  # Only include documents with snippets
            blocks.append(ContextBlock(
                document_id=doc_id,
                title=group['title'],
                snippets=group['snippets']
            ))
    
    return blocks


async def build_context_short_path(query: str, config: SmartRoutingConfig, document_id: Optional[int] = None) -> ContextBundle:
    """
    Build context using optimized SHORT path parameters
    
    Args:
        query: User query
        config: Smart routing configuration
        document_id: Optional specific document to search
        
    Returns:
        ContextBundle with retrieved information
    """
    from search.multi_document_search import ContextBundle
    
    logger.info(f"Building SHORT path context for: {query[:100]}...")
    
    # Step 1: Generate query embedding
    query_embedding = embedding_service.generate_embedding(query)
    
    # Step 2: Run parallel search with optimized parameters
    vector_task = asyncio.create_task(
        asyncio.to_thread(_vector_search_segments_optimized, query_embedding, config, document_id)
    )
    text_task = asyncio.create_task(
        asyncio.to_thread(_text_search_segments_optimized, query, config, document_id)
    )
    
    vector_results, text_results = await asyncio.gather(vector_task, text_task)
    
    logger.info(f"Found {len(vector_results)} vector + {len(text_results)} text results")
    
    # Step 3: Hybrid rerank with configurable alpha
    final_results = _hybrid_rerank_optimized(vector_results, text_results, config.short_alpha)
    
    # Step 4: Group by document with SHORT path limits
    blocks = _group_results_optimized(final_results, config)
    
    # Step 5: Format context text
    context_parts = []
    for block in blocks:
        context_parts.append(f"{{{block.title}}}")
        for snippet in block.snippets:
            context_parts.append(snippet)
        context_parts.append("")  # Empty line between documents
    
    context_text = "\n".join(context_parts).strip()
    
    logger.info(f"SHORT path context: {len(blocks)} docs, {len(final_results)} total segments")
    
    return ContextBundle(
        query=query,
        context_text=context_text,
        blocks=blocks
    )


async def synthesize_answer_short(query: str, context: ContextBundle, config: SmartRoutingConfig = None) -> str:
    """
    Synthesize answer using SHORT path - single LLM call with mandatory citations
    
    Args:
        query: User query
        context: Retrieved context bundle
        config: Smart routing configuration for token limits
        
    Returns:
        Synthesized answer with citations
    """
    from .token_manager import truncate_context_by_tokens, add_response_token_limit, validate_response_length
    from .smart_routing_config import DEFAULT_CONFIG
    
    config = config or DEFAULT_CONFIG
    
    # Truncate context if needed
    context = truncate_context_by_tokens(context, config)
    
    llm = ChatOpenAI(
        model=settings.MODEL_NAME,
        temperature=0.3,  # Lower temperature for consistent citations
        openai_api_key=settings.OPENAI_API_KEY,
        max_tokens=config.max_response_tokens  # Set response token limit
    )
    
    system_prompt = """You are a precise document-based Q&A assistant. Provide direct, well-cited answers using ONLY the retrieved document context.

MANDATORY CITATION RULES:
- Use format: {Document Title} [§section] for every fact
- Never provide information not explicitly in the context
- If context is insufficient, clearly state limitations
- Organize multi-document answers clearly

Be concise, accurate, and always cite your sources."""
    
    # Add token limit instructions
    system_prompt = add_response_token_limit(system_prompt, config)

    user_prompt = f"""Question: {query}

Retrieved Context:
{context.context_text}

Provide a comprehensive answer based solely on the retrieved context. Use mandatory citations for all facts."""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ]

    try:
        response = llm.invoke(messages)
        # Validate and truncate response if needed
        validated_response = validate_response_length(response.content, config)
        return validated_response
    except Exception as e:
        logger.error(f"SHORT path synthesis failed: {e}")
        return f"I apologize, but I encountered an error while synthesizing the answer: {str(e)}"


async def run_short_path(query: str, config: SmartRoutingConfig, document_id: Optional[int] = None) -> ShortPathResult:
    """
    Execute the complete SHORT path: retrieve + synthesize
    
    Args:
        query: User query
        config: Smart routing configuration  
        document_id: Optional specific document to search
        
    Returns:
        ShortPathResult with answer and debug info
    """
    try:
        logger.info(f"Executing SHORT path for: {query[:100]}...")
        
        # Step 1: Build context with SHORT path parameters
        context = await build_context_short_path(query, config, document_id)
        
        # Step 2: Synthesize answer with mandatory citations
        answer = await synthesize_answer_short(query, context, config)
        
        # Step 3: Prepare debug info for escalation decisions
        debug_info = {
            "total_docs": len(context.blocks),
            "total_segments": sum(len(block.snippets) for block in context.blocks),
            "has_context": len(context.context_text.strip()) > 0,
            "context_length": len(context.context_text),
        }
        
        logger.info(f"SHORT path completed: {debug_info['total_docs']} docs, {debug_info['total_segments']} segments")
        
        return ShortPathResult(
            answer=answer,
            context=context,
            debug_info=debug_info,
            success=True
        )
        
    except Exception as e:
        logger.error(f"SHORT path failed: {e}")
        return ShortPathResult(
            answer=f"I encountered an error processing your request: {str(e)}",
            context=None,
            debug_info={"error": str(e)},
            success=False,
            error=str(e)
        )