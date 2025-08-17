import io
import re
import json
from typing import List, Dict, Optional

from services.document_parser import document_parser
from services.text_chunker import text_chunker
from database.postgres_client import postgres_client
from document_ingestion.models import ExtractedRule, Severity
from .models import ComplianceIssue, SegmentComplianceResult, DocumentEvaluationResponse
from agent.token_manager import estimate_tokens
from utils.logging_config import get_logger
from config import settings
import openai

logger = get_logger(__name__)


class RuleRelevanceFilter:
    """Filters rules based on relevance to document segments."""
    
    def __init__(self):
        self.compliance_keywords = {
            'security': ['security', 'secure', 'protection', 'safeguard', 'encrypt', 'access control'],
            'privacy': ['privacy', 'personal', 'confidential', 'pii', 'data protection'],
            'audit': ['audit', 'log', 'monitoring', 'tracking', 'record'],
            'access': ['access', 'authorization', 'authentication', 'permission'],
            'data': ['data', 'information', 'database', 'storage', 'backup'],
            'incident': ['incident', 'breach', 'response', 'recovery', 'contingency'],
            'training': ['training', 'awareness', 'education', 'competency'],
            'documentation': ['document', 'policy', 'procedure', 'standard']
        }
    
    def extract_keywords(self, text: str) -> List[str]:
        """Extract meaningful keywords from text."""
        text_lower = text.lower()
        
        # Remove common stop words and extract meaningful terms
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text_lower)
        
        # Filter out common stop words
        stop_words = {'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'her', 'was', 'one', 'our', 'had', 'but', 'what', 'said', 'each', 'which', 'their', 'time', 'will', 'way', 'about', 'would', 'there', 'could', 'been', 'have', 'they', 'this', 'that', 'with', 'from', 'into', 'more', 'than', 'also', 'were', 'been', 'when', 'where', 'some', 'many', 'most', 'other', 'such', 'only', 'then', 'them', 'these', 'much', 'very', 'well', 'made', 'over', 'just', 'used', 'like', 'may', 'should', 'must', 'shall'}
        
        keywords = [word for word in words if word not in stop_words and len(word) > 3]
        
        # Add category keywords if found
        category_keywords = []
        for category, cat_keywords in self.compliance_keywords.items():
            if any(keyword in text_lower for keyword in cat_keywords):
                category_keywords.extend(cat_keywords)
        
        return list(set(keywords + category_keywords))
    
    def calculate_relevance_score(self, segment_keywords: List[str], rule: ExtractedRule) -> float:
        """Calculate relevance score between segment and rule."""
        rule_text = f"{rule.title} {rule.requirement}".lower()
        rule_keywords = self.extract_keywords(rule_text)
        
        if not segment_keywords or not rule_keywords:
            return 0.0
        
        # Calculate keyword overlap
        overlap = set(segment_keywords) & set(rule_keywords)
        overlap_score = len(overlap) / max(len(segment_keywords), len(rule_keywords))
        
        # Boost score for exact phrase matches
        phrase_bonus = 0.0
        for keyword in segment_keywords:
            if keyword in rule_text:
                phrase_bonus += 0.1
        
        # Boost score based on rule severity
        severity_weight = {'high': 1.2, 'medium': 1.0, 'low': 0.8}.get(rule.severity.value, 1.0)
        
        final_score = (overlap_score + phrase_bonus) * severity_weight
        return min(final_score, 1.0)  # Cap at 1.0
    
    def find_relevant_rules(self, segment_text: str, rules: List[ExtractedRule], top_k: int = 8) -> List[ExtractedRule]:
        """Find most relevant rules for a document segment."""
        segment_keywords = self.extract_keywords(segment_text)
        
        if not segment_keywords:
            # If no keywords found, return high-priority rules
            return [rule for rule in rules if rule.severity == Severity.HIGH][:top_k]
        
        # Score all rules
        scored_rules = []
        for rule in rules:
            score = self.calculate_relevance_score(segment_keywords, rule)
            if score > 0.1:  # Only include rules with meaningful relevance
                scored_rules.append((score, rule))
        
        # Sort by score and return top-k
        scored_rules.sort(reverse=True, key=lambda x: x[0])
        return [rule for _, rule in scored_rules[:top_k]]


class DocumentEvaluationService:
    """Service for evaluating documents against compliance rules."""
    
    def __init__(self):
        self.relevance_filter = RuleRelevanceFilter()
        self.max_context_chars = 24000
    
    def evaluate_document(self, file_stream: io.BytesIO, filename: str, framework_id: str) -> DocumentEvaluationResponse:
        """Evaluate a document against framework rules without persisting it."""
        logger.info(f"Starting evaluation of {filename} against framework {framework_id}")
        
        try:
            # Parse document content
            document_text = document_parser.parse_document(file_stream, filename)
            logger.info(f"Parsed document: {len(document_text)} characters")
            
            # Chunk into segments
            segments = text_chunker.chunk_text(document_text)
            logger.info(f"Created {len(segments)} segments")
            
            # Load framework rules
            rules = self._load_framework_rules(framework_id)
            logger.info(f"Loaded {len(rules)} rules for framework")
            
            if not rules:
                return self._create_empty_result(filename, framework_id, "No rules found for framework")
            
            # Evaluate each segment
            segment_results = []
            for ordinal, segment_text in segments:
                try:
                    result = self._evaluate_segment(segment_text, ordinal, rules)
                    segment_results.append(result)
                except Exception as e:
                    logger.error(f"Failed to evaluate segment {ordinal}: {str(e)}")
                    # Continue with other segments
                    continue
            
            # Calculate overall metrics
            overall_score = self._calculate_overall_score(segment_results)
            summary = self._generate_summary(segment_results)
            
            return DocumentEvaluationResponse(
                document_name=filename,
                framework_id=framework_id,
                total_segments=len(segments),
                segments_processed=len(segment_results),
                overall_compliance_score=overall_score,
                segment_results=segment_results,
                summary=summary
            )
            
        except Exception as e:
            logger.error(f"Document evaluation failed: {str(e)}")
            raise ValueError(f"Failed to evaluate document: {str(e)}")
    
    def _load_framework_rules(self, framework_id: str) -> List[ExtractedRule]:
        """Load extracted rules for a framework from database."""
        sql = """
        SELECT code, title, requirement
        FROM compliance_rules
        WHERE compliance_framework_id = :framework_id::uuid
        ORDER BY code ASC
        """
        
        try:
            logger.info(f"Loading rules for framework {framework_id}")
            response = postgres_client.execute_statement(sql, [
                {'name': 'framework_id', 'value': {'stringValue': framework_id}}
            ])
            
            logger.info(f"Query returned {len(response.get('records', []))} records")
            
            rules = []
            for record in response['records']:
                rule = ExtractedRule(
                    code=record[0]['stringValue'],
                    title=record[1]['stringValue'],
                    requirement=record[2]['stringValue'],
                    severity=Severity.MEDIUM,  # Default severity since not stored in schema
                    evidence_quotes=[],  # Empty since not stored in current schema
                    evidence_segments=[]  # Not needed for evaluation
                )
                rules.append(rule)
                logger.debug(f"Loaded rule: {rule.code} - {rule.title}")
            
            logger.info(f"Successfully loaded {len(rules)} rules for framework {framework_id}")
            return rules
            
        except Exception as e:
            logger.error(f"Failed to load rules for framework {framework_id}: {str(e)}")
            return []
    
    def _evaluate_segment(self, segment_text: str, ordinal: int, all_rules: List[ExtractedRule]) -> SegmentComplianceResult:
        """Evaluate a single document segment against relevant rules."""
        # Find relevant rules for this segment
        relevant_rules = self.relevance_filter.find_relevant_rules(segment_text, all_rules)
        
        if not relevant_rules:
            return SegmentComplianceResult(
                segment_ordinal=ordinal,
                segment_preview=segment_text[:200] + "..." if len(segment_text) > 200 else segment_text,
                applicable_rules=[],
                compliance_status="no_applicable_rules",
                issues_found=[],
                confidence_score=1.0
            )
        
        # Build context for analysis
        context = self._build_analysis_context(segment_text, relevant_rules)
        
        # Analyze compliance using LLM
        analysis_result = self._analyze_compliance_with_llm(segment_text, relevant_rules)
        
        # Convert issues to ComplianceIssue objects
        issues_found = [
            ComplianceIssue(
                rule_code=issue['rule_code'],
                issue_type=issue['issue_type'],
                description=issue['description'],
                severity=issue['severity']
            ) for issue in analysis_result['issues']
        ]
        
        return SegmentComplianceResult(
            segment_ordinal=ordinal,
            segment_preview=segment_text[:200] + "..." if len(segment_text) > 200 else segment_text,
            applicable_rules=[{
                'code': rule.code,
                'title': rule.title,
                'requirement': rule.requirement,
                'severity': rule.severity.value
            } for rule in relevant_rules],
            compliance_status=analysis_result['status'],
            issues_found=issues_found,
            confidence_score=analysis_result['confidence']
        )
    
    def _build_analysis_context(self, segment_text: str, rules: List[ExtractedRule]) -> str:
        """Build context string for rule analysis within token limits."""
        context_parts = [
            f"Document Segment:\n{segment_text}\n",
            "Applicable Compliance Rules:"
        ]
        
        current_length = len('\n'.join(context_parts))
        
        for rule in rules:
            rule_text = f"\n{rule.code}: {rule.title}\nRequirement: {rule.requirement}\nSeverity: {rule.severity.value}\n"
            
            if current_length + len(rule_text) < self.max_context_chars:
                context_parts.append(rule_text)
                current_length += len(rule_text)
            else:
                break
        
        return '\n'.join(context_parts)
    
    def _analyze_compliance_with_llm(self, segment_text: str, rules: List[ExtractedRule]) -> Dict:
        """Analyze compliance using LLM for rigorous evaluation."""
        # Build the prompt for LLM analysis
        prompt = self._build_compliance_analysis_prompt(segment_text, rules)
        
        # Call OpenAI API
        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a compliance analysis expert. Analyze product descriptions against regulatory requirements with extreme rigor. Look for explicit violations, missing required elements, and non-compliance issues."
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            temperature=0.1,
            max_tokens=1000
        )
        
        # Parse the LLM response
        analysis_text = response.choices[0].message.content
        return self._parse_llm_analysis_response(analysis_text)
    
    def _build_compliance_analysis_prompt(self, segment_text: str, rules: List[ExtractedRule]) -> str:
        """Build the prompt for LLM compliance analysis."""
        prompt_parts = [
            "COMPLIANCE ANALYSIS TASK:",
            "Analyze the following product description against the provided compliance rules.",
            "Be extremely rigorous - look for explicit violations and missing required elements.",
            "",
            "PRODUCT DESCRIPTION:",
            f'"""{segment_text}"""',
            "",
            "COMPLIANCE RULES TO CHECK:"
        ]
        
        for i, rule in enumerate(rules, 1):
            prompt_parts.append(f"{i}. {rule.code}: {rule.title}")
            prompt_parts.append(f"   Requirement: {rule.requirement}")
            prompt_parts.append("")
        
        prompt_parts.extend([
            "ANALYSIS INSTRUCTIONS:",
            "1. Check if the product description violates any of the listed rules",
            "2. Look for explicitly missing elements (e.g., 'No CE mark visible', 'No warnings attached')",
            "3. Determine if required labels, warnings, or certifications are absent",
            "4. Consider the product type and whether rules apply to it",
            "",
            "RESPONSE FORMAT (JSON):",
            "{",
            '  "overall_status": "compliant|needs_review|non_compliant",',
            '  "confidence": 0.0-1.0,',
            '  "issues": [',
            '    {',
            '      "rule_code": "CODE",',
            '      "issue_type": "missing_required_element|explicit_violation|insufficient_information",',
            '      "description": "Detailed description of the issue",',
            '      "severity": "high|medium|low"',
            '    }',
            '  ]',
            '}',
            "",
            "Focus on explicit violations and clearly missing required elements. Be rigorous but fair."
        ])
        
        return '\n'.join(prompt_parts)
    
    def _parse_llm_analysis_response(self, analysis_text: str) -> Dict:
        """Parse the LLM analysis response."""
        import re
        
        # Look for JSON block in the response
        json_match = re.search(r'\{.*\}', analysis_text, re.DOTALL)
        if not json_match:
            raise ValueError("LLM response does not contain valid JSON")
        
        json_str = json_match.group(0)
        parsed = json.loads(json_str)
        
        # Validate the response structure
        required_keys = ['overall_status', 'confidence', 'issues']
        if not all(key in parsed for key in required_keys):
            raise ValueError(f"LLM response missing required keys: {required_keys}")
        
        return {
            'status': parsed['overall_status'],
            'confidence': float(parsed['confidence']),
            'issues': parsed['issues']
        }
    
    def _calculate_overall_score(self, segment_results: List[SegmentComplianceResult]) -> float:
        """Calculate overall compliance score for the document."""
        if not segment_results:
            return 0.0
        
        total_score = 0.0
        for result in segment_results:
            if result.compliance_status == "compliant":
                total_score += 1.0
            elif result.compliance_status == "needs_review":
                total_score += 0.5
            # non_compliant adds 0.0
        
        return total_score / len(segment_results)
    
    def _generate_summary(self, segment_results: List[SegmentComplianceResult]) -> str:
        """Generate a summary of the evaluation results."""
        total_segments = len(segment_results)
        compliant_segments = sum(1 for r in segment_results if r.compliance_status == "compliant")
        review_segments = sum(1 for r in segment_results if r.compliance_status == "needs_review")
        non_compliant_segments = sum(1 for r in segment_results if r.compliance_status == "non_compliant")
        
        total_issues = sum(len(r.issues_found) for r in segment_results)
        high_severity_issues = sum(1 for r in segment_results for issue in r.issues_found if issue.severity == 'high')
        
        return f"Evaluated {total_segments} segments. {compliant_segments} compliant, {review_segments} need review, {non_compliant_segments} non-compliant. Found {total_issues} total issues ({high_severity_issues} high severity)."
    
    def _create_empty_result(self, filename: str, framework_id: str, message: str) -> DocumentEvaluationResponse:
        """Create empty result when evaluation cannot proceed."""
        return DocumentEvaluationResponse(
            document_name=filename,
            framework_id=framework_id,
            total_segments=0,
            segments_processed=0,
            overall_compliance_score=0.0,
            segment_results=[],
            summary=f"Evaluation could not be completed: {message}",
            status="error",
            message=message
        )


# Singleton instance
document_evaluation_service = DocumentEvaluationService()