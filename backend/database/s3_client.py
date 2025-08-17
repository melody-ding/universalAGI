import boto3
import hashlib
from typing import BinaryIO
from botocore.exceptions import ClientError
from config import settings

class S3Client:
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.aws.access_key_id,
            aws_secret_access_key=settings.aws.secret_access_key,
            region_name=settings.aws.region
        )
        self.bucket_name = settings.aws.s3_bucket_name
    
    def compute_file_hash(self, file_stream: BinaryIO) -> str:
        """Compute SHA-256 hash of file stream without loading entire file into memory."""
        hasher = hashlib.sha256()
        
        # Reset stream position
        file_stream.seek(0)
        
        # Stream through file in chunks
        while chunk := file_stream.read(8192):
            hasher.update(chunk)
        
        # Reset stream position for potential reuse
        file_stream.seek(0)
        
        return hasher.hexdigest()
    
    def check_file_exists(self, doc_hash: str) -> bool:
        """Check if a file with the given hash already exists in S3."""
        try:
            # List objects with the hash prefix
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=f"{doc_hash}/original/",
                MaxKeys=1
            )
            return response.get('KeyCount', 0) > 0
        except ClientError:
            return False
    
    def upload_file(self, file_stream: BinaryIO, doc_hash: str, original_filename: str, content_type: str = None) -> str:
        """Upload file to S3 and return the S3 key."""
        s3_key = f"{doc_hash}/original/{original_filename}"
        
        try:
            # Reset stream position
            file_stream.seek(0)
            
            # Use provided content_type or default to octet-stream
            upload_content_type = content_type or 'application/octet-stream'
            
            # Upload file
            self.s3_client.upload_fileobj(
                file_stream,
                self.bucket_name,
                s3_key,
                ExtraArgs={
                    'ContentType': upload_content_type,
                    'Metadata': {
                        'original-filename': original_filename,
                        'doc-hash': doc_hash
                    }
                }
            )
            
            return s3_key
        except ClientError as e:
            raise Exception(f"Failed to upload file to S3: {str(e)}")
    
    def get_file_url(self, s3_key: str) -> str:
        """Generate a presigned URL for the file."""
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': s3_key},
                ExpiresIn=3600  # 1 hour
            )
            return url
        except ClientError as e:
            raise Exception(f"Failed to generate presigned URL: {str(e)}")
    
    def get_s3_key_from_hash_and_filename(self, doc_hash: str, original_filename: str) -> str:
        """Generate S3 key from document hash and original filename."""
        return f"{doc_hash}/original/{original_filename}"
    
    def generate_viewer_url(self, s3_key: str, content_type: str = None) -> str:
        """Generate a presigned URL specifically for document viewing with longer expiry."""
        try:
            params = {
                'Bucket': self.bucket_name, 
                'Key': s3_key,
                'ResponseContentDisposition': 'inline'  # For viewing in browser
            }
            
            # Override content type if provided to ensure proper browser handling
            if content_type:
                params['ResponseContentType'] = content_type
            
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params=params,
                ExpiresIn=7200  # 2 hours for viewer
            )
            return url
        except ClientError as e:
            raise Exception(f"Failed to generate viewer URL: {str(e)}")
    
    def get_s3_key_from_document(self, doc_hash: str) -> str:
        """Get the S3 key for a document by listing objects with the hash prefix."""
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=f"{doc_hash}/original/",
                MaxKeys=1
            )
            
            if response.get('KeyCount', 0) > 0:
                return response['Contents'][0]['Key']
            else:
                raise Exception(f"No file found for document hash: {doc_hash}")
        except ClientError as e:
            raise Exception(f"Failed to get S3 key: {str(e)}")
    
    def delete_file_by_hash(self, doc_hash: str) -> bool:
        """Delete all files associated with a document hash from S3."""
        try:
            # List all objects with the hash prefix
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=f"{doc_hash}/"
            )
            
            if response.get('KeyCount', 0) == 0:
                return True  # No files to delete
            
            # Delete all objects
            objects_to_delete = [{'Key': obj['Key']} for obj in response['Contents']]
            
            self.s3_client.delete_objects(
                Bucket=self.bucket_name,
                Delete={'Objects': objects_to_delete}
            )
            
            return True
        except ClientError as e:
            raise Exception(f"Failed to delete files from S3: {str(e)}")

s3_client = S3Client()