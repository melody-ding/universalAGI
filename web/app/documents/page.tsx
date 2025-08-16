"use client";

import { useState, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Upload, FileText, Trash2, Download, Eye } from "lucide-react";

interface Document {
  id: string;
  name: string;
  size: number;
  type: string;
  uploadedAt: Date;
  status: 'uploading' | 'processing' | 'ready' | 'error';
}

export default function DocumentsPage() {
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
    const formData = new FormData();
    formData.append('file', file);

    try {
      // Update status to processing
      setDocuments(prev => prev.map(doc => 
        doc.id === documentId ? { ...doc, status: 'processing' } : doc
      ));

      // Simulate upload to backend
      const response = await fetch('http://localhost:8000/upload-document', {
        method: 'POST',
        body: formData,
      });

      if (response.ok) {
        setDocuments(prev => prev.map(doc => 
          doc.id === documentId ? { ...doc, status: 'ready' } : doc
        ));
      } else {
        throw new Error('Upload failed');
      }
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
    <div className="flex flex-col h-full">
      <div className="p-6 border-b">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Documents</h1>
            <p className="text-gray-600 mt-1">Upload and manage your documents</p>
          </div>
          <Button onClick={handleUploadClick} disabled={isUploading}>
            <Upload className="w-4 h-4 mr-2" />
            Upload Documents
          </Button>
        </div>
      </div>

      <div className="flex-1 overflow-hidden">
        <ScrollArea className="h-full">
          <div className="p-6">
            {documents.length === 0 ? (
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
            ) : (
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
            )}
          </div>
        </ScrollArea>
      </div>

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
