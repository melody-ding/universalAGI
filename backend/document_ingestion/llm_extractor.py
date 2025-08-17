import json
from typing import List, Dict, Any, Tuple
from abc import ABC, abstractmethod
from langchain_openai import ChatOpenAI

from .models import CandidateGroup, ExtractedRule, DocumentSegment, Severity
from utils.logging_config import get_logger
from config import settings

logger = get_logger(__name__)


class LLMProvider(ABC):
    """Abstract interface for LLM providers."""
    
    @abstractmethod
    def extract_rules(self, prompt: str) -> str:
        """Extract rules using LLM and return JSON response."""
        pass


class OpenAILLMProvider(LLMProvider):
    """OpenAI LLM provider using gpt-3.5-turbo for cost-effective rule extraction."""
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-3.5-turbo",  # Cheaper model
            temperature=0.1,  # Low temperature for consistent output
            openai_api_key=settings.OPENAI_API_KEY,
            max_tokens=1000
        )
        
    def extract_rules(self, prompt: str) -> str:
        """Extract rules using OpenAI LLM."""
        try:
            # Format for JSON output
            formatted_prompt = f"""You are a compliance expert. Respond ONLY with valid JSON in the exact format specified in the prompt.

{prompt}

Remember: Respond with ONLY the JSON object, no additional text."""
            
            response = self.llm.invoke(formatted_prompt)
            return response.content.strip()
            
        except Exception as e:
            logger.error(f"OpenAI API error: {str(e)}")
            # Fallback to empty rules on API failure
            return json.dumps({"rules": []})


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for testing when OpenAI is not available."""
    
    def extract_rules(self, prompt: str) -> str:
        """Return mock JSON response with actual quotes from document."""
        # Extract actual text from the prompt to use as evidence
        lines = prompt.split('\n')
        context_start = False
        document_lines = []
        
        for line in lines:
            if line.startswith('CONTEXT:'):
                context_start = True
                continue
            if context_start and line.startswith('INSTRUCTIONS:'):
                break
            if context_start and line.strip():
                document_lines.append(line.strip())
        
        # Use first meaningful line as evidence quote, or fallback
        evidence_quote = "compliance requirements must be followed"
        if document_lines:
            for line in document_lines:
                if len(line) > 20 and not line.startswith('Segment') and not line.startswith('Document Section:'):
                    evidence_quote = line[:100]  # First 100 chars
                    break
        
        return json.dumps({
            "rules": [
                {
                    "code": "COMP-001",
                    "title": "Compliance Requirement",
                    "requirement": "Organizations must follow applicable compliance requirements",
                    "severity": "medium",
                    "evidence_quotes": [evidence_quote]
                }
            ]
        })


class RuleExtractor:
    """Extracts compliance rules from candidate groups using LLM."""
    
    def __init__(self, llm_provider: LLMProvider = None):
        if llm_provider is None:
            try:
                self.llm_provider = OpenAILLMProvider()
                logger.info("Using OpenAI LLM provider for rule extraction")
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI provider, falling back to mock: {str(e)}")
                self.llm_provider = MockLLMProvider()
        else:
            self.llm_provider = llm_provider
            
        self.prompt_builder = PromptBuilder()
        self.response_parser = ResponseParser()
    
    def extract_from_group(self, group: CandidateGroup, framework_info: dict = None) -> List[ExtractedRule]:
        """Extract 0-3 prescriptive rules from a candidate group."""
        logger.info(f"Starting rule extraction for group: {group.heading_prefix}")
        logger.debug(f"Group contains {len(group.segments)} segments")
        
        try:
            logger.debug("Building extraction prompt")
            prompt = self.prompt_builder.build_extraction_prompt(group, framework_info)
            logger.debug(f"Prompt length: {len(prompt)} characters")
            
            logger.debug("Sending request to LLM provider")
            llm_response = self.llm_provider.extract_rules(prompt)
            logger.debug(f"LLM response length: {len(llm_response)} characters")
            
            logger.debug("Parsing LLM response")
            extracted_rules = self.response_parser.parse_response(llm_response, group.segments)
            logger.info(f"Successfully extracted {len(extracted_rules)} rules from group {group.heading_prefix}")
            
            return extracted_rules
        
        except Exception as e:
            logger.error(f"Failed to extract rules from group {group.heading_prefix}: {str(e)}", exc_info=True)
            return []


class PromptBuilder:
    """Builds prompts for LLM rule extraction."""
    
    def __init__(self):
        # Simple LLM client for focus area generation
        try:
            self.focus_llm = ChatOpenAI(
                model="gpt-3.5-turbo",
                temperature=0.3,
                openai_api_key=settings.OPENAI_API_KEY,
                max_tokens=200
            )
        except Exception as e:
            logger.warning(f"Failed to initialize focus LLM: {str(e)}")
            self.focus_llm = None
    
    def build_extraction_prompt(self, group: CandidateGroup, framework_info: dict = None) -> str:
        """Create extraction prompt for a candidate group."""
        logger.debug(f"Building prompt for group: {group.heading_prefix}")
        context_text = self._build_context_text(group)
        logger.debug(f"Built context text with {len(context_text)} characters")
        
        # Build framework-specific guidance
        framework_guidance = ""
        if framework_info:
            focus_areas = self._get_framework_focus_areas(framework_info)
            framework_guidance = f"""
