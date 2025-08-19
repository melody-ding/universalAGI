const getApiUrl = (): string => {
  // Always try environment variable first
  if (process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL;
  }
  
  // Runtime fallback - check if we're in browser and on a different host
  if (typeof window !== 'undefined') {
    const currentHost = window.location.hostname;
    if (currentHost !== 'localhost' && currentHost !== '127.0.0.1') {
      // We're on a remote server, use port 80 for backend
      return `http://${currentHost}:80`;
    }
  }
  
  // Development fallback
  return 'http://localhost:8000';
};

export const API_BASE_URL = getApiUrl();

export const apiEndpoints = {
  sendMessage: `${API_BASE_URL}/send-message-stream`,
  uploadDocument: `${API_BASE_URL}/upload-document`,
  getDocuments: `${API_BASE_URL}/documents`,
  getDocument: (id: number) => `${API_BASE_URL}/documents/${id}`,
  getDocumentViewerUrl: (id: number) => `${API_BASE_URL}/documents/${id}/viewer-url`,
  deleteDocument: (id: number) => `${API_BASE_URL}/documents/${id}`,
};