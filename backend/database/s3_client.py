import boto3
import hashlib
import os
from typing import BinaryIO
from botocore.exceptions import ClientError

class S3Client:
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_REGION', 'us-east-1')
        )
        self.bucket_name = os.getenv('S3_BUCKET_NAME')
    
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
    
    def upload_file(self, file_stream: BinaryIO, doc_hash: str, original_filename: str) -> str:
        """Upload file to S3 and return the S3 key."""
        s3_key = f"{doc_hash}/original/{original_filename}"
        
        try:
            # Reset stream position
            file_stream.seek(0)
            
            # Upload file
            self.s3_client.upload_fileobj(
                file_stream,
                self.bucket_name,
                s3_key,
                ExtraArgs={
                    'ContentType': 'application/octet-stream',
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