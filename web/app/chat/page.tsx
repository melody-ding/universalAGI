"use client";

import { useState, useRef, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Card, CardContent } from "@/components/ui/card";
import { ThinkingSteps } from "@/components/ThinkingSteps";
import { MarkdownMessage } from "@/components/MarkdownMessage";

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
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([
    { id: 1, text: "Hello! How can I help you today?", sender: "bot" },
  ]);
  const [inputText, setInputText] = useState("");
  const [selectedImage, setSelectedImage] = useState<File | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const messageIdCounter = useRef(2);

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

  const handleStreamingResponse = useCallback((formData: FormData) => {
    return new Promise<void>((resolve, reject) => {
      // Close existing EventSource if any
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }

      // Create bot message placeholder
      const botMessageId = messageIdCounter.current++;
      const botMessage: Message = {
        id: botMessageId,
        text: "",
        sender: "bot",
        thinkingSteps: [],
        isThinking: true
      };
      
      setMessages(prev => [...prev, botMessage]);

      // Prepare form data for streaming endpoint
      
      // Note: EventSource doesn't support POST with FormData directly
      // We'll use fetch with stream reading instead
      fetch('http://localhost:8000/send-message-stream', {
        method: 'POST',
        body: formData,
      })
      .then(response => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        if (!response.body) {
          throw new Error('No response body');
        }
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        
        const readChunk = () => {
          reader.read().then(({ done, value }) => {
            if (done) {
              setIsProcessing(false);
              resolve();
              return;
            }
            
            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');
            
            for (const line of lines) {
              if (line.startsWith('data: ')) {
                const data = line.slice(6);
                if (data === '[DONE]') {
                  setIsProcessing(false);
                  resolve();
                  return;
                }
                
                try {
                  const parsed = JSON.parse(data);
                  if (parsed.type === 'thinking_step') {
                    const thinkingStep = {
                      content: parsed.content,
                      step: parsed.data?.step || 1,
                      total_steps: parsed.data?.total_steps || 1
                    };
                    setMessages(prev => prev.map(msg => 
                      msg.id === botMessageId 
                        ? { ...msg, thinkingSteps: [...(msg.thinkingSteps || []), thinkingStep] }
                        : msg
                    ));
                  } else if (parsed.type === 'content') {
                    setMessages(prev => prev.map(msg => 
                      msg.id === botMessageId 
                        ? { ...msg, text: msg.text + parsed.data, isThinking: false }
                        : msg
                    ));
                  } else if (parsed.type === 'error') {
                    console.error('Streaming error:', parsed.content);
                    setMessages(prev => prev.map(msg => 
                      msg.id === botMessageId 
                        ? { ...msg, text: `Error: ${parsed.content}`, isThinking: false }
                        : msg
                    ));
                    setIsProcessing(false);
                    reject(new Error(parsed.content));
                    return;
                  } else if (parsed.type === 'response_complete') {
                    setMessages(prev => prev.map(msg => 
                      msg.id === botMessageId 
                        ? { ...msg, text: parsed.content || parsed.data?.content || parsed.content, isThinking: false }
                        : msg
                    ));
                    setIsProcessing(false);
                    resolve();
                    return;
                  } else if (parsed.type === 'thinking_complete' || parsed.type === 'response_start') {
                    // Continue processing, don't stop here
                  } else if (parsed.type === 'stream_end') {
                    setIsProcessing(false);
                    resolve();
                    return;
                  }
                } catch (e) {
                  console.error('Error parsing SSE data:', e, 'Raw data:', data);
                }
              }
            }
            
            readChunk();
          }).catch(reject);
        };
        
        readChunk();
      })
      .catch(error => {
        console.error('Error:', error);
        setMessages(prev => prev.map(msg => 
          msg.id === botMessageId 
            ? { ...msg, text: "Sorry, there was an error processing your request.", isThinking: false }
            : msg
        ));
        setIsProcessing(false);
        reject(error);
      });
    });
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim() && !selectedImage) return;

    const userMessage: Message = {
      id: messageIdCounter.current++,
      text: inputText,
      sender: 'user'
    };

    setMessages(prev => [...prev, userMessage]);
    setInputText("");
    setIsProcessing(true);

    const formData = new FormData();
    formData.append('message', inputText);
    if (selectedImage) {
      formData.append('image', selectedImage);
    }

    try {
      await handleStreamingResponse(formData);
    } catch (error) {
      console.error('Error handling response:', error);
    } finally {
      setSelectedImage(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-hidden">
        <ScrollArea className="h-full p-4">
          <div className="space-y-4">
            {messages.map((message) => (
              <Card key={message.id} className={`${
                message.sender === 'user' ? 'ml-auto bg-blue-50' : 'mr-auto bg-gray-50'
              } max-w-3xl`}>
                <CardContent className="p-4">
                  <div className="flex items-start space-x-3">
                    <div className="flex-1">
                      {message.sender === 'bot' && message.thinkingSteps && message.thinkingSteps.length > 0 && (
                        <ThinkingSteps 
                          steps={message.thinkingSteps} 
                          isThinking={message.isThinking}
                          isComplete={!message.isThinking && message.text.length > 0}
                        />
                      )}
                      {message.isThinking ? (
                        <div className="flex items-center space-x-2">
                          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
                          <span className="text-gray-600">Thinking...</span>
                        </div>
                      ) : (
                        <MarkdownMessage content={message.text} />
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </ScrollArea>
      </div>
      
      <div className="border-t p-4">
        <form onSubmit={handleSubmit} className="flex items-end space-x-2">
          <div className="flex-1 space-y-2">
            <Input
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              placeholder="Type your message..."
              disabled={isProcessing}
              className="min-h-[60px]"
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
    </div>
  );
}
