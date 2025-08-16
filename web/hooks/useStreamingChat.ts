"use client";

import { useState, useRef, useCallback } from "react";
import { apiEndpoints } from "@/lib/api";

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

export function useStreamingChat() {
  const [messages, setMessages] = useState<Message[]>([
    { id: 1, text: "Hello! How can I help you today?", sender: "bot" },
  ]);
  const [isProcessing, setIsProcessing] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);
  const messageIdCounter = useRef(2);

  const handleStreamingResponse = useCallback((formData: FormData) => {
    return new Promise<void>((resolve, reject) => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }

      const botMessageId = messageIdCounter.current++;
      const botMessage: Message = {
        id: botMessageId,
        text: "",
        sender: "bot",
        thinkingSteps: [],
        isThinking: true
      };
      
      setMessages(prev => [...prev, botMessage]);

      fetch(apiEndpoints.sendMessage, {
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
        
        let buffer = '';
        
        const readChunk = () => {
          reader.read().then(({ done, value }) => {
            if (done) {
              setIsProcessing(false);
              resolve();
              return;
            }
            
            const chunk = decoder.decode(value);
            buffer += chunk;
            
            // Process complete lines from buffer
            const lines = buffer.split('\n');
            // Keep the last incomplete line in buffer
            buffer = lines.pop() || '';
            
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
                    // Continue processing
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

  const sendMessage = useCallback(async (text: string, image?: File) => {
    const userMessage: Message = {
      id: messageIdCounter.current++,
      text,
      sender: 'user'
    };

    setMessages(prev => [...prev, userMessage]);
    setIsProcessing(true);

    const formData = new FormData();
    formData.append('message', text);
    if (image) {
      formData.append('image', image);
    }

    try {
      await handleStreamingResponse(formData);
    } catch (error) {
      console.error('Error handling response:', error);
    }
  }, [handleStreamingResponse]);

  return {
    messages,
    isProcessing,
    sendMessage
  };
}