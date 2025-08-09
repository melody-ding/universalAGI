"""
Planner Module - Responsible for generating multi-step plans for user queries
"""

import json
import re
from typing import Dict, List, Any, Optional
from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage
from config import settings


class PlanStep:
    """Represents a single step in an execution plan"""
    
    def __init__(self, action: str, reasoning: str, tool_needed: Optional[str] = None):
        self.action = action
        self.reasoning = reasoning
        self.tool_needed = tool_needed
        self.status = "pending"  # pending, executing, completed, failed
        self.result = None
        self.observations = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "reasoning": self.reasoning,
            "tool_needed": self.tool_needed,
            "status": self.status,
            "result": self.result,
            "observations": self.observations
        }
    
    def __repr__(self) -> str:
        return f"PlanStep(action='{self.action[:50]}...', status='{self.status}')"


class ExecutionPlan:
    """Represents a complete execution plan with multiple steps"""
    
    def __init__(self, objective: str, steps: List[PlanStep], context: Dict[str, Any] = None):
        self.objective = objective
        self.steps = steps
        self.context = context or {}
        self.status = "created"  # created, executing, completed, failed, needs_replanning
        self.current_step_index = 0

    def get_current_step(self) -> Optional[PlanStep]:
        """Get the current step to execute"""
        if self.current_step_index < len(self.steps):
            return self.steps[self.current_step_index]
        return None

    def advance_step(self):
        """Move to the next step"""
        self.current_step_index += 1

    def is_complete(self) -> bool:
        """Check if all steps have been executed"""
        return self.current_step_index >= len(self.steps)

    def get_progress(self) -> Dict[str, Any]:
        """Get progress statistics"""
        completed = sum(1 for step in self.steps if step.status == "completed")
        failed = sum(1 for step in self.steps if step.status == "failed")
        return {
            "total_steps": len(self.steps),
            "completed": completed,
            "failed": failed,
            "current_index": self.current_step_index,
            "progress_percent": (completed / len(self.steps)) * 100 if self.steps else 0
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "objective": self.objective,
            "steps": [step.to_dict() for step in self.steps],
            "context": self.context,
            "status": self.status,
            "current_step_index": self.current_step_index,
            "progress": self.get_progress()
        }
    
    def __repr__(self) -> str:
        return f"ExecutionPlan(objective='{self.objective[:50]}...', steps={len(self.steps)}, status='{self.status}')"


