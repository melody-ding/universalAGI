"""
Smart Routing Configuration for Optimized Agent Architecture

This module provides backward compatibility for agent routing configuration.
The actual configuration is now managed through the consolidated config system.
"""

from dataclasses import dataclass
from typing import Dict

# Import the new configuration types from the main config
try:
    from config import settings, RouterConfig as ConfigRouterConfig, EscalationConfig as ConfigEscalationConfig, AgentConfig as ConfigAgentConfig
    _CONFIG_AVAILABLE = True
except ImportError:
    _CONFIG_AVAILABLE = False


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


def _create_default_config() -> SmartRoutingConfig:
    """Create default configuration, using consolidated config if available"""
    if _CONFIG_AVAILABLE:
        # Use values from the consolidated configuration
        agent_config = settings.agent
        return SmartRoutingConfig(
            router=RouterConfig(
                weights=agent_config.router.weights,
                threshold=agent_config.router.threshold
            ),
            escalation=EscalationConfig(
                min_strong_segments=agent_config.escalation.min_strong_segments,
                max_distinct_docs=agent_config.escalation.max_distinct_docs,
                min_avg_vec_sim=agent_config.escalation.min_avg_vec_sim,
                min_fts_hit_rate=agent_config.escalation.min_fts_hit_rate
            ),
            probe_doc_limit=agent_config.probe_doc_limit,
            probe_candidates_per_type=agent_config.probe_candidates_per_type,
            short_top_docs=agent_config.short_top_docs,
            short_per_doc=agent_config.short_per_doc,
            short_vector_limit=agent_config.short_vector_limit,
            short_text_limit=agent_config.short_text_limit,
            short_alpha=agent_config.short_alpha,
            long_max_subqueries=agent_config.long_max_subqueries,
            long_max_steps=agent_config.long_max_steps,
            long_budget_tokens=agent_config.long_budget_tokens,
            long_budget_time_sec=agent_config.long_budget_time_sec,
            max_response_tokens=agent_config.max_response_tokens,
            max_context_tokens=agent_config.max_context_tokens,
            max_context_chars=agent_config.max_context_chars
        )
    else:
        # Fallback to hardcoded defaults if config not available
        return SmartRoutingConfig(
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


# Default configuration - now loads from consolidated config system
DEFAULT_CONFIG = _create_default_config()