import boto3
import os
import time
from typing import List, Optional, Dict, Any
from database.models import DocumentModel, DocumentSegmentModel, ComplianceGroupModel
from services.embedding_service import embedding_service
from utils.logging_config import get_logger, log_database_operation
from utils.retry import retry_database_operation
from utils.exceptions import DatabaseError, ConnectionError, create_database_error

logger = get_logger(__name__)

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
    
    @retry_database_operation("execute_statement")
    def execute_statement(self, sql: str, parameters: List = None):
        """Execute SQL statement using RDS Data API."""
        start_time = time.time()
        logger = get_logger(__name__)
        
        try:
            params = {
                'resourceArn': self.database_arn,
                'secretArn': self.secret_arn,
                'database': self.database_name,
                'sql': sql
            }
            
            if parameters:
                params['parameters'] = parameters
            
            result = self.rds_client.execute_statement(**params)
            
            # Log successful operation
            duration = time.time() - start_time
            log_database_operation(
                logger.bind(operation="execute_statement"),
                "EXECUTE", "custom", duration, True
            )
            
            return result
            
        except Exception as e:
            # Log failed operation
            duration = time.time() - start_time
            log_database_operation(
                logger.bind(operation="execute_statement"),
                "EXECUTE", "custom", duration, False
            )
            
            # Raise appropriate error
            raise create_database_error("EXECUTE", "custom", e)
    
    def check_document_exists(self, checksum: str) -> Optional[DocumentModel]:
        """Check if a document with the given checksum already exists."""
        response = self.execute_statement(
            "SELECT id, title, checksum, blob_link, mime_type, created_at FROM documents WHERE checksum = :checksum",
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
                mime_type=record[4].get('stringValue'),
                embedding=None,  # Skip embedding parsing for now
                created_at=created_at
            )
        return None
    
    def insert_document(self, title: Optional[str], checksum: str, blob_link: str, mime_type: Optional[str] = None) -> int:
        """Insert a new document and return its ID."""
        parameters = [
            {'name': 'title', 'value': {'stringValue': title} if title else {'isNull': True}},
            {'name': 'checksum', 'value': {'stringValue': checksum}},
            {'name': 'blob_link', 'value': {'stringValue': blob_link}},
            {'name': 'mime_type', 'value': {'stringValue': mime_type} if mime_type else {'isNull': True}}
        ]
        
        response = self.execute_statement(
            """
            INSERT INTO documents (title, checksum, blob_link, mime_type)
            VALUES (:title, :checksum, :blob_link, :mime_type)
            RETURNING id
            """,
            parameters
        )
        
        return response['records'][0][0]['longValue']
    
    @retry_database_operation("insert_document_segment")
    def insert_document_segment(self, document_id: int, segment_ordinal: int, text: str, embedding: List[float]) -> int:
        """Insert a document segment and return its ID."""
        start_time = time.time()
        logger = get_logger(__name__)
        
        # Convert embedding list to string format for vector type
        embedding_str = '[' + ','.join(map(str, embedding)) + ']'
        logger.info(
            "Inserting document segment",
            extra_fields={
                "document_id": document_id,
                "segment_ordinal": segment_ordinal,
                "text_length": len(text),
                "embedding_length": len(embedding)
            }
        )
        
        try:
            parameters = [
                {'name': 'document_id', 'value': {'longValue': document_id}},
                {'name': 'segment_ordinal', 'value': {'longValue': segment_ordinal}},
                {'name': 'text', 'value': {'stringValue': text}},
                {'name': 'embedding', 'value': {'stringValue': embedding_str}}
            ]
            
            response = self.execute_statement(
                """
                INSERT INTO document_segments (document_id, segment_ordinal, text, embedding)
                VALUES (:document_id, :segment_ordinal, :text, :embedding::vector)
                RETURNING id
                """,
                parameters
            )
            
            segment_id = response['records'][0][0]['longValue']
            
            # Log successful operation
            duration = time.time() - start_time
            log_database_operation(
                logger.bind(operation="insert_document_segment"),
                "INSERT", "document_segments", duration, True,
                document_id=document_id, segment_id=segment_id
            )
            
            return segment_id
            
        except Exception as e:
            # Log failed operation
            duration = time.time() - start_time
            log_database_operation(
                logger.bind(operation="insert_document_segment"),
                "INSERT", "document_segments", duration, False,
                document_id=document_id, segment_ordinal=segment_ordinal
            )
            
            # Raise appropriate error
            raise create_database_error("INSERT", "document_segments", e)
    
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
            "SELECT id, title, checksum, blob_link, mime_type, created_at, compliance_framework_id FROM documents ORDER BY created_at DESC"
        )
        
        documents = []
        for record in response['records']:
            # Parse created_at datetime from string if present
            created_at = None
            if len(record) > 5 and record[5].get('stringValue'):
                from datetime import datetime
                try:
                    created_at = datetime.fromisoformat(record[5]['stringValue'].replace('Z', '+00:00'))
                except:
                    created_at = None
            
            documents.append(DocumentModel(
                id=record[0].get('longValue'),
                title=record[1].get('stringValue'),
                checksum=record[2].get('stringValue'),
                blob_link=record[3].get('stringValue'),
                mime_type=record[4].get('stringValue'),
                embedding=None,  # Skip embedding parsing for listing
                created_at=created_at,
                compliance_framework_id=record[6].get('stringValue') if len(record) > 6 else None
            ))
        
        return documents
    
    def get_documents_by_compliance_framework(self, compliance_framework_id: str) -> List[DocumentModel]:
        """Get all documents assigned to a specific compliance framework."""
        response = self.execute_statement(
            "SELECT id, title, checksum, blob_link, mime_type, created_at, compliance_framework_id FROM documents WHERE compliance_framework_id = :compliance_framework_id::uuid ORDER BY created_at DESC",
            [{'name': 'compliance_framework_id', 'value': {'stringValue': compliance_framework_id}}]
        )
        
        documents = []
        for record in response['records']:
            # Parse created_at datetime from string if present
            created_at = None
            if len(record) > 5 and record[5].get('stringValue'):
                from datetime import datetime
                try:
                    created_at = datetime.fromisoformat(record[5]['stringValue'].replace('Z', '+00:00'))
                except:
                    created_at = None
            
            documents.append(DocumentModel(
                id=record[0].get('longValue'),
                title=record[1].get('stringValue'),
                checksum=record[2].get('stringValue'),
                blob_link=record[3].get('stringValue'),
                mime_type=record[4].get('stringValue'),
                embedding=None,  # Skip embedding parsing for listing
                created_at=created_at,
                compliance_framework_id=record[6].get('stringValue') if len(record) > 6 else None
            ))
        
        return documents
    
    def get_document_by_id(self, document_id: int) -> Optional[DocumentModel]:
        """Get a single document by ID."""
        response = self.execute_statement(
            "SELECT id, title, checksum, blob_link, mime_type, created_at, compliance_framework_id FROM documents WHERE id = :document_id",
            [{'name': 'document_id', 'value': {'longValue': document_id}}]
        )
        
        if not response['records']:
            return None
        
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
            mime_type=record[4].get('stringValue'),
            embedding=None,  # Skip embedding parsing for single document
            created_at=created_at,
            compliance_framework_id=record[6].get('stringValue') if len(record) > 6 else None
        )
    
    def get_all_compliance_groups(self) -> List[ComplianceGroupModel]:
        """Get all compliance groups from the database."""
        response = self.execute_statement(
            "SELECT id, name, description, embedding, created_at, updated_at FROM compliance_frameworks ORDER BY created_at DESC"
        )
        
        compliance_groups = []
        for record in response['records']:
            # Parse datetime fields from string if present
            created_at = None
            updated_at = None
            
            if len(record) > 4 and record[4].get('stringValue'):
                from datetime import datetime
                try:
                    created_at = datetime.fromisoformat(record[4]['stringValue'].replace('Z', '+00:00'))
                except:
                    created_at = None
            
            if len(record) > 5 and record[5].get('stringValue'):
                from datetime import datetime
                try:
                    updated_at = datetime.fromisoformat(record[5]['stringValue'].replace('Z', '+00:00'))
                except:
                    updated_at = None
            
            # Parse embedding if present
            embedding = None
            if len(record) > 3 and record[3].get('stringValue'):
                try:
                    import json
                    embedding = json.loads(record[3]['stringValue'])
                except:
                    embedding = None
            
            compliance_groups.append(ComplianceGroupModel(
                id=record[0].get('stringValue'),  # UUID is string value
                name=record[1].get('stringValue'),
                description=record[2].get('stringValue'),
                embedding=embedding,
                created_at=created_at,
                updated_at=updated_at
            ))
        
        return compliance_groups
    
    def get_compliance_group_by_id(self, group_id: str) -> Optional[ComplianceGroupModel]:
        """Get a single compliance group by ID."""
        response = self.execute_statement(
            "SELECT id, name, description, embedding, created_at, updated_at FROM compliance_frameworks WHERE id = :group_id::uuid",
            [{'name': 'group_id', 'value': {'stringValue': group_id}}]
        )
        
        if not response['records']:
            return None
        
        record = response['records'][0]
        
        # Parse datetime fields from string if present
        created_at = None
        updated_at = None
        
        if len(record) > 4 and record[4].get('stringValue'):
            from datetime import datetime
            try:
                created_at = datetime.fromisoformat(record[4]['stringValue'].replace('Z', '+00:00'))
            except:
                created_at = None
        
        if len(record) > 5 and record[5].get('stringValue'):
            from datetime import datetime
            try:
                updated_at = datetime.fromisoformat(record[5]['stringValue'].replace('Z', '+00:00'))
            except:
                updated_at = None
        
        # Parse embedding if present
        embedding = None
        if len(record) > 3 and record[3].get('stringValue'):
            try:
                import json
                embedding = json.loads(record[3]['stringValue'])
            except:
                embedding = None
        
        return ComplianceGroupModel(
            id=record[0].get('stringValue'),
            name=record[1].get('stringValue'),
            description=record[2].get('stringValue'),
            embedding=embedding,
            created_at=created_at,
            updated_at=updated_at
        )
    
    def compliance_group_name_exists(self, name: str) -> bool:
        """Check if a compliance group with the given name already exists."""
        response = self.execute_statement(
            "SELECT COUNT(*) FROM compliance_frameworks WHERE LOWER(name) = LOWER(:name)",
            [{'name': 'name', 'value': {'stringValue': name.strip()}}]
        )
        
        count = response['records'][0][0]['longValue']
        return count > 0
    
    def _generate_compliance_group_embedding(self, name: str, description: Optional[str] = None) -> List[float]:
        """Generate embedding for compliance group based on name and description."""
        # Combine name and description for embedding
        text_parts = [name]
        if description and description.strip():
            text_parts.append(description.strip())
        
        combined_text = " - ".join(text_parts)
        return embedding_service.generate_embedding(combined_text)
    
    def create_compliance_group(self, name: str, description: Optional[str] = None) -> str:
        """Create a new compliance group and return its ID."""
        # Generate embedding for the compliance group
        embedding = self._generate_compliance_group_embedding(name, description)
        embedding_str = '[' + ','.join(map(str, embedding)) + ']'
        
        parameters = [
            {'name': 'name', 'value': {'stringValue': name}},
            {'name': 'description', 'value': {'stringValue': description} if description else {'isNull': True}},
            {'name': 'embedding', 'value': {'stringValue': embedding_str}}
        ]
        
        response = self.execute_statement(
            """
            INSERT INTO compliance_frameworks (name, description, embedding)
            VALUES (:name, :description, :embedding::vector)
            RETURNING id
            """,
            parameters
        )
        
        group_id = response['records'][0][0]['stringValue']
        logger.info(f"Created compliance group {group_id} with name: {name} and embedding")
        return group_id
    
    def update_compliance_group(self, group_id: str, name: Optional[str] = None, description: Optional[str] = None) -> bool:
        """Update a compliance group. Returns True if updated successfully."""
        # If name or description is being updated, we need to regenerate the embedding
        if name is not None or description is not None:
            # Get current values to fill in any missing fields for embedding generation
            current_group = self.get_compliance_group_by_id(group_id)
            if not current_group:
                return False
            
            final_name = name if name is not None else current_group.name
            final_description = description if description is not None else current_group.description
            
            # Generate new embedding
            embedding = self._generate_compliance_group_embedding(final_name, final_description)
            embedding_str = '[' + ','.join(map(str, embedding)) + ']'
        
        # Build dynamic update query based on provided fields
        update_fields = []
        parameters = [{'name': 'group_id', 'value': {'stringValue': group_id}}]
        
        if name is not None:
            update_fields.append("name = :name")
            parameters.append({'name': 'name', 'value': {'stringValue': name}})
        
        if description is not None:
            update_fields.append("description = :description")
            parameters.append({'name': 'description', 'value': {'stringValue': description} if description else {'isNull': True}})
        
        # Add embedding update if name or description changed
        if name is not None or description is not None:
            update_fields.append("embedding = :embedding::vector")
            parameters.append({'name': 'embedding', 'value': {'stringValue': embedding_str}})
        
        if not update_fields:
            return False  # Nothing to update
        
        # Add updated_at
        update_fields.append("updated_at = CURRENT_TIMESTAMP")
        
        sql = f"UPDATE compliance_frameworks SET {', '.join(update_fields)} WHERE id = :group_id::uuid"
        
        response = self.execute_statement(sql, parameters)
        
        # Check if any rows were affected
        updated = response.get('numberOfRecordsUpdated', 0) > 0
        if updated and (name is not None or description is not None):
            logger.info(f"Updated compliance group {group_id} with new embedding")
        
        return updated
    
    def delete_compliance_group(self, group_id: str) -> bool:
        """Delete a compliance group. Returns True if deleted successfully."""
        parameters = [{'name': 'group_id', 'value': {'stringValue': group_id}}]
        
        response = self.execute_statement(
            "DELETE FROM compliance_frameworks WHERE id = :group_id::uuid",
            parameters
        )
        
        logger.info(f"Deleted compliance group {group_id}")
        return response.get('numberOfRecordsUpdated', 0) > 0
    
    def update_document_compliance_framework(self, document_id: int, compliance_framework_id: Optional[str]) -> bool:
        """Update a document's compliance framework assignment. Returns True if updated successfully."""
        parameters = [
            {'name': 'document_id', 'value': {'longValue': document_id}},
            {'name': 'compliance_framework_id', 'value': {'stringValue': compliance_framework_id} if compliance_framework_id else {'isNull': True}}
        ]
        
        # Delete any existing rules for this document when compliance framework changes
        # This ensures rules are cleaned up whether setting to null or changing to a different framework
        logger.info(f"Updating document {document_id} compliance framework - deleting associated rules")
        try:
            rules_deleted = self.execute_statement(
                "DELETE FROM compliance_rules WHERE document_id = :document_id",
                [{'name': 'document_id', 'value': {'longValue': document_id}}]
            )
            deleted_count = rules_deleted.get('numberOfRecordsUpdated', 0)
            if deleted_count > 0:
                logger.info(f"Deleted {deleted_count} compliance rules for document {document_id}")
            else:
                logger.info(f"No existing compliance rules found for document {document_id}")
        except Exception as e:
            logger.warning(f"Failed to delete compliance rules for document {document_id}: {str(e)}")
            # Continue with the update even if rule deletion fails
        
        # Update the document's compliance framework
        if compliance_framework_id is None:
            # Handle null case separately to avoid casting null to uuid
            response = self.execute_statement(
                "UPDATE documents SET compliance_framework_id = NULL WHERE id = :document_id",
                [{'name': 'document_id', 'value': {'longValue': document_id}}]
            )
        else:
            response = self.execute_statement(
                "UPDATE documents SET compliance_framework_id = :compliance_framework_id::uuid WHERE id = :document_id",
                parameters
            )
        
        logger.info(f"Updated document {document_id} compliance framework to {compliance_framework_id}")
        return response.get('numberOfRecordsUpdated', 0) > 0

postgres_client = PostgresClient()