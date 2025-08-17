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
                        {message.sender === 'bot' && message.thinkingSteps && message.thinkingSteps.length > 0 && (
                          <ThinkingSteps 
                            steps={message.thinkingSteps} 
                            isThinking={message.isThinking}
                            isComplete={!message.isThinking && message.text.length > 0}
                          />
                        )}
                        <MessageWithCitations content={message.text} />
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