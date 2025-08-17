"use client";

import { useRef } from "react";
import { Button } from "@/components/ui/button";
import { Upload, FileText } from "lucide-react";

interface DocumentUploadSectionProps {
  selectedFile: File | null;
  onFileSelect: (file: File) => void;
  isAnalyzing: boolean;
  onRunAnalysis: () => void;
}

export function DocumentUploadSection({ 
  selectedFile, 
  onFileSelect, 
  isAnalyzing, 
  onRunAnalysis 
}: DocumentUploadSectionProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      onFileSelect(file);
    }
  };

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4">
        <Button 
          onClick={handleUploadClick} 
          variant="outline"
          disabled={isAnalyzing}
        >
          <Upload className="h-4 w-4 mr-2" />
          Select Document
        </Button>
        {selectedFile && (
          <div className="flex items-center text-sm text-gray-600">
            <FileText className="h-4 w-4 mr-2" />
            <span className="font-medium">{selectedFile.name}</span>
            <span className="text-gray-400 ml-2">({formatFileSize(selectedFile.size)})</span>
          </div>
        )}
      </div>

      {selectedFile && (
        <Button 
          onClick={onRunAnalysis} 
          disabled={isAnalyzing}
          className="w-full"
        >
          {isAnalyzing ? (
            <>
              <div className="h-4 w-4 mr-2 animate-spin rounded-full border-2 border-white border-t-transparent" />
              Analyzing Document...
            </>
          ) : (
            <>
              <FileText className="h-4 w-4 mr-2" />
              Run Compliance Analysis
            </>
          )}
        </Button>
      )}

      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.doc,.docx,.txt"
        onChange={handleFileSelect}
        className="hidden"
      />
    </div>
  );
}