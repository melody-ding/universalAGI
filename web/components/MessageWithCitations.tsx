"use client";

import { useState, useEffect } from "react";
import { MarkdownMessage } from "./MarkdownMessage";
import { CitationFootnotes } from "./CitationFootnotes";
import { CitationInfo } from "@/lib/citations";

interface MessageWithCitationsProps {
  content: string;
  className?: string;
  messageId?: string; // Unique identifier for this message
}

export function MessageWithCitations({ content, className = "", messageId }: MessageWithCitationsProps) {
  // Generate a unique message ID if not provided
  const uniqueMessageId = messageId || `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  const [citations, setCitations] = useState<CitationInfo[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);

  useEffect(() => {
    const processCitations = async () => {
      if (!content.includes('[[doc:')) {
        setCitations([]);
        return;
      }

      setIsProcessing(true);
      try {
        // Extract unique citation tokens
        const citationRegex = /\[\[doc:(\d+),\s*seg:(\d+)\]\]/g;
        const tokens = [];
        const seenCitations = new Set<string>();
        
        let match;
        while ((match = citationRegex.exec(content)) !== null) {
          const documentId = parseInt(match[1]);
          const segmentOrdinal = parseInt(match[2]);
          const citationKey = `${documentId}-${segmentOrdinal}`;
          
          if (!seenCitations.has(citationKey)) {
            seenCitations.add(citationKey);
            tokens.push({ documentId, segmentOrdinal });
          }
        }
        
        // Resolve citations
        if (tokens.length > 0) {
          console.log('Found citation tokens:', tokens);
          const resolveCitations = (await import('@/lib/citations')).resolveCitations;
          const resolvedCitations = await resolveCitations(tokens);
          console.log('Resolved citations:', resolvedCitations);
          console.log('Setting citations with indices:', resolvedCitations.map(c => c.index));
          console.log('Citation data structure check:', resolvedCitations.map(c => ({
            index: c.index,
            documentId: c.documentId,
            segmentOrdinal: c.segmentOrdinal,
            hasTitle: !!c.documentTitle,
            hasText: !!c.text,
            hasUrl: !!c.documentUrl
          })));
          setCitations(resolvedCitations);
        } else {
          console.log('No citation tokens found');
          setCitations([]);
        }
      } catch (error) {
        console.error('Error processing citations:', error);
        setCitations([]);
      } finally {
        setIsProcessing(false);
      }
    };

    processCitations();
  }, [content]);

  // Create a wrapper that processes citations in a simple, reliable way
  const CitationWrapper = ({ content }: { content: string }) => {
    // Parse citation tokens and replace with simple numbered markers
    const citationRegex = /\[\[doc:(\d+),\s*seg:(\d+)\]\]/g;
    const seenCitations = new Map<string, number>();
    let citationCounter = 1;
    
    // Replace citation tokens with simple clickable spans using unique message-scoped IDs
    const processedContent = content.replace(citationRegex, (match, docId, segId) => {
      const citationKey = `${docId}-${segId}`;
      
      if (!seenCitations.has(citationKey)) {
        seenCitations.set(citationKey, citationCounter++);
      }
      
      const citationNumber = seenCitations.get(citationKey);
      const uniqueCitationId = `${uniqueMessageId}-citation-${citationNumber}`;
      return `<sup class="citation-marker" data-citation="${citationNumber}" data-message-id="${uniqueMessageId}" style="color: #2563eb; cursor: pointer; font-family: ui-monospace, SFMono-Regular, monospace; font-size: 0.75rem; margin-left: 0.125rem; padding: 0.125rem 0.25rem; border-radius: 0.25rem; transition: all 0.2s ease; background-color: rgba(37, 99, 235, 0.1);">[${citationNumber}]</sup>`;
    });

    const handleCitationClick = (citationNumber: string) => {
      const uniqueCitationId = `${uniqueMessageId}-citation-${citationNumber}`;
      console.log(`Citation ${citationNumber} clicked for message ${uniqueMessageId}`);
      console.log('Looking for element with ID:', uniqueCitationId);
      console.log('Available citations:', citations.map((c: any) => c.index));
      
      const citationElement = document.getElementById(uniqueCitationId);
      console.log('Citation element found:', citationElement);
      
      if (citationElement) {
        citationElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
        citationElement.classList.add('highlight-citation');
        setTimeout(() => {
          citationElement.classList.remove('highlight-citation');
        }, 2000);
      } else {
        console.warn(`Citation element with ID ${uniqueCitationId} not found`);
        // Try again after a short delay in case footnotes are still rendering
        setTimeout(() => {
          const retryElement = document.getElementById(uniqueCitationId);
          if (retryElement) {
            retryElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
            retryElement.classList.add('highlight-citation');
            setTimeout(() => {
              retryElement.classList.remove('highlight-citation');
            }, 2000);
          }
        }, 500);
      }
    };

    // Add click handlers after component mounts - only for citations in this message
    useEffect(() => {
      const citationElements = document.querySelectorAll(`.citation-marker[data-message-id="${uniqueMessageId}"]`);
      citationElements.forEach((element) => {
        const citationNumber = element.getAttribute('data-citation');
        if (citationNumber) {
          const clickHandler = (e: Event) => {
            e.preventDefault();
            handleCitationClick(citationNumber);
          };
          element.addEventListener('click', clickHandler);
          
          // Store handler for cleanup
          (element as any)._clickHandler = clickHandler;
        }
      });

      // Cleanup function
      return () => {
        const citationElements = document.querySelectorAll(`.citation-marker[data-message-id="${uniqueMessageId}"]`);
        citationElements.forEach((element) => {
          if ((element as any)._clickHandler) {
            element.removeEventListener('click', (element as any)._clickHandler);
            delete (element as any)._clickHandler;
          }
        });
      };
    }, [processedContent, citations, uniqueMessageId]);

    return (
      <div className="citation-container">
        <MarkdownMessage content={processedContent} />
      </div>
    );
  };

  if (isProcessing) {
    return (
      <div className={className}>
        <MarkdownMessage content={content} />
        <div className="text-xs text-gray-500 mt-2">Processing citations...</div>
      </div>
    );
  }

  // Debug: Show if citations were found
  console.log(`Citations loaded for content: ${citations.length} citations found`);

  const renderContent = () => {
    if (!content.includes('[[doc:')) {
      console.log('No citations found in content:', content.substring(0, 100) + '...');
      return <MarkdownMessage content={content} />;
    }

    console.log('Processing content with citations:', content.substring(0, 100) + '...');
    console.log('Citation tokens found:', content.match(/\[\[doc:\d+,\s*seg:\d+\]\]/g) || []);
    return <CitationWrapper content={content} />;
  };

  return (
    <div className={className}>
      {renderContent()}
      <CitationFootnotes citations={citations} messageId={uniqueMessageId} />
      
      {/* Add CSS for citation highlighting */}
      <style jsx>{`
        :global(.highlight-citation) {
          background-color: #fef3c7;
          transition: background-color 0.3s ease;
          border-radius: 4px;
          padding: 2px 4px;
        }
        :global(.citation-marker:hover) {
          color: #1d4ed8 !important;
          background-color: #dbeafe !important;
        }
      `}</style>
    </div>
  );
}
