from dataclasses import dataclass
from typing import List, Optional
from enum import Enum


class Severity(Enum):
    HIGH = "high"
    MEDIUM = "medium" 
    LOW = "low"


@dataclass
class DocumentSegment:
    """Document segment with extraction metadata."""
    id: int
    document_id: int
    segment_ordinal: int
    text: str
    heading_path: List[str]
    chapter_level: int
    score: float = 0.0


@dataclass
class CandidateGroup:
    """Group of candidate segments for rule extraction."""
    heading_prefix: str
    segments: List[DocumentSegment]
    density_score: float


@dataclass
class ExtractedRule:
    """Extracted compliance rule with evidence."""
    code: str
    title: str
    requirement: str
    severity: Severity
    evidence_quotes: List[str]
    evidence_segments: List[DocumentSegment]


@dataclass
class ExtractionResult:
    """Result of rule extraction process."""
    success: bool
    framework_id: str
    rules_extracted: int
    rules: List[ExtractedRule]
    error: Optional[str] = None