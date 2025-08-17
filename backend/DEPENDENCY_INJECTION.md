# Dependency Injection Implementation

This document describes the dependency injection system implemented to improve the architectural soundness of the AI agent.

## Overview

The dependency injection system decouples components, improves testability, and makes the codebase more maintainable by:

- **Abstracting dependencies** through service interfaces
- **Centralizing configuration** through a service container
- **Enabling easy testing** with mock implementations
- **Supporting runtime customization** of service implementations

## Architecture

### Service Interfaces

All major services now have abstract interfaces defined in `services/interfaces.py`:

- `DocumentService` - Document parsing and validation
- `SearchService` - Hybrid search operations
- `FrameworkService` - Compliance framework operations
- `AnalysisService` - Document analysis operations
- `OrchestrationService` - Agent orchestration (planned)
- `EmbeddingService` - Embedding operations (planned)

### Service Implementations

Concrete implementations are provided in separate files:

- `DocumentServiceImpl` - Wraps existing document parser
- `SearchServiceImpl` - Wraps multi-document search
- `FrameworkServiceImpl` - Wraps framework matcher
- `AnalysisServiceImpl` - Wraps document evaluation service

### Service Container

The `ServiceContainer` class manages service registration and resolution:

```python
from services.service_container import get_service, service_container
from services.interfaces import DocumentService

# Get service instance
doc_service = get_service(DocumentService)

# Register custom implementation
service_container.register_singleton(DocumentService, MyCustomDocumentService)
```

## Usage Examples

### Creating Agents with Dependency Injection

```python
from agent.agent_factory import create_react_agent, create_analysis_agent

# Create standard agent
agent = create_react_agent(
    model_name="gpt-4o-mini",
    planner_temperature=0.1
)

# Create specialized analysis agent
analysis_agent = create_analysis_agent(
    model_name="gpt-4o"
)
```

### Using Services Directly

```python
from services.service_container import get_document_service, get_search_service

# Use document service
doc_service = get_document_service()
result = await doc_service.parse_document(file_stream, "document.pdf")

# Use search service
search_service = get_search_service()
search_result = await search_service.hybrid_search("compliance requirements")
```

### Customizing Services for Testing

```python
from services.service_container import configure_services
from services.interfaces import SearchService

class MockSearchService(SearchService):
    async def hybrid_search(self, query, document_id=None, **kwargs):
        return SearchResult(
            documents_found=1,
            total_snippets=5,
            context_text="Mock search result",
            citations=[],
            metadata={"query": query}
        )

# Configure mock for testing
configure_services(SearchService=MockSearchService())

# Now all agents will use the mock service
agent = create_react_agent()
```

## Benefits Achieved

### 1. **Loose Coupling**
- Components depend on abstractions, not concrete implementations
- Easy to swap implementations without changing dependent code
- Reduced dependency chain complexity

### 2. **Improved Testability**
- Easy to inject mock services for unit testing
- Individual components can be tested in isolation
- Test scenarios can be precisely controlled

### 3. **Enhanced Maintainability**
- Clear separation of concerns
- Service implementations can evolve independently
- Configuration centralized in service container

### 4. **Runtime Flexibility**
- Services can be customized for different environments
- A/B testing of different implementations
- Performance optimizations can be swapped in dynamically

## Migration Guide

### For Existing Code

Replace direct imports with service injection:

**Before:**
```python
from services.document_parser import document_parser
from search.multi_document_search import build_grouped_context

class MyTool:
    def __init__(self):
        self.parser = document_parser
    
    async def execute(self, query):
        context = await build_grouped_context(None, query)
```

**After:**
```python
from services.interfaces import DocumentService, SearchService
from services.service_container import get_document_service, get_search_service

class MyTool:
    def __init__(self, 
                 document_service: Optional[DocumentService] = None,
                 search_service: Optional[SearchService] = None):
        self.document_service = document_service or get_document_service()
        self.search_service = search_service or get_search_service()
    
    async def execute(self, query):
        search_result = await self.search_service.hybrid_search(query)
```

### For New Components

Always use dependency injection from the start:

```python
from services.interfaces import MyService
from services.service_container import get_service

class NewComponent:
    def __init__(self, my_service: Optional[MyService] = None):
        self.my_service = my_service or get_service(MyService)
```

## Best Practices

### 1. **Interface Design**
- Keep interfaces focused and cohesive
- Use dataclasses for structured return types
- Include async methods where appropriate
- Document expected behavior clearly

### 2. **Service Registration**
- Register stateless services as singletons
- Use factories for complex initialization
- Register instances for pre-configured objects
- Override services sparingly and document why

### 3. **Error Handling**
- Services should handle their own errors gracefully
- Return structured error information
- Log failures appropriately
- Maintain service contracts even during failures

### 4. **Testing**
- Create mock implementations for all interfaces
- Test service implementations independently
- Use dependency injection for integration tests
- Verify service container configuration

## Performance Considerations

### Service Resolution
- Singleton services are cached after first resolution
- Service creation overhead is minimal
- Use factories for expensive initialization only

### Memory Usage
- Singletons persist for application lifetime
- Transient services are garbage collected normally
- Monitor memory usage if using many custom services

### Startup Time
- Services are created lazily on first access
- Default services have minimal initialization overhead
- Custom services should optimize initialization

## Future Enhancements

### Planned Additions
1. **Configuration-based service registration**
2. **Automatic dependency resolution from type hints**
3. **Service health monitoring**
4. **Performance metrics collection**
5. **Service lifecycle management**

### Extension Points
- Custom service interfaces for domain-specific needs
- Plugin architecture for third-party services
- Environment-specific service configurations
- Dynamic service discovery mechanisms

## Troubleshooting

### Common Issues

**Service not found:**
```
ValueError: No registration found for MyService
```
- Ensure service is registered in service container
- Check import statements and interface inheritance

**Circular dependencies:**
```
RecursionError: maximum recursion depth exceeded
```
- Refactor to break circular dependencies
- Use lazy initialization where appropriate

**Service initialization failures:**
```
Exception during service creation
```
- Check service constructor parameters
- Verify dependencies are available
- Review service implementation logs

### Debugging Tips

1. **Enable debug logging** for service container
2. **Check service registrations** using container inspection
3. **Verify service interfaces** match implementations
4. **Test services independently** before integration
5. **Use type hints** to catch interface mismatches early
