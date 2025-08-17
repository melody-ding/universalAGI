import re
from typing import Set
from .models import DocumentSegment


class SegmentScorer:
    """Scores document segments for rule extraction potential."""
    
    # Scoring weights
    OBLIGATION_WEIGHT = 3.0
    CONTROL_WEIGHT = 2.0
    STRUCTURE_WEIGHT = 1.5
    HEADING_WEIGHT = 2.0
    THRESHOLD_WEIGHT = 2.5
    LENGTH_BONUS = 1.0
    LONG_PENALTY = 0.8
    
    def __init__(self):
        self.obligation_words = self._load_obligation_words()
        self.control_keywords = self._load_control_keywords()
    
    def score(self, segment: DocumentSegment) -> float:
        """Calculate comprehensive score for a segment."""
        text_lower = segment.text.lower()
        score = 0.0
        
        score += self._score_obligations(text_lower)
        score += self._score_controls(text_lower)
        score += self._score_structure(segment.text)
        score += self._score_headings(segment)
        score += self._score_thresholds(text_lower)
        score += self._score_length(segment.text)
        
        return score
    
    def _score_obligations(self, text_lower: str) -> float:
        """Score based on obligation words."""
        count = sum(1 for word in self.obligation_words if word in text_lower)
        return count * self.OBLIGATION_WEIGHT
    
    def _score_controls(self, text_lower: str) -> float:
        """Score based on control keywords."""
        count = sum(1 for word in self.control_keywords if word in text_lower)
        return count * self.CONTROL_WEIGHT
    
    def _score_structure(self, text: str) -> float:
        """Score based on structural elements."""
        if re.search(r'^\s*[\-\*\•]|\d+\.|\([a-z]\)', text, re.MULTILINE):
            return self.STRUCTURE_WEIGHT
        return 0.0
    
    def _score_headings(self, segment: DocumentSegment) -> float:
        """Score based on heading presence."""
        if segment.heading_path:
            return len(segment.heading_path) * self.HEADING_WEIGHT
        return 0.0
    
    def _score_thresholds(self, text_lower: str) -> float:
        """Score based on numeric thresholds."""
        if re.search(r'\d+\s*(days?|hours?|minutes?|%|percent|times?)', text_lower):
            return self.THRESHOLD_WEIGHT
        return 0.0
    
    def _score_length(self, text: str) -> float:
        """Score based on text length (favor medium-length)."""
        length = len(text)
        if 100 <= length <= 1000:
            return self.LENGTH_BONUS
        elif length > 1000:
            return -0.2  # Small penalty for very long segments
        return 0.0
    
    def _load_obligation_words(self) -> Set[str]:
        """Load obligation vocabulary."""
        return {
            'must', 'shall', 'required', 'mandatory', 'obligatory', 'compulsory',
            'should', 'ought', 'recommended', 'advised', 'expected',
            'prohibited', 'forbidden', 'banned', 'not permitted',
            'ensure', 'verify', 'confirm', 'validate', 'guarantee'
        }
    
    def _load_control_keywords(self) -> Set[str]:
        """Load control vocabulary."""
        return {
            'control', 'policy', 'procedure', 'process', 'mechanism',
            'safeguard', 'measure', 'protection', 'security', 'compliance',
            'requirement', 'standard', 'guideline', 'framework', 'regulation'
        }