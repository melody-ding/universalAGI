"use client";

import { useRef } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface ChatInputProps {
  inputText: string;
  setInputText: (text: string) => void;
  selectedDocument: File | null;
  setSelectedDocument: (file: File | null) => void;
  isProcessing: boolean;
  onSubmit: (e: React.FormEvent) => void;
}

export function ChatInput({
  inputText,
  setInputText,
  selectedDocument,
  setSelectedDocument,
  isProcessing,
  onSubmit
}: ChatInputProps) {
  const documentInputRef = useRef<HTMLInputElement>(null);

  const handleDocumentSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file && file.type === 'application/pdf') {
      setSelectedDocument(file);
    } else if (file) {
      alert('Please select a PDF file');
    }
  };

  const handleDocumentButtonClick = () => {
    documentInputRef.current?.click();
  };

  const removeSelectedDocument = () => {
    setSelectedDocument(null);
    if (documentInputRef.current) {
      documentInputRef.current.value = '';
    }
  };

  return (
    <div className="border-t p-4">
      <form onSubmit={onSubmit} className="flex items-end space-x-2">
        <div className="flex-1 space-y-2">
          <Input
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder="Type your message..."
            disabled={isProcessing}
          />
          {selectedDocument && (
            <div className="flex items-center space-x-2 text-sm text-gray-600">
              <span>Selected PDF: {selectedDocument.name}</span>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={removeSelectedDocument}
                className="h-6 px-2"
              >
                Remove
              </Button>
            </div>
          )}
        </div>
        <div className="flex space-x-2">
          <Button
            type="button"
            variant="outline"
            onClick={handleDocumentButtonClick}
            disabled={isProcessing}
            className="px-3"
          >
            📄
          </Button>
          <Button type="submit" disabled={isProcessing || (!inputText.trim() && !selectedDocument)}>
            {isProcessing ? "Sending..." : "Send"}
          </Button>
        </div>
      </form>
      <input
        ref={documentInputRef}
        type="file"
        accept="application/pdf"
        onChange={handleDocumentSelect}
        className="hidden"
      />
    </div>
  );
}