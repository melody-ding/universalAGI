export interface ThinkingStep {
  content: string;
  step: number;
  total_steps: number;
}

export interface Message {
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
