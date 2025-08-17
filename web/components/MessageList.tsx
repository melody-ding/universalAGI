"use client";

import { ScrollArea } from "@/components/ui/scroll-area";
import { Card, CardContent } from "@/components/ui/card";
import { ThinkingSteps } from "@/components/ThinkingSteps";
import { MessageWithCitations } from "@/components/MessageWithCitations";

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

interface MessageListProps {
  messages: Message[];
}

export function MessageList({ messages }: MessageListProps) {
  return (
    <div className="flex-1 overflow-hidden">
      <ScrollArea className="h-full p-4">
        <div className="space-y-4">
          {messages.map((message) => (
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
                <Card className={`${
                  message.sender === 'user' ? 'ml-auto bg-blue-50' : 'mr-auto bg-gray-50'
                } max-w-3xl`}>
                  <CardContent className="p-4">
                    <div className="flex items-start space-x-3">
                      <div className="flex-1">
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
                  </CardContent>
                </Card>
              )}
            </div>
          ))}
        </div>
      </ScrollArea>
    </div>
  );
}