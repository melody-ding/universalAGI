"use client";

import { useState, useEffect } from "react";
import { MarkdownMessage } from "./MarkdownMessage";
import { CitationFootnotes } from "./CitationFootnotes";
import { CitationInfo } from "@/lib/citations";

interface MessageWithCitationsProps {
  content: string;
  className?: string;
}

export function MessageWithCitations({ content, className = "" }: MessageWithCitationsProps) {
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

  // Create a wrapper that adds click handlers after markdown rendering
  const CitationWrapper = ({ content }: { content: string }) => {
    // Parse citation tokens and replace with simple numbered markers for markdown
    const citationRegex = /\[\[doc:(\d+),\s*seg:(\d+)\]\]/g;
    const seenCitations = new Map<string, number>();
    let citationCounter = 1;
    
    // Replace citation tokens with simple markers that markdown won't interfere with
    const markdownContent = content.replace(citationRegex, (match, docId, segId) => {
      const citationKey = `${docId}-${segId}`;
      
      if (!seenCitations.has(citationKey)) {
        seenCitations.set(citationKey, citationCounter++);
      }
      
      const citationNumber = seenCitations.get(citationKey);
      return `[${citationNumber}]`;
    });

    // Use useEffect to add click handlers after the component mounts
    useEffect(() => {
      const addClickHandlers = () => {
        const citationElements = document.querySelectorAll('.citation-marker-processed');
        citationElements.forEach((element) => {
          const citationNumber = element.getAttribute('data-citation');
          if (citationNumber) {
            element.addEventListener('click', (e) => {
              e.preventDefault();
              console.log(`Citation ${citationNumber} clicked`);
              console.log('Looking for element with ID:', `citation-${citationNumber}`);
              console.log('Available citations:', citations.map(c => c.index));
              console.log('All elements with citation IDs:', Array.from(document.querySelectorAll('[id^="citation-"]')).map(el => el.id));
              const citationElement = document.getElementById(`citation-${citationNumber}`);
              console.log('Citation element found:', citationElement);
              if (citationElement) {
                citationElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
                citationElement.classList.add('highlight-citation');
                setTimeout(() => {
                  citationElement.classList.remove('highlight-citation');
                }, 2000);
              } else {
                console.warn(`Citation element with ID citation-${citationNumber} not found`);
                // Try again after a short delay in case footnotes are still rendering
                setTimeout(() => {
                  const retryElement = document.getElementById(`citation-${citationNumber}`);
                  console.log('Retry - Citation element found:', retryElement);
                  if (retryElement) {
                    retryElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    retryElement.classList.add('highlight-citation');
                    setTimeout(() => {
                      retryElement.classList.remove('highlight-citation');
                    }, 2000);
                  }
                }, 500);
              }
            });
          }
        });
      };

      // Process citations after the component renders
      const timer = setTimeout(() => {
        const container = document.querySelector('.citation-container');
        if (container) {
          const textContent = container.innerHTML;
          
          // Replace [1], [2], etc. with clickable elements
          const processedHTML = textContent.replace(/\[(\d+)\]/g, (match, num) => {
            return `<sup class="citation-marker-processed" data-citation="${num}" style="color: #2563eb; cursor: pointer; font-family: ui-monospace, SFMono-Regular, monospace; font-size: 0.75rem; margin-left: 0.125rem; padding: 0.125rem 0.25rem; border-radius: 0.25rem; transition: all 0.2s ease;">[${num}]</sup>`;
          });
          
          container.innerHTML = processedHTML;
          addClickHandlers();
        }
      }, 100);

      return () => clearTimeout(timer);
    }, [content]);

    return (
      <div className="citation-container">
        <MarkdownMessage content={markdownContent} />
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
      console.log('No citations found in content:', content);
      return <MarkdownMessage content={content} />;
    }

    console.log('Processing content with citations:', content);
    return <CitationWrapper content={content} />;
  };

  return (
    <div className={className}>
      {renderContent()}
      <CitationFootnotes citations={citations} />
      
      {/* Add CSS for citation highlighting */}
      <style jsx>{`
        :global(.highlight-citation) {
          background-color: #fef3c7;
          transition: background-color 0.3s ease;
          border-radius: 4px;
          padding: 2px 4px;
        }
        :global(.citation-marker-processed:hover) {
          color: #1d4ed8 !important;
          background-color: #dbeafe !important;
        }
      `}</style>
    </div>
  );
}
