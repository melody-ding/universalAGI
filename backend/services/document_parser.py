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
        for page in reader.pages:
            text = page.extract_text()
            if text.strip():
                text_content.append(text)
        
        full_text = '\n'.join(text_content)
        return self._normalize_text(full_text)
    
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
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove common header/footer patterns (basic cleanup)
        text = re.sub(r'Page \d+ of \d+', '', text, flags=re.IGNORECASE)
        text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)
        
        # Clean up line breaks and spacing
        text = text.strip()
        
        return text

document_parser = DocumentParser()