"""
Smart Orchestrator - Tiny orchestrator with escalation logic
"""

import logging
from typing import Dict, Any, Optional

from .smart_routing_config import SmartRoutingConfig, DEFAULT_CONFIG
from .smart_probe import compute_probe_signals, compute_routing_score, ProbeSignals
from .short_path import run_short_path, ShortPathResult
from .long_path import run_long_path, LongPathResult

logger = logging.getLogger(__name__)


def should_escalate_from_short(
    short_result: ShortPathResult, 
    signals: ProbeSignals, 
    config: SmartRoutingConfig
) -> bool:
    """
    Determine if SHORT path result should escalate to LONG path
    
    Args:
        short_result: Result from SHORT path execution
        signals: Original probe signals
        config: Smart routing configuration
        
    Returns:
        True if escalation is needed, False otherwise
    """
    if not short_result.success or not short_result.context:
        logger.info("Escalating due to SHORT path failure")
        return True
    
    debug_info = short_result.debug_info
    escalation = config.escalation
    
    # Check escalation conditions
    reasons = []
    
    # Strong evidence check
    if debug_info.get("total_segments", 0) < escalation.min_strong_segments:
        reasons.append(f"insufficient segments ({debug_info.get('total_segments', 0)} < {escalation.min_strong_segments})")
    
    # Document distribution check
    if debug_info.get("total_docs", 0) > escalation.max_distinct_docs:
        reasons.append(f"too many docs ({debug_info.get('total_docs', 0)} > {escalation.max_distinct_docs})")
    
    # Quality thresholds
    if signals.avg_vec_sim < escalation.min_avg_vec_sim:
        reasons.append(f"low vector similarity ({signals.avg_vec_sim:.2f} < {escalation.min_avg_vec_sim})")
    
    if signals.fts_hit_rate < escalation.min_fts_hit_rate:
        reasons.append(f"low FTS hit rate ({signals.fts_hit_rate:.2f} < {escalation.min_fts_hit_rate})")
    
    # Check for obvious conflicts (simple heuristic)
    context_text = short_result.context.context_text.lower()
    conflict_indicators = ["however", "but", "although", "contradicts", "differs", "opposed"]
    has_conflicts = sum(1 for indicator in conflict_indicators if indicator in context_text) >= 2
    
    if has_conflicts:
        reasons.append("potential conflicts detected")
    
    # Escalate if any condition is met
    should_escalate = len(reasons) > 0
    
    if should_escalate:
        logger.info(f"Escalating SHORT->LONG: {', '.join(reasons)}")
    else:
        logger.info("SHORT path result sufficient, no escalation needed")
    
    return should_escalate


async def smart_handle_message(
    query: str, 
    config: Optional[SmartRoutingConfig] = None,
    document_id: Optional[int] = None
) -> str:
    """
    Main entrypoint for smart orchestrated message handling
    
    Args:
        query: User query string
        config: Smart routing configuration (uses default if None)
        document_id: Optional specific document to search
        
    Returns:
        Response string from either SHORT or LONG path
    """
    config = config or DEFAULT_CONFIG
    
    try:
        logger.info(f"Smart orchestrator processing: {query[:100]}...")
        
        # Step 1: Cheap probe to compute signals
        signals = compute_probe_signals(query, config)
        
        # Step 2: Compute routing score
        score = compute_routing_score(signals, config)
        
        # Step 3: Route based on score
        if score >= config.router.threshold:
            path = "SHORT"
            logger.info(f"ROUTE DECISION: SHORT path selected")
            logger.info(f"   Score: {score:.3f} >= threshold {config.router.threshold}")
            logger.info(f"   Signals: vec_sim={signals.avg_vec_sim:.2f}, fts_rate={signals.fts_hit_rate:.2f}, docs={signals.unique_docs}")
            
            # Execute SHORT path
            short_result = await run_short_path(query, config, document_id)
            
            # Check for escalation
            if should_escalate_from_short(short_result, signals, config):
                logger.info("ESCALATION: SHORT->LONG triggered")
                logger.info(f"   Reason: {short_result.debug_info}")
                long_result = await run_long_path(query, signals, config)
                logger.info("FINAL ROUTE: SHORT->LONG (escalated)")
                return long_result.answer
            else:
                logger.info("FINAL ROUTE: SHORT (completed)")
                return short_result.answer
                
        else:
            path = "LONG"
            logger.info(f"ROUTE DECISION: LONG path selected")
            logger.info(f"   Score: {score:.3f} < threshold {config.router.threshold}")
            logger.info(f"   Signals: vec_sim={signals.avg_vec_sim:.2f}, fts_rate={signals.fts_hit_rate:.2f}, docs={signals.unique_docs}")
            
            # Execute LONG path directly
            long_result = await run_long_path(query, signals, config)
            logger.info("FINAL ROUTE: LONG (completed)")
            return long_result.answer
            
    except Exception as e:
        logger.error(f"Smart orchestrator failed: {e}")
        return f"I encountered an error while processing your request: {str(e)}"


