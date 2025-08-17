"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { X } from "lucide-react";
import { ChatInput } from "@/components/ChatInput";
import { MessageList } from "@/components/MessageList";
import { MessageWithCitations } from "@/components/MessageWithCitations";
import { ThinkingSteps } from "@/components/ThinkingSteps";
import { apiEndpoints } from "@/lib/api";

// Reuse the same interfaces as the main chat for consistency
interface ThinkingStep {
  content: string;
  step: number;
  total_steps: number;
}

interface Message {
  id: number;
  text: string;
  sender: 'user' | 'bot';
  thinkingSteps?: ThinkingStep[];
  isThinking?: boolean;
  attachedFile?: {
    name: string;
    size: number;
    type: string;
  };
}

interface DocumentChatPanelProps {
  isOpen: boolean;
  onClose: () => void;
  documentId: number;
  documentTitle?: string;
}

export function DocumentChatPanel({ isOpen, onClose, documentId, documentTitle }: DocumentChatPanelProps) {
  const [chatMessages, setChatMessages] = useState<Message[]>([]);
  const [inputText, setInputText] = useState("");
  const [isProcessing, setIsProcessing] = useState(false);

  // Add initial welcome message when panel opens for the first time
  useEffect(() => {
    if (isOpen && chatMessages.length === 0) {
      const welcomeMessage: Message = {
        id: Date.now(),
        text: documentTitle 
          ? `I can see you're viewing the document "${documentTitle}". How can I help you with this document?`
          : "How can I help you with this document?",
        sender: 'bot'
      };
      setChatMessages([welcomeMessage]);
    }
  }, [isOpen, documentTitle, chatMessages.length]);

  const handleChatSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim()) return;

    const userMessage: Message = {
      id: Date.now(),
      text: inputText,
      sender: 'user'
    };

    setChatMessages(prev => [...prev, userMessage]);
    const messageText = inputText;
    setInputText("");
    setIsProcessing(true);

    try {
      // Call the chat API with document context
      const formData = new FormData();
      formData.append('message', messageText);
      formData.append('document_id', documentId.toString());

      const response = await fetch(apiEndpoints.sendMessage, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      // Handle streaming response
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      
      if (!reader) {
        throw new Error('No response body');
      }

      const botMessage: Message = {
        id: Date.now() + 1,
        text: "",
        sender: 'bot',
        thinkingSteps: [],
        isThinking: true
      };
      setChatMessages(prev => [...prev, botMessage]);

      let buffer = '';
      
      const readChunk = async () => {
        const { done, value } = await reader.read();
        
        if (done) {
          setIsProcessing(false);
          return;
        }
        
        const chunk = decoder.decode(value);
        buffer += chunk;
        
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data === '[DONE]') {
              setIsProcessing(false);
              return;
            }
            
            try {
              const parsed = JSON.parse(data);
              if (parsed.type === 'thinking_step') {
                const thinkingStep: ThinkingStep = {
                  content: parsed.content,
                  step: parsed.data?.step || parsed.step || 1,
                  total_steps: parsed.data?.total_steps || parsed.total_steps || 1
                };
                setChatMessages(prev => prev.map(msg => 
                  msg.id === botMessage.id 
                    ? { ...msg, thinkingSteps: [...(msg.thinkingSteps || []), thinkingStep] }
                    : msg
                ));
              } else if (parsed.type === 'content') {
                setChatMessages(prev => prev.map(msg => 
                  msg.id === botMessage.id 
                    ? { ...msg, text: msg.text + parsed.data, isThinking: false }
                    : msg
                ));
              } else if (parsed.type === 'response_complete') {
                setChatMessages(prev => prev.map(msg => 
                  msg.id === botMessage.id 
                    ? { ...msg, text: parsed.content || parsed.data?.content || parsed.content, isThinking: false }
                    : msg
                ));
                setIsProcessing(false);
                return;
              } else if (parsed.type === 'thinking_complete' || parsed.type === 'response_start') {
                setChatMessages(prev => prev.map(msg => 
                  msg.id === botMessage.id 
                    ? { ...msg, isThinking: false }
                    : msg
                ));
              } else if (parsed.type === 'stream_end') {
                setIsProcessing(false);
                return;
              } else if (parsed.type === 'error') {
                setChatMessages(prev => prev.map(msg => 
                  msg.id === botMessage.id 
                    ? { ...msg, text: `Error: ${parsed.content}`, isThinking: false }
                    : msg
                ));
                setIsProcessing(false);
                return;
              }
            } catch (e) {
              console.error('Error parsing SSE data:', e);
            }
          }
        }
        
        await readChunk();
      };
      
      await readChunk();
      
    } catch (error) {
      console.error('Error in chat:', error);
      setChatMessages(prev => prev.map(msg => 
        msg.id === (Date.now() + 1)
          ? { ...msg, text: "Sorry, there was an error processing your request." }
          : msg
      ));
      setIsProcessing(false);
    }
  };

  return (
    <>
      {/* Chat Panel */}
      <div className={`fixed right-0 top-0 h-full w-96 bg-white border-l shadow-xl z-50 transform transition-transform duration-300 ease-in-out ${
        isOpen ? 'translate-x-0' : 'translate-x-full'
      }`}>
        {/* Chat Header */}
        <div className="flex items-center justify-between p-4 border-b bg-gray-50">
          <h3 className="text-lg font-semibold text-gray-900">Document Chat</h3>
          <Button
            onClick={onClose}
            variant="ghost"
            size="sm"
            className="h-8 w-8 p-0"
          >
            <X className="w-4 h-4" />
          </Button>
        </div>

        {/* Chat Messages Area */}
        <div className="flex-1 overflow-auto p-4" style={{ height: 'calc(100% - 140px)' }}>
          <div className="space-y-4">
            {chatMessages.map((message) => (
              <div key={message.id}>
                {message.sender === 'bot' && message.isThinking ? (
                  <div className="mr-auto max-w-3xl">
                    <ThinkingSteps 
                      steps={message.thinkingSteps || []} 
                      isThinking={message.isThinking}
                      isComplete={!message.isThinking && message.text.length > 0}
                    />
                  </div>
                ) : (
                  <div className={`${
                    message.sender === 'user' ? 'ml-auto bg-blue-50' : 'mr-auto bg-gray-50'
                  } max-w-3xl rounded-lg border p-4`}>
                    <div className="flex flex-col space-y-3">
                      {message.sender === 'user' && message.attachedFile && (
                        <div className="mb-2 flex items-center space-x-2 text-sm text-gray-600 bg-blue-100 p-2 rounded-md">
                          <span className="text-blue-600">📎</span>
                          <span className="font-medium">{message.attachedFile.name}</span>
                          <span className="text-gray-500">({(message.attachedFile.size / 1024 / 1024).toFixed(1)} MB)</span>
                        </div>
                      )}
                      {message.sender === 'bot' && message.thinkingSteps && message.thinkingSteps.length > 0 && (
                        <ThinkingSteps 
                          steps={message.thinkingSteps} 
                          isThinking={message.isThinking}
                          isComplete={!message.isThinking && message.text.length > 0}
                        />
                      )}
                      <MessageWithCitations content={message.text} messageId={message.id.toString()} />
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
        
        {/* Chat Input - Fixed at bottom */}
        <div className="absolute bottom-0 left-0 right-0 border-t bg-white">
          <div className="border-t p-4">
            <form onSubmit={handleChatSubmit} className="flex items-end space-x-2">
              <div className="flex-1">
                <input
                  value={inputText}
                  onChange={(e) => setInputText(e.target.value)}
                  placeholder="Type your message..."
                  disabled={isProcessing}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <button 
                type="submit" 
                disabled={isProcessing || !inputText.trim()}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isProcessing ? "Sending..." : "Send"}
              </button>
            </form>
          </div>
        </div>
      </div>

      {/* Overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black bg-opacity-20 z-40"
          onClick={onClose}
        />
      )}
    </>
  );
}
