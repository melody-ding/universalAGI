"""
Smart Probe - Cheap signal computation for routing decisions
"""

import re
import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter

from database.postgres_client import postgres_client
from services.embedding_service import embedding_service
from .smart_routing_config import SmartRoutingConfig

logger = logging.getLogger(__name__)


@dataclass
class ProbeSignals:
    """Signals computed from cheap probe"""
    avg_vec_sim: float
    fts_hit_rate: float
    top_doc_share: float
    unique_docs: int
    has_quotes_or_ids: bool
    has_compare_temporal_conditions: bool
    
    # Debug info
    doc_counts: Dict[int, int]
    total_candidates: int
    vector_candidates: int
    fts_candidates: int


def _prefilter_documents(query_embedding: List[float], limit: int = 10) -> List[Dict]:
    """Fast document-level prefiltering using document embeddings"""
    embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'
    
    sql = """
    SELECT id, title, (embedding <=> :query_embedding::vector) as similarity_score
    FROM documents
    ORDER BY embedding <=> :query_embedding::vector
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
            'title': record[1].get('stringValue'),
            'similarity_score': record[2].get('doubleValue', 1.0)
        })
    
    return results


def _sample_candidates_vector(query_embedding: List[float], doc_ids: List[int], limit: int = 3) -> List[Dict]:
    """Sample top vector similarity candidates from prefiltered documents"""
    if not doc_ids:
        return []
    
    embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'
    doc_ids_str = ','.join(map(str, doc_ids))
    
    sql = f"""
    SELECT ds.id, ds.document_id, ds.segment_ordinal, ds.text, d.title,
           (ds.embedding <=> :query_embedding::vector) as similarity_score
    FROM document_segments ds
    JOIN documents d ON ds.document_id = d.id
    WHERE ds.document_id IN ({doc_ids_str})
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


