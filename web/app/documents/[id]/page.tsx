"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ArrowLeft, FileText, Calendar, ChevronLeft } from "lucide-react";
import { apiEndpoints } from "@/lib/api";
import { DocumentChatPanel } from "@/components/DocumentChatPanel";

// Text Viewer Component
interface TextViewerProps {
  url: string;
  filename: string;
  onLoad: () => void;
  onError: () => void;
}

function TextViewer({ url, filename, onLoad, onError }: TextViewerProps) {
  const [content, setContent] = useState<string>('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchContent = async () => {
      try {
        const response = await fetch(url);
        if (!response.ok) throw new Error('Failed to fetch content');
        const text = await response.text();
        setContent(text);
        onLoad();
      } catch (error) {
        console.error('Error fetching text content:', error);
        onError();
      } finally {
        setLoading(false);
      }
    };

    fetchContent();
  }, [url, onLoad, onError]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900"></div>
      </div>
    );
  }

  const ext = filename.toLowerCase().split('.').pop();
  const isMarkdown = ext === 'md';

  return (
    <div className="w-full h-full overflow-auto p-4 bg-white">
      <div className="mb-4">
        <h3 className="text-lg font-semibold text-gray-900">{filename}</h3>
        <p className="text-sm text-gray-600">Text content preview</p>
      </div>
      <pre className="whitespace-pre-wrap font-mono text-sm text-gray-800 bg-gray-50 p-4 rounded border">
        {content}
      </pre>
    </div>
  );
}

interface DocumentDetail {
  id: number;
  title: string;
  checksum: string;
  blob_link: string;
  created_at: string;
  num_segments?: number;
  mime_type?: string;
}

