"""
Streaming Smart Orchestrator - Real-time progress streaming for UI
"""

import logging
import json
from typing import AsyncGenerator, Optional, Dict, Any

from .smart_routing_config import SmartRoutingConfig, DEFAULT_CONFIG
from .smart_probe import compute_probe_signals, compute_routing_score, ProbeSignals
from .short_path import run_short_path, ShortPathResult
from .long_path import run_long_path, LongPathResult
from .token_manager import validate_response_length, validate_json_response_length

logger = logging.getLogger(__name__)


async def stream_smart_orchestration(
    query: str, 
    config: Optional[SmartRoutingConfig] = None,
    document_id: Optional[int] = None,
    file_context: Optional[Dict[str, Any]] = None
) -> AsyncGenerator[str, None]:
    """
    Stream smart orchestrated message handling with real-time progress
    
    Args:
        query: User query string
        config: Smart routing configuration (uses default if None)
        document_id: Optional specific document to search
        file_context: Optional file context for document analysis
        
    Yields:
        SSE formatted progress events
    """
    config = config or DEFAULT_CONFIG
    
    try:
        logger.info(f"Streaming smart orchestrator processing: {query[:100]}...")
        
        # Check for document analysis intent first
        if file_context:
            from .file_context import document_analysis_detector
            
            should_analyze = document_analysis_detector.should_analyze_document(query, file_context)
            if should_analyze:
                logger.info("Document analysis intent detected, routing to analysis workflow")
                async for event in _stream_document_analysis(query, file_context):
                    yield event
                return
        
        # If document_id is provided, go directly to map-reduce
        if document_id:
            logger.info(f"Document ID provided ({document_id}), using direct map-reduce analysis")
            
            # Step 1: Start analysis
            yield f"data: {json.dumps({'type': 'thinking_step', 'content': 'Analyzing document...', 'step': 1})}\n\n"
            logger.info("Yielded step 1: Analyzing document...")
            
            from search.single_document_search import map_reduce_single_document
            
            # Execute map-reduce directly
            logger.info("Starting map-reduce execution...")
            single_doc_context = await map_reduce_single_document(query, document_id)
            logger.info("Map-reduce execution completed")
            
            # Step 2: Synthesis
            yield f"data: {json.dumps({'type': 'thinking_step', 'content': 'Synthesizing findings...', 'step': 2})}\n\n"
            logger.info("Yielded step 2: Synthesizing findings...")
            
            # Return the map-reduce result directly
            yield f"data: {json.dumps({'type': 'thinking_complete', 'content': 'Document analysis complete', 'execution_summary': {'path': 'MAP-REDUCE'}})}\n\n"
            
            response_data = {'type': 'response_complete', 'content': single_doc_context.context_text}
            response_event = json.dumps(response_data)
            yield f"data: {response_event}\n\n"
            
            logger.info("FINAL ROUTE: MAP-REDUCE (completed)")
            return
        
        # Step 1: Probe analysis for regular chat
        yield f"data: {json.dumps({'type': 'thinking_step', 'content': 'Analyzing question...', 'step': 1})}\n\n"
        
        signals = compute_probe_signals(query, config)
        
        
        score = compute_routing_score(signals, config)
        
        # Step 2: Route decision
        if score >= config.router.threshold:
            path = "SHORT"
            
            logger.info(f"ROUTE DECISION: SHORT path selected")
            logger.info(f"   Score: {score:.3f} >= threshold {config.router.threshold}")
            logger.info(f"   Signals: vec_sim={signals.avg_vec_sim:.2f}, fts_rate={signals.fts_hit_rate:.2f}, docs={signals.unique_docs}")
            
            # Execute SHORT path with progress streaming
            
            # Stream the SHORT path execution with more granular steps
            async for step_event in _stream_short_path_execution(query, config, document_id):
                yield step_event
            
            # Get the final result
            short_result = await run_short_path(query, config, document_id)
            
            # Check for escalation
            if _should_escalate_from_short(short_result, signals, config):
                logger.info("ESCALATION: SHORT->LONG triggered")
                
                # Stream LONG path execution
                async for event in _stream_long_path_execution(query, signals, config, document_id):
                    yield event
                    
                logger.info("FINAL ROUTE: SHORT->LONG (escalated)")
                return
            else:
                yield f"data: {json.dumps({'type': 'thinking_step', 'content': 'Synthesizing answer...', 'step': 8})}\n\n"
                                
                # Ensure SHORT path response is also JSON-safe
                validated_answer = validate_response_length(short_result.answer, config)
                try:
                    response_data = {'type': 'response_complete', 'content': validated_answer}
                    response_event = json.dumps(response_data)
                    response_event = validate_json_response_length(response_event, config)
                    yield f"data: {response_event}\n\n"
                except (UnicodeDecodeError, ValueError) as e:
                    logger.error(f"JSON encoding error for SHORT response: {e}")
                    safe_content = validated_answer.encode('utf-8', errors='replace').decode('utf-8')
                    response_event = json.dumps({'type': 'response_complete', 'content': safe_content})
                    yield f"data: {response_event}\n\n"
                
                logger.info("FINAL ROUTE: SHORT (completed)")
                return
                
        else:
            path = "LONG"
            yield f"data: {json.dumps({'type': 'thinking_step', 'content': 'Using comprehensive search approach...', 'step': 3})}\n\n"
            
            logger.info(f"ROUTE DECISION: LONG path selected")
            logger.info(f"   Score: {score:.3f} < threshold {config.router.threshold}")
            logger.info(f"   Signals: vec_sim={signals.avg_vec_sim:.2f}, fts_rate={signals.fts_hit_rate:.2f}, docs={signals.unique_docs}")
            
            # Stream LONG path execution
            async for event in _stream_long_path_execution(query, signals, config):
                yield event
                
            logger.info("FINAL ROUTE: LONG (completed)")
            return
            
    except Exception as e:
        logger.error(f"Streaming smart orchestrator failed: {e}")
        yield f"data: {json.dumps({'type': 'error', 'content': f'Error in smart orchestration: {str(e)}'})}\n\n"