class Planner:
    """Strategic planner that creates execution plans for user requests"""
    
    def __init__(self, model_name: str = None, temperature: float = 0.1):
        self.llm = ChatOpenAI(
            model=model_name or settings.MODEL_NAME,
            temperature=temperature,  # Lower temperature for more consistent planning
            openai_api_key=settings.OPENAI_API_KEY
        )

    async def create_plan(self, user_message: str, has_image: bool = False, context: Dict[str, Any] = None) -> ExecutionPlan:
        """
        Generate a comprehensive plan for the user's request
        
        Args:
            user_message: The user's input message
            has_image: Whether an image was uploaded
            context: Additional context for planning
            
        Returns:
            ExecutionPlan: A complete execution plan
        """
        planning_prompt = self._build_planning_prompt(user_message, has_image, context)
        
        messages = [
            SystemMessage(content=self._get_planner_system_prompt()),
            HumanMessage(content=planning_prompt)
        ]

        try:
            response = self.llm.invoke(messages)
            plan_data = self._parse_plan_response(response.content)
            
            # Convert to ExecutionPlan object
            steps = [
                PlanStep(
                    action=step.get("action", ""),
                    reasoning=step.get("reasoning", ""),
                    tool_needed=step.get("tool_needed")
                )
                for step in plan_data.get("steps", [])
            ]
            
            return ExecutionPlan(
                objective=plan_data.get("objective", "Process user request"),
                steps=steps,
                context=context or {}
            )

        except Exception as e:
            # Fallback plan if LLM fails
            return self._create_fallback_plan(user_message, has_image)

    async def replan(self, current_plan: ExecutionPlan, execution_results: List[Dict], user_feedback: str = None) -> ExecutionPlan:
        """
        Re-plan based on execution results and potential user feedback
        
        Args:
            current_plan: The current execution plan
            execution_results: Results from previous execution attempts
            user_feedback: Optional user feedback for replanning
            
        Returns:
            ExecutionPlan: Updated plan with additional steps
        """
        replanning_prompt = self._build_replanning_prompt(current_plan, execution_results, user_feedback)
        
        messages = [
            SystemMessage(content=self._get_replanner_system_prompt()),
            HumanMessage(content=replanning_prompt)
        ]

        try:
            response = self.llm.invoke(messages)
            plan_data = self._parse_plan_response(response.content)
            
            # Create new plan with updated steps
            new_steps = [
                PlanStep(
                    action=step.get("action", ""),
                    reasoning=step.get("reasoning", ""),
                    tool_needed=step.get("tool_needed")
                )
                for step in plan_data.get("steps", [])
            ]
            
            # Update the existing plan
            current_plan.steps.extend(new_steps)
            current_plan.status = "executing"
            
            return current_plan

        except Exception as e:
            # If replanning fails, mark current plan as needing human intervention
            current_plan.status = "needs_replanning"
            return current_plan

    def _get_planner_system_prompt(self) -> str:
        """System prompt for the planning LLM"""
        return """You are an expert planning agent. Your job is to analyze user requests and create detailed, executable plans.

For each plan, you should:
1. Understand the user's core objective
2. Break down the task into logical, sequential steps
3. For each step, specify what action to take and why
4. Identify if any tools or resources are needed
5. Consider potential challenges and how to address them

Output your plan as a JSON object with this structure:
{
    "objective": "Clear description of what needs to be accomplished",
    "complexity": "low|medium|high",
    "steps": [
        {
            "action": "Specific action to take",
            "reasoning": "Why this step is necessary",
            "tool_needed": "Name of tool if required (optional)",
            "expected_outcome": "What should result from this step"
        }
    ]
}

Make your plans specific, actionable, and well-reasoned. Each step should build logically on the previous ones."""

    def _get_replanner_system_prompt(self) -> str:
        """System prompt for replanning"""
        return """You are a replanning agent. Based on the execution results of a previous plan, you need to determine what additional steps are needed to complete the user's objective.

Analyze:
1. What was accomplished successfully
2. What failed or was incomplete
3. What new information was discovered
4. What the user actually needs now

Create additional steps to complete the objective, or modify the approach based on new findings."""

    def _build_planning_prompt(self, user_message: str, has_image: bool, context: Dict[str, Any]) -> str:
        """Build the planning prompt"""
        prompt = f"""Please create a detailed plan for this user request:

USER REQUEST: "{user_message}"
HAS IMAGE: {has_image}
"""
        
        if context:
            prompt += f"ADDITIONAL CONTEXT: {json.dumps(context, indent=2)}\n"
        
        prompt += """
Analyze the request carefully and create a step-by-step plan. Consider:
- What is the user really asking for?
- What information or resources might be needed?
- What are the logical steps to accomplish this?
- What could go wrong and how to handle it?

Create a comprehensive plan that will lead to a successful outcome."""

        return prompt

    def _build_replanning_prompt(self, current_plan: ExecutionPlan, execution_results: List[Dict], user_feedback: str = None) -> str:
        """Build the replanning prompt"""
        prompt = f"""The previous plan execution has completed with the following results:

ORIGINAL OBJECTIVE: {current_plan.objective}

EXECUTION RESULTS:
"""
        for i, result in enumerate(execution_results):
            prompt += f"Step {i+1}: {result.get('status', 'unknown')} - {result.get('result', 'no result')}\n"

        if user_feedback:
            prompt += f"\nUSER FEEDBACK: {user_feedback}\n"

        prompt += """
Based on these results, determine what additional steps are needed to fully accomplish the objective. Create new steps that:
1. Build on what was already accomplished
2. Address any failures or incomplete results
3. Incorporate any new information discovered
4. Respond to user feedback if provided

Output only the additional steps needed as a JSON plan."""

        return prompt

    def _parse_plan_response(self, response_content: str) -> Dict[str, Any]:
        """Parse the LLM response to extract the plan JSON"""
        try:
            # Try to find JSON in the response
            json_match = re.search(r'\{.*\}', response_content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

        # If JSON parsing fails, try to extract key information manually
        lines = response_content.split('\n')
        objective = "Process user request"
        steps = []

        for line in lines:
            if 'objective' in line.lower():
                objective = line.split(':', 1)[1].strip().strip('"')
            elif line.strip().startswith(('-', '*', '1.', '2.', '3.')):
                # Extract step information
                step_text = line.strip().lstrip('-*123456789. ')
                steps.append({
                    "action": step_text,
                    "reasoning": "Extracted from plan description"
                })

        return {
            "objective": objective,
            "steps": steps
        }

    def _create_fallback_plan(self, user_message: str, has_image: bool) -> ExecutionPlan:
        """Create a basic fallback plan when LLM planning fails"""
        steps = [
            PlanStep(
                action="Analyze the user's request in detail",
                reasoning="Need to understand what they're asking for"
            ),
            PlanStep(
                action="Gather relevant information and context",
                reasoning="Collect necessary data to provide a complete response"
            )
        ]

        if has_image:
            steps.insert(1, PlanStep(
                action="Examine and analyze the uploaded image",
                reasoning="The image likely contains important context for the request"
            ))

        steps.append(PlanStep(
            action="Formulate comprehensive response",
            reasoning="Provide a complete and helpful answer to the user"
        ))

        return ExecutionPlan(
            objective="Understand and respond to user request",
            steps=steps
        )