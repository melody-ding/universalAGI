"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { DocumentEvaluationResponse } from "@/lib/api/compliance-groups";

interface AnalysisSummaryProps {
  result: DocumentEvaluationResponse;
}

export function AnalysisSummary({ result }: AnalysisSummaryProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Analysis Summary</CardTitle>
        <CardDescription>
          Results for: {result.document_name}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
          <div className="text-center p-3 bg-blue-50 rounded-lg">
            <div className="text-2xl font-bold text-blue-600">
              {result.total_segments}
            </div>
            <div className="text-sm text-blue-700">Total Segments</div>
          </div>
          <div className="text-center p-3 bg-green-50 rounded-lg">
            <div className="text-2xl font-bold text-green-600">
              {Math.round(result.overall_compliance_score * 100)}%
            </div>
            <div className="text-sm text-green-700">Compliance Score</div>
          </div>
          <div className="text-center p-3 bg-purple-50 rounded-lg">
            <div className="text-2xl font-bold text-purple-600">
              {result.segments_processed}
            </div>
            <div className="text-sm text-purple-700">Segments Processed</div>
          </div>
        </div>
        <p className="text-sm text-gray-700 bg-gray-50 p-3 rounded-lg">
          {result.summary}
        </p>
      </CardContent>
    </Card>
  );
}