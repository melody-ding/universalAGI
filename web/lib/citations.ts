import { API_BASE_URL } from './api';

export interface CitationToken {
  documentId: number;
  segmentOrdinal: number;
}

export interface ResolvedCitation {
  documentId: number;
  segmentOrdinal: number;
  text: string;
  documentTitle: string;
  documentUrl: string;
}

export interface CitationInfo extends ResolvedCitation {
  index: number; // For footnote numbering
}

/**
 * Parse citation tokens from text and return unique citations
 * @param text - Text containing citation tokens like [[doc:123, seg:45]]
 * @returns Array of unique citation tokens and text with citation markers
 */
export function parseCitationTokens(text: string): {
  tokens: CitationToken[];
  textWithMarkers: string;
} {
  const citationRegex = /\[\[doc:(\d+),\s*seg:(\d+)\]\]/g;
  const tokens: CitationToken[] = [];
  const seenCitations = new Set<string>();
  
  let match;
  let citationIndex = 1;
  let processedText = text;
  
  while ((match = citationRegex.exec(text)) !== null) {
    const documentId = parseInt(match[1]);
    const segmentOrdinal = parseInt(match[2]);
    const citationKey = `${documentId}-${segmentOrdinal}`;
    
    if (!seenCitations.has(citationKey)) {
      seenCitations.add(citationKey);
      tokens.push({ documentId, segmentOrdinal });
      
      // Replace citation token with footnote marker
      processedText = processedText.replace(
        match[0],
        `<sup class="citation-marker" data-citation-index="${citationIndex}">[${citationIndex}]</sup>`
      );
      citationIndex++;
    } else {
      // Find existing index for this citation
      const existingIndex = tokens.findIndex(
        token => token.documentId === documentId && token.segmentOrdinal === segmentOrdinal
      ) + 1;
      
      processedText = processedText.replace(
        match[0],
        `<sup class="citation-marker" data-citation-index="${existingIndex}">[${existingIndex}]</sup>`
      );
    }
  }
  
  return { tokens, textWithMarkers: processedText };
}

/**
 * Resolve citation tokens to full citation information
 * @param tokens - Array of citation tokens to resolve
 * @returns Promise resolving to array of citation info
 */
export async function resolveCitations(tokens: CitationToken[]): Promise<CitationInfo[]> {
  if (tokens.length === 0) return [];
  
  const requestBody = {
    citations: tokens.map(token => ({
      document_id: token.documentId,
      segment_ordinal: token.segmentOrdinal
    }))
  };
  
  try {
    console.log('Resolving citations with request:', requestBody);
    const response = await fetch(`${API_BASE_URL}/resolve-citations`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestBody),
    });
    
    console.log('Citation resolution response status:', response.status);
    
    if (!response.ok) {
      const errorText = await response.text();
      console.error('Citation resolution failed with response:', errorText);
      throw new Error(`Failed to resolve citations: ${response.status} - ${errorText}`);
    }
    
    const data = await response.json();
    console.log('Citation resolution response data:', data);
    
    const resolvedCitations = data.citations.map((citation: ResolvedCitation, index: number) => ({
      ...citation,
      index: index + 1
    }));
    
    console.log('Final resolved citations:', resolvedCitations);
    return resolvedCitations;
  } catch (error) {
    console.error('Error resolving citations:', error);
    return [];
  }
}

/**
 * Process message text with citations - parse tokens and resolve them
 * @param text - Raw message text with citation tokens
 * @returns Object with processed text and citation information
 */
export async function processMessageWithCitations(text: string): Promise<{
  processedText: string;
  citations: CitationInfo[];
}> {
  const { tokens, textWithMarkers } = parseCitationTokens(text);
  const citations = await resolveCitations(tokens);
  
  return {
    processedText: textWithMarkers,
    citations
  };
}
