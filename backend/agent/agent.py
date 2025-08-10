"""
Main Agent Module - ReAct Agent implementing Plan-and-Execute architecture
"""

import json
import asyncio
from typing import Dict, List, Any, Optional, AsyncGenerator, Union, Callable
from dataclasses import dataclass
from .planner import Planner, ExecutionPlan, PlanStep
from .executor import Executor, ExecutionResult
from .tools import Tool


@dataclass
class AgentResponse:
    """Represents a complete agent response"""
    content: str
    plan: ExecutionPlan
    execution_results: List[ExecutionResult]
    metadata: Dict[str, Any]
    success: bool = True
    error: Optional[str] = None


class StreamingEvent:
    """Represents a streaming event from the agent"""
    
    def __init__(self, event_type: str, content: str, data: Dict[str, Any] = None):
        self.type = event_type
        self.content = content
        self.data = data or {}
        self.timestamp = asyncio.get_event_loop().time()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "content": self.content,
            "timestamp": self.timestamp,
            **self.data
        }
    
    def to_sse_format(self) -> str:
        """Convert to Server-Sent Events format"""
        return f"data: {json.dumps(self.to_dict())}\n\n"


class ReActAgent:
    """
    Main ReAct Agent implementing Plan-and-Execute architecture
    
    This agent separates planning from execution, creating comprehensive plans
    and executing them step by step with real-time streaming capabilities.
    """
    
    def __init__(self, 
                 model_name: str = None,
                 planner_temperature: float = 0.1,
                 executor_temperature: float = None):
        """
        Initialize the ReAct Agent
        
        Args:
            model_name: LLM model to use
            planner_temperature: Temperature for planning (lower = more consistent)
            executor_temperature: Temperature for execution (higher = more creative)
        """
        self.planner = Planner(model_name, planner_temperature)
        self.executor = Executor(model_name, executor_temperature)
        self.session_history = []
        
    async def process_request(self, 
                            user_message: str, 
                            context: Dict[str, Any] = None,
                            has_image: bool = False) -> AgentResponse:
        """
        Process a user request through the complete Plan-and-Execute cycle
        
        Args:
            user_message: The user's input message
            context: Additional context for processing
            has_image: Whether an image was uploaded
            
        Returns:
            AgentResponse: Complete response with plan, results, and final content
        """
        try:
            # Phase 1: Planning
            plan = await self.planner.create_plan(user_message, has_image, context)
            
            # Phase 2: Execution
            execution_results = await self.executor.execute_plan(plan)
            
            # Phase 3: Response Generation
            final_content = await self._generate_final_response(
                user_message, plan, execution_results, context
            )
            
            # Store in session history
            self.session_history.append({
                "user_message": user_message,
                "plan": plan.to_dict(),
                "results": [r.to_dict() for r in execution_results],
                "response": final_content
            })
            
            return AgentResponse(
                content=final_content,
                plan=plan,
                execution_results=execution_results,
                metadata={
                    "total_steps": len(plan.steps),
                    "successful_steps": sum(1 for r in execution_results if r.success),
                    "execution_time": sum(r.execution_time for r in execution_results),
                    "plan_status": plan.status
                }
            )
            
        except Exception as e:
            return AgentResponse(
                content=f"I encountered an error while processing your request: {str(e)}",
                plan=None,
                execution_results=[],
                metadata={},
                success=False,
                error=str(e)
            )
    
    async def stream_request(self, 
                           user_message: str,
                           context: Dict[str, Any] = None,
                           has_image: bool = False) -> AsyncGenerator[StreamingEvent, None]:
        """
        Process a user request with real-time streaming
        
        Args:
            user_message: The user's input message
            context: Additional context for processing
            has_image: Whether an image was uploaded
            
        Yields:
            StreamingEvent: Real-time events during processing
        """
        try:
            step_counter = 0
            
            def next_step():
                nonlocal step_counter
                step_counter += 1
                return step_counter
            
            # Phase 1: Planning (internal, no UI output)
            plan = await self.planner.create_plan(user_message, has_image, context)
            
            execution_results = []
            
            for i, step in enumerate(plan.steps):
                yield StreamingEvent(
                    "thinking_step",
                    step.action,
                    {"step": next_step(), "total_steps": len(plan.steps)}
                )
                
                try:
                    result = await self.executor.execute_step(step, context or {})
                    execution_results.append(result)
                    
                except Exception as e:
                    yield StreamingEvent(
                        "thinking_step",
                        f"⚠ ERROR: {str(e)[:100]}...",
                        {"step": next_step(), "total_steps": len(plan.steps)}
                    )
            
            # Phase 3: Completion
            success_count = sum(1 for result in execution_results if result.success)
            total_steps = len(execution_results)
            
            yield StreamingEvent(
                "thinking_complete",
                f"✅ COMPLETE: Executed {success_count}/{total_steps} steps successfully.",
                {
                    "execution_summary": {
                        "total_steps": total_steps,
                        "successful_steps": success_count,
                        "plan_status": plan.status
                    }
                }
            )
            
            # Phase 4: Final Response Generation
            yield StreamingEvent(
                "response_start",
                "Generating response...",
                {}
            )
            
            final_content = await self._generate_final_response(
                user_message, plan, execution_results, context
            )
            
            # Stream the final response (could be enhanced to stream token by token)
            yield StreamingEvent(
                "response_complete",
                final_content,
                {"response": final_content}
            )
            
            yield StreamingEvent(
                "stream_end",
                "Response complete",
                {}
            )
            
        except Exception as e:
            yield StreamingEvent(
                "error",
                f"An error occurred: {str(e)}",
                {"error": str(e)}
            )
    
    async def _generate_final_response(self, 
                                     user_message: str,
                                     plan: ExecutionPlan,
                                     execution_results: List[ExecutionResult],
                                     context: Dict[str, Any] = None) -> str:
        """
        Generate the final response based on plan execution results
        
        Args:
            user_message: Original user message
            plan: Execution plan that was used
            execution_results: Results from executing the plan
            context: Additional context
            
        Returns:
            Final response content
        """
        from langchain_openai import ChatOpenAI
        from langchain.schema import SystemMessage, HumanMessage
        from config import settings
        
        # Use a separate LLM instance for final response generation
        response_llm = ChatOpenAI(
            model=settings.MODEL_NAME,
            temperature=settings.MODEL_TEMPERATURE,
            openai_api_key=settings.OPENAI_API_KEY
        )
        
        # Build context from execution results
        execution_summary = ""
        for i, result in enumerate(execution_results):
            status = "✓" if result.success else "✗"
            execution_summary += f"{status} Step {i+1}: {result.step.action}\n"
            if result.observations:
                execution_summary += f"  Result: {result.observations[0]}\n"
            if result.error:
                execution_summary += f"  Error: {result.error}\n"
            execution_summary += "\n"
        
        system_prompt = """You are an expert reasoning assistant. You have just completed detailed internal reasoning about the user's request and executed a comprehensive plan. 

Now provide your final, well-reasoned response that addresses their question comprehensively based on your analysis and execution results. Be clear, helpful, and direct.

Do not mention the internal planning or execution process - just provide the final answer as if you reasoned through it naturally."""
        
        user_prompt = f"""User's original request: "{user_message}"

Plan objective: {plan.objective}

Execution results summary:
{execution_summary}

Based on this thorough analysis and execution, provide a comprehensive response to the user's request."""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        try:
            response = response_llm.invoke(messages)
            return response.content
        except Exception as e:
            return f"I've analyzed your request thoroughly, but encountered an issue generating the final response: {str(e)}"
    
    def add_tool(self, name: str, tool: Tool):
        """Add a custom tool to the executor"""
        self.executor.add_tool(name, tool)
    
    def remove_tool(self, name: str):
        """Remove a tool from the executor"""
        self.executor.remove_tool(name)
    
    def list_tools(self) -> List[str]:
        """List available tools"""
        return self.executor.list_tools()
    
    def get_session_history(self) -> List[Dict[str, Any]]:
        """Get the session history"""
        return self.session_history
    
    def clear_session(self):
        """Clear the session history"""
        self.session_history = []