COMPLIANCE FRAMEWORK: {framework_info['name']}
Framework Description: {framework_info['description']}

Based on this framework, focus on extracting rules related to:
{focus_areas}
"""
        
        return f"""
You are a compliance expert tasked with extracting prescriptive controls from regulatory documents.

{framework_guidance}

Analyze the following document segments and extract 0-3 prescriptive compliance rules that specify concrete actions or requirements.

CONTEXT:
{context_text}

INSTRUCTIONS:
1. Extract only prescriptive rules that specify concrete actions, not descriptive text
2. For each evidence quote, provide the exact character range (start and end positions) in the segment text
3. Use specific, actionable titles and requirements
4. Assign severity: "high" for safety/legal violations, "medium" for compliance violations, "low" for best practices
5. For the code field: EXTRACT the actual regulatory code/identifier from the document text (e.g., "Article 2", "Annex V Part B.6", "2009/48/EC", "Section 2.1"). If no regulatory code exists, use the section number or heading (e.g., "Section_2.1", "Bath_Toys")

OUTPUT FORMAT (strict JSON):
{{
  "rules": [
    {{
      "code": "string",
      "title": "string (max 80 chars)",
      "requirement": "string (max 200 chars)",
      "severity": "high|medium|low",
      "evidence": [
        {{
          "segment_number": 1,
          "start_char": 123,
          "end_char": 245,
          "quote": "exact text from segment"
        }}
      ]
    }}
  ]
}}

IMPORTANT: 
- segment_number refers to "Segment 1", "Segment 2", etc. in the CONTEXT
- start_char and end_char are character positions within that segment's text
- quote must be the EXACT text from those character positions
- Return empty rules array if no prescriptive controls found
- For code field: Use ACTUAL regulatory identifiers from the document (Article numbers, Annex references, directive numbers, section headings). DO NOT make up codes like "SAFETY-001"
"""
    
    def _get_framework_focus_areas(self, framework_info: dict) -> str:
        """Generate focus areas using LLM based on framework description."""
        if not self.focus_llm:
            # Fallback to simple keyword matching
            return self._get_simple_focus_areas(framework_info)
        
        try:
            prompt = f"""
Based on this compliance framework description, list 3-5 specific focus areas for rule extraction:

Framework: {framework_info['name']}
Description: {framework_info['description']}

