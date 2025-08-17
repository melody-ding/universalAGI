"use client";

import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { FileText } from "lucide-react";
import { complianceGroupsAPI, type DocumentEvaluationResponse } from "@/lib/api/compliance-groups";
import { DocumentUploadSection } from "./DocumentUploadSection";
import { AnalysisSummary } from "./AnalysisSummary";
import { SegmentAnalysisList } from "./SegmentAnalysisList";
import { ErrorDisplay } from "./ErrorDisplay";

interface DocumentAnalysisProps {
  frameworkId: string;
  frameworkName: string;
}

export function DocumentAnalysis({ frameworkId, frameworkName }: DocumentAnalysisProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<DocumentEvaluationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleFileSelect = (file: File) => {
    setSelectedFile(file);
    setAnalysisResult(null);
    setError(null);
  };

  const runAnalysis = async () => {
    if (!selectedFile) {
      setError("Please select a file first");
      return;
    }

    setIsAnalyzing(true);
    setError(null);

    try {
      const result = await complianceGroupsAPI.evaluateDocument(selectedFile, frameworkId);
      setAnalysisResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed');
      console.error('Analysis error:', err);
    } finally {
      setIsAnalyzing(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center">
          <FileText className="h-5 w-5 mr-2 text-blue-600" />
          Run Analysis
        </CardTitle>
        <CardDescription>
          Upload a document to analyze it against the {frameworkName} compliance framework
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <DocumentUploadSection
          selectedFile={selectedFile}
          onFileSelect={handleFileSelect}
          isAnalyzing={isAnalyzing}
          onRunAnalysis={runAnalysis}
        />

        {error && (
          <ErrorDisplay error={error} onDismiss={() => setError(null)} />
        )}

        {analysisResult && (
          <div className="space-y-6">
            <AnalysisSummary result={analysisResult} />
            <SegmentAnalysisList segments={analysisResult.segment_results} />
          </div>
        )}
      </CardContent>
    </Card>
  );
}