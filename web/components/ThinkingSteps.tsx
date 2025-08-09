"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ChevronDown, ChevronRight, Brain, Loader2 } from "lucide-react";

interface ThinkingStep {
  content: string;
  step: number;
  total_steps: number;
}

interface ThinkingStepsProps {
  steps: ThinkingStep[];
  isThinking: boolean;
  isComplete: boolean;
}

export function ThinkingSteps({ steps, isThinking, isComplete }: ThinkingStepsProps) {
  const [isExpanded, setIsExpanded] = useState(true);

  // Reset displayed steps when steps array changes significantly (new message)
  useEffect(() => {
    if (steps.length === 0) {
      // This is a new message, reset everything
    }
  }, [steps]);

  if (!isThinking && steps.length === 0) {
    return null;
  }

  return (
    <Card className="mb-4 border-blue-200 bg-blue-50/50 dark:border-blue-800 dark:bg-blue-950/20">
      <CardHeader className="pb-2">
        <Button
          variant="ghost"
          className="flex items-center justify-between p-0 h-auto font-medium text-blue-700 dark:text-blue-300 hover:text-blue-800 dark:hover:text-blue-200"
          onClick={() => setIsExpanded(!isExpanded)}
        >
          <div className="flex items-center gap-2">
            <Brain className="h-4 w-4" />
            <span>
              {isThinking && !isComplete 
                ? "Thinking..." 
                : isComplete 
                  ? "Chain of Thought" 
                  : "Processing..."}
            </span>
            {isThinking && !isComplete && (
              <Loader2 className="h-3 w-3 animate-spin" />
            )}
          </div>
          {isExpanded ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </Button>
      </CardHeader>
      
      {isExpanded && (
        <CardContent className="pt-0">
          <div className="space-y-2">
            {steps.map((step, index) => (
              <div
                key={`step-${step.step}`}
                className="flex items-start gap-3 p-2 rounded-lg bg-white/60 dark:bg-gray-800/40 border border-blue-100 dark:border-blue-900 animate-in slide-in-from-left duration-300"
                style={{ animationDelay: `${index * 100}ms` }}
              >
                <div className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-100 dark:bg-blue-900 flex items-center justify-center text-xs font-medium text-blue-700 dark:text-blue-300">
                  {step.step}
                </div>
                <div className="flex-1 text-sm text-gray-700 dark:text-gray-300">
                  {step.content}
                </div>
              </div>
            ))}
            
          </div>
          
          {steps.length > 0 && (
            <div className="mt-3 pt-2 border-t border-blue-200 dark:border-blue-800">
              <div className="flex items-center gap-2 text-xs text-blue-600 dark:text-blue-400">
                <Brain className="h-3 w-3" />
                <span>
                  {isComplete 
                    ? `Completed ${steps.length} reasoning steps`
                    : `Step ${Math.max(...steps.map(s => s.step))} of ${Math.max(...steps.map(s => s.total_steps), steps[0]?.total_steps || 0)}`}
                </span>
              </div>
            </div>
          )}
        </CardContent>
      )}
    </Card>
  );
}