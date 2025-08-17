from typing import List, Set
from collections import defaultdict

from .models import ExtractedRule, Severity
from utils.logging_config import get_logger

logger = get_logger(__name__)


class RuleValidator:
    """Validates, deduplicates, and caps extracted rules."""
    
    MAX_FINAL_RULES = 12
    
    def validate_and_deduplicate(self, rules: List[ExtractedRule]) -> List[ExtractedRule]:
        """Validate, deduplicate, and cap the final rule set."""
        valid_rules = self._filter_valid_rules(rules)
        deduplicated_rules = self._deduplicate_rules(valid_rules)
        capped_rules = self._cap_rules(deduplicated_rules)
        
        return capped_rules
    
    def _filter_valid_rules(self, rules: List[ExtractedRule]) -> List[ExtractedRule]:
        """Filter out rules without mappable evidence."""
        return [rule for rule in rules if rule.evidence_segments]
    
    def _deduplicate_rules(self, rules: List[ExtractedRule]) -> List[ExtractedRule]:
        """Remove duplicate rules and merge evidence."""
        title_to_rules = defaultdict(list)
        
        # Group rules by normalized title
        for rule in rules:
            normalized_title = self._normalize_title(rule.title)
            title_to_rules[normalized_title].append(rule)
        
        # Merge duplicates
        merged_rules = []
        for title_group in title_to_rules.values():
            merged_rule = self._merge_rule_group(title_group)
            merged_rules.append(merged_rule)
        
        return merged_rules
    
    def _normalize_title(self, title: str) -> str:
        """Normalize title for deduplication."""
        return title.lower().strip()
    
    def _merge_rule_group(self, rule_group: List[ExtractedRule]) -> ExtractedRule:
        """Merge a group of similar rules."""
        primary_rule = rule_group[0]
        
        if len(rule_group) == 1:
            return primary_rule
        
        # Merge evidence from all rules
        all_quotes = []
        all_segments = []
        
        for rule in rule_group:
            all_quotes.extend(rule.evidence_quotes)
            all_segments.extend(rule.evidence_segments)
        
        # Deduplicate evidence
        unique_quotes = list(dict.fromkeys(all_quotes))  # Preserves order
        unique_segments = self._deduplicate_segments(all_segments)
        
        return ExtractedRule(
            code=primary_rule.code,
            title=primary_rule.title,
            requirement=primary_rule.requirement,
            severity=self._select_highest_severity(rule_group),
            evidence_quotes=unique_quotes,
            evidence_segments=unique_segments
        )
    
    def _deduplicate_segments(self, segments):
        """Remove duplicate segments by ID."""
        seen_ids = set()
        unique_segments = []
        
        for segment in segments:
            if segment.id not in seen_ids:
                seen_ids.add(segment.id)
                unique_segments.append(segment)
        
        return unique_segments
    
    def _select_highest_severity(self, rule_group: List[ExtractedRule]) -> Severity:
        """Select the highest severity from a group of rules."""
        severity_order = {Severity.HIGH: 0, Severity.MEDIUM: 1, Severity.LOW: 2}
        
        highest_severity = min(rule_group, key=lambda r: severity_order[r.severity])
        return highest_severity.severity
    
    def _cap_rules(self, rules: List[ExtractedRule]) -> List[ExtractedRule]:
        """Cap rules to maximum limit, prioritizing by severity."""
        sorted_rules = self._sort_by_priority(rules)
        return sorted_rules[:self.MAX_FINAL_RULES]
    
    def _sort_by_priority(self, rules: List[ExtractedRule]) -> List[ExtractedRule]:
        """Sort rules by severity priority."""
        severity_order = {Severity.HIGH: 0, Severity.MEDIUM: 1, Severity.LOW: 2}
        
        return sorted(rules, key=lambda r: (
            severity_order[r.severity],
            -len(r.evidence_segments),  # More evidence = higher priority
            r.title  # Alphabetical as tiebreaker
        ))