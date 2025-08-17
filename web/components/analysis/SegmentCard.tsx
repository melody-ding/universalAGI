"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { SegmentComplianceResult } from "@/lib/api/compliance-groups";
import { 
  getComplianceStatusColor, 
  getComplianceStatusIcon, 
  formatComplianceStatus,
  getSeverityColor 
} from "./ComplianceUtils";

interface SegmentCardProps {
  segment: SegmentComplianceResult;
}

export function SegmentCard({ segment }: SegmentCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <Card className="border-l-4 border-l-gray-200">
      <CardContent className="p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center space-x-3">
            <Badge variant="outline" className="text-xs">
              Segment {segment.segment_ordinal + 1}
            </Badge>
            <Badge 
              className={`text-xs ${getComplianceStatusColor(segment.compliance_status)}`}
            >
              {getComplianceStatusIcon(segment.compliance_status)}
              <span className="ml-1">{formatComplianceStatus(segment.compliance_status)}</span>
            </Badge>
            <Badge variant="outline" className="text-xs">
              {Math.round(segment.confidence_score * 100)}% confidence
            </Badge>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsExpanded(!isExpanded)}
          >
            {isExpanded ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
          </Button>
        </div>

        <p className="text-sm text-gray-700 mb-3 font-mono bg-gray-50 p-2 rounded">
          {segment.segment_preview}
        </p>

        {isExpanded && (
          <div className="space-y-4 border-t pt-4">
            {/* Applicable Rules */}
            {segment.applicable_rules.length > 0 && (
              <div>
                <h4 className="font-medium text-sm text-gray-900 mb-2">
                  Applicable Rules ({segment.applicable_rules.length})
                </h4>
                <div className="space-y-2">
                  {segment.applicable_rules.map((rule, idx) => (
                    <div key={idx} className="text-xs bg-blue-50 p-2 rounded">
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-medium text-blue-900">{rule.code}</span>
                        <Badge className={`${getSeverityColor(rule.severity)} text-xs`}>
                          {rule.severity}
                        </Badge>
                      </div>
                      <p className="text-blue-800 font-medium">{rule.title}</p>
                      <p className="text-blue-700 mt-1">{rule.requirement}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Issues Found */}
            {segment.issues_found.length > 0 && (
              <div>
                <h4 className="font-medium text-sm text-gray-900 mb-2">
                  Issues Found ({segment.issues_found.length})
                </h4>
                <div className="space-y-2">
                  {segment.issues_found.map((issue, idx) => (
                    <div key={idx} className="text-xs bg-red-50 p-2 rounded border-l-2 border-red-200">
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-medium text-red-900">{issue.rule_code}</span>
                        <Badge className={`${getSeverityColor(issue.severity)} text-xs`}>
                          {issue.severity}
                        </Badge>
                      </div>
                      <p className="text-red-800 font-medium capitalize">
                        {issue.issue_type.replace(/_/g, ' ')}
                      </p>
                      <p className="text-red-700 mt-1">{issue.description}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}