export default function DocumentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const [document, setDocument] = useState<DocumentDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [viewerUrl, setViewerUrl] = useState<string | null>(null);
  const [viewerLoading, setViewerLoading] = useState(false);
  const [viewerError, setViewerError] = useState<string | null>(null);
  const [viewerLoaded, setViewerLoaded] = useState(false);
  const [viewerContentError, setViewerContentError] = useState(false);
  
  // Chat panel state
  const [isChatOpen, setIsChatOpen] = useState(false);

  const documentId = params.id as string;

  useEffect(() => {
    if (documentId) {
      fetchDocumentDetail();
    }
  }, [documentId]);

  useEffect(() => {
    if (document) {
      fetchViewerUrl();
    }
  }, [document]);

  const fetchDocumentDetail = async () => {
    try {
      setIsLoading(true);
      setError(null);
      
      const response = await fetch(apiEndpoints.getDocument(parseInt(documentId)));
      
      if (!response.ok) {
        throw new Error(`Failed to fetch document: ${response.status}`);
      }
      
      const data = await response.json();
      setDocument(data);
    } catch (error) {
      console.error('Error fetching document:', error);
      setError(error instanceof Error ? error.message : 'Failed to fetch document');
    } finally {
      setIsLoading(false);
    }
  };

  const fetchViewerUrl = async () => {
    try {
      setViewerLoading(true);
      setViewerError(null);
      
      console.log('Fetching viewer URL for document ID:', documentId);
      const response = await fetch(apiEndpoints.getDocumentViewerUrl(parseInt(documentId)));
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error('Failed to fetch viewer URL:', response.status, errorText);
        throw new Error(`Failed to fetch viewer URL: ${response.status} - ${errorText}`);
      }
      
      const data = await response.json();
      console.log('Received viewer URL:', data.viewer_url);
      setViewerUrl(data.viewer_url);
      setViewerLoaded(false);
      setViewerContentError(false);
    } catch (error) {
      console.error('Error fetching viewer URL:', error);
      setViewerError(error instanceof Error ? error.message : 'Failed to fetch viewer URL');
    } finally {
      setViewerLoading(false);
    }
  };


  const handleViewInNewTab = () => {
    if (viewerUrl) {
      window.open(viewerUrl, '_blank');
    }
  };

  const getFileExtension = (title: string): string => {
    return title.toLowerCase().split('.').pop() || '';
  };

  const getFileType = (
    title: string,
    mimeType?: string
  ): 'pdf' | 'image' | 'video' | 'audio' | 'text' | 'unknown' => {
    if (mimeType) {
      if (mimeType === 'application/pdf') return 'pdf';
      if (mimeType.startsWith('image/')) return 'image';
      if (mimeType.startsWith('video/')) return 'video';
      if (mimeType.startsWith('audio/')) return 'audio';
      if (mimeType.startsWith('text/')) return 'text';
      if (
        ['application/json', 'application/xml', 'application/csv'].includes(
          mimeType
        )
      )
        return 'text';
    }

    const ext = getFileExtension(title);

    if (ext === 'pdf') return 'pdf';
    if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'bmp'].includes(ext)) return 'image';
    if (['mp4', 'webm', 'ogg', 'avi', 'mov'].includes(ext)) return 'video';
    if (['mp3', 'wav', 'ogg', 'aac', 'm4a'].includes(ext)) return 'audio';
    if (['txt', 'md', 'csv', 'json', 'xml', 'log'].includes(ext)) return 'text';

    return 'unknown';
  };

  const fileType = document ? getFileType(document.title, document.mime_type) : 'unknown';

  // Handle loading for file types that don't have reliable onLoad events
  useEffect(() => {
    if (viewerUrl) {
      if (fileType === 'pdf') {
        // PDF object/embed don't have reliable onLoad events
        const timer = setTimeout(() => setViewerLoaded(true), 1500);
        return () => clearTimeout(timer);
      } else if (fileType === 'unknown') {
        // Unknown types show message immediately
        setViewerLoaded(true);
      }
    }
  }, [viewerUrl, fileType]);

  const renderViewer = () => {
    if (!viewerUrl || !document) return null;
    
    switch (fileType) {
      case 'pdf':
        return (
          <object
            data={viewerUrl}
            type="application/pdf"
            className="w-full h-full"
          >
            <embed
              src={viewerUrl}
              type="application/pdf"
              className="w-full h-full"
            />
          </object>
        );
      
      case 'image':
        return (
          <img
            src={viewerUrl}
            alt={document.title}
            className="max-w-full max-h-full object-contain mx-auto"
            onLoad={() => setViewerLoaded(true)}
            onError={() => setViewerContentError(true)}
          />
        );
      
      case 'video':
        return (
          <video
            src={viewerUrl}
            controls
            className="max-w-full max-h-full mx-auto"
            onLoadedData={() => setViewerLoaded(true)}
            onError={() => setViewerContentError(true)}
          >
            Your browser does not support video playback.
          </video>
        );
      
      case 'audio':
        return (
          <div className="flex flex-col items-center justify-center h-full space-y-4">
            <div className="text-center">
              <FileText className="w-16 h-16 text-blue-600 mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-gray-900 mb-2">{document.title}</h3>
            </div>
            <audio
              src={viewerUrl}
              controls
              className="w-full max-w-md"
              onLoadedData={() => setViewerLoaded(true)}
              onError={() => setViewerContentError(true)}
            >
              Your browser does not support audio playback.
            </audio>
          </div>
        );
      
      case 'text':
        return <TextViewer url={viewerUrl} filename={document.title} onLoad={() => setViewerLoaded(true)} onError={() => setViewerContentError(true)} />;
      
      default:
        // Fallback for unknown types
        return (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <FileText className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <p className="text-gray-600 mb-2">Preview not available for this file type</p>
              <p className="text-xs text-gray-500 mb-4">File type: .{getFileExtension(document.title)}</p>
              <div className="space-x-2">
                <Button onClick={handleViewInNewTab} variant="outline">
                  View in New Tab
                </Button>
              </div>
            </div>
          </div>
        );
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return {
      date: date.toLocaleDateString('en-US', { 
        year: 'numeric', 
        month: 'long', 
        day: 'numeric' 
      }),
      time: date.toLocaleTimeString('en-US', { 
        hour: '2-digit', 
        minute: '2-digit' 
      })
    };
  };

  if (isLoading) {
    return (
      <div className="flex flex-col h-full">
        <div className="p-6 border-b">
          <Button 
            variant="ghost" 
            onClick={() => router.back()}
            className="mb-4"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back
          </Button>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="flex flex-col items-center space-y-4">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900"></div>
            <p className="text-gray-600">Loading document details...</p>
          </div>
        </div>
      </div>
    );
  }

  if (error || !document) {
    return (
      <div className="flex flex-col h-full">
        <div className="p-6 border-b">
          <Button 
            variant="ghost" 
            onClick={() => router.back()}
            className="mb-4"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back
          </Button>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <p className="text-red-600 mb-4">{error || 'Document not found'}</p>
            <Button onClick={() => router.push('/documents')}>
              Return to Documents
            </Button>
          </div>
        </div>
      </div>
    );
  }

  const { date, time } = formatDate(document.created_at);



  return (
    <div className="flex flex-col h-full relative">
      {/* Header */}
      <div className="p-6 border-b bg-white">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <Button 
              variant="ghost" 
              onClick={() => router.back()}
              size="sm"
            >
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back
            </Button>
            <div className="flex items-center space-x-3">
              <FileText className="w-6 h-6 text-blue-600" />
              <div>
                <h1 className="text-2xl font-bold text-gray-900">{document.title}</h1>
                <p className="text-gray-600">Document Details</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-6 bg-white">
        <div className="max-w-6xl mx-auto space-y-6">
          
          {/* Document Information Card */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <FileText className="w-5 h-5" />
                <span>Document Information</span>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex items-center space-x-4">
                <div className="p-3 bg-blue-100 rounded-lg">
                  <FileText className="w-6 h-6 text-blue-600" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-gray-900">{document.title}</h3>
                  <p className="text-gray-600">Document title</p>
                </div>
              </div>
              
              <div className="flex items-center space-x-4">
                <div className="p-3 bg-green-100 rounded-lg">
                  <Calendar className="w-6 h-6 text-green-600" />
                </div>
                <div>
                  <p className="text-lg font-semibold text-gray-900">{date}</p>
                  <p className="text-gray-600">Uploaded on {time}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Status Card */}
          <Card>
            <CardHeader>
              <CardTitle>Processing Status</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center space-x-3">
                <Badge variant="default" className="bg-green-100 text-green-800">
                  ✓ Processed
                </Badge>
                <div>
                  <p className="text-sm text-gray-700">
                    Document has been successfully uploaded, parsed, and is ready for search and analysis.
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Document Viewer Card */}
          <Card>
            <CardHeader>
              <CardTitle>Document Preview</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="w-full h-[600px] border rounded-lg overflow-hidden bg-gray-50">
                {viewerLoading ? (
                  <div className="flex items-center justify-center h-full">
                    <div className="text-center">
                      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900 mx-auto mb-4"></div>
                      <p className="text-gray-600">Loading document preview...</p>
                    </div>
                  </div>
                ) : viewerError || !viewerUrl ? (
                  <div className="flex items-center justify-center h-full">
                    <div className="text-center">
                      <FileText className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                      <p className="text-gray-600 mb-2">
                        {viewerError || 'Unable to preview this document'}
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="relative w-full h-full">
                    {!viewerLoaded && !viewerContentError && (
                      <div className="absolute inset-0 flex items-center justify-center bg-gray-50 z-10">
                        <div className="text-center">
                          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900 mx-auto mb-4"></div>
                          <p className="text-gray-600">Loading preview...</p>
                        </div>
                      </div>
                    )}
                    {viewerContentError && (
                      <div className="absolute inset-0 flex items-center justify-center bg-gray-50 z-10">
                        <div className="text-center">
                          <FileText className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                          <p className="text-gray-600 mb-2">Unable to preview this document</p>
                          <p className="text-xs text-gray-500 mb-4">Try viewing in a new tab</p>
                          <div className="space-x-2">
                            <Button onClick={handleViewInNewTab} variant="outline">
                              View in New Tab
                            </Button>
                          </div>
                        </div>
                      </div>
                    )}
                    {renderViewer()}
                  </div>
                )}
              </div>
              <div className="mt-4 flex justify-between items-center">
                <p className="text-sm text-gray-600">
                  Preview may not be available for all document types
                </p>
                <div className="flex space-x-2">
                  {viewerUrl && (
                    <Button 
                      onClick={() => fetchViewerUrl()} 
                      variant="outline" 
                      size="sm"
                      disabled={viewerLoading}
                    >
                      Refresh Preview
                    </Button>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Floating Chat Button */}
      <Button
        onClick={() => setIsChatOpen(true)}
        className={`fixed right-6 top-1/2 -translate-y-1/2 z-40 h-12 w-12 rounded-full shadow-lg transition-all duration-300 ${
          isChatOpen ? 'opacity-0 pointer-events-none' : 'opacity-100'
        }`}
        size="sm"
      >
        <ChevronLeft className="w-5 h-5" />
      </Button>

      {/* Document Chat Panel */}
      <DocumentChatPanel
        isOpen={isChatOpen}
        onClose={() => setIsChatOpen(false)}
        documentId={parseInt(documentId)}
        documentTitle={document?.title}
      />
    </div>
  );
}