"""
Tools Module - Specialized tools for the executor to use
"""

from typing import Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage
from config import settings


class Tool:
    """Base class for tools that can be used by the executor"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    async def execute(self, parameters: Dict[str, Any]) -> Any:
        """Execute the tool with given parameters"""
        raise NotImplementedError("Subclasses must implement execute method")
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}')"


class LLMTool(Tool):
    """Tool that uses LLM for general subtasks"""
    
    def __init__(self, name: str, description: str, temperature: float = None):
        super().__init__(name, description)
        self.llm = ChatOpenAI(
            model=settings.MODEL_NAME,
            temperature=temperature or settings.MODEL_TEMPERATURE,
            openai_api_key=settings.OPENAI_API_KEY
        )

    async def execute(self, parameters: Dict[str, Any]) -> str:
        """Execute LLM-based task"""
        prompt = parameters.get("prompt", "")
        system_prompt = parameters.get("system_prompt", "You are a helpful assistant.")
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt)
        ]
        
        response = self.llm.invoke(messages)
        return response.content


class AnalysisTool(LLMTool):
    """Specialized tool for analysis tasks"""
    
    def __init__(self):
        super().__init__(
            name="analysis",
            description="Analyze content, data, or information to extract insights and understanding",
            temperature=0.1  # Lower temperature for consistent analysis
        )
    
    async def execute(self, parameters: Dict[str, Any]) -> str:
        """Execute analysis task"""
        content = parameters.get("content", "")
        analysis_type = parameters.get("analysis_type", "general")
        context = parameters.get("context", "")
        
        system_prompt = f"""You are an expert analyst specialized in {analysis_type} analysis. 
Your job is to carefully examine the provided content and extract meaningful insights, patterns, and conclusions.

Be thorough, objective, and provide specific observations backed by evidence from the content."""

        prompt = f"""Please analyze the following content:

CONTENT TO ANALYZE:
{content}

ANALYSIS CONTEXT: {context}
ANALYSIS TYPE: {analysis_type}

Provide a detailed analysis including:
1. Key observations
2. Important patterns or insights
3. Conclusions and implications
4. Any recommendations if applicable"""

        parameters["system_prompt"] = system_prompt
        parameters["prompt"] = prompt
        
        return await super().execute(parameters)


class GenerationTool(LLMTool):
    """Specialized tool for content generation tasks"""
    
    def __init__(self):
        super().__init__(
            name="generation",
            description="Generate content, text, or creative output based on requirements",
            temperature=0.7  # Higher temperature for creativity
        )
    
    async def execute(self, parameters: Dict[str, Any]) -> str:
        """Execute content generation task"""
        requirements = parameters.get("requirements", "")
        content_type = parameters.get("content_type", "text")
        style = parameters.get("style", "neutral")
        context = parameters.get("context", "")
        
        system_prompt = f"""You are an expert content creator specialized in generating high-quality {content_type}.
Your writing style should be {style}, and you should create content that meets the specified requirements exactly.

Focus on clarity, relevance, and engagement while maintaining the requested style and format."""

        prompt = f"""Please generate {content_type} content based on these requirements:

REQUIREMENTS:
{requirements}

CONTEXT: {context}
STYLE: {style}

Create content that:
1. Meets all specified requirements
2. Is well-structured and engaging
3. Maintains consistency with the requested style
4. Is appropriate for the given context"""

        parameters["system_prompt"] = system_prompt
        parameters["prompt"] = prompt
        
        return await super().execute(parameters)


class ReasoningTool(LLMTool):
    """Specialized tool for logical reasoning and problem-solving"""
    
    def __init__(self):
        super().__init__(
            name="reasoning",
            description="Perform logical reasoning, problem-solving, and step-by-step thinking",
            temperature=0.2  # Lower temperature for logical consistency
        )
    
    async def execute(self, parameters: Dict[str, Any]) -> str:
        """Execute reasoning task"""
        problem = parameters.get("problem", "")
        reasoning_type = parameters.get("reasoning_type", "logical")
        constraints = parameters.get("constraints", [])
        
        system_prompt = f"""You are an expert in {reasoning_type} reasoning and problem-solving.
Your approach should be systematic, logical, and thorough. Break down complex problems into manageable steps.

Always show your reasoning process clearly and validate your conclusions."""

        constraints_text = "\n".join([f"- {constraint}" for constraint in constraints]) if constraints else "None specified"

        prompt = f"""Please solve this problem using {reasoning_type} reasoning:

PROBLEM:
{problem}

CONSTRAINTS:
{constraints_text}

Please provide:
1. Problem analysis and understanding
2. Step-by-step reasoning process
3. Consideration of constraints and limitations
4. Final solution or conclusion
5. Validation of your reasoning"""

        parameters["system_prompt"] = system_prompt
        parameters["prompt"] = prompt
        
        return await super().execute(parameters)


class EvaluationTool(LLMTool):
    """Specialized tool for evaluation and assessment tasks"""
    
    def __init__(self):
        super().__init__(
            name="evaluation",
            description="Evaluate, assess, and provide judgments on content, solutions, or options",
            temperature=0.1  # Lower temperature for consistent evaluation
        )
    
    async def execute(self, parameters: Dict[str, Any]) -> str:
        """Execute evaluation task"""
        subject = parameters.get("subject", "")
        criteria = parameters.get("criteria", [])
        scale = parameters.get("scale", "qualitative")
        context = parameters.get("context", "")
        
        system_prompt = """You are an expert evaluator with the ability to assess content, solutions, and options objectively.
Your evaluations should be fair, thorough, and based on clear criteria.

Provide detailed reasoning for your assessments and be specific about strengths and weaknesses."""

        criteria_text = "\n".join([f"- {criterion}" for criterion in criteria]) if criteria else "General quality and effectiveness"

        prompt = f"""Please evaluate the following subject:

SUBJECT TO EVALUATE:
{subject}

EVALUATION CRITERIA:
{criteria_text}

EVALUATION SCALE: {scale}
CONTEXT: {context}

Please provide:
1. Assessment against each criterion
2. Overall evaluation and score (if applicable)
3. Strengths and weaknesses
4. Specific recommendations for improvement
5. Summary judgment"""

        parameters["system_prompt"] = system_prompt
        parameters["prompt"] = prompt
        
        return await super().execute(parameters)