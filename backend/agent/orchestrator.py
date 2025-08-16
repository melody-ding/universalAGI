"""
Lightweight Orchestration Layer - Routes between LIGHT and HEAVY agent paths

This module implements a routing system that decides whether to handle requests
with a lightweight one-shot response or escalate to the full ReAct agent.

Required environment variables:
- OPENAI_API_KEY: OpenAI API key for model access

Usage:
    from agent.orchestrator import handle_message
    
    response = handle_message("Hello, how are you?")
    print(response)
"""

import json
import os
from typing import Dict, Any
from openai import OpenAI


def route_message(user_text: str) -> Dict[str, Any]:
    """
    Run orchestrator prompt to determine routing strategy.
    
    Args:
        user_text: User's input message
        
    Returns:
        Dict containing routing decision and metadata
        
    Raises:
        ValueError: If JSON parsing fails or required fields are missing
    """
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    system_prompt = """You are a lightweight orchestrator that routes between simple responses and document-based answers.
- Output strict JSON only, no prose.
- LIGHT: Use for simple greetings, chitchat, basic definitions that don't require document lookup
- HEAVY: Use for ANY informational questions that could benefit from document search, including questions about specific topics, requests for explanations, summaries, analysis, or any detailed information
- Key distinction: "Hello" = LIGHT, "What is machine learning?" = HEAVY (could have documents), "Tell me about the contract terms" = HEAVY
- When in doubt between LIGHT/HEAVY for informational questions, choose HEAVY (document search is better than guessing)
- If LIGHT seems feasible, include a ≤2-sentence `light_draft`. Otherwise set it to "".
JSON schema:
{ "type":"object","properties":{
    "route":{"enum":["LIGHT","HEAVY"]},
    "intent":{"enum":["chitchat","faq","document_query","clarify"]},
    "confidence":{"type":"number","minimum":0,"maximum":1},
    "query":{"type":"string"},
    "light_draft":{"type":"string"},
    "why":{"type":"string"}
  },"required":["route","intent","confidence","query","light_draft","why"],
  "additionalProperties":false }"""
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text}
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        
        result = json.loads(response.choices[0].message.content)
        
        # Validate required fields
        required_fields = ["route", "intent", "confidence", "query", "light_draft", "why"]
        if not all(field in result for field in required_fields):
            raise ValueError(f"Missing required fields in orchestrator response: {result}")
            
        return result
        
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse orchestrator JSON response: {e}")
    except Exception as e:
        raise ValueError(f"Orchestrator API call failed: {e}")


def run_light_agent(user_text: str, intent: str, query: str, light_draft: str) -> str:
    """
    Run light one-shot prompt for simple responses.
    
    Args:
        user_text: Original user message
        intent: Classified intent from orchestrator
        query: Processed query from orchestrator
        light_draft: Pre-drafted response from orchestrator
        
    Returns:
        Brief response (≤2 sentences) or "ESCALATE" if uncertain
    """
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    system_prompt = "You are the LIGHT responder. Provide helpful informational responses without tools. For instructional requests (recipes, how-to guides, explanations), provide clear step-by-step information. Keep responses concise but complete. If you cannot provide a satisfactory answer, output exactly: ESCALATE."
    
    user_prompt = f"""Original message: "{user_text}"
Intent: {intent}
Query: {query}
Suggested draft: "{light_draft}"

Provide a brief, helpful response or output exactly "ESCALATE" if you're uncertain."""
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            max_tokens=500
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        return "ESCALATE"


def run_heavy_agent(user_text: str) -> str:
    """
    Placeholder that calls the heavy ReAct agent.
    
    Args:
        user_text: User's input message
        
    Returns:
        Response from the heavy ReAct agent
    """
    # Import here to avoid circular imports
    from .agent import ReActAgent
    import asyncio
    
    try:
        agent = ReActAgent()
        
        # Run the async method in a sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            response = loop.run_until_complete(agent.process_request(user_text))
            return response.content
        finally:
            loop.close()
            
    except Exception as e:
        return f"I encountered an error while processing your request: {str(e)}"


def handle_message(user_text: str) -> str:
    """
    Main entrypoint for message handling with routing and escalation.
    
    Args:
        user_text: User's input message
        
    Returns:
        Response from either light or heavy agent path
    """
    try:
        # Step 1: Get routing decision
        routing_result = route_message(user_text)
        
        # Step 2: Apply routing logic
        should_use_light = (
            routing_result["route"] == "LIGHT" and
            routing_result["intent"] in ["chitchat", "faq"] and
            routing_result["confidence"] >= 0.65
        )
        
        # Always route document queries to heavy agent
        if routing_result["intent"] == "document_query":
            should_use_light = False
        
        if should_use_light:
            # Step 3a: Try light path
            light_response = run_light_agent(
                user_text,
                routing_result["intent"],
                routing_result["query"],
                routing_result["light_draft"]
            )
            
            # Step 3b: Handle escalation
            if light_response == "ESCALATE":
                return run_heavy_agent(user_text)
            else:
                return light_response
        else:
            # Step 3c: Use heavy path directly
            return run_heavy_agent(user_text)
            
    except Exception as e:
        # Fallback to heavy agent on any orchestration errors
        return run_heavy_agent(user_text)