async def _stream_short_path_execution(query: str, config: SmartRoutingConfig, document_id: Optional[int] = None) -> AsyncGenerator[str, None]:
    """Stream SHORT path execution with granular progress"""
    
    try:
        # Import here to avoid circular imports
        from .short_path import build_context_short_path
        
        
        # Show what we're doing based on whether we have a document_id
        search_desc = f"Searching for: {query[:60]}..."
        yield f"data: {json.dumps({'type': 'thinking_step', 'content': search_desc, 'step': 2})}\n\n"
        
        # Build context (this is where the RAG tool logging happens)
        context = await build_context_short_path(query, config, document_id)
        
        # Report search results
        docs_found = len(context.blocks)
        segments_found = sum(len(block.snippets) for block in context.blocks)
        
    except Exception as e:
        logger.error(f"Error in SHORT path streaming: {e}")
        yield f"data: {json.dumps({'type': 'thinking_step', 'content': f'Search error: {str(e)}', 'step': 5})}\n\n"


async def _stream_long_path_execution(query: str, signals: ProbeSignals, config: SmartRoutingConfig, document_id: Optional[int] = None) -> AsyncGenerator[str, None]:
    """Stream LONG path execution with detailed progress"""
    
    try:
        logger.info("Starting LONG path execution streaming...")
        
        yield f"data: {json.dumps({'type': 'thinking_step', 'content': 'Planning comprehensive search...', 'step': 4})}\n\n"
        
        # Import here to avoid circular imports
        from .long_path import generate_subqueries, execute_subquery, synthesize_comprehensive_answer, EvidenceBundle
        import time
        
        start_time = time.time()
        
        # Generate subqueries
        logger.info("Generating subqueries...")
        subqueries = await generate_subqueries(query, signals, config)
        logger.info(f"Generated {len(subqueries)} subqueries")
        
        step_counter = 5
        
        yield f"data: {json.dumps({'type': 'thinking_step', 'content': f'Breaking down into {len(subqueries)} focused searches...', 'step': step_counter})}\n\n"
        step_counter += 1
        
        # Execute subqueries with progress
        contexts = []
        executed_subqueries = []
        
        for i, subquery in enumerate(subqueries):
            logger.info(f"Executing subquery {i+1}/{len(subqueries)}: {subquery.query[:50]}...")
            
            yield f"data: {json.dumps({'type': 'thinking_step', 'content': f'Search {i+1}/{len(subqueries)}: {subquery.query[:50]}...', 'step': step_counter})}\n\n"
            step_counter += 1
            
            # Check early exit before each subquery (except first)
            if i > 0:
                evidence = EvidenceBundle(
                    contexts=contexts,
                    total_docs=len(set(block.document_id for ctx in contexts for block in ctx.blocks)),
                    total_segments=sum(sum(len(block.snippets) for block in ctx.blocks) for ctx in contexts),
                    avg_vec_sim=signals.avg_vec_sim,
                    fts_hit_rate=signals.fts_hit_rate,
                    execution_time=time.time() - start_time
                )
                
                from .long_path import _should_early_exit
                early_exit_reason = _should_early_exit(evidence, config, start_time)
                if early_exit_reason:
                    logger.info(f"Early exit triggered: {early_exit_reason}")
                    yield f"data: {json.dumps({'type': 'thinking_step', 'content': 'Found sufficient information', 'step': step_counter})}\n\n"
                    break
            
            # Execute subquery with streaming
            if document_id:
                yield f"data: {json.dumps({'type': 'thinking_step', 'content': f'Analyzing document sections for: {subquery.query[:60]}...', 'step': step_counter})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'thinking_step', 'content': f'Searching for: {subquery.query[:60]}...', 'step': step_counter})}\n\n"
            step_counter += 1
            
            context = await execute_subquery(subquery, config, document_id)
            contexts.append(context)
            executed_subqueries.append(subquery)
            
            # Stream search results
            logger.info(f"Subquery {i+1} completed: {len(context.blocks)} docs")
            
            step_counter += 1
        
        # Final synthesis
        logger.info("Starting final synthesis...")
        yield f"data: {json.dumps({'type': 'thinking_step', 'content': 'Analyzing and synthesizing results...', 'step': step_counter})}\n\n"
        
        final_evidence = EvidenceBundle(
            contexts=contexts,
            total_docs=len(set(block.document_id for ctx in contexts for block in ctx.blocks)),
            total_segments=sum(sum(len(block.snippets) for block in ctx.blocks) for ctx in contexts),
            avg_vec_sim=signals.avg_vec_sim,
            fts_hit_rate=signals.fts_hit_rate,
            execution_time=time.time() - start_time
        )
        
        logger.info(f"Final evidence: {final_evidence.total_docs} docs, {final_evidence.total_segments} segments")
        
        answer = await synthesize_comprehensive_answer(query, final_evidence, config)
        logger.info("Synthesis completed")
        
        yield f"data: {json.dumps({'type': 'thinking_complete', 'content': 'Detailed analysis complete', 'execution_summary': {'path': 'LONG', 'subqueries': len(executed_subqueries), 'docs': final_evidence.total_docs, 'segments': final_evidence.total_segments}})}\n\n"
        
        # Ensure response content doesn't break JSON structure
        validated_answer = validate_response_length(answer, config)
        
        # Escape any problematic characters in the response for JSON
        try:
            response_data = {'type': 'response_complete', 'content': validated_answer}
            response_event = json.dumps(response_data)
            response_event = validate_json_response_length(response_event, config)
            yield f"data: {response_event}\n\n"
        except (UnicodeDecodeError, ValueError) as e:
            logger.error(f"JSON encoding error for response: {e}")
            # Fallback to safe response
            safe_content = validated_answer.encode('utf-8', errors='replace').decode('utf-8')
            response_event = json.dumps({'type': 'response_complete', 'content': safe_content})
            yield f"data: {response_event}\n\n"
        
    except Exception as e:
        logger.error(f"Error in LONG path streaming: {e}", exc_info=True)
        yield f"data: {json.dumps({'type': 'error', 'content': f'Error in LONG path execution: {str(e)}'})}\n\n"


