"use client";

import { useState, useRef, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Card, CardContent } from "@/components/ui/card";
import { ThinkingSteps } from "@/components/ThinkingSteps";

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

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([
    { id: 1, text: "Hello! How can I help you today?", sender: "bot" },
  ]);
  const [inputText, setInputText] = useState("");
  const [selectedImage, setSelectedImage] = useState<File | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

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
      const botMessageId = Date.now();
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
                try {
                  const data = JSON.parse(line.slice(6));
                  
                  setMessages(prev => {
                    return prev.map(msg => {
                      if (msg.id === botMessageId) {
                        const updatedMsg = { ...msg };
                        
                        switch (data.type) {
                          case 'thinking_step':
                            const newStep = {
                              content: data.content,
                              step: data.step,
                              total_steps: data.total_steps
                            };
                            // Only add if this step doesn't already exist
                            const existingSteps = msg.thinkingSteps || [];
                            const stepExists = existingSteps.some(s => s.step === newStep.step);
                            if (!stepExists) {
                              updatedMsg.thinkingSteps = [...existingSteps, newStep];
                            }
                            break;
                            
                          case 'thinking_complete':
                            updatedMsg.isThinking = false;
                            break;
                            
                          case 'response_token':
                            updatedMsg.text = (updatedMsg.text || '') + data.content;
                            break;
                            
                          case 'response_complete':
                            updatedMsg.text = data.content;
                            updatedMsg.isThinking = false;
                            break;
                            
                          case 'error':
                            updatedMsg.text = `Error: ${data.content}`;
                            updatedMsg.isThinking = false;
                            break;
                        }
                        
                        return updatedMsg;
                      }
                      return msg;
                    });
                  });
                } catch (e) {
                  console.error('Error parsing SSE data:', e);
                }
              }
            }
            
            readChunk();
          }).catch(reject);
        };
        
        readChunk();
      })
      .catch(error => {
        console.error('Streaming error:', error);
        setMessages(prev => [
          ...prev.filter(msg => msg.id !== botMessageId),
          {
            id: botMessageId,
            text: "Sorry, I encountered an error. Please try again.",
            sender: "bot",
          },
        ]);
        setIsProcessing(false);
        reject(error);
      });
    });
  }, []);

  const handleSend = async () => {
    if (!inputText.trim() && !selectedImage) return;
    if (isProcessing) return;

    const userMessage: Message = { 
      id: Date.now() - 1, 
      text: inputText || (selectedImage ? "Image uploaded" : ""), 
      sender: "user" 
    };
    setMessages((prev) => [...prev, userMessage]);
    
    const currentText = inputText;
    const currentImage = selectedImage;
    setInputText("");
    setSelectedImage(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }

    setIsProcessing(true);

    try {
      const formData = new FormData();
      formData.append('message', currentText);
      formData.append('conversation_history', JSON.stringify(messages.map(msg => ({
        content: msg.text,
        role: msg.sender === "user" ? "user" : "assistant"
      }))));
      
      if (currentImage) {
        formData.append('image', currentImage);
      }

      await handleStreamingResponse(formData);
    } catch (error) {
      console.error("Error sending message:", error);
      setIsProcessing(false);
    }
  };

  return (
    <div className="flex flex-col h-screen">
      <header className="border-b px-6 py-4">
        <h1 className="text-2xl font-bold tracking-tight">Chat Interface</h1>
      </header>

      <ScrollArea className="flex-1 p-4">
        <div className="flex flex-col gap-4 max-w-3xl mx-auto">
          {messages.map((message) => (
            <div
              key={message.id}
              className={`flex ${
                message.sender === "user" ? "justify-end" : "justify-start"
              }`}
            >
              <div className={`max-w-[85%] ${message.sender === "user" ? "" : "w-full"}`}>
                {message.sender === "bot" && (message.thinkingSteps?.length || message.isThinking) && (
                  <ThinkingSteps 
                    steps={message.thinkingSteps || []} 
                    isThinking={message.isThinking || false}
                    isComplete={!message.isThinking && (message.thinkingSteps?.length || 0) > 0}
                  />
                )}
                <Card
                  className={`${
                    message.sender === "user" ? "bg-primary" : "bg-muted"
                  }`}
                >
                  <CardContent
                    className={`p-3 ${
                      message.sender === "user"
                        ? "text-primary-foreground"
                        : "text-muted-foreground"
                    }`}
                  >
                    {message.text || (message.isThinking ? "Thinking..." : "")}
                  </CardContent>
                </Card>
              </div>
            </div>
          ))}
        </div>
      </ScrollArea>

      <footer className="border-t p-4">
        <div className="max-w-3xl mx-auto">
          {selectedImage && (
            <div className="mb-3 p-2 bg-muted rounded-md flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 bg-primary/10 rounded flex items-center justify-center">
                  📎
                </div>
                <span className="text-sm text-muted-foreground">
                  {selectedImage.name}
                </span>
              </div>
              <Button 
                variant="ghost" 
                size="sm" 
                onClick={removeSelectedImage}
                className="h-6 w-6 p-0"
              >
                ✕
              </Button>
            </div>
          )}
          <div className="flex gap-2">
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              onChange={handleImageSelect}
              className="hidden"
            />
            <Button
              variant="outline"
              size="icon"
              onClick={handleImageButtonClick}
              className="shrink-0"
            >
              📎
            </Button>
            <Input
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyPress={(e) => e.key === "Enter" && handleSend()}
              placeholder="Type a message..."
              className="flex-1"
            />
            <Button onClick={handleSend} disabled={isProcessing}>
              {isProcessing ? "Processing..." : "Send"}
            </Button>
          </div>
        </div>
      </footer>
    </div>
  );
}
