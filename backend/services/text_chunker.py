import re
from typing import List, Tuple

class TextChunker:
    def __init__(self, max_tokens: int = 800, overlap_tokens: int = 50):
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
    
    def chunk_text(self, text: str) -> List[Tuple[int, str]]:
        """
        Split text into chunks with overlap.
        Returns list of tuples: (segment_ordinal, chunk_text)
        """
        # Simple tokenization by splitting on whitespace and punctuation
        tokens = self._tokenize(text)
        
        if len(tokens) <= self.max_tokens:
            return [(0, text)]
        
        chunks = []
        chunk_ordinal = 0
        start_idx = 0
        
        while start_idx < len(tokens):
            # Calculate end index for this chunk
            end_idx = min(start_idx + self.max_tokens, len(tokens))
            
            # Extract chunk tokens
            chunk_tokens = tokens[start_idx:end_idx]
            chunk_text = self._reconstruct_text(chunk_tokens)
            
            # Add chunk to list
            chunks.append((chunk_ordinal, chunk_text))
            chunk_ordinal += 1
            
            # Calculate next start position with overlap
            if end_idx >= len(tokens):
                break
            
            start_idx = end_idx - self.overlap_tokens
            
            # Ensure we don't go backwards
            if start_idx <= 0:
                start_idx = end_idx
        
        return chunks
    
    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization by splitting on whitespace and preserving punctuation."""
        # Split on whitespace but keep punctuation attached
        tokens = text.split()
        return tokens
    
    def _reconstruct_text(self, tokens: List[str]) -> str:
        """Reconstruct text from tokens."""
        return ' '.join(tokens).strip()
    
    def estimate_tokens(self, text: str) -> int:
        """Estimate the number of tokens in text."""
        return len(self._tokenize(text))

text_chunker = TextChunker()