def _should_escalate_from_short(
    short_result: ShortPathResult, 
    signals: ProbeSignals, 
    config: SmartRoutingConfig
) -> bool:
    """Determine if SHORT path result should escalate to LONG path"""
    if not short_result.success or not short_result.context:
        return True
    
    debug_info = short_result.debug_info
    escalation = config.escalation
    
    # Check escalation conditions
    reasons = []
    
    if debug_info.get("total_segments", 0) < escalation.min_strong_segments:
        reasons.append(f"insufficient segments ({debug_info.get('total_segments', 0)} < {escalation.min_strong_segments})")
    
    if debug_info.get("total_docs", 0) > escalation.max_distinct_docs:
        reasons.append(f"too many docs ({debug_info.get('total_docs', 0)} > {escalation.max_distinct_docs})")
    
    if signals.avg_vec_sim < escalation.min_avg_vec_sim:
        reasons.append(f"low vector similarity ({signals.avg_vec_sim:.2f} < {escalation.min_avg_vec_sim})")
    
    if signals.fts_hit_rate < escalation.min_fts_hit_rate:
        reasons.append(f"low FTS hit rate ({signals.fts_hit_rate:.2f} < {escalation.min_fts_hit_rate})")
    
    # Check for conflicts
    context_text = short_result.context.context_text.lower()
    conflict_indicators = ["however", "but", "although", "contradicts", "differs", "opposed"]
    has_conflicts = sum(1 for indicator in conflict_indicators if indicator in context_text) >= 2
    
    if has_conflicts:
        reasons.append("potential conflicts detected")
    
    should_escalate = len(reasons) > 0
    
    if should_escalate:
        logger.info(f"Escalating SHORT->LONG: {', '.join(reasons)}")
    
    return should_escalate


