"""
Agent factory for creating agents with dependency injection.
"""

from typing import Optional, Dict, Any
from agent.agent import ReActAgent
from agent.planner import Planner
from agent.executor import Executor
from agent.rag_tool import RAGTool
from agent.document_analysis_tool import DocumentAnalysisTool
from services.service_container import service_container, get_search_service, get_analysis_service
from utils.logging_config import get_logger

logger = get_logger(__name__)


class AgentFactory:
    """Factory for creating agents with proper dependency injection."""
    
    def __init__(self):
        self.service_container = service_container
    
    def create_react_agent(self, 
                          model_name: str = None,
                          planner_temperature: float = 0.1,
                          executor_temperature: float = None,
                          custom_tools: Optional[Dict[str, Any]] = None) -> ReActAgent:
        """
        Create a ReAct agent with dependency injection.
        
        Args:
            model_name: LLM model to use
            planner_temperature: Temperature for planning
            executor_temperature: Temperature for execution
            custom_tools: Additional tools to include
            
        Returns:
            Configured ReActAgent instance
        """
        logger.info("Creating ReAct agent with dependency injection")
        
        # Create tools with dependency injection
        tools = self._create_tools()
        
        # Add any custom tools
        if custom_tools:
            tools.update(custom_tools)
            logger.info(f"Added {len(custom_tools)} custom tools")
        
        # Create planner and executor
        planner = Planner(model_name, planner_temperature)
        executor = Executor(model_name, executor_temperature, tools)
        
        # Create agent
        agent = ReActAgent(
            model_name=model_name,
            planner_temperature=planner_temperature,
            executor_temperature=executor_temperature,
            planner=planner,
            executor=executor
        )
        
        logger.info("ReAct agent created successfully")
        return agent
    
    def create_lightweight_agent(self, model_name: str = None) -> ReActAgent:
        """
        Create a lightweight agent with minimal tools for fast responses.
        
        Args:
            model_name: LLM model to use
            
        Returns:
            Lightweight ReActAgent instance
        """
        logger.info("Creating lightweight agent")
        
        # Only include essential tools for speed
        tools = {
            "search_documents": RAGTool(get_search_service())
        }
        
        # Use faster temperatures
        agent = self.create_react_agent(
            model_name=model_name,
            planner_temperature=0.0,  # Very consistent planning
            executor_temperature=0.1,  # Fast execution
            custom_tools=tools
        )
        
        logger.info("Lightweight agent created successfully")
        return agent
    
    def create_analysis_agent(self, model_name: str = None) -> ReActAgent:
        """
        Create an agent specialized for document analysis.
        
        Args:
            model_name: LLM model to use
            
        Returns:
            Analysis-specialized ReActAgent instance
        """
        logger.info("Creating analysis-specialized agent")
        
        # Include analysis-focused tools
        from services.interfaces import DocumentService, FrameworkService
        
        tools = {
            "search_documents": RAGTool(get_search_service()),
            "document_analysis": DocumentAnalysisTool(
                document_service=self.service_container.get(DocumentService),
                framework_service=self.service_container.get(FrameworkService),
                analysis_service=get_analysis_service()
            )
        }
        
        # Use balanced temperatures for analysis
        agent = self.create_react_agent(
            model_name=model_name,
            planner_temperature=0.1,
            executor_temperature=0.2,
            custom_tools=tools
        )
        
        logger.info("Analysis agent created successfully")
        return agent
    
    def _create_tools(self) -> Dict[str, Any]:
        """Create standard tools with dependency injection."""
        tools = {
            "search_documents": RAGTool(get_search_service())
        }
        
        # Add document analysis tool if services are available
        try:
            tools["document_analysis"] = DocumentAnalysisTool()
            logger.debug("Added document analysis tool")
        except Exception as e:
            logger.warning(f"Could not create document analysis tool: {str(e)}")
        
        logger.info(f"Created {len(tools)} standard tools")
        return tools
    
    def configure_services(self, **service_overrides):
        """
        Configure service overrides for testing or customization.
        
        Args:
            **service_overrides: Service interface -> implementation mappings
        """
        logger.info(f"Configuring {len(service_overrides)} service overrides")
        
        for interface, implementation in service_overrides.items():
            if isinstance(implementation, type):
                self.service_container.register_singleton(interface, implementation)
            else:
                self.service_container.register_instance(interface, implementation)
        
        logger.info("Service configuration completed")


# Global factory instance
agent_factory = AgentFactory()


# Convenience functions
def create_react_agent(**kwargs) -> ReActAgent:
    """Create a ReAct agent with default configuration."""
    return agent_factory.create_react_agent(**kwargs)


def create_lightweight_agent(**kwargs) -> ReActAgent:
    """Create a lightweight agent for fast responses."""
    return agent_factory.create_lightweight_agent(**kwargs)


def create_analysis_agent(**kwargs) -> ReActAgent:
    """Create an analysis-specialized agent."""
    return agent_factory.create_analysis_agent(**kwargs)


def configure_agent_services(**service_overrides):
    """Configure service overrides for agent creation."""
    agent_factory.configure_services(**service_overrides)