def _sample_candidates_fts(query: str, doc_ids: List[int], limit: int = 3) -> List[Dict]:
    """Sample top FTS candidates from prefiltered documents"""
    if not doc_ids:
        return []
    
    doc_ids_str = ','.join(map(str, doc_ids))
    
    sql = f"""
    SELECT ds.id, ds.document_id, ds.segment_ordinal, ds.text, d.title,
           ts_rank(ds.ts, plainto_tsquery('english', :query)) as text_score
    FROM document_segments ds
    JOIN documents d ON ds.document_id = d.id
    WHERE ds.document_id IN ({doc_ids_str})
      AND ds.ts @@ plainto_tsquery('english', :query)
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


def _detect_query_patterns(query: str) -> Tuple[bool, bool]:
    """Detect specific query patterns using regex"""
    
    # Quotes or ID patterns
    quote_patterns = [
        r'"[^"]*"',  # quoted strings
        r"'[^']*'",  # single quoted strings
        r'\b(?:id|ID|identifier)\s*[:\-]?\s*\w+',  # ID references
        r'\b(?:section|page|paragraph)\s+\d+',  # section references
        r'\b(?:article|clause|item)\s+\d+',  # article references
    ]
    
    has_quotes_or_ids = any(re.search(pattern, query, re.IGNORECASE) for pattern in quote_patterns)
    
    # Temporal/comparison patterns
    temporal_patterns = [
        r'\b(?:before|after|since|until|during)\b',
        r'\b(?:compare|comparison|versus|vs|difference)\b',
        r'\b(?:earlier|later|previous|next|recent)\b',
        r'\b(?:first|last|initial|final)\b',
        r'\b(?:older|newer|latest|earliest)\b',
        r'\b\d{4}\b',  # years
        r'\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\b',
    ]
    
    has_compare_temporal = any(re.search(pattern, query, re.IGNORECASE) for pattern in temporal_patterns)
    
    return has_quotes_or_ids, has_compare_temporal


def compute_probe_signals(query: str, config: SmartRoutingConfig) -> ProbeSignals:
    """
    Compute routing signals from a cheap probe
    
    Args:
        query: User query string
        config: Smart routing configuration
        
    Returns:
        ProbeSignals with computed metrics
    """
    logger.info(f"Computing probe signals for query: {query[:100]}...")
    
    # Step 1: Embed query once
    query_embedding = embedding_service.generate_embedding(query)
    
    # Step 2: Document prefilter
    top_docs = _prefilter_documents(query_embedding, config.probe_doc_limit)
    doc_ids = [doc['id'] for doc in top_docs]
    logger.info(f"Prefiltered to {len(doc_ids)} documents")
    
    if not doc_ids:
        # No documents found - return minimal signals
        has_quotes_or_ids, has_compare_temporal = _detect_query_patterns(query)
        return ProbeSignals(
            avg_vec_sim=0.0,
            fts_hit_rate=0.0,
            top_doc_share=1.0,
            unique_docs=0,
            has_quotes_or_ids=has_quotes_or_ids,
            has_compare_temporal_conditions=has_compare_temporal,
            doc_counts={},
            total_candidates=0,
            vector_candidates=0,
            fts_candidates=0
        )
    
    # Step 3: Sample candidates
    vector_candidates = _sample_candidates_vector(
        query_embedding, doc_ids, config.probe_candidates_per_type
    )
    fts_candidates = _sample_candidates_fts(
        query, doc_ids, config.probe_candidates_per_type
    )
    
    logger.info(f"Found {len(vector_candidates)} vector + {len(fts_candidates)} FTS candidates")
    
    # Step 4: Compute signals
    all_candidates = vector_candidates + fts_candidates
    
    # avg_vec_sim: average similarity of vector candidates
    if vector_candidates:
        avg_vec_sim = sum(1 - c['similarity_score'] for c in vector_candidates) / len(vector_candidates)
        avg_vec_sim = max(0.0, min(1.0, avg_vec_sim))  # clamp to [0,1]
    else:
        avg_vec_sim = 0.0
    
    # fts_hit_rate: ratio of FTS hits to total candidates
    total_possible_fts = len(doc_ids) * config.probe_candidates_per_type
    fts_hit_rate = len(fts_candidates) / max(1, total_possible_fts)
    
    # Document distribution
    doc_counts = Counter(c['document_id'] for c in all_candidates)
    unique_docs = len(doc_counts)
    
    # top_doc_share: max concentration in single document
    if doc_counts:
        top_doc_share = max(doc_counts.values()) / sum(doc_counts.values())
    else:
        top_doc_share = 1.0
    
    # Pattern detection
    has_quotes_or_ids, has_compare_temporal = _detect_query_patterns(query)
    
    logger.info(f"Signals: vec_sim={avg_vec_sim:.3f}, fts_rate={fts_hit_rate:.3f}, "
                f"doc_share={top_doc_share:.3f}, unique_docs={unique_docs}")
    
    return ProbeSignals(
        avg_vec_sim=avg_vec_sim,
        fts_hit_rate=fts_hit_rate,
        top_doc_share=top_doc_share,
        unique_docs=unique_docs,
        has_quotes_or_ids=has_quotes_or_ids,
        has_compare_temporal_conditions=has_compare_temporal,
        doc_counts=dict(doc_counts),
        total_candidates=len(all_candidates),
        vector_candidates=len(vector_candidates),
        fts_candidates=len(fts_candidates)
    )


def compute_routing_score(signals: ProbeSignals, config: SmartRoutingConfig) -> float:
    """
    Compute linear routing score from signals
    
    Args:
        signals: Computed probe signals
        config: Smart routing configuration
        
    Returns:
        Routing score (higher = more suitable for SHORT path)
    """
    weights = config.router.weights
    
    score = (
        weights["avg_vec_sim"] * signals.avg_vec_sim +
        weights["fts_hit_rate"] * signals.fts_hit_rate +
        weights["top_doc_share"] * signals.top_doc_share +
        weights["unique_docs"] * (signals.unique_docs / 10.0) +  # normalize unique_docs
        weights["has_quotes_or_ids"] * (1.0 if signals.has_quotes_or_ids else 0.0) +
        weights["has_compare_temporal_conditions"] * (1.0 if signals.has_compare_temporal_conditions else 0.0)
    )
    
    logger.info(f"Routing score: {score:.3f} (threshold: {config.router.threshold})")
    return score