async def _stream_document_analysis(query: str, file_context: Dict[str, Any]) -> AsyncGenerator[str, None]:
    """Stream document analysis workflow with progress updates."""
    try:
        logger.info(f"Starting document analysis for: {file_context.get('filename', 'unknown file')}")
        
        # Step 1: Initialize analysis
        yield f"data: {json.dumps({'type': 'thinking_step', 'content': 'Preparing document analysis...', 'step': 1})}\n\n"
        
        # Import analysis tool
        from .document_analysis_tool import DocumentAnalysisTool
        
        # Step 2: Parse document
        filename = file_context.get('filename', 'document')
        yield f"data: {json.dumps({'type': 'thinking_step', 'content': f'Parsing document: {filename}...', 'step': 2})}\n\n"
        
        # Step 3: Find frameworks
        yield f"data: {json.dumps({'type': 'thinking_step', 'content': 'Finding relevant compliance frameworks...', 'step': 3})}\n\n"
        
        # Step 4: Run analysis
        yield f"data: {json.dumps({'type': 'thinking_step', 'content': 'Running compliance analysis...', 'step': 4})}\n\n"
        
        # Execute analysis
        analysis_tool = DocumentAnalysisTool()
        analysis_parameters = {
            'file_content': file_context.get('file_content'),
            'filename': file_context.get('filename', 'document'),
            'file_text': file_context.get('file_text'),
            'framework_ids': file_context.get('framework_ids')
        }
        
        result = await analysis_tool.execute(analysis_parameters)
        
        # Step 5: Complete
        yield f"data: {json.dumps({'type': 'thinking_complete', 'content': 'Document analysis complete', 'execution_summary': {'path': 'DOCUMENT_ANALYSIS', 'filename': file_context.get('filename')}})}\n\n"
        
        # Return formatted result
        yield f"data: {json.dumps({'type': 'response_complete', 'content': result})}\n\n"
        
        logger.info("Document analysis completed successfully")
        
    except Exception as e:
        logger.error(f"Document analysis failed: {str(e)}")
        error_message = f"Document analysis failed: {str(e)}"
        yield f"data: {json.dumps({'type': 'error', 'content': error_message})}\n\n"