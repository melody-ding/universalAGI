import os
import re
import logging
from typing import BinaryIO, Optional
from fastapi import UploadFile
from database.s3_client import s3_client
from database.postgres_client import postgres_client
from database.models import DocumentUploadResponse
from services.document_parser import document_parser
from services.text_chunker import text_chunker
from services.embedding_service import embedding_service

logger = logging.getLogger(__name__)

class DocumentUploadService:
    def __init__(self):
        pass
    
    async def process_document_upload(self, file: UploadFile) -> DocumentUploadResponse:
        """
        Main orchestration method for document upload process.
        Follows the complete pipeline: hash -> dedup -> S3 -> parse -> chunk -> embed -> store
        """
        # Step 1: Receive file and record original filename
        original_filename = file.filename
        if not original_filename:
            raise ValueError("File must have a filename")
        
        # Step 2: Read file content once and create multiple streams
        file_content = await file.read()
        
        # Create separate streams for each operation
        hash_stream = self._create_file_stream(file_content)
        doc_hash = s3_client.compute_file_hash(hash_stream)
        
        # Step 3: Check for deduplication via database
        existing_doc = postgres_client.check_document_exists(doc_hash)
        if existing_doc:
            logger.info(f"Found existing document with checksum {doc_hash}, deleting and re-processing")
            # Delete existing document and segments to re-process
            postgres_client.delete_document_and_segments(existing_doc.id)
        
        # Step 4: Upload to S3
        upload_stream = self._create_file_stream(file_content)
        s3_key = s3_client.upload_file(upload_stream, doc_hash, original_filename)
        blob_link = s3_client.get_file_url(s3_key)
        
        # Step 5: Insert root document row
        title = self._clean_filename_for_title(original_filename)
        document_id = postgres_client.insert_document(title, doc_hash, blob_link)
        
        # Step 6: Extract text content
        parse_stream = self._create_file_stream(file_content)
        text_content = document_parser.parse_document(parse_stream, original_filename)
        logger.info(f"Extracted text length: {len(text_content)}")
        
        # Step 7: Chunk the text
        chunks = text_chunker.chunk_text(text_content)
        logger.info(f"Created {len(chunks)} chunks")
        
        # Step 8: Generate embeddings for all chunks
        chunk_texts = [chunk[1] for chunk in chunks]
        logger.info(f"About to generate embeddings for {len(chunk_texts)} chunks")
        embeddings = embedding_service.generate_embeddings_batch(chunk_texts)
        logger.info(f"Generated {len(embeddings)} embeddings")
        
        # Step 9: Insert segments
        segment_embeddings = []
        for i, ((segment_ordinal, chunk_text), embedding) in enumerate(zip(chunks, embeddings)):
            logger.info(f"Inserting segment {i+1}/{len(chunks)}")
            try:
                postgres_client.insert_document_segment(
                    document_id=document_id,
                    segment_ordinal=segment_ordinal,
                    text=chunk_text,
                    embedding=embedding
                )
                segment_embeddings.append(embedding)
                logger.info(f"Successfully inserted segment {i+1}")
            except Exception as e:
                logger.error(f"Failed to insert segment {i+1}: {str(e)}")
                raise
        
        # Step 10: Compute and store document-level embedding
        if segment_embeddings:
            logger.info(f"Computing document embedding from {len(segment_embeddings)} segments")
            # Also embed the title if it exists
            all_embeddings = segment_embeddings.copy()
            if title:
                title_embedding = embedding_service.generate_embedding(title)
                all_embeddings.append(title_embedding)
            
            document_embedding = embedding_service.compute_mean_embedding(all_embeddings)
            postgres_client.update_document_embedding(document_id, document_embedding)
            logger.info(f"Updated document embedding")
        
        # Step 11: Return response
        return DocumentUploadResponse(
            document_id=document_id,
            checksum=doc_hash,
            blob_link=blob_link,
            num_segments=len(chunks)
        )
    
    def _create_file_stream(self, content: bytes) -> BinaryIO:
        """Create a file-like stream from bytes content."""
        from io import BytesIO
        return BytesIO(content)
    
    def _clean_filename_for_title(self, filename: str) -> Optional[str]:
        """Clean filename to create a readable title."""
        if not filename:
            return None
        
        # Remove file extension
        name_without_ext = os.path.splitext(filename)[0]
        
        # Replace underscores and hyphens with spaces
        title = re.sub(r'[_-]', ' ', name_without_ext)
        
        # Remove special characters except spaces
        title = re.sub(r'[^\w\s]', '', title)
        
        # Clean up multiple spaces
        title = re.sub(r'\s+', ' ', title).strip()
        
        # Capitalize words
        title = title.title()
        
        return title if title else None

document_upload_service = DocumentUploadService()