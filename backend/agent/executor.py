"""
Executor Module - Responsible for executing individual steps of a plan
"""

import asyncio
import time
from typing import Dict, Any, Optional, List
from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage
from config import settings
from .planner import ExecutionPlan, PlanStep
from .tools import Tool
from .rag_tool import RAGTool
from utils.logging_config import get_logger, log_external_service_call
from utils.retry import retry_external_service
from utils.exceptions import ExternalServiceError, ProcessingError, create_external_service_error


class ExecutionResult:
    """Represents the result of executing a single step"""
    
    def __init__(self, step: PlanStep, success: bool, result: Any = None, observations: List[str] = None, error: str = None):
        self.step = step
        self.success = success
        self.result = result
        self.observations = observations or []
        self.error = error
        self.execution_time = 0
        self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step": self.step.to_dict(),
            "success": self.success,
            "result": self.result,
            "observations": self.observations,
            "error": self.error,
            "execution_time": self.execution_time,
            "timestamp": self.timestamp
        }
    
    def __repr__(self) -> str:
        status = "SUCCESS" if self.success else "FAILED"
        return f"ExecutionResult({status}, time={self.execution_time:.2f}s)"


class Executor:
    """Executes individual steps of execution plans using available tools"""
    
    def __init__(self, model_name: str = None, temperature: float = None):
        self.llm = ChatOpenAI(
            model=model_name or settings.MODEL_NAME,
            temperature=temperature or settings.MODEL_TEMPERATURE,
            openai_api_key=settings.OPENAI_API_KEY
        )
        self.tools = self._initialize_tools()

    def _initialize_tools(self) -> Dict[str, Tool]:
        """Initialize available tools for RAG-only execution"""
        return {
            "search_documents": RAGTool()
        }

    async def execute_plan(self, plan: ExecutionPlan, progress_callback: Optional[callable] = None) -> List[ExecutionResult]:
        """
        Execute a complete plan step by step
        
        Args:
            plan: The execution plan to execute
            progress_callback: Optional callback for progress updates
            
        Returns:
            List of execution results for each step
        """
        results = []
        plan.status = "executing"

        if progress_callback:
            await progress_callback({
                "type": "execution_start",
                "content": f"Starting execution of plan: {plan.objective}",
                "plan": plan.to_dict()
            })

        while not plan.is_complete():
            current_step = plan.get_current_step()
            if not current_step:
                break

            # Execute the current step
            result = await self.execute_step(current_step, plan.context, progress_callback)
            results.append(result)

            # Update step status
            current_step.status = "completed" if result.success else "failed"
            current_step.result = result.result
            current_step.observations = result.observations

            # Move to next step
            plan.advance_step()

            # Check if we need to stop due to critical failure
            if not result.success and self._is_critical_failure(result):
                plan.status = "failed"
                break

        # Mark plan as completed if all steps succeeded
        if plan.is_complete() and all(r.success for r in results):
            plan.status = "completed"
        elif not all(r.success for r in results):
            plan.status = "partial_failure"

        if progress_callback:
            await progress_callback({
                "type": "execution_complete",
                "content": f"Plan execution {plan.status}",
                "results": [r.to_dict() for r in results]
            })

        return results

    async def execute_step(self, step: PlanStep, context: Dict[str, Any], progress_callback: Optional[callable] = None) -> ExecutionResult:
        """
        Execute a single step of the plan
        
        Args:
            step: The step to execute
            context: Execution context
            progress_callback: Optional callback for progress updates
            
        Returns:
            ExecutionResult: Result of the step execution
        """
        start_time = time.time()
        step.status = "executing"
        logger = get_logger(__name__)

        logger.info(
            "Executing plan step",
            extra_fields={
                "step_action": step.action[:100] + "..." if len(step.action) > 100 else step.action,
                "tool_needed": step.tool_needed,
                "context_keys": list(context.keys()) if context else []
            }
        )

        if progress_callback:
            await progress_callback({
                "type": "step_start",
                "content": f"EXECUTING: {step.action}",
                "step": step.to_dict()
            })

        try:
            # Determine execution method based on step requirements
            if step.tool_needed and step.tool_needed in self.tools:
                result = await self._execute_with_tool(step, context, progress_callback)
            else:
                result = await self._execute_with_llm(step, context, progress_callback)

            # Generate observations about the execution
            observations = await self._generate_observations(step, result, context)

            execution_result = ExecutionResult(
                step=step,
                success=True,
                result=result,
                observations=observations
            )

            logger.info(
                "Step executed successfully",
                extra_fields={
                    "step_action": step.action[:100] + "..." if len(step.action) > 100 else step.action,
                    "result_length": len(str(result)) if result else 0,
                    "observations_count": len(observations)
                }
            )

        except Exception as e:
            logger.error(
                f"Step execution failed: {str(e)}",
                extra_fields={
                    "step_action": step.action[:100] + "..." if len(step.action) > 100 else step.action,
                    "error_type": type(e).__name__
                },
                exc_info=True
            )
            
            execution_result = ExecutionResult(
                step=step,
                success=False,
                error=str(e),
                observations=[f"Execution failed: {str(e)}"]
            )

        execution_result.execution_time = time.time() - start_time

        if progress_callback:
            await progress_callback({
                "type": "step_complete",
                "content": f"RESULT: {execution_result.observations[0] if execution_result.observations else 'Step completed'}",
                "result": execution_result.to_dict()
            })

        return execution_result

    async def _execute_with_tool(self, step: PlanStep, context: Dict[str, Any], progress_callback: Optional[callable] = None) -> Any:
        """Execute step using a specific tool"""
        tool = self.tools[step.tool_needed]
        
        if progress_callback:
            await progress_callback({
                "type": "tool_execution",
                "content": f"Using tool: {tool.name}",
                "tool": tool.name
            })

        # Extract search query from the step action for RAG tool
        if step.tool_needed == "search_documents":
            # Extract query from action like "Search documents for information about X"
            query = step.action.replace("Search documents for", "").strip()
            if query.startswith("information about"):
                query = query.replace("information about", "").strip()
            if query.startswith(":"):
                query = query[1:].strip()
            
            return await tool.execute(query=query)
        
        # Fallback for other tools (though we only have RAG tool now)
        return await tool.execute(action=step.action, reasoning=step.reasoning, context=context)

    @retry_external_service("llm_execution")
    async def _execute_with_llm(self, step: PlanStep, context: Dict[str, Any], progress_callback: Optional[callable] = None) -> str:
        """Execute step using direct LLM interaction"""
        start_time = time.time()
        logger = get_logger(__name__)
        
        execution_prompt = self._build_execution_prompt(step, context)
        
        messages = [
            SystemMessage(content=self._get_executor_system_prompt()),
            HumanMessage(content=execution_prompt)
        ]

        if progress_callback:
            await progress_callback({
                "type": "llm_execution",
                "content": "Processing with language model...",
            })

        try:
            response = self.llm.invoke(messages)
            
            # Log successful LLM call
            duration = time.time() - start_time
            log_external_service_call(
                logger.bind(operation="llm_execution"),
                "OpenAI", "chat_completion", duration, True,
                model=settings.MODEL_NAME,
                prompt_length=len(execution_prompt),
                response_length=len(response.content)
            )
            
            return response.content
            
        except Exception as e:
            # Log failed LLM call
            duration = time.time() - start_time
            log_external_service_call(
                logger.bind(operation="llm_execution"),
                "OpenAI", "chat_completion", duration, False,
                model=settings.MODEL_NAME,
                prompt_length=len(execution_prompt)
            )
            
            # Raise appropriate error
            raise create_external_service_error("OpenAI", "chat_completion", e)

    async def _generate_observations(self, step: PlanStep, result: Any, context: Dict[str, Any]) -> List[str]:
        """Generate observations about the step execution"""
        observation_prompt = f"""
        Step executed: {step.action}
        Step reasoning: {step.reasoning}
        Execution result: {str(result)[:200]}...
        
        Generate 1-2 specific observations about what was accomplished in this step and what was learned.
        Focus on concrete outcomes and insights that would be useful for subsequent steps.
        """

        messages = [
            SystemMessage(content="You are analyzing execution results and generating insightful observations."),
            HumanMessage(content=observation_prompt)
        ]

        try:
            response = self.llm.invoke(messages)
            # Split into separate observations if multiple sentences
            observations = [obs.strip() for obs in response.content.split('.') if obs.strip()]
            return observations[:2]  # Limit to 2 observations
        except:
            return [f"Completed: {step.action}"]

    def _build_execution_prompt(self, step: PlanStep, context: Dict[str, Any]) -> str:
        """Build prompt for LLM execution of a step"""
        prompt = f"""Execute this specific step:

ACTION: {step.action}
REASONING: {step.reasoning}

"""
        
        # Include retrieved document context for synthesis steps
        if "synthesize" in step.action.lower() and context:
            prompt += "RETRIEVED INFORMATION:\n"
            for key, value in context.items():
                if "context" in key.lower() and isinstance(value, str):
                    prompt += f"{value}\n\n"
                else:
                    prompt += f"- {key}: {value}\n"
        elif context:
            prompt += "CONTEXT:\n"
            for key, value in context.items():
                prompt += f"- {key}: {value}\n"

        prompt += """
Execute this action and provide the result. 

For synthesis steps: Combine the retrieved information to provide a comprehensive answer to the user's question. Use specific details from the documents and cite sources where appropriate.

For other steps: Be specific and detailed in your response.
"""

        return prompt

    def _build_tool_prompt(self, step: PlanStep, context: Dict[str, Any]) -> str:
        """Build prompt for tool execution"""
        return f"""
        Execute: {step.action}
        
        Context: {context}
        Reasoning: {step.reasoning}
        
        Provide a detailed response for this specific action.
        """

    def _get_executor_system_prompt(self) -> str:
        """System prompt for the RAG-focused executor"""
        return """You are a RAG synthesis agent responsible for combining retrieved document information to answer user questions.

Your job is to:
1. Synthesize information from retrieved documents into comprehensive answers
2. Cite specific sources when referencing document content
3. Provide clear, well-structured responses based on the available information
4. Acknowledge limitations when documents don't contain sufficient information

When synthesizing information:
- Combine insights from multiple sources when available
- Maintain accuracy to the source documents
- Organize information logically
- Provide direct answers to the user's question based on the retrieved context"""

    def _is_critical_failure(self, result: ExecutionResult) -> bool:
        """Determine if a failure should stop the entire plan execution"""
        # For now, consider all failures as non-critical (continue execution)
        # This could be enhanced with more sophisticated logic based on step importance
        return False

    def add_tool(self, name: str, tool: Tool):
        """Add a custom tool to the executor"""
        self.tools[name] = tool

    def remove_tool(self, name: str):
        """Remove a tool from the executor"""
        if name in self.tools:
            del self.tools[name]

    def list_tools(self) -> List[str]:
        """List available tools"""
        return list(self.tools.keys())

    def get_tool(self, name: str) -> Optional[Tool]:
        """Get a specific tool by name"""
        return self.tools.get(name)