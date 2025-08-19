import { API_BASE_URL } from '../api';

export interface ComplianceGroup {
  id: string;
  name: string;
  description?: string;
  created_at: string;
  updated_at: string;
}

export interface CreateComplianceGroupRequest {
  name: string;
  description?: string;
}

export interface UpdateComplianceGroupRequest {
  name?: string;
  description?: string;
}

export interface ComplianceGroupsResponse {
  compliance_groups: ComplianceGroup[];
}

export interface ComplianceGroupResponse extends ComplianceGroup {
  status: string;
}

export interface ComplianceGroupDocument {
  id: number;
  title: string;
  checksum: string;
  blob_link: string;
  created_at: string;
  mime_type?: string;
  compliance_framework_id?: string;
}

export interface ComplianceGroupDocumentsResponse {
  documents: ComplianceGroupDocument[];
  compliance_group: {
    id: string;
    name: string;
  };
}

export interface ComplianceIssue {
  rule_code: string;
  issue_type: string;
  description: string;
  severity: string;
}

export interface SegmentComplianceResult {
  segment_ordinal: number;
  segment_preview: string;
  applicable_rules: Array<{
    code: string;
    title: string;
    requirement: string;
    severity: string;
  }>;
  compliance_status: string;
  issues_found: ComplianceIssue[];
  confidence_score: number;
}

export interface DocumentEvaluationResponse {
  document_name: string;
  framework_id: string;
  total_segments: number;
  segments_processed: number;
  overall_compliance_score: number;
  segment_results: SegmentComplianceResult[];
  summary: string;
  status: string;
  message?: string;
}

class ComplianceGroupsAPI {
  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${API_BASE_URL}${endpoint}`;
    
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(
        errorData.detail || 
        errorData.message || 
        `API request failed: ${response.status} ${response.statusText}`
      );
    }

    return response.json();
  }

  async getAllComplianceGroups(): Promise<ComplianceGroup[]> {
    const response = await this.request<ComplianceGroupsResponse>('/compliance-groups');
    return response.compliance_groups;
  }

  async getComplianceGroup(id: string): Promise<ComplianceGroup> {
    return this.request<ComplianceGroup>(`/compliance-groups/${id}`);
  }

  async createComplianceGroup(data: CreateComplianceGroupRequest): Promise<ComplianceGroupResponse> {
    return this.request<ComplianceGroupResponse>('/compliance-groups', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateComplianceGroup(
    id: string, 
    data: UpdateComplianceGroupRequest
  ): Promise<ComplianceGroupResponse> {
    return this.request<ComplianceGroupResponse>(`/compliance-groups/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteComplianceGroup(id: string): Promise<{ message: string; status: string }> {
    return this.request<{ message: string; status: string }>(`/compliance-groups/${id}`, {
      method: 'DELETE',
    });
  }

  async getComplianceGroupDocuments(id: string): Promise<ComplianceGroupDocumentsResponse> {
    return this.request<ComplianceGroupDocumentsResponse>(`/compliance-groups/${id}/documents`);
  }

  async evaluateDocument(file: File, frameworkId: string): Promise<DocumentEvaluationResponse> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('framework_id', frameworkId);

    const url = `${API_BASE_URL}/evaluate-document`;
    
    const response = await fetch(url, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(
        errorData.detail || 
        errorData.message || 
        `Document evaluation failed: ${response.status} ${response.statusText}`
      );
    }

    return response.json();
  }
}

export const complianceGroupsAPI = new ComplianceGroupsAPI();
