from typing import List, Optional, Dict, Any
from services.embedding_service import embedding_service
from database.postgres_client import postgres_client
from utils.logging_config import get_logger

logger = get_logger(__name__)

class FrameworkMatcher:
    """Service for matching documents to relevant compliance frameworks using embeddings."""
    
    def __init__(self, similarity_threshold: float = 0.3):
        self.similarity_threshold = similarity_threshold
    
    async def find_relevant_frameworks(self, document_text: str, max_frameworks: int = 3) -> List[str]:
        """
        Find compliance frameworks relevant to the document content.
        
        Args:
            document_text: Text content of the document
            max_frameworks: Maximum number of frameworks to return
            
        Returns:
            List of framework IDs ordered by relevance
        """
        try:
            # Generate embedding for document (use first 2000 chars for efficiency)
            doc_text_sample = document_text[:2000] if len(document_text) > 2000 else document_text
            doc_embedding = embedding_service.generate_embedding(doc_text_sample)
            embedding_str = '[' + ','.join(map(str, doc_embedding)) + ']'
            
            # Query for similar frameworks using vector similarity
            sql = """
            SELECT id, name, embedding <=> :doc_embedding::vector as distance
            FROM compliance_frameworks 
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> :doc_embedding::vector
            LIMIT :max_frameworks
            """
            
            response = postgres_client.execute_statement(sql, [
                {'name': 'doc_embedding', 'value': {'stringValue': embedding_str}},
                {'name': 'max_frameworks', 'value': {'longValue': max_frameworks * 2}}  # Get extra to filter
            ])
            
            # Filter by similarity threshold and return framework IDs
            relevant_frameworks = []
            for record in response.get('records', []):
                distance = record[2].get('doubleValue', 1.0)
                similarity = 1.0 - distance
                
                if similarity >= self.similarity_threshold:
                    framework_id = record[0].get('stringValue')
                    framework_name = record[1].get('stringValue', 'Unknown')
                    relevant_frameworks.append(framework_id)
                    logger.info(f"Found relevant framework: {framework_name} (similarity: {similarity:.2f})")
            
            # Limit to requested number
            return relevant_frameworks[:max_frameworks]
            
        except Exception as e:
            logger.error(f"Error finding relevant frameworks: {str(e)}")
            raise RuntimeError(f"Failed to find relevant frameworks: {str(e)}")
    
    async def debug_framework_matching(self, document_text: str) -> Dict[str, Any]:
        """Debug method to show detailed framework matching information."""
        try:
            # Get all frameworks first
            all_frameworks_sql = """
            SELECT id, name, description, embedding IS NOT NULL as has_embedding
            FROM compliance_frameworks 
            ORDER BY name
            """
            
            all_response = postgres_client.execute_statement(all_frameworks_sql)
            all_frameworks = []
            
            for record in all_response.get('records', []):
                all_frameworks.append({
                    'id': record[0].get('stringValue'),
                    'name': record[1].get('stringValue'),
                    'description': record[2].get('stringValue'),
                    'has_embedding': record[3].get('booleanValue', False)
                })
            
            # Generate embedding for document
            doc_text_sample = document_text[:2000] if len(document_text) > 2000 else document_text
            doc_embedding = embedding_service.generate_embedding(doc_text_sample)
            embedding_str = '[' + ','.join(map(str, doc_embedding)) + ']'
            
            # Get similarity scores for all frameworks with embeddings
            similarity_sql = """
            SELECT id, name, embedding <=> :doc_embedding::vector as distance
            FROM compliance_frameworks 
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> :doc_embedding::vector
            """
            
            similarity_response = postgres_client.execute_statement(similarity_sql, [
                {'name': 'doc_embedding', 'value': {'stringValue': embedding_str}}
            ])
            
            similarities = []
            for record in similarity_response.get('records', []):
                distance = record[2].get('doubleValue', 1.0)
                similarity = 1.0 - distance
                similarities.append({
                    'id': record[0].get('stringValue'),
                    'name': record[1].get('stringValue'),
                    'similarity': similarity,
                    'passes_threshold': similarity >= self.similarity_threshold
                })
            
            return {
                'document_sample': doc_text_sample[:200] + "..." if len(doc_text_sample) > 200 else doc_text_sample,
                'total_frameworks': len(all_frameworks),
                'frameworks_with_embeddings': len([f for f in all_frameworks if f['has_embedding']]),
                'similarity_threshold': self.similarity_threshold,
                'all_frameworks': all_frameworks,
                'similarity_scores': similarities,
                'matching_frameworks': [s for s in similarities if s['passes_threshold']]
            }
            
        except Exception as e:
            logger.error(f"Error in debug framework matching: {str(e)}")
            return {'error': str(e)}

# Singleton instance
framework_matcher = FrameworkMatcher()