# Backward compatibility function for existing orchestrator interface
async def handle_message_smart(user_text: str) -> str:
    """
    Backward compatibility wrapper for existing orchestrator interface
    
    Args:
        user_text: User's input message
        
    Returns:
        Response from smart orchestrator
    """
    return await smart_handle_message(user_text)


# Statistics and debugging functions
def get_routing_stats(query: str, config: Optional[SmartRoutingConfig] = None) -> Dict[str, Any]:
    """
    Get detailed routing statistics for debugging
    
    Args:
        query: User query
        config: Smart routing configuration
        
    Returns:
        Dictionary with detailed routing information
    """
    config = config or DEFAULT_CONFIG
    
    signals = compute_probe_signals(query, config)
    score = compute_routing_score(signals, config)
    
    return {
        "query": query,
        "signals": {
            "avg_vec_sim": signals.avg_vec_sim,
            "fts_hit_rate": signals.fts_hit_rate,
            "top_doc_share": signals.top_doc_share,
            "unique_docs": signals.unique_docs,
            "has_quotes_or_ids": signals.has_quotes_or_ids,
            "has_compare_temporal_conditions": signals.has_compare_temporal_conditions,
        },
        "score": score,
        "threshold": config.router.threshold,
        "recommended_path": "SHORT" if score >= config.router.threshold else "LONG",
        "weights": config.router.weights,
        "debug": {
            "doc_counts": signals.doc_counts,
            "total_candidates": signals.total_candidates,
            "vector_candidates": signals.vector_candidates,
            "fts_candidates": signals.fts_candidates,
        }
    }


def explain_routing_decision(query: str, config: Optional[SmartRoutingConfig] = None) -> str:
    """
    Generate human-readable explanation of routing decision
    
    Args:
        query: User query
        config: Smart routing configuration
        
    Returns:
        Human-readable explanation string
    """
    stats = get_routing_stats(query, config)
    
    explanation = f"""Routing Analysis for: "{query[:100]}{'...' if len(query) > 100 else ''}"

SIGNALS:
• Vector similarity: {stats['signals']['avg_vec_sim']:.3f}
• FTS hit rate: {stats['signals']['fts_hit_rate']:.3f}  
• Document concentration: {stats['signals']['top_doc_share']:.3f}
• Unique documents: {stats['signals']['unique_docs']}
• Has quotes/IDs: {stats['signals']['has_quotes_or_ids']}
• Has temporal/comparison: {stats['signals']['has_compare_temporal_conditions']}

SCORING:
• Final score: {stats['score']:.3f}
• Threshold: {stats['threshold']}
• Recommended path: {stats['recommended_path']}

REASONING:
"""
    
    if stats['recommended_path'] == "SHORT":
        explanation += "Score above threshold suggests straightforward document retrieval is sufficient."
    else:
        explanation += "Score below threshold suggests complex analysis requiring multiple subqueries."
    
    return explanation