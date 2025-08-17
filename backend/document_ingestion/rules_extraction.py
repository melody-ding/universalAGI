import re
from typing import List, Dict, Any

from database.postgres_client import postgres_client
from .models import DocumentSegment, ExtractionResult
from .candidate_pool import CandidatePoolBuilder
from .grouping import SectionGrouper
from .llm_extractor import RuleExtractor, LLMProvider
from .validation import RuleValidator
from .persistence import RulePersistence
from utils.logging_config import get_logger

logger = get_logger(__name__)


class RulesExtractionOrchestrator:
    """Main orchestrator for the rules extraction pipeline."""
    
    MAX_GROUPS_TO_PROCESS = 15
    
    def __init__(self, llm_provider: LLMProvider = None):
        self.pool_builder = CandidatePoolBuilder()
        self.grouper = SectionGrouper()
        self.extractor = RuleExtractor(llm_provider)
        self.validator = RuleValidator()
        self.persistence = RulePersistence()
    
    def extract_rules_for_framework(self, framework_id: str) -> ExtractionResult:
        """
        Execute complete rules extraction pipeline for a framework.
        
        Args:
            framework_id: UUID of the compliance framework
            
        Returns:
            ExtractionResult with success status and extracted rules
        """
        logger.info(f"Starting rule extraction for framework {framework_id}")
        
        try:
            # Step 1: Load framework information
            framework_info = self._load_framework_info(framework_id)
            if not framework_info:
                return self._create_empty_result(framework_id, "Framework not found")
            
            logger.info(f"Loaded framework: {framework_info['name']}")
            
            # Step 2: Load framework segments
            segments = self._load_framework_segments(framework_id)
            if not segments:
                return self._create_empty_result(framework_id, "No segments found")
            
            logger.info(f"Loaded {len(segments)} segments")
            
            # Step 3: Build candidate pool
            candidates = self.pool_builder.build_pool(segments)
            logger.info(f"Built candidate pool: {len(candidates)} segments")
            
            # Step 4: Group candidates by section
            groups = self.grouper.group_by_section(candidates)
            logger.info(f"Created {len(groups)} section groups")
            
            # Step 5: Extract rules from groups with framework context
            extracted_rules = self._extract_rules_from_groups(groups, framework_info)
            logger.info(f"Extracted {len(extracted_rules)} raw rules")
            
            # Step 5: Validate and deduplicate
            final_rules = self.validator.validate_and_deduplicate(extracted_rules)
            logger.info(f"Final validated rules: {len(final_rules)}")
            
            # Step 6: Persist to database
            persisted_count = self.persistence.persist_rules(framework_id, final_rules)
            logger.info(f"Persisted {persisted_count} rules")
            
            return ExtractionResult(
                success=True,
                framework_id=framework_id,
                rules_extracted=len(final_rules),
                rules=final_rules
            )
            
        except Exception as e:
            logger.error(f"Rule extraction failed for framework {framework_id}: {str(e)}")
            return ExtractionResult(
                success=False,
                framework_id=framework_id,
                rules_extracted=0,
                rules=[],
                error=str(e)
            )
    
    def _load_framework_info(self, framework_id: str) -> dict:
        """Load compliance framework information."""
        sql = """
        SELECT id, name, description
        FROM compliance_frameworks
        WHERE id = :framework_id::uuid
        """
        
        response = postgres_client.execute_statement(sql, [
            {'name': 'framework_id', 'value': {'stringValue': framework_id}}
        ])
        
        if not response['records']:
            return None
            
        record = response['records'][0]
        return {
            'id': record[0]['stringValue'],
            'name': record[1]['stringValue'],
            'description': record[2]['stringValue'] if record[2].get('stringValue') else ''
        }
    
    def _load_framework_segments(self, framework_id: str) -> List[DocumentSegment]:
        """Load all document segments for the framework."""
        sql = """
        SELECT ds.id, ds.document_id, ds.segment_ordinal, ds.text
        FROM document_segments ds
        JOIN documents d ON ds.document_id = d.id
        WHERE d.compliance_framework_id = :framework_id::uuid
        ORDER BY d.id, ds.segment_ordinal
        """
        
        response = postgres_client.execute_statement(sql, [
            {'name': 'framework_id', 'value': {'stringValue': framework_id}}
        ])
        
        segments = []
        for record in response['records']:
            segment = DocumentSegment(
                id=record[0]['longValue'],
                document_id=record[1]['longValue'],
                segment_ordinal=record[2]['longValue'],
                text=record[3]['stringValue'],
                heading_path=self._extract_heading_path(record[3]['stringValue']),
                chapter_level=0
            )
            segment.chapter_level = len(segment.heading_path)
            segments.append(segment)
        
        return segments
    
    def _extract_heading_path(self, text: str) -> List[str]:
        """Extract hierarchical heading structure from text."""
        lines = text.strip().split('\n')
        headings = []
        
        for line in lines[:5]:  # Check first few lines
            line = line.strip()
            if not line:
                continue
            
            # Numbered headings
            if re.match(r'^(\d+\.|\d+\.\d+\.?|[A-Z]\.|\([a-z]\))', line):
                headings.append(line)
            # Markdown headings
            elif line.startswith('#'):
                headings.append(line.lstrip('#').strip())
            # All-caps titles
            elif line.isupper() and len(line) > 5:
                headings.append(line)
        
        return headings[:2]  # Max 2 levels
    
    def _extract_rules_from_groups(self, groups, framework_info):
        """Extract rules from section groups with framework context."""
        all_rules = []
        
        for group in groups[:self.MAX_GROUPS_TO_PROCESS]:
            rules = self.extractor.extract_from_group(group, framework_info)
            all_rules.extend(rules)
        
        return all_rules
    
    def _create_empty_result(self, framework_id: str, message: str) -> ExtractionResult:
        """Create empty result with warning message."""
        logger.warning(f"Empty result for framework {framework_id}: {message}")
        
        return ExtractionResult(
            success=True,
            framework_id=framework_id,
            rules_extracted=0,
            rules=[],
            error=message
        )