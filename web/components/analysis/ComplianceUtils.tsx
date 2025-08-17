import { CheckCircle, AlertTriangle, XCircle, Clock } from "lucide-react";

export const getComplianceStatusColor = (status: string) => {
  switch (status) {
    case 'compliant': return 'text-green-600 bg-green-50 border-green-200';
    case 'needs_review': return 'text-yellow-600 bg-yellow-50 border-yellow-200';
    case 'non_compliant': return 'text-red-600 bg-red-50 border-red-200';
    case 'no_applicable_rules': return 'text-gray-600 bg-gray-50 border-gray-200';
    default: return 'text-gray-600 bg-gray-50 border-gray-200';
  }
};

export const getComplianceStatusIcon = (status: string) => {
  switch (status) {
    case 'compliant': return <CheckCircle className="h-4 w-4" />;
    case 'needs_review': return <AlertTriangle className="h-4 w-4" />;
    case 'non_compliant': return <XCircle className="h-4 w-4" />;
    case 'no_applicable_rules': return <Clock className="h-4 w-4" />;
    default: return <Clock className="h-4 w-4" />;
  }
};

export const formatComplianceStatus = (status: string) => {
  switch (status) {
    case 'compliant': return 'Compliant';
    case 'needs_review': return 'Needs Review';
    case 'non_compliant': return 'Non-Compliant';
    case 'no_applicable_rules': return 'No Rules Applied';
    default: return status.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
  }
};

export const getSeverityColor = (severity: string) => {
  switch (severity) {
    case 'high': return 'text-red-600 bg-red-100';
    case 'medium': return 'text-yellow-600 bg-yellow-100';
    case 'low': return 'text-blue-600 bg-blue-100';
    default: return 'text-gray-600 bg-gray-100';
  }
};