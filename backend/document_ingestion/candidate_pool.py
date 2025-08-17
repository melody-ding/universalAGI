from typing import List, Dict
from collections import defaultdict

from .models import DocumentSegment
from .scoring import SegmentScorer


class CandidatePoolBuilder:
    """Builds high-recall candidate pool for rule extraction."""
    
    MAX_GLOBAL_CANDIDATES = 200
    MAX_CHAPTER_CANDIDATES = 10
    FAMILY_CANDIDATES_PER_THEME = 2
    
    FAMILY_THEMES = {
        'encryption': ['encrypt', 'cipher', 'cryptograph', 'key management', 'ssl', 'tls'],
        'logging': ['log', 'audit', 'record', 'monitor', 'track'],
        'retention': ['retain', 'archive', 'delete', 'purge', 'lifecycle'],
        'residency': ['location', 'geographic', 'jurisdiction', 'country', 'region'],
        'access': ['access', 'authorization', 'authentication', 'permission', 'privilege'],
        'backup': ['backup', 'recovery', 'restore', 'disaster', 'continuity']
    }
    
    def __init__(self):
        self.scorer = SegmentScorer()
    
    def build_pool(self, segments: List[DocumentSegment]) -> List[DocumentSegment]:
        """Build comprehensive candidate pool with scoring and coverage."""
        # Score all segments
        for segment in segments:
            segment.score = self.scorer.score(segment)
        
        # Get candidates from different strategies
        global_candidates = self._get_global_top_k(segments)
        chapter_candidates = self._ensure_chapter_coverage(segments)
        family_candidates = self._family_sweep(segments)
        
        # Union and deduplicate
        return self._deduplicate_candidates([
            *global_candidates,
            *chapter_candidates, 
            *family_candidates
        ])
    
    def _get_global_top_k(self, segments: List[DocumentSegment]) -> List[DocumentSegment]:
        """Get globally highest-scoring segments."""
        sorted_segments = sorted(segments, key=lambda s: s.score, reverse=True)
        return sorted_segments[:self.MAX_GLOBAL_CANDIDATES]
    
    def _ensure_chapter_coverage(self, segments: List[DocumentSegment]) -> List[DocumentSegment]:
        """Ensure each chapter contributes candidates."""
        chapter_groups = self._group_by_chapter(segments)
        
        coverage_candidates = []
        for chapter_segments in chapter_groups.values():
            sorted_chapter = sorted(chapter_segments, key=lambda s: s.score, reverse=True)
            coverage_candidates.extend(sorted_chapter[:self.MAX_CHAPTER_CANDIDATES])
        
        return coverage_candidates
    
    def _group_by_chapter(self, segments: List[DocumentSegment]) -> Dict[str, List[DocumentSegment]]:
        """Group segments by chapter (document + first heading)."""
        chapters = defaultdict(list)
        
        for segment in segments:
            chapter_key = f"doc_{segment.document_id}"
            if segment.heading_path:
                chapter_key += f"_{segment.heading_path[0]}"
            chapters[chapter_key].append(segment)
        
        return chapters
    
    def _family_sweep(self, segments: List[DocumentSegment]) -> List[DocumentSegment]:
        """Add thematic coverage across compliance families."""
        family_candidates = []
        
        for theme, keywords in self.FAMILY_THEMES.items():
            theme_segments = self._find_theme_segments(segments, keywords)
            if theme_segments:
                sorted_theme = sorted(theme_segments, key=lambda s: s.score, reverse=True)
                family_candidates.extend(sorted_theme[:self.FAMILY_CANDIDATES_PER_THEME])
        
        return family_candidates
    
    def _find_theme_segments(self, segments: List[DocumentSegment], keywords: List[str]) -> List[DocumentSegment]:
        """Find segments matching thematic keywords."""
        matching_segments = []
        
        for segment in segments:
            text_lower = segment.text.lower()
            if any(keyword in text_lower for keyword in keywords):
                matching_segments.append(segment)
        
        return matching_segments
    
    def _deduplicate_candidates(self, candidates: List[DocumentSegment]) -> List[DocumentSegment]:
        """Remove duplicate candidates and sort by score."""
        seen_ids = set()
        unique_candidates = []
        
        for candidate in candidates:
            if candidate.id not in seen_ids:
                seen_ids.add(candidate.id)
                unique_candidates.append(candidate)
        
        return sorted(unique_candidates, key=lambda s: s.score, reverse=True)