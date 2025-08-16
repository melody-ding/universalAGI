"""
Token Management - Utilities for managing token limits
"""

import logging
from typing import List, Dict, Any
from search.multi_document_search import ContextBundle, ContextBlock
from .smart_routing_config import SmartRoutingConfig

logger = logging.getLogger(__name__)


def estimate_tokens(text: str) -> int:
    """
    Estimate token count using character-based approximation
    
    Args:
        text: Text to estimate tokens for
        
    Returns:
        Estimated token count
    """
    # Rough approximation: 4 characters per token on average
    return len(text) // 4


def truncate_context_by_tokens(context: ContextBundle, config: SmartRoutingConfig) -> ContextBundle:
    """
    Truncate context to fit within token limits
    
    Args:
        context: Original context bundle
        config: Smart routing configuration
        
    Returns:
        Truncated context bundle that fits within limits
    """
    max_chars = config.max_context_chars
    current_chars = len(context.context_text)
    
    if current_chars <= max_chars:
        logger.info(f"Context within limits: {current_chars} <= {max_chars} chars")
        return context
    
    logger.info(f"Truncating context: {current_chars} > {max_chars} chars")
    
    # Truncate by removing least relevant snippets from each document
    truncated_blocks = []
    remaining_chars = max_chars
    
    # Reserve space for document titles and formatting
    title_overhead = sum(len(f"{{{block.title}}}\n\n") for block in context.blocks)
    remaining_chars -= title_overhead
    
    # Distribute remaining characters across documents proportionally
    total_snippet_chars = sum(
        sum(len(snippet) for snippet in block.snippets) 
        for block in context.blocks
    )
    
    for block in context.blocks:
        block_snippet_chars = sum(len(snippet) for snippet in block.snippets)
        
        if total_snippet_chars > 0:
            # Proportional allocation
            block_char_budget = int((block_snippet_chars / total_snippet_chars) * remaining_chars)
        else:
            block_char_budget = remaining_chars // len(context.blocks)
        
        # Keep snippets until we exceed budget
        truncated_snippets = []
        used_chars = 0
        
        for snippet in block.snippets:
            if used_chars + len(snippet) <= block_char_budget:
                truncated_snippets.append(snippet)
                used_chars += len(snippet)
            else:
                # Try to fit a truncated version of this snippet
                remaining_in_budget = block_char_budget - used_chars
                if remaining_in_budget > 100:  # Only if we have meaningful space left
                    truncated_snippet = snippet[:remaining_in_budget-3] + "..."
                    truncated_snippets.append(truncated_snippet)
                break
        
        if truncated_snippets:  # Only include blocks with content
            truncated_blocks.append(ContextBlock(
                document_id=block.document_id,
                title=block.title,
                snippets=truncated_snippets
            ))
    
    # Rebuild context text
    context_parts = []
    for block in truncated_blocks:
        context_parts.append(f"{{{block.title}}}")
        for snippet in block.snippets:
            context_parts.append(snippet)
        context_parts.append("")  # Empty line between documents
    
    truncated_context_text = "\n".join(context_parts).strip()
    
    logger.info(f"Context truncated: {len(truncated_context_text)} chars, {len(truncated_blocks)} docs")
    
    return ContextBundle(
        query=context.query,
        context_text=truncated_context_text,
        blocks=truncated_blocks
    )


def truncate_contexts_list(contexts: List[ContextBundle], config: SmartRoutingConfig) -> List[ContextBundle]:
    """
    Truncate a list of contexts to fit within overall token budget
    
    Args:
        contexts: List of context bundles
        config: Smart routing configuration
        
    Returns:
        List of truncated contexts
    """
    if not contexts:
        return contexts
    
    # Calculate total characters
    total_chars = sum(len(ctx.context_text) for ctx in contexts)
    
    if total_chars <= config.max_context_chars:
        return contexts
    
    logger.info(f"Truncating {len(contexts)} contexts: {total_chars} > {config.max_context_chars} chars")
    
    # Distribute character budget across contexts
    char_budget_per_context = config.max_context_chars // len(contexts)
    
    truncated_contexts = []
    for ctx in contexts:
        if len(ctx.context_text) <= char_budget_per_context:
            truncated_contexts.append(ctx)
        else:
            # Create a temporary config for this context
            temp_config = SmartRoutingConfig(
                router=config.router,
                escalation=config.escalation,
                max_context_chars=char_budget_per_context
            )
            truncated_ctx = truncate_context_by_tokens(ctx, temp_config)
            truncated_contexts.append(truncated_ctx)
    
    return truncated_contexts


def add_response_token_limit(system_prompt: str, config: SmartRoutingConfig) -> str:
    """
    Add token limit instruction to system prompt
    
    Args:
        system_prompt: Original system prompt
        config: Smart routing configuration
        
    Returns:
        Enhanced system prompt with token limits
    """
    token_instruction = f"""

RESPONSE LIMITS:
- Keep your response under {config.max_response_tokens} tokens (~{config.max_response_tokens * 4} characters)
- Be comprehensive but concise
- Prioritize the most important information if space is limited
- Use clear, efficient language"""

    return system_prompt + token_instruction


def validate_response_length(response: str, config: SmartRoutingConfig) -> str:
    """
    Validate and potentially truncate response if it exceeds limits
    Ensures response remains well-formed even when truncated
    
    Args:
        response: Generated response
        config: Smart routing configuration
        
    Returns:
        Response truncated if necessary, maintaining proper formatting
    """
    estimated_tokens = estimate_tokens(response)
    
    if estimated_tokens <= config.max_response_tokens:
        return response
    
    logger.warning(f"Response too long: {estimated_tokens} > {config.max_response_tokens} tokens, truncating")
    
    # Truncate to character limit with buffer for truncation message
    max_chars = config.max_response_tokens * 4 - 200  # Leave buffer for truncation message
    
    if len(response) > max_chars:
        truncated = response[:max_chars]
        
        # Smart truncation to maintain well-formed structure
        truncated = _smart_truncate(truncated)
        
        # Add truncation notice
        truncated += "\n\n[Response truncated due to length limits]"
        return truncated
    
    return response


def _smart_truncate(text: str) -> str:
    """
    Intelligently truncate text to maintain structure and readability
    
    Args:
        text: Text to truncate
        
    Returns:
        Truncated text that's well-formed
    """
    # Try to end at a sentence boundary
    if '.' in text:
        # Find the last complete sentence
        last_period = text.rfind('.')
        if last_period > len(text) * 0.8:  # Only if we don't lose too much content
            return text[:last_period + 1]
    
    # Try to end at a paragraph boundary
    if '\n\n' in text:
        last_paragraph = text.rfind('\n\n')
        if last_paragraph > len(text) * 0.8:  # Only if we don't lose too much content
            return text[:last_paragraph]
    
    # Try to end at a line boundary
    if '\n' in text:
        last_newline = text.rfind('\n')
        if last_newline > len(text) * 0.9:  # Only if we don't lose much content
            return text[:last_newline]
    
    # Fallback: end at last complete word
    last_space = text.rfind(' ')
    if last_space > len(text) * 0.9:
        return text[:last_space]
    
    # Final fallback: just truncate (shouldn't happen often)
    return text


def ensure_json_validity(json_str: str) -> str:
    """
    Ensure a JSON string is valid, fixing common truncation issues
    
    Args:
        json_str: Potentially truncated JSON string
        
    Returns:
        Valid JSON string
    """
    import json as json_module
    
    try:
        # Try to parse as-is
        json_module.loads(json_str)
        return json_str
    except json_module.JSONDecodeError:
        pass
    
    # Common fixes for truncated JSON
    fixed = json_str.strip()
    
    # Remove trailing commas
    fixed = fixed.rstrip(',').rstrip()
    
    # Try to close unclosed structures
    open_braces = fixed.count('{') - fixed.count('}')
    open_brackets = fixed.count('[') - fixed.count(']')
    open_quotes = fixed.count('"') % 2
    
    # Close unclosed quotes
    if open_quotes:
        fixed += '"'
    
    # Close unclosed arrays
    for _ in range(open_brackets):
        fixed += ']'
    
    # Close unclosed objects
    for _ in range(open_braces):
        fixed += '}'
    
    try:
        # Validate the fix
        json_module.loads(fixed)
        return fixed
    except json_module.JSONDecodeError:
        # If still invalid, return a minimal valid response
        return '{"error": "Response truncated and could not be repaired", "partial_content": "' + json_str.replace('"', '\\"')[:100] + '..."}'


def validate_json_response_length(response: str, config: SmartRoutingConfig) -> str:
    """
    Validate JSON response length and ensure JSON validity even when truncated
    
    Args:
        response: JSON response string
        config: Smart routing configuration
        
    Returns:
        Valid JSON response, truncated if necessary
    """
    estimated_tokens = estimate_tokens(response)
    
    if estimated_tokens <= config.max_response_tokens:
        return ensure_json_validity(response)
    
    logger.warning(f"JSON response too long: {estimated_tokens} > {config.max_response_tokens} tokens, truncating")
    
    # Truncate to character limit with buffer
    max_chars = config.max_response_tokens * 4 - 100  # Leave buffer for JSON repair
    
    if len(response) > max_chars:
        truncated = response[:max_chars]
        # Ensure valid JSON structure
        return ensure_json_validity(truncated)
    
    return ensure_json_validity(response)