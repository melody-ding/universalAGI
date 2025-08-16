import boto3
import os
import logging
from typing import List, Optional, Dict, Any
from database.models import DocumentModel, DocumentSegmentModel

logger = logging.getLogger(__name__)

class PostgresClient:
    def __init__(self):
        self.rds_client = boto3.client(
            'rds-data',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_REGION', 'us-east-1')
        )
        self.database_arn = os.getenv('RDS_CLUSTER_ARN')
        self.secret_arn = os.getenv('RDS_SECRET_ARN')
        self.database_name = os.getenv('RDS_DATABASE_NAME', 'postgres')
    
    def execute_statement(self, sql: str, parameters: List = None):
        """Execute SQL statement using RDS Data API."""
        params = {
            'resourceArn': self.database_arn,
            'secretArn': self.secret_arn,
            'database': self.database_name,
            'sql': sql
        }
        
        if parameters:
            params['parameters'] = parameters
        
        return self.rds_client.execute_statement(**params)
    
    def check_document_exists(self, checksum: str) -> Optional[DocumentModel]:
        """Check if a document with the given checksum already exists."""
        response = self.execute_statement(
            "SELECT id, title, checksum, blob_link, embedding, created_at FROM documents WHERE checksum = :checksum",
            [{'name': 'checksum', 'value': {'stringValue': checksum}}]
        )
        
        if response['records']:
            record = response['records'][0]
            
            # Parse created_at datetime from string if present
            created_at = None
            if len(record) > 5 and record[5].get('stringValue'):
                from datetime import datetime
                try:
                    created_at = datetime.fromisoformat(record[5]['stringValue'].replace('Z', '+00:00'))
                except:
                    created_at = None
            
            return DocumentModel(
                id=record[0].get('longValue'),
                title=record[1].get('stringValue'),
                checksum=record[2].get('stringValue'),
                blob_link=record[3].get('stringValue'),
                embedding=None,  # Skip embedding parsing for now
                created_at=created_at
            )
        return None
    
    def insert_document(self, title: Optional[str], checksum: str, blob_link: str) -> int:
        """Insert a new document and return its ID."""
        parameters = [
            {'name': 'title', 'value': {'stringValue': title} if title else {'isNull': True}},
            {'name': 'checksum', 'value': {'stringValue': checksum}},
            {'name': 'blob_link', 'value': {'stringValue': blob_link}}
        ]
        
        response = self.execute_statement(
            """
            INSERT INTO documents (title, checksum, blob_link)
            VALUES (:title, :checksum, :blob_link)
            RETURNING id
            """,
            parameters
        )
        
        return response['records'][0][0]['longValue']
    
    def insert_document_segment(self, document_id: int, segment_ordinal: int, text: str, embedding: List[float]) -> int:
        """Insert a document segment and return its ID."""
        # Convert embedding list to string format for vector type
        embedding_str = '[' + ','.join(map(str, embedding)) + ']'
        logger.info(f"Inserting segment with embedding length: {len(embedding)}")
        logger.info(f"Embedding string preview: {embedding_str[:100]}...")
        
        parameters = [
            {'name': 'document_id', 'value': {'longValue': document_id}},
            {'name': 'segment_ordinal', 'value': {'longValue': segment_ordinal}},
            {'name': 'text', 'value': {'stringValue': text}},
            {'name': 'embedding', 'value': {'stringValue': embedding_str}}
        ]
        
        try:
            response = self.execute_statement(
                """
                INSERT INTO document_segments (document_id, segment_ordinal, text, embedding)
                VALUES (:document_id, :segment_ordinal, :text, :embedding::vector)
                RETURNING id
                """,
                parameters
            )
            
            return response['records'][0][0]['longValue']
        except Exception as e:
            logger.error(f"Error in insert_document_segment: {str(e)}")
            logger.info(f"Parameters were: document_id={document_id}, segment_ordinal={segment_ordinal}, text_length={len(text)}")
            raise
    
    def update_document_embedding(self, document_id: int, embedding: List[float]):
        """Update the document's mean-pooled embedding."""
        embedding_str = '[' + ','.join(map(str, embedding)) + ']'
        logger.info(f"Updating document {document_id} embedding with length: {len(embedding)}")
        
        parameters = [
            {'name': 'embedding', 'value': {'stringValue': embedding_str}},
            {'name': 'document_id', 'value': {'longValue': document_id}}
        ]
        
        try:
            self.execute_statement(
                "UPDATE documents SET embedding = :embedding::vector WHERE id = :document_id",
                parameters
            )
            logger.info(f"Successfully updated document {document_id} embedding")
        except Exception as e:
            logger.error(f"Error in update_document_embedding: {str(e)}")
            raise
    
    def get_document_segments_count(self, document_id: int) -> int:
        """Get the count of segments for a document."""
        parameters = [
            {'name': 'document_id', 'value': {'longValue': document_id}}
        ]
        
        response = self.execute_statement(
            "SELECT COUNT(*) FROM document_segments WHERE document_id = :document_id",
            parameters
        )
        
        return response['records'][0][0]['longValue']
    
    def delete_document_and_segments(self, document_id: int, include_s3_cleanup: bool = True):
        """Delete a document and all its segments from database and optionally S3."""
        logger.info(f"Deleting document {document_id} and its segments (S3 cleanup: {include_s3_cleanup})")
        
        # Get document info for S3 deletion if needed
        document_checksum = None
        if include_s3_cleanup:
            doc_response = self.execute_statement(
                "SELECT checksum FROM documents WHERE id = :document_id",
                [{'name': 'document_id', 'value': {'longValue': document_id}}]
            )
            if doc_response['records']:
                document_checksum = doc_response['records'][0][0].get('stringValue')
        
        # Delete segments first (due to foreign key constraint)
        parameters = [
            {'name': 'document_id', 'value': {'longValue': document_id}}
        ]
        
        try:
            # Delete all segments for this document
            self.execute_statement(
                "DELETE FROM document_segments WHERE document_id = :document_id",
                parameters
            )
            logger.info(f"Deleted segments for document {document_id}")
            
            # Delete the document
            self.execute_statement(
                "DELETE FROM documents WHERE id = :document_id",
                parameters
            )
            logger.info(f"Deleted document {document_id}")
            
            # Delete from S3 if requested and we have the checksum
            if include_s3_cleanup and document_checksum:
                from database.s3_client import s3_client
                try:
                    s3_client.delete_file_by_hash(document_checksum)
                    logger.info(f"Deleted S3 files for document {document_id} with checksum {document_checksum}")
                except Exception as s3_error:
                    logger.warning(f"Failed to delete S3 files for document {document_id}: {str(s3_error)}")
            
        except Exception as e:
            logger.error(f"Error in delete_document_and_segments: {str(e)}")
            raise
    
    def get_all_documents(self) -> List[DocumentModel]:
        """Get all documents from the database."""
        response = self.execute_statement(
            "SELECT id, title, checksum, blob_link, created_at FROM documents ORDER BY created_at DESC"
        )
        
        documents = []
        for record in response['records']:
            # Parse created_at datetime from string if present
            created_at = None
            if len(record) > 4 and record[4].get('stringValue'):
                from datetime import datetime
                try:
                    created_at = datetime.fromisoformat(record[4]['stringValue'].replace('Z', '+00:00'))
                except:
                    created_at = None
            
            documents.append(DocumentModel(
                id=record[0].get('longValue'),
                title=record[1].get('stringValue'),
                checksum=record[2].get('stringValue'),
                blob_link=record[3].get('stringValue'),
                embedding=None,  # Skip embedding parsing for listing
                created_at=created_at
            ))
        
        return documents

postgres_client = PostgresClient()