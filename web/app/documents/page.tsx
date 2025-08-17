"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { ScrollArea } from "@/components/ui/scroll-area";
import { DocumentUpload } from "@/components/DocumentUpload";
import { DocumentTable } from "@/components/DocumentTable";
import { CitationTest } from "@/components/CitationTest";
import { Button } from "@/components/ui/button";
import { apiEndpoints } from "@/lib/api";

interface UploadedDocument {
  id: number;
  title: string;
  checksum: string;
  blob_link: string;
  created_at: string;
  mime_type?: string;
  compliance_framework_id?: string;
}

export default function DocumentsPage() {
  const [uploadedDocuments, setUploadedDocuments] = useState<UploadedDocument[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showCitationTest, setShowCitationTest] = useState(false);
  const router = useRouter();

  useEffect(() => {
    fetchUploadedDocuments();
  }, []);

  const fetchUploadedDocuments = async () => {
    try {
      setIsLoading(true);
      const response = await fetch(apiEndpoints.getDocuments);
      if (response.ok) {
        const data = await response.json();
        setUploadedDocuments(data.documents);
      } else {
        console.error('Failed to fetch documents, status:', response.status);
      }
    } catch (error) {
      console.error('Error fetching documents:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleUpload = async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(apiEndpoints.uploadDocument, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw new Error('Upload failed');
    }

    await fetchUploadedDocuments();
  };

  const handleView = (document: UploadedDocument) => {
    router.push(`/documents/${document.id}`);
  };

  const handleDownload = (document: UploadedDocument) => {
    window.open(document.blob_link, '_blank');
  };

  const handleDelete = async (document: UploadedDocument) => {
    if (!confirm(`Are you sure you want to delete "${document.title}"? This action cannot be undone.`)) {
      return;
    }

    try {
      const response = await fetch(apiEndpoints.deleteDocument(document.id), {
        method: 'DELETE',
      });

      if (!response.ok) {
        throw new Error('Delete failed');
      }

      await fetchUploadedDocuments();
    } catch (error) {
      console.error('Error deleting document:', error);
      alert('Failed to delete document. Please try again.');
    }
  };

  const handleComplianceFrameworkUpdate = async (documentId: number, complianceFrameworkId: string | null) => {
    try {
      const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const response = await fetch(`${API_BASE_URL}/documents/${documentId}/compliance-framework`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          compliance_framework_id: complianceFrameworkId,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || errorData.message || 'Failed to update compliance framework');
      }

      // Refresh the documents list to show the updated compliance framework
      await fetchUploadedDocuments();
    } catch (error) {
      console.error('Error updating compliance framework:', error);
      alert('Failed to update compliance framework. Please try again.');
      throw error; // Re-throw to handle in the DocumentTable component
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
          <Button 
            onClick={() => setShowCitationTest(!showCitationTest)}
            variant="outline"
            className="ml-4"
          >
            {showCitationTest ? 'Hide Citation Test' : 'Test Citations'}
          </Button>
        </div>
        {showCitationTest && (
          <div className="mt-6">
            <CitationTest />
          </div>
        )}
      </div>

      <div className="flex-1 overflow-hidden">
        {isLoading ? (
          <div className="h-full flex items-center justify-center">
            <div className="flex flex-col items-center space-y-4">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900"></div>
              <p className="text-gray-600">Loading documents...</p>
            </div>
          </div>
        ) : (
          <ScrollArea className="h-full">
            <div className="p-6 space-y-6">
              <DocumentUpload 
                onUpload={handleUpload} 
                hasExistingDocuments={uploadedDocuments.length > 0}
              />
              <DocumentTable 
                documents={uploadedDocuments}
                onView={handleView}
                onDownload={handleDownload}
                onDelete={handleDelete}
                onComplianceFrameworkUpdate={handleComplianceFrameworkUpdate}
              />
            </div>
          </ScrollArea>
        )}
      </div>
    </div>
  );
}
