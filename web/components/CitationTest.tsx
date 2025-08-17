"use client";

import { useState, useEffect } from "react";
import { MessageWithCitations } from "./MessageWithCitations";

interface Document {
  id: number;
  title: string;
}

export function CitationTest() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [testMessage, setTestMessage] = useState('');

  useEffect(() => {
    const fetchDocuments = async () => {
      try {
        const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/documents`);
        if (response.ok) {
          const data = await response.json();
          setDocuments(data.documents);
          
          // Create test message with real document IDs
          if (data.documents.length >= 2) {
            const doc1 = data.documents[0];
            const doc2 = data.documents[1];
            console.log('Creating test message with documents:', doc1.id, doc2.id);
            const message = `This is a test message with citations using your actual documents. According to the research [[doc:${doc1.id}, seg:1]], this approach works well. Additionally, another study [[doc:${doc2.id}, seg:2]] confirms these findings. The first source [[doc:${doc1.id}, seg:1]] also mentions that the methodology is sound.`;
            console.log('Generated test message:', message);
            setTestMessage(message);
          } else if (data.documents.length >= 1) {
            const doc1 = data.documents[0];
            setTestMessage(`This is a test message with citations using your actual document. According to the research [[doc:${doc1.id}, seg:1]], this approach works well. The same source [[doc:${doc1.id}, seg:2]] also mentions additional findings.`);
          } else {
            setTestMessage('No documents found. Please upload some documents first to test citations.');
          }
        }
      } catch (error) {
        console.error('Error fetching documents:', error);
        setTestMessage('Error loading documents. Using fallback test: According to the research [[doc:1, seg:5]], this approach works well.');
      }
    };

    fetchDocuments();
  }, []);

  if (!testMessage) {
    return (
      <div className="p-4 max-w-4xl mx-auto">
        <h2 className="text-xl font-bold mb-4">Citation System Test</h2>
        <div className="bg-gray-50 p-4 rounded-lg">
          <p className="text-gray-500">Loading test data...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-4 max-w-4xl mx-auto">
      <h2 className="text-xl font-bold mb-4">Citation System Test</h2>
      
      {documents.length > 0 && (
        <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded">
          <p className="text-sm text-blue-800">
            <strong>Using your actual documents:</strong> {documents.map(d => d.title).join(', ')}
          </p>
        </div>
      )}
      
      <div className="bg-gray-50 p-4 rounded-lg">
        <h3 className="text-sm font-semibold text-gray-600 mb-2">Test Message:</h3>
        <MessageWithCitations content={testMessage} />
      </div>
      
      <div className="mt-4 text-sm text-gray-600">
        <p><strong>Instructions:</strong></p>
        <ul className="list-disc list-inside mt-2 space-y-1">
          <li>You should see numbered citations like [1], [2] in the text above</li>
          <li>Citations should be blue and clickable</li>
          <li>Hovering should show a light blue background</li>
          <li>Clicking should scroll to the corresponding footnote</li>
          <li>Footnotes should appear below with document details</li>
        </ul>
      </div>
      
      <div className="mt-4 bg-yellow-50 border border-yellow-200 rounded p-3">
        <p className="text-sm text-yellow-800">
          <strong>Note:</strong> This test uses your actual uploaded documents. 
          If no citations appear, check the browser console for error messages about document resolution.
        </p>
      </div>
    </div>
  );
}
