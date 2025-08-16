"use client";

import { useState, useRef } from "react";

interface FileUploadOptions {
  accept?: string;
  multiple?: boolean;
  onUpload?: (file: File) => Promise<void>;
  onError?: (error: Error) => void;
}

export function useFileUpload(options: FileUploadOptions = {}) {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const {
    accept = "*/*",
    multiple = false,
    onUpload,
    onError
  } = options;

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (files) {
      const fileArray = Array.from(files);
      setSelectedFiles(fileArray);
      
      if (onUpload) {
        uploadFiles(fileArray);
      }
    }
  };

  const uploadFiles = async (files: File[]) => {
    if (!onUpload) return;
    
    setIsUploading(true);
    
    try {
      for (const file of files) {
        await onUpload(file);
      }
    } catch (error) {
      const uploadError = error instanceof Error ? error : new Error('Upload failed');
      onError?.(uploadError);
    } finally {
      setIsUploading(false);
    }
  };

  const triggerFileSelect = () => {
    fileInputRef.current?.click();
  };

  const clearFiles = () => {
    setSelectedFiles([]);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const removeFile = (index: number) => {
    setSelectedFiles(prev => prev.filter((_, i) => i !== index));
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const fileInputProps = {
    ref: fileInputRef,
    type: "file" as const,
    accept,
    multiple,
    onChange: handleFileSelect,
    className: "hidden"
  };

  return {
    selectedFiles,
    isUploading,
    triggerFileSelect,
    clearFiles,
    removeFile,
    formatFileSize,
    fileInputProps
  };
}