Provide a bullet-point list of specific compliance focus areas that would be relevant for extracting rules from regulatory documents. Be specific and actionable.
"""
            
            response = self.focus_llm.invoke(prompt)
            focus_areas = response.content.strip()
            logger.debug(f"Generated focus areas using LLM: {focus_areas}")
            return focus_areas
            
        except Exception as e:
            logger.warning(f"Failed to generate focus areas with LLM: {str(e)}")
            return self._get_simple_focus_areas(framework_info)
    
    def _get_simple_focus_areas(self, framework_info: dict) -> str:
        """Simple keyword-based focus areas as fallback."""
        description = framework_info.get('description', '').lower()
        focus_areas = []
        
        if 'chemical' in description or 'reach' in description or 'rohs' in description:
            focus_areas.append("- Chemical safety and substance restrictions")
        if 'children' in description or 'toy' in description or 'age' in description:
            focus_areas.append("- Child safety and age-appropriate design")
        if 'battery' in description or 'lithium' in description:
            focus_areas.append("- Battery safety and handling requirements")
        if 'choking' in description or 'warning' in description:
            focus_areas.append("- Warning labels and choking hazards")
        if 'marking' in description or 'ce' in description or 'ukca' in description:
            focus_areas.append("- Product marking and certification requirements")
        if 'manual' in description or 'user' in description:
            focus_areas.append("- User documentation and safety instructions")
        
        if not focus_areas:
            focus_areas.append("- General compliance and safety requirements")
            
        return '\n'.join(focus_areas)
    
    def _build_context_text(self, group: CandidateGroup) -> str:
        """Build context text from group segments."""
        context = f"Document Section: {group.heading_prefix}\n\n"
        
        for i, segment in enumerate(group.segments):
            context += f"Segment {i+1}:\n{segment.text}\n\n"
        
        return context


class ResponseParser:
    """Parses LLM responses into ExtractedRule objects."""
    
    def parse_response(self, llm_response: str, segments: List[DocumentSegment]) -> List[ExtractedRule]:
        """Parse JSON response into ExtractedRule objects."""
        logger.debug("Starting to parse LLM response")
        
        try:
            data = json.loads(llm_response)
            logger.debug(f"Successfully parsed JSON response with {len(data.get('rules', []))} raw rules")
            
            rules = []
            valid_rules_count = 0
            invalid_rules_count = 0
            
            for i, rule_data in enumerate(data.get('rules', [])):
                logger.debug(f"Processing rule {i+1}: {rule_data.get('title', 'No title')}")
                
                if self._validate_rule_data(rule_data):
                    rule = self._build_extracted_rule(rule_data, segments)
                    if rule:
                        rules.append(rule)
                        valid_rules_count += 1
                        logger.debug(f"Successfully built rule: {rule.code} - {rule.title}")
                    else:
                        invalid_rules_count += 1
                        logger.warning(f"Rule validation passed but building failed for rule: {rule_data.get('title', 'No title')}")
                else:
                    invalid_rules_count += 1
                    logger.warning(f"Rule validation failed for rule: {rule_data.get('title', 'No title')}")
            
            logger.info(f"Parsing complete: {valid_rules_count} valid rules, {invalid_rules_count} invalid rules")
            return rules
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {str(e)}")
            logger.debug(f"Raw LLM response (first 500 chars): {llm_response[:500]}")
            return []
    
    def _validate_rule_data(self, rule_data: Dict[str, Any]) -> bool:
        """Validate rule data structure with character ranges."""
        required_fields = ['code', 'title', 'requirement', 'severity', 'evidence']
        
        missing_fields = [field for field in required_fields if field not in rule_data]
        if missing_fields:
            logger.warning(f"Rule missing required fields: {missing_fields}")
            return False
        
        if rule_data['severity'] not in ['high', 'medium', 'low']:
            logger.warning(f"Invalid severity value: {rule_data['severity']}")
            return False
        
        if not isinstance(rule_data['evidence'], list) or not rule_data['evidence']:
            logger.warning(f"Invalid evidence: must be non-empty list, got {type(rule_data['evidence'])}")
            return False
        
        # Validate evidence structure
        for i, evidence in enumerate(rule_data['evidence']):
            if not isinstance(evidence, dict):
                logger.warning(f"Evidence {i} must be a dictionary")
                return False
            
            required_evidence_fields = ['segment_number', 'start_char', 'end_char', 'quote']
            missing_evidence_fields = [field for field in required_evidence_fields if field not in evidence]
            if missing_evidence_fields:
                logger.warning(f"Evidence {i} missing required fields: {missing_evidence_fields}")
                return False
            
            if not isinstance(evidence['segment_number'], int) or evidence['segment_number'] < 1:
                logger.warning(f"Evidence {i} has invalid segment_number: {evidence['segment_number']}")
                return False
                
            if not isinstance(evidence['start_char'], int) or not isinstance(evidence['end_char'], int):
                logger.warning(f"Evidence {i} has invalid character positions")
                return False
                
            if evidence['start_char'] >= evidence['end_char']:
                logger.warning(f"Evidence {i} has invalid character range: start={evidence['start_char']}, end={evidence['end_char']}")
                return False
        
        logger.debug(f"Rule data validation passed for: {rule_data.get('title', 'No title')}")
        return True
    
    def _build_extracted_rule(self, rule_data: Dict[str, Any], segments: List[DocumentSegment]) -> ExtractedRule:
        """Build ExtractedRule from validated data with character ranges."""
        logger.debug(f"Building extracted rule for: {rule_data['code']} - {rule_data['title']}")
        
        evidence_segments, evidence_quotes = self._map_character_ranges_to_segments(
            rule_data['evidence'], 
            segments
        )
        
        if not evidence_segments:
            logger.warning(f"No evidence segments mapped for rule {rule_data['code']}, skipping rule")
            return None
        
        logger.debug(f"Mapped {len(evidence_segments)} evidence segments for rule {rule_data['code']}")
        
        return ExtractedRule(
            code=rule_data['code'],
            title=rule_data['title'],
            requirement=rule_data['requirement'],
            severity=Severity(rule_data['severity']),
            evidence_quotes=evidence_quotes,
            evidence_segments=evidence_segments
        )
    
    def _map_character_ranges_to_segments(self, evidence_list: List[Dict], segments: List[DocumentSegment]) -> Tuple[List[DocumentSegment], List[str]]:
        """Map character ranges to segments and extract precise quotes."""
        logger.debug(f"Mapping {len(evidence_list)} character ranges to {len(segments)} segments")
        mapped_segments = []
        extracted_quotes = []
        
        for evidence in evidence_list:
            segment_number = evidence['segment_number']
            start_char = evidence['start_char']
            end_char = evidence['end_char']
            expected_quote = evidence['quote']
            
            # Find the corresponding segment (1-based indexing)
            if segment_number < 1 or segment_number > len(segments):
                logger.warning(f"Invalid segment_number {segment_number}, must be between 1 and {len(segments)}")
                continue
                
            segment = segments[segment_number - 1]  # Convert to 0-based
            
            # Validate character range
            if start_char < 0 or end_char > len(segment.text) or start_char >= end_char:
                logger.warning(f"Invalid character range [{start_char}:{end_char}] for segment {segment_number} (text length: {len(segment.text)})")
                continue
            
            # Extract actual quote using character range
            actual_quote = segment.text[start_char:end_char]
            
            # Verify the quote matches what LLM claimed
            if actual_quote.strip() != expected_quote.strip():
                logger.warning(f"Quote mismatch in segment {segment_number}. Expected: '{expected_quote[:50]}...', Got: '{actual_quote[:50]}...'")
                # Use actual quote from character range (more reliable)
                
            mapped_segments.append(segment)
            extracted_quotes.append(actual_quote)
            logger.debug(f"Mapped character range [{start_char}:{end_char}] to segment {segment.id}: '{actual_quote[:50]}...'")
        
        logger.debug(f"Successfully mapped {len(mapped_segments)} out of {len(evidence_list)} character ranges")
        return mapped_segments, extracted_quotes
    
    def _map_quotes_to_segments(self, quotes: List[str], segments: List[DocumentSegment]) -> List[DocumentSegment]:
        """Legacy method - map evidence quotes back to source segments."""
        logger.debug(f"Using legacy quote mapping for {len(quotes)} quotes")
        mapped_segments = []
        
        for quote in quotes:
            for segment in segments:
                if quote.strip() in segment.text:
                    mapped_segments.append(segment)
                    logger.debug(f"Mapped quote to segment {segment.id}: '{quote[:50]}...'")
                    break
        
        return mapped_segments