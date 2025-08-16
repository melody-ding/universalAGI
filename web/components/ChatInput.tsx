"use client";

import { useRef } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface ChatInputProps {
  inputText: string;
  setInputText: (text: string) => void;
  selectedImage: File | null;
  setSelectedImage: (file: File | null) => void;
  isProcessing: boolean;
  onSubmit: (e: React.FormEvent) => void;
}

export function ChatInput({
  inputText,
  setInputText,
  selectedImage,
  setSelectedImage,
  isProcessing,
  onSubmit
}: ChatInputProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleImageSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file && file.type.startsWith('image/')) {
      setSelectedImage(file);
    }
  };

  const handleImageButtonClick = () => {
    fileInputRef.current?.click();
  };

  const removeSelectedImage = () => {
    setSelectedImage(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
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
          {selectedImage && (
            <div className="flex items-center space-x-2 text-sm text-gray-600">
              <span>Selected: {selectedImage.name}</span>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={removeSelectedImage}
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
            onClick={handleImageButtonClick}
            disabled={isProcessing}
            className="px-3"
          >
            📷
          </Button>
          <Button type="submit" disabled={isProcessing || (!inputText.trim() && !selectedImage)}>
            {isProcessing ? "Sending..." : "Send"}
          </Button>
        </div>
      </form>
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        onChange={handleImageSelect}
        className="hidden"
      />
    </div>
  );
}