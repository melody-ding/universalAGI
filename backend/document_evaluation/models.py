from pydantic import BaseModel
from typing import List, Optional, Dict


class ComplianceIssue(BaseModel):
    rule_code: str
    issue_type: str
    description: str
    severity: str


class SegmentComplianceResult(BaseModel):
    segment_ordinal: int
    segment_preview: str
    applicable_rules: List[Dict]
    compliance_status: str
    issues_found: List[ComplianceIssue]
    confidence_score: float


class DocumentEvaluationRequest(BaseModel):
    framework_id: str


class DocumentEvaluationResponse(BaseModel):
    document_name: str
    framework_id: str
    total_segments: int
    segments_processed: int
    overall_compliance_score: float
    segment_results: List[SegmentComplianceResult]
    summary: str
    status: str = "success"
    message: Optional[str] = None