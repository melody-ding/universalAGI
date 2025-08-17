"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { XCircle } from "lucide-react";

interface ErrorDisplayProps {
  error: string;
  onDismiss: () => void;
}

export function ErrorDisplay({ error, onDismiss }: ErrorDisplayProps) {
  return (
    <Card className="border-red-200 bg-red-50">
      <CardContent className="p-4">
        <div className="flex items-center">
          <XCircle className="h-5 w-5 text-red-600 mr-3" />
          <div>
            <h3 className="text-sm font-medium text-red-800">Analysis Error</h3>
            <p className="text-sm text-red-700 mt-1">{error}</p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={onDismiss}
            className="ml-auto text-red-600 border-red-300 hover:bg-red-100"
          >
            Dismiss
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}