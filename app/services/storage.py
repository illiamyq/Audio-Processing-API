import boto3
from botocore.exceptions import ClientError

from app.setup.config import settings

_client = None


def get_s3_client():
    global _client
    if _client is None:
        _client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name=settings.S3_REGION,
        )
    return _client


def ensure_bucket():
    client = get_s3_client()
    try:
        client.head_bucket(Bucket=settings.S3_BUCKET)
    except ClientError:
        client.create_bucket(Bucket=settings.S3_BUCKET)


def upload_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    client = get_s3_client()
    client.put_object(Bucket=settings.S3_BUCKET, Key=key, Body=data, ContentType=content_type)
    return key


def upload_file(key: str, filepath: str, content_type: str = "application/octet-stream") -> str:
    client = get_s3_client()
    client.upload_file(filepath, settings.S3_BUCKET, key, ExtraArgs={"ContentType": content_type})
    return key


def download_bytes(key: str) -> bytes:
    client = get_s3_client()
    response = client.get_object(Bucket=settings.S3_BUCKET, Key=key)
    return response["Body"].read()


def delete_object(key: str):
    client = get_s3_client()
    client.delete_object(Bucket=settings.S3_BUCKET, Key=key)


def presigned_url(key: str, expires: int = 3600) -> str:
    client = get_s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.S3_BUCKET, "Key": key},
        ExpiresIn=expires,
    )
