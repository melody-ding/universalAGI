"use client";

import { useState, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Upload, FileText, Trash2, Download, Eye } from "lucide-react";

interface Document {
  id: string;
  name: string;
  size: number;
  type: string;
  uploadedAt: Date;
  status: 'uploading' | 'processing' | 'ready' | 'error';
}

interface DocumentUploadProps {
  onUpload: (file: File) => Promise<void>;
  hasExistingDocuments?: boolean;
  className?: string;
}

export function DocumentUpload({ onUpload, hasExistingDocuments = false, className = "" }: DocumentUploadProps) {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (files) {
      Array.from(files).forEach(file => {
        const document: Document = {
          id: Date.now().toString() + Math.random().toString(36).substr(2, 9),
          name: file.name,
          size: file.size,
          type: file.type,
          uploadedAt: new Date(),
          status: 'uploading'
        };

        setDocuments(prev => [...prev, document]);
        uploadFile(file, document.id);
      });
    }
  };

  const uploadFile = async (file: File, documentId: string) => {
    try {
      setDocuments(prev => prev.map(doc => 
        doc.id === documentId ? { ...doc, status: 'processing' } : doc
      ));

      await onUpload(file);

      setDocuments(prev => prev.map(doc => 
        doc.id === documentId ? { ...doc, status: 'ready' } : doc
      ));
    } catch (error) {
      console.error('Upload error:', error);
      setDocuments(prev => prev.map(doc => 
        doc.id === documentId ? { ...doc, status: 'error' } : doc
      ));
    }
  };

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const removeDocument = (documentId: string) => {
    setDocuments(prev => prev.filter(doc => doc.id !== documentId));
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const getStatusColor = (status: Document['status']) => {
    switch (status) {
      case 'uploading': return 'text-blue-600';
      case 'processing': return 'text-yellow-600';
      case 'ready': return 'text-green-600';
      case 'error': return 'text-red-600';
      default: return 'text-gray-600';
    }
  };

  const getStatusText = (status: Document['status']) => {
    switch (status) {
      case 'uploading': return 'Uploading...';
      case 'processing': return 'Processing...';
      case 'ready': return 'Ready';
      case 'error': return 'Error';
      default: return 'Unknown';
    }
  };

  return (
    <div className={className}>
      <div className="flex items-center justify-between mb-6">
        <Button onClick={handleUploadClick} disabled={isUploading}>
          <Upload className="w-4 h-4 mr-2" />
          Upload Documents
        </Button>
      </div>

      {documents.length === 0 && !hasExistingDocuments ? (
        <Card className="text-center py-12">
          <CardContent>
            <FileText className="w-12 h-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">No documents yet</h3>
            <p className="text-gray-600 mb-4">Upload your first document to get started</p>
            <Button onClick={handleUploadClick}>
              <Upload className="w-4 h-4 mr-2" />
              Upload Documents
            </Button>
          </CardContent>
        </Card>
      ) : documents.length > 0 ? (
        <div>
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Upload Queue</h2>
          <div className="grid gap-4">
            {documents.map((document) => (
              <Card key={document.id}>
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                      <FileText className="w-8 h-8 text-blue-600" />
                      <div>
                        <h3 className="font-medium text-gray-900">{document.name}</h3>
                        <div className="flex items-center space-x-4 text-sm text-gray-500">
                          <span>{formatFileSize(document.size)}</span>
                          <span>•</span>
                          <span>{document.uploadedAt.toLocaleDateString()}</span>
                          <span>•</span>
                          <span className={getStatusColor(document.status)}>
                            {getStatusText(document.status)}
                          </span>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      {document.status === 'ready' && (
                        <>
                          <Button variant="outline" size="sm">
                            <Eye className="w-4 h-4" />
                          </Button>
                          <Button variant="outline" size="sm">
                            <Download className="w-4 h-4" />
                          </Button>
                        </>
                      )}
                      <Button 
                        variant="outline" 
                        size="sm" 
                        onClick={() => removeDocument(document.id)}
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      ) : null}

      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept=".pdf,.doc,.docx,.txt,.md,.csv,.xlsx,.xls"
        onChange={handleFileSelect}
        className="hidden"
      />
    </div>
  );
}