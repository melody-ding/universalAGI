"use client";

import { useState } from "react";
import { MessageList } from "@/components/MessageList";
import { ChatInput } from "@/components/ChatInput";
import { useStreamingChat } from "@/hooks/useStreamingChat";

export default function ChatPage() {
  const [inputText, setInputText] = useState("");
  const [selectedDocument, setSelectedDocument] = useState<File | null>(null);
  const { messages, isProcessing, sendMessage } = useStreamingChat();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim() && !selectedDocument) return;

    await sendMessage(inputText, undefined, selectedDocument || undefined);
    setInputText("");
    setSelectedDocument(null);
  };

  return (
    <div className="flex flex-col h-full">
      <MessageList messages={messages} />
      <ChatInput
        inputText={inputText}
        setInputText={setInputText}
        selectedDocument={selectedDocument}
        setSelectedDocument={setSelectedDocument}
        isProcessing={isProcessing}
        onSubmit={handleSubmit}
      />
    </div>
  );
}
