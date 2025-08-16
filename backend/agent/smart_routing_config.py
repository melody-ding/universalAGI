"""
Smart Routing Configuration for Optimized Agent Architecture
"""

from dataclasses import dataclass
from typing import Dict


@dataclass
class RouterConfig:
    """Configuration for routing between SHORT and LONG paths"""
    weights: Dict[str, float]
    threshold: float


@dataclass
class EscalationConfig:
    """Configuration for escalation rules"""
    min_strong_segments: int
    max_distinct_docs: int
    min_avg_vec_sim: float
    min_fts_hit_rate: float


@dataclass
class SmartRoutingConfig:
    """Complete configuration for smart routing system"""
    router: RouterConfig
    escalation: EscalationConfig
    
    # Search parameters
    probe_doc_limit: int = 10
    probe_candidates_per_type: int = 3
    
    # SHORT path parameters
    short_top_docs: int = 15
    short_per_doc: int = 3
    short_vector_limit: int = 20
    short_text_limit: int = 20
    short_alpha: float = 0.6  # vector weight in hybrid
    
    # LONG path parameters
    long_max_subqueries: int = 3
    long_max_steps: int = 5
    long_budget_tokens: int = 8000
    long_budget_time_sec: int = 30
    
    # Response limits
    max_response_tokens: int = 4000  # Max tokens in final response
    max_context_tokens: int = 12000  # Max tokens in context sent to LLM
    max_context_chars: int = 48000   # Rough char limit for context (4 chars per token)


# Default configuration matching the specification
DEFAULT_CONFIG = SmartRoutingConfig(
    router=RouterConfig(
        weights={
            "avg_vec_sim": 0.9,
            "fts_hit_rate": 0.5,
            "top_doc_share": 0.8,
            "unique_docs": -0.7,
            "has_quotes_or_ids": -0.1,
            "has_compare_temporal_conditions": -0.6
        },
        threshold=0.5
    ),
    escalation=EscalationConfig(
        min_strong_segments=2,
        max_distinct_docs=4,
        min_avg_vec_sim=0.60, 
        min_fts_hit_rate=0.10
    )
)