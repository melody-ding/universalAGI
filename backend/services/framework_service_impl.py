"""
Concrete implementation of FrameworkService.
"""

from typing import List, Dict, Any, Optional
from services.interfaces import FrameworkService, FrameworkMatchResult
from services.framework_matcher import framework_matcher
from database.postgres_client import postgres_client
from utils.logging_config import get_logger

logger = get_logger(__name__)


class FrameworkServiceImpl(FrameworkService):
    """Concrete implementation of FrameworkService."""
    
    def __init__(self):
        self.framework_matcher = framework_matcher
        self.db_client = postgres_client
    
    async def find_relevant_frameworks(self, document_text: str) -> FrameworkMatchResult:
        """Find relevant frameworks for a document."""
        try:
            logger.info("Finding relevant compliance frameworks for document")
            
            # Use the existing framework matcher
            framework_ids = await self.framework_matcher.find_relevant_frameworks(document_text)
            
            if not framework_ids:
                logger.warning("No relevant frameworks found")
                return FrameworkMatchResult(
                    framework_ids=[],
                    confidence_scores={},
                    reasoning="No matching frameworks found based on document content analysis."
                )
            
            # Get confidence scores (if available from matcher)
            confidence_scores = {}
            for framework_id in framework_ids:
                # For now, assign a default confidence score
                # This could be enhanced with actual scoring from the matcher
                confidence_scores[framework_id] = 0.8
            
            reasoning = f"Found {len(framework_ids)} relevant frameworks based on document content analysis: {', '.join(framework_ids)}"
            
            logger.info(f"Found {len(framework_ids)} relevant frameworks")
            
            return FrameworkMatchResult(
                framework_ids=framework_ids,
                confidence_scores=confidence_scores,
                reasoning=reasoning
            )
            
        except Exception as e:
            logger.error(f"Failed to find relevant frameworks: {str(e)}")
            return FrameworkMatchResult(
                framework_ids=[],
                confidence_scores={},
                reasoning=f"Error during framework matching: {str(e)}"
            )
    
    async def get_framework_info(self, framework_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific framework."""
        try:
            logger.info(f"Retrieving framework info for: {framework_id}")
            
            framework = self.db_client.get_compliance_group_by_id(framework_id)
            if not framework:
                logger.warning(f"Framework not found: {framework_id}")
                return None
            
            framework_info = {
                "id": framework.id,
                "name": framework.name,
                "description": framework.description,
                "created_at": framework.created_at.isoformat() if framework.created_at else None,
                "updated_at": framework.updated_at.isoformat() if framework.updated_at else None
            }
            
            # Get additional metadata like document count
            try:
                documents = self.db_client.get_documents_by_compliance_framework(framework_id)
                framework_info["document_count"] = len(documents)
            except Exception as e:
                logger.warning(f"Could not get document count for framework {framework_id}: {str(e)}")
                framework_info["document_count"] = 0
            
            logger.info(f"Retrieved framework info for {framework_id}")
            return framework_info
            
        except Exception as e:
            logger.error(f"Failed to get framework info for {framework_id}: {str(e)}")
            return None
    
    async def list_available_frameworks(self) -> List[Dict[str, Any]]:
        """List all available frameworks."""
        try:
            logger.info("Listing all available frameworks")
            
            frameworks = self.db_client.get_all_compliance_groups()
            
            framework_list = []
            for framework in frameworks:
                framework_info = {
                    "id": framework.id,
                    "name": framework.name,
                    "description": framework.description,
                    "created_at": framework.created_at.isoformat() if framework.created_at else None,
                    "updated_at": framework.updated_at.isoformat() if framework.updated_at else None
                }
                
                # Get document count for each framework
                try:
                    documents = self.db_client.get_documents_by_compliance_framework(framework.id)
                    framework_info["document_count"] = len(documents)
                except Exception as e:
                    logger.warning(f"Could not get document count for framework {framework.id}: {str(e)}")
                    framework_info["document_count"] = 0
                
                framework_list.append(framework_info)
            
            logger.info(f"Listed {len(framework_list)} available frameworks")
            return framework_list
            
        except Exception as e:
            logger.error(f"Failed to list available frameworks: {str(e)}")
            return []
