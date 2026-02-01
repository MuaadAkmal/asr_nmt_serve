"""Object storage service for audio files and results."""

import base64
import hashlib
import json
from datetime import timedelta
from io import BytesIO
from typing import Optional
from uuid import uuid4

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from src.config import get_settings

settings = get_settings()


class StorageService:
    """Service for managing object storage (MinIO/S3)."""

    def __init__(self):
        self._client = None
        self._bucket = settings.minio_bucket

    @property
    def client(self):
        """Lazy initialization of S3 client."""
        if self._client is None:
            endpoint_url = f"{'https' if settings.minio_use_ssl else 'http'}://{settings.minio_endpoint}"
            self._client = boto3.client(
                "s3",
                endpoint_url=endpoint_url,
                aws_access_key_id=settings.minio_access_key,
                aws_secret_access_key=settings.minio_secret_key,
                config=Config(signature_version="s3v4"),
            )
            self._ensure_bucket()
        return self._client

    def _ensure_bucket(self):
        """Create bucket if it doesn't exist."""
        try:
            self.client.head_bucket(Bucket=self._bucket)
        except ClientError:
            self.client.create_bucket(Bucket=self._bucket)

    def _generate_path(self, job_id: str, task_id: str, filename: str) -> str:
        """Generate storage path for a file."""
        return f"jobs/{job_id}/tasks/{task_id}/{filename}"

    async def upload_audio_from_url(
        self, audio_url: str, job_id: str, task_id: str
    ) -> str:
        """
        Download audio from URL and upload to storage.
        Returns the storage path.
        """
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.get(audio_url, follow_redirects=True)
            response.raise_for_status()
            content = response.content

        # Detect content type
        content_type = response.headers.get("content-type", "audio/wav")
        ext = self._get_extension(content_type)
        filename = f"input{ext}"
        path = self._generate_path(job_id, task_id, filename)

        self.client.upload_fileobj(
            BytesIO(content),
            self._bucket,
            path,
            ExtraArgs={"ContentType": content_type},
        )

        return path

    def upload_audio_from_base64(
        self, audio_b64: str, job_id: str, task_id: str, content_type: str = "audio/wav"
    ) -> str:
        """
        Decode base64 audio and upload to storage.
        Returns the storage path.
        """
        content = base64.b64decode(audio_b64)
        ext = self._get_extension(content_type)
        filename = f"input{ext}"
        path = self._generate_path(job_id, task_id, filename)

        self.client.upload_fileobj(
            BytesIO(content),
            self._bucket,
            path,
            ExtraArgs={"ContentType": content_type},
        )

        return path

    def upload_result(
        self, result: dict, job_id: str, task_id: str
    ) -> str:
        """
        Upload task result as JSON.
        Returns the storage path.
        """
        path = self._generate_path(job_id, task_id, "result.json")
        content = json.dumps(result, ensure_ascii=False, indent=2)

        self.client.put_object(
            Bucket=self._bucket,
            Key=path,
            Body=content.encode("utf-8"),
            ContentType="application/json",
        )

        return path

    def download_audio(self, storage_path: str) -> bytes:
        """Download audio file from storage."""
        response = self.client.get_object(Bucket=self._bucket, Key=storage_path)
        return response["Body"].read()

    def download_result(self, storage_path: str) -> dict:
        """Download result JSON from storage."""
        response = self.client.get_object(Bucket=self._bucket, Key=storage_path)
        content = response["Body"].read().decode("utf-8")
        return json.loads(content)

    def generate_presigned_url(
        self, storage_path: str, expires_in: int = 3600
    ) -> str:
        """Generate a presigned URL for downloading a file."""
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": storage_path},
            ExpiresIn=expires_in,
        )

    def generate_upload_url(
        self, job_id: str, task_id: str, content_type: str = "audio/wav", expires_in: int = 3600
    ) -> dict:
        """
        Generate a presigned URL for uploading a file directly to storage.
        
        Returns:
            dict with 'upload_url', 'storage_path', and 'expires_in'
        """
        ext = self._get_extension(content_type)
        filename = f"input{ext}"
        path = self._generate_path(job_id, task_id, filename)
        
        url = self.client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self._bucket,
                "Key": path,
                "ContentType": content_type,
            },
            ExpiresIn=expires_in,
        )
        
        return {
            "upload_url": url,
            "storage_path": path,
            "expires_in": expires_in,
            "content_type": content_type,
        }

    def generate_batch_upload_urls(
        self, job_id: str, count: int, content_type: str = "audio/wav", expires_in: int = 3600
    ) -> list[dict]:
        """
        Generate multiple presigned upload URLs for a batch job.
        
        Returns:
            List of dicts with 'task_id', 'upload_url', 'storage_path', 'expires_in'
        """
        urls = []
        for i in range(count):
            task_id = str(uuid4())
            upload_info = self.generate_upload_url(job_id, task_id, content_type, expires_in)
            upload_info["task_id"] = task_id
            urls.append(upload_info)
        return urls

    def delete_job_files(self, job_id: str):
        """Delete all files for a job."""
        prefix = f"jobs/{job_id}/"
        response = self.client.list_objects_v2(Bucket=self._bucket, Prefix=prefix)

        if "Contents" in response:
            objects = [{"Key": obj["Key"]} for obj in response["Contents"]]
            self.client.delete_objects(
                Bucket=self._bucket, Delete={"Objects": objects}
            )

    def _get_extension(self, content_type: str) -> str:
        """Get file extension from content type."""
        mapping = {
            "audio/wav": ".wav",
            "audio/x-wav": ".wav",
            "audio/mpeg": ".mp3",
            "audio/mp3": ".mp3",
            "audio/ogg": ".ogg",
            "audio/flac": ".flac",
            "audio/m4a": ".m4a",
            "audio/webm": ".webm",
        }
        return mapping.get(content_type, ".wav")

    def health_check(self) -> bool:
        """Check if storage is accessible."""
        try:
            self.client.head_bucket(Bucket=self._bucket)
            return True
        except Exception:
            return False


# Singleton instance
storage_service = StorageService()
