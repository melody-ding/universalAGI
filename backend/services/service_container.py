"""
Service container for dependency injection.
"""

from typing import Dict, Type, Any, Optional
from services.interfaces import (
    DocumentService, SearchService, FrameworkService, 
    AnalysisService, OrchestrationService, EmbeddingService
)
from services.document_service_impl import DocumentServiceImpl
from services.search_service_impl import SearchServiceImpl
from services.framework_service_impl import FrameworkServiceImpl
from services.analysis_service_impl import AnalysisServiceImpl
from utils.logging_config import get_logger

logger = get_logger(__name__)


class ServiceContainer:
    """Container for managing service dependencies."""
    
    def __init__(self):
        self._services: Dict[Type, Any] = {}
        self._singletons: Dict[Type, Any] = {}
        self._factories: Dict[Type, callable] = {}
        
        # Register default implementations
        self._register_default_services()
    
    def _register_default_services(self):
        """Register default service implementations."""
        # Register singletons for stateless services
        self.register_singleton(DocumentService, DocumentServiceImpl)
        self.register_singleton(SearchService, SearchServiceImpl)
        self.register_singleton(FrameworkService, FrameworkServiceImpl)
        self.register_singleton(AnalysisService, AnalysisServiceImpl)
        
        logger.info("Default services registered in container")
    
    def register_singleton(self, interface: Type, implementation: Type):
        """Register a service as a singleton."""
        self._singletons[interface] = implementation
        logger.debug(f"Registered singleton: {interface.__name__} -> {implementation.__name__}")
    
    def register_transient(self, interface: Type, implementation: Type):
        """Register a service as transient (new instance each time)."""
        self._services[interface] = implementation
        logger.debug(f"Registered transient: {interface.__name__} -> {implementation.__name__}")
    
    def register_factory(self, interface: Type, factory: callable):
        """Register a service factory function."""
        self._factories[interface] = factory
        logger.debug(f"Registered factory: {interface.__name__}")
    
    def register_instance(self, interface: Type, instance: Any):
        """Register a specific instance."""
        self._singletons[interface] = instance
        logger.debug(f"Registered instance: {interface.__name__}")
    
    def get(self, interface: Type) -> Any:
        """Get a service instance."""
        # Check for existing singleton instance
        if interface in self._singletons:
            singleton_impl = self._singletons[interface]
            if not isinstance(singleton_impl, type):
                # Already instantiated
                return singleton_impl
            else:
                # Need to instantiate
                instance = singleton_impl()
                self._singletons[interface] = instance
                logger.debug(f"Created singleton instance: {interface.__name__}")
                return instance
        
        # Check for factory
        if interface in self._factories:
            instance = self._factories[interface]()
            logger.debug(f"Created instance from factory: {interface.__name__}")
            return instance
        
        # Check for transient
        if interface in self._services:
            instance = self._services[interface]()
            logger.debug(f"Created transient instance: {interface.__name__}")
            return instance
        
        raise ValueError(f"No registration found for {interface.__name__}")
    
    def resolve_dependencies(self, target_class: Type) -> Any:
        """Resolve dependencies for a class constructor."""
        # This is a simple implementation - could be enhanced with annotation inspection
        try:
            # For now, just instantiate without dependency injection
            # This could be enhanced to inspect __init__ annotations and resolve them
            return target_class()
        except Exception as e:
            logger.error(f"Failed to resolve dependencies for {target_class.__name__}: {str(e)}")
            raise


# Global service container instance
service_container = ServiceContainer()


def get_service(interface: Type) -> Any:
    """Convenience function to get a service from the global container."""
    return service_container.get(interface)


def configure_services(**overrides):
    """Configure service overrides."""
    for interface, implementation in overrides.items():
        if isinstance(implementation, type):
            service_container.register_singleton(interface, implementation)
        else:
            service_container.register_instance(interface, implementation)
    
    logger.info(f"Configured {len(overrides)} service overrides")


# Convenience getters for common services
def get_document_service() -> DocumentService:
    """Get the document service."""
    return get_service(DocumentService)


def get_search_service() -> SearchService:
    """Get the search service."""
    return get_service(SearchService)


def get_framework_service() -> FrameworkService:
    """Get the framework service."""
    return get_service(FrameworkService)


def get_analysis_service() -> AnalysisService:
    """Get the analysis service."""
    return get_service(AnalysisService)
