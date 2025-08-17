from typing import List
import uuid

from database.postgres_client import postgres_client
from .models import ExtractedRule, DocumentSegment
from services.embedding_service import embedding_service
from utils.logging_config import get_logger

logger = get_logger(__name__)


class RulePersistence:
    """Handles persistence of extracted rules to database."""
    
    def persist_rules(self, framework_id: str, rules: List[ExtractedRule]) -> int:
        """Persist rules and evidence to database."""
        persisted_count = 0
        
        for rule in rules:
            try:
                rule_id = self._insert_compliance_rule(framework_id, rule)
                self._log_rule_sources(rule_id, rule.evidence_segments, rule.evidence_quotes)
                persisted_count += 1
                
            except Exception as e:
                logger.error(f"Failed to persist rule {rule.code}: {str(e)}")
        
        return persisted_count
    
    def _insert_compliance_rule(self, framework_id: str, rule: ExtractedRule) -> str:
        """Insert compliance rule with upsert logic."""
        # Generate real embedding for the rule
        embedding_str = self._generate_rule_embedding(rule)
        
        # Get document ID from the first evidence segment
        document_id = rule.evidence_segments[0].document_id if rule.evidence_segments else None
        if not document_id:
            raise ValueError(f"Rule {rule.code} has no evidence segments with document_id")
        
        sql = """
        INSERT INTO compliance_rules (compliance_framework_id, document_id, code, title, requirement, embedding)
        VALUES (:framework_id::uuid, :document_id, :code, :title, :requirement, :embedding::vector)
        ON CONFLICT (compliance_framework_id, code) 
        DO UPDATE SET 
            title = EXCLUDED.title, 
            requirement = EXCLUDED.requirement,
            document_id = EXCLUDED.document_id
        RETURNING id
        """
        
        parameters = [
            {'name': 'framework_id', 'value': {'stringValue': framework_id}},
            {'name': 'document_id', 'value': {'longValue': document_id}},
            {'name': 'code', 'value': {'stringValue': rule.code}},
            {'name': 'title', 'value': {'stringValue': rule.title}},
            {'name': 'requirement', 'value': {'stringValue': rule.requirement}},
            {'name': 'embedding', 'value': {'stringValue': embedding_str}}
        ]
        
        response = postgres_client.execute_statement(sql, parameters)
        rule_id = response['records'][0][0]['stringValue']
        
        logger.info(f"Persisted rule {rule.code} with ID {rule_id}")
        return rule_id
    
    def _log_rule_sources(self, rule_id: str, segments: List[DocumentSegment], quotes: List[str]):
        """Log rule source evidence (placeholder for rule_sources table)."""
        logger.info(f"Would link rule {rule_id} to {len(segments)} evidence segments")
        
        # This will be implemented when rule_sources table is created
        # for segment, quote in zip(segments, quotes):
        #     self._insert_rule_source(rule_id, segment.id, quote)
    
    def _insert_rule_source(self, rule_id: str, segment_id: int, quote: str):
        """Insert rule source evidence link."""
        sql = """
        INSERT INTO rule_sources (compliance_rule_id, document_segment_id, evidence_quote)
        VALUES (:rule_id::uuid, :segment_id, :quote)
        ON CONFLICT (compliance_rule_id, document_segment_id) DO NOTHING
        """
        
        parameters = [
            {'name': 'rule_id', 'value': {'stringValue': rule_id}},
            {'name': 'segment_id', 'value': {'longValue': segment_id}},
            {'name': 'quote', 'value': {'stringValue': quote}}
        ]
        
        postgres_client.execute_statement(sql, parameters)
    
    def _generate_rule_embedding(self, rule: ExtractedRule) -> str:
        """Generate real embedding for compliance rule."""
        # Combine rule information into a comprehensive text for embedding
        rule_text = f"{rule.title}. {rule.requirement}. Evidence: {' '.join(rule.evidence_quotes)}"
        
        logger.debug(f"Generating embedding for rule {rule.code}")
        embedding = embedding_service.generate_embedding(rule_text)
        
        # Convert to string format for PostgreSQL vector
        embedding_str = '[' + ','.join([str(x) for x in embedding]) + ']'
        logger.debug(f"Generated embedding for rule {rule.code} (length: {len(embedding)})")
        
        return embedding_str