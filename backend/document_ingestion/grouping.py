from typing import List
from collections import defaultdict

from .models import DocumentSegment, CandidateGroup


class SectionGrouper:
    """Groups candidate segments by section for coherent rule extraction."""
    
    MAX_SEGMENTS_PER_GROUP = 5
    MIN_SEGMENTS_PER_GROUP = 2
    
    def group_by_section(self, candidates: List[DocumentSegment]) -> List[CandidateGroup]:
        """Group candidates by heading path for coherent processing."""
        section_groups = self._create_section_groups(candidates)
        candidate_groups = self._build_candidate_groups(section_groups)
        
        return self._sort_by_density(candidate_groups)
    
    def _create_section_groups(self, candidates: List[DocumentSegment]) -> dict:
        """Create groups based on heading hierarchy."""
        groups = defaultdict(list)
        
        for candidate in candidates:
            group_key = self._generate_group_key(candidate)
            groups[group_key].append(candidate)
        
        return groups
    
    def _generate_group_key(self, segment: DocumentSegment) -> str:
        """Generate grouping key from heading path."""
        if segment.heading_path:
            key = segment.heading_path[0]
            if len(segment.heading_path) > 1:
                key += f" > {segment.heading_path[1]}"
            return key
        
        return f"Document_{segment.document_id}_General"
    
    def _build_candidate_groups(self, section_groups: dict) -> List[CandidateGroup]:
        """Convert section groups to CandidateGroup objects."""
        groups = []
        
        for heading_prefix, group_segments in section_groups.items():
            if len(group_segments) >= self.MIN_SEGMENTS_PER_GROUP:
                limited_segments = self._limit_group_size(group_segments)
                density_score = self._calculate_density(limited_segments)
                
                groups.append(CandidateGroup(
                    heading_prefix=heading_prefix,
                    segments=limited_segments,
                    density_score=density_score
                ))
        
        return groups
    
    def _limit_group_size(self, segments: List[DocumentSegment]) -> List[DocumentSegment]:
        """Limit group to top-scoring segments."""
        sorted_segments = sorted(segments, key=lambda s: s.score, reverse=True)
        return sorted_segments[:self.MAX_SEGMENTS_PER_GROUP]
    
    def _calculate_density(self, segments: List[DocumentSegment]) -> float:
        """Calculate group density score."""
        if not segments:
            return 0.0
        
        return sum(s.score for s in segments) / len(segments)
    
    def _sort_by_density(self, groups: List[CandidateGroup]) -> List[CandidateGroup]:
        """Sort groups by density score."""
        return sorted(groups, key=lambda g: g.density_score, reverse=True)