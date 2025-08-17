import io
import re
from typing import BinaryIO
from PyPDF2 import PdfReader
from docx import Document

class DocumentParser:
    def __init__(self):
        pass
    
    def parse_document(self, file_stream: BinaryIO, filename: str) -> str:
        """Parse document content based on file type."""
        file_extension = filename.lower().split('.')[-1]
        
        if file_extension == 'pdf':
            return self._parse_pdf(file_stream)
        elif file_extension in ['docx', 'doc']:
            return self._parse_docx(file_stream)
        elif file_extension == 'txt':
            return self._parse_txt(file_stream)
        else:
            raise ValueError(f"Unsupported file type: {file_extension}")
    
    def _parse_pdf(self, file_stream: BinaryIO) -> str:
        """Extract text from PDF file."""
        file_stream.seek(0)
        reader = PdfReader(file_stream)
        
        text_content = []
        for page_num, page in enumerate(reader.pages):
            text = page.extract_text()
            if text.strip():
                # Clean up each page before combining
                page_text = self._clean_page_text(text)
                if page_text.strip():
                    text_content.append(page_text)
        
        full_text = '\n\n'.join(text_content)
        return self._normalize_text(full_text)
    
    def _clean_page_text(self, text: str) -> str:
        """Clean individual page text before normalization."""
        # Remove common PDF extraction artifacts
        text = re.sub(r'\uf0b7', '• ', text)  # Bullet point Unicode
        text = re.sub(r'\uf020', ' ', text)   # Non-breaking space
        text = re.sub(r'\x0c', '\n', text)    # Form feed to newline
        
        # Fix character encoding issues
        text = text.replace('\u2019', "'")    # Right single quotation
        text = text.replace('\u2018', "'")    # Left single quotation
        text = text.replace('\u201c', '"')    # Left double quotation
        text = text.replace('\u201d', '"')    # Right double quotation
        text = text.replace('\u2013', '-')    # En dash
        text = text.replace('\u2014', '--')   # Em dash
        text = text.replace('\u2026', '...')  # Ellipsis
        
        return text
    
    def _parse_docx(self, file_stream: BinaryIO) -> str:
        """Extract text from DOCX file."""
        file_stream.seek(0)
        doc = Document(file_stream)
        
        text_content = []
        for paragraph in doc.paragraphs:
            text = paragraph.text.strip()
            if text:
                text_content.append(text)
        
        full_text = '\n'.join(text_content)
        return self._normalize_text(full_text)
    
    def _parse_txt(self, file_stream: BinaryIO) -> str:
        """Extract text from TXT file."""
        file_stream.seek(0)
        content = file_stream.read()
        
        # Try to decode as UTF-8, fallback to latin-1
        try:
            text = content.decode('utf-8')
        except UnicodeDecodeError:
            text = content.decode('latin-1')
        
        return self._normalize_text(text)
    
    def _normalize_text(self, text: str) -> str:
        """Normalize whitespace and clean up text."""
        # Fix broken words split across lines (common in PDFs)
        text = re.sub(r'(\w)-\s*\n\s*(\w)', r'\1\2', text)
        
        # Handle bullet points and lists better
        text = re.sub(r'^\s*[•·▪▫‣⁃]\s*', '• ', text, flags=re.MULTILINE)
        text = re.sub(r'^\s*[\-\*]\s+', '• ', text, flags=re.MULTILINE)
        
        # Preserve paragraph breaks but normalize spacing
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)  # Multiple newlines to double
        text = re.sub(r'(?<!\n)\n(?!\n)', ' ', text)    # Single newlines to spaces
        
        # Remove common header/footer patterns
        text = re.sub(r'Page \d+ of \d+', '', text, flags=re.IGNORECASE)
        text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'\b\d{1,2}/\d{1,2}/\d{2,4}\b', '', text)  # Remove dates
        
        # Clean up repeated punctuation and spaces
        text = re.sub(r'\.{3,}', '...', text)           # Multiple dots
        text = re.sub(r'\s{2,}', ' ', text)             # Multiple spaces
        text = re.sub(r'\t+', ' ', text)                # Tabs to single space
        
        # Remove standalone numbers (page numbers, etc.)
        text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)
        
        # Remove table of contents patterns
        text = re.sub(r'^.*?\.{3,}\s*\d+\s*$', '', text, flags=re.MULTILINE)
        
        # Remove headers/footers with common patterns
        text = re.sub(r'^\s*(CONFIDENTIAL|PROPRIETARY|DRAFT|INTERNAL USE ONLY).*$', '', text, flags=re.MULTILINE | re.IGNORECASE)
        text = re.sub(r'^\s*Page \d+ of \d+.*$', '', text, flags=re.MULTILINE | re.IGNORECASE)
        text = re.sub(r'^\s*\d+\s*/\s*\d+\s*$', '', text, flags=re.MULTILINE)
        
        # Remove watermarks and document metadata
        text = re.sub(r'Generated on \d{1,2}/\d{1,2}/\d{4}', '', text, flags=re.IGNORECASE)
        text = re.sub(r'Printed on \d{1,2}/\d{1,2}/\d{4}', '', text, flags=re.IGNORECASE)
        
        # Clean up tables with excessive spacing
        text = re.sub(r'\s*\|\s*', ' | ', text)  # Normalize table separators
        text = re.sub(r'_{3,}', '', text)        # Remove underline formatting
        
        # Remove excessive punctuation artifacts
        text = re.sub(r'[^\w\s\.\,\!\?\;\:\-\(\)\[\]\{\}\"\'\/\@\#\$\%\&\*\+\=\<\>\|\\\^\~\`\•]', '', text)
        
        # Final cleanup
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)  # Normalize paragraph breaks
        text = text.strip()
        
        return text

document_parser = DocumentParser()