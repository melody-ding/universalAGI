from typing import Dict, Any

from .rules_extraction import RulesExtractionOrchestrator
from .llm_extractor import LLMProvider
from utils.logging_config import get_logger

logger = get_logger(__name__)


def extract_rules_for_framework_trigger(
    framework_id: str, 
    llm_provider: LLMProvider = None
) -> Dict[str, Any]:
    """
    Trigger function for rules extraction when compliance group is assigned.
    
    This is the main entry point that should be called from routes when:
    - Documents are assigned to a compliance framework
    - User manually triggers rule extraction
    - Batch processing of frameworks
    
    Args:
        framework_id: UUID of the compliance framework
        llm_provider: Optional custom LLM provider
        
    Returns:
        Dictionary with extraction results and statistics
    """
    logger.info(f"Triggered rule extraction for framework {framework_id}")
    
    try:
        orchestrator = RulesExtractionOrchestrator(llm_provider)
        result = orchestrator.extract_rules_for_framework(framework_id)
        
        return {
            'success': result.success,
            'framework_id': result.framework_id,
            'rules_extracted': result.rules_extracted,
            'error': result.error,
            'rules': [
                {
                    'code': rule.code,
                    'title': rule.title,
                    'requirement': rule.requirement,
                    'severity': rule.severity.value,
                    'evidence_count': len(rule.evidence_quotes)
                }
                for rule in result.rules
            ]
        }
        
    except Exception as e:
        logger.error(f"Trigger failed for framework {framework_id}: {str(e)}")
        return {
            'success': False,
            'framework_id': framework_id,
            'error': str(e),
            'rules_extracted': 0,
            'rules': []
        }


def batch_extract_rules_for_all_frameworks(llm_provider: LLMProvider = None) -> Dict[str, Any]:
    """
    Batch process rule extraction for all frameworks.
    
    Useful for:
    - Initial system setup
    - Bulk reprocessing after algorithm updates
    - Scheduled maintenance tasks
    
    Args:
        llm_provider: Optional custom LLM provider
        
    Returns:
        Summary of batch processing results
    """
    from database.postgres_client import postgres_client
    
    logger.info("Starting batch rule extraction for all frameworks")
    
    try:
        # Get all frameworks
        response = postgres_client.execute_statement(
            "SELECT id FROM compliance_frameworks ORDER BY created_at"
        )
        
        framework_ids = [record[0]['stringValue'] for record in response['records']]
        logger.info(f"Found {len(framework_ids)} frameworks to process")
        
        results = []
        total_rules = 0
        
        for framework_id in framework_ids:
            result = extract_rules_for_framework_trigger(framework_id, llm_provider)
            results.append(result)
            
            if result['success']:
                total_rules += result['rules_extracted']
                logger.info(f"Framework {framework_id}: {result['rules_extracted']} rules")
            else:
                logger.error(f"Framework {framework_id} failed: {result.get('error')}")
        
        success_count = sum(1 for r in results if r['success'])
        
        return {
            'success': True,
            'frameworks_processed': len(framework_ids),
            'frameworks_succeeded': success_count,
            'frameworks_failed': len(framework_ids) - success_count,
            'total_rules_extracted': total_rules,
            'results': results
        }
        
    except Exception as e:
        logger.error(f"Batch processing failed: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'frameworks_processed': 0,
            'total_rules_extracted': 0
        }