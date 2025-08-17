"use client";

import { useState } from "react";
import { CitationInfo } from "@/lib/citations";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ExternalLink, Eye, Copy, Check } from "lucide-react";

interface CitationFootnotesProps {
  citations: CitationInfo[];
}

export function CitationFootnotes({ citations }: CitationFootnotesProps) {
  const [expandedCitations, setExpandedCitations] = useState<Set<number>>(new Set());
  const [copiedCitations, setCopiedCitations] = useState<Set<number>>(new Set());

  if (citations.length === 0) return null;

  const toggleExpanded = (index: number) => {
    const newExpanded = new Set(expandedCitations);
    if (newExpanded.has(index)) {
      newExpanded.delete(index);
    } else {
      newExpanded.add(index);
    }
    setExpandedCitations(newExpanded);
  };

  const copyToClipboard = async (citation: CitationInfo) => {
    try {
      const text = (citation as any).text || 'No text available';
      await navigator.clipboard.writeText(text);
      setCopiedCitations(prev => new Set(prev).add(citation.index));
      setTimeout(() => {
        setCopiedCitations(prev => {
          const newSet = new Set(prev);
          newSet.delete(citation.index);
          return newSet;
        });
      }, 2000);
    } catch (error) {
      console.error('Failed to copy text:', error);
    }
  };

  return (
    <div className="mt-6 border-t pt-4">
      <h3 className="text-sm font-semibold text-gray-700 mb-3">Sources & Citations</h3>
      <div className="space-y-2">
        {citations.map((citation, index) => {
          const isExpanded = expandedCitations.has(citation.index);
          const isCopied = copiedCitations.has(citation.index);
          
          // Create a safe unique key (handle both camelCase and snake_case)
          const docId = (citation as any).documentId || (citation as any).document_id;
          const segOrdinal = (citation as any).segmentOrdinal || (citation as any).segment_ordinal;
          const safeKey = docId && segOrdinal !== undefined
            ? `${docId}-${segOrdinal}-${citation.index}`
            : `citation-${citation.index || index}`;
          
          return (
            <Card 
              key={safeKey}
              id={`citation-${citation.index || index + 1}`}
              className="text-xs scroll-mt-4"
            >
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-xs">
                    <span className="inline-flex items-center gap-2">
                      <span className="font-mono bg-blue-100 text-blue-700 px-1 py-0.5 rounded">
                        [{citation.index || index + 1}]
                      </span>
                      <span className="font-medium text-gray-900">
                        {(citation as any).documentTitle || (citation as any).document_title || 'Unknown Document'}
                      </span>
                    </span>
                  </CardTitle>
                  <div className="flex items-center gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => copyToClipboard(citation)}
                      className="h-6 w-6 p-0"
                      title="Copy citation text"
                    >
                      {isCopied ? (
                        <Check className="w-3 h-3 text-green-600" />
                      ) : (
                        <Copy className="w-3 h-3" />
                      )}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => toggleExpanded(citation.index)}
                      className="h-6 w-6 p-0"
                      title={isExpanded ? "Hide full text" : "Show full text"}
                    >
                      <Eye className="w-3 h-3" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        const url = (citation as any).documentUrl || (citation as any).document_url;
                        if (url) window.open(url, '_blank');
                      }}
                      className="h-6 w-6 p-0"
                      title="View document"
                      disabled={!((citation as any).documentUrl || (citation as any).document_url)}
                    >
                      <ExternalLink className="w-3 h-3" />
                    </Button>
                  </div>
                </div>
              </CardHeader>
              {isExpanded && (
                <CardContent className="pt-0">
                  <div className="bg-gray-50 p-2 rounded border text-xs text-gray-700 leading-relaxed">
                    {(citation as any).text || 'Citation text not available'}
                  </div>
                </CardContent>
              )}
            </Card>
          );
        })}
      </div>
    </div